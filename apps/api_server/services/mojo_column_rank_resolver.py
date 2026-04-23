from __future__ import annotations

import atexit
import json
import os
import socket
import struct
import subprocess
import tempfile
import threading
import time
import zlib
from collections.abc import Callable
from itertools import count
from pathlib import Path
from typing import Any

import structlog

from mojo.engine.vector_kernels.resolver import (
    _ROLE_MAP,
    _SOURCE_MAP,
    DEFINITE_META_THRESHOLD,
    ROLE_DERIVED,
    ROLE_OTHER,
    ROLE_UNIT,
    SOURCE_UNKNOWN,
    ColumnVectorResolver,
    ResolverOutcome,
    ResolverReason,
    TopKEntry,
    VectorResolverResult,
    _meta_reason,
    _token_overlap,
    expand_tokens,
    make_query_token_ids,
    tokenize_name,
)

logger = structlog.get_logger(__name__)

MojoCaller = Callable[[dict[str, Any], int], dict[str, Any] | None]
_PLANNER_MOJO_POOL_SIZE = max(
    1,
    int(os.environ.get("ALGENTA_PLANNER_MOJO_POOL_SIZE", str(min(4, max(1, os.cpu_count() or 1))))),
)
_PLANNER_MOJO_FAILURE_COOLDOWN_S = max(
    1.0,
    float(os.environ.get("ALGENTA_PLANNER_MOJO_FAILURE_COOLDOWN_S", "15.0")),
)

_ROLE_ID_TO_NAME: dict[int, str] = {
    ROLE_OTHER: "other",
    ROLE_UNIT: "unit_measure",
    ROLE_DERIVED: "derived_measure",
}
_CLIENT_POOLS: dict[str, _PlannerMojoClientPool] = {}
_CLIENTS_LOCK = threading.Lock()
_CLIENT_INSTANCE_COUNTER = count(1)


class _PlannerMojoSocketClient:
    """Persistent sync Mojo server connection for planner-side ranking."""

    def __init__(self, binary_path: Path) -> None:
        self._binary_path = binary_path
        self._proc: subprocess.Popen[bytes] | None = None
        self._socket: socket.socket | None = None
        client_id = next(_CLIENT_INSTANCE_COUNTER)
        self._socket_path = (
            Path(tempfile.gettempdir())
            / (
                "algenta-planner-rank-"
                f"{os.getpid()}-{client_id}-{abs(hash(str(binary_path.resolve()))) & 0xFFFF:x}.sock"
            )
        )
        self._lock = threading.RLock()
        self._initialized_session_key: str | None = None
        self._disabled_until = 0.0

    def invoke(
        self,
        payload: dict[str, Any],
        timeout: float,
        *,
        session_key: str | None = None,
        init_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        with self._lock:
            if time.monotonic() < self._disabled_until:
                return None
            try:
                self._ensure_started(timeout)
                if (
                    session_key is not None
                    and init_payload is not None
                    and self._initialized_session_key != session_key
                ):
                    init_result = self._send_payload(init_payload, timeout)
                    if init_result.get("status") != "ok":
                        raise RuntimeError(
                            "planner Mojo rank resident init failed: "
                            f"{init_result.get('error', init_result)}"
                        )
                    self._initialized_session_key = session_key
                result = self._send_payload(payload, timeout)
                if isinstance(result, dict) and "error" not in result:
                    return result
            except Exception as exc:
                logger.debug("planner_mojo_rank_client_error", error=str(exc))
                self._disabled_until = time.monotonic() + _PLANNER_MOJO_FAILURE_COOLDOWN_S
                self.close()
        return None

    def close(self) -> None:
        with self._lock:
            if self._socket is not None:
                try:
                    self._socket.close()
                except OSError:
                    pass
                self._socket = None
            self._initialized_session_key = None
            if self._proc is not None:
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=1.0)
                except Exception:
                    try:
                        self._proc.kill()
                    except Exception as exc:
                        logger.debug("planner_mojo_rank_kill_failed", error=str(exc))
                self._proc = None
            if self._socket_path.exists():
                try:
                    self._socket_path.unlink()
                except OSError:
                    pass

    def _ensure_started(self, timeout: float) -> None:
        if self._socket is not None and self._proc is not None and self._proc.poll() is None:
            return

        self.close()
        if self._socket_path.exists():
            self._socket_path.unlink()

        self._proc = subprocess.Popen(  # noqa: S603
            [str(self._binary_path), "--server", str(self._socket_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + timeout
        while not self._socket_path.exists():
            if self._proc.poll() is not None:
                raise RuntimeError("planner Mojo rank server exited during startup")
            if time.monotonic() >= deadline:
                raise TimeoutError("planner Mojo rank server startup timed out")
            time.sleep(0.005)

        last_error: Exception | None = None
        while time.monotonic() < deadline:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.settimeout(timeout)
                sock.connect(str(self._socket_path))
                ready = json.loads(self._recv_frame(sock).decode("utf-8"))
                if ready.get("status") != "ready":
                    raise RuntimeError(f"unexpected planner Mojo rank handshake: {ready}")
                self._socket = sock
                return
            except Exception as exc:
                last_error = exc
                sock.close()
                if self._proc.poll() is not None:
                    raise RuntimeError("planner Mojo rank server exited during startup") from exc
                time.sleep(0.005)

        raise TimeoutError("planner Mojo rank server handshake timed out") from last_error

    def _send_payload(self, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        assert self._socket is not None
        self._socket.settimeout(timeout)
        body = json.dumps(payload).encode("utf-8")
        self._socket.sendall(struct.pack(">I", len(body)) + body)
        raw = self._recv_frame(self._socket)
        result = json.loads(raw.decode("utf-8"))
        if not isinstance(result, dict):
            raise RuntimeError(f"planner Mojo rank server returned invalid payload: {result!r}")
        return result

    @staticmethod
    def _recv_exact(sock: socket.socket, length: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < length:
            chunk = sock.recv(length - len(chunks))
            if not chunk:
                raise ConnectionError("planner Mojo rank socket closed")
            chunks.extend(chunk)
        return bytes(chunks)

    def _recv_frame(self, sock: socket.socket) -> bytes:
        header = self._recv_exact(sock, 4)
        frame_len = struct.unpack(">I", header)[0]
        return self._recv_exact(sock, frame_len)


class _PlannerMojoClientPool:
    """Small round-robin pool of persistent planner Mojo rank clients."""

    def __init__(self, binary_path: Path, size: int) -> None:
        self._clients = [_PlannerMojoSocketClient(binary_path) for _ in range(size)]
        self._next_index = 0
        self._lock = threading.Lock()

    def invoke(
        self,
        payload: dict[str, Any],
        timeout: float,
        *,
        session_key: str | None = None,
        init_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        with self._lock:
            if session_key:
                client_index = zlib.adler32(session_key.encode("utf-8")) % len(self._clients)
                client = self._clients[client_index]
            else:
                client = self._clients[self._next_index]
                self._next_index = (self._next_index + 1) % len(self._clients)
        return client.invoke(
            payload,
            timeout,
            session_key=session_key,
            init_payload=init_payload,
        )

    def close(self) -> None:
        for client in self._clients:
            client.close()


def _get_planner_pool(binary_path: Path) -> _PlannerMojoClientPool:
    key = str(binary_path.resolve())
    with _CLIENTS_LOCK:
        pool = _CLIENT_POOLS.get(key)
        if pool is None:
            pool = _PlannerMojoClientPool(binary_path.resolve(), _PLANNER_MOJO_POOL_SIZE)
            _CLIENT_POOLS[key] = pool
        return pool


def _close_planner_clients() -> None:
    with _CLIENTS_LOCK:
        pools = list(_CLIENT_POOLS.values())
        _CLIENT_POOLS.clear()
    for pool in pools:
        pool.close()


def invoke_column_rank(
    payload: dict[str, Any],
    *,
    binary_path: Path,
    timeout: float = 1.0,
    session_key: str | None = None,
    init_payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    return _get_planner_pool(binary_path).invoke(
        payload,
        timeout,
        session_key=session_key,
        init_payload=init_payload,
    )


def invoke_planner_mojo(
    payload: dict[str, Any],
    *,
    binary_path: Path,
    timeout: float = 1.0,
) -> dict[str, Any] | None:
    """Send a generic planner Mojo request over the resident socket transport."""
    return _get_planner_pool(binary_path).invoke(payload, timeout)


atexit.register(_close_planner_clients)


class MojoColumnRankResolver:
    """Planner-facing resolver that keeps Python prefiltering and Mojo ranking."""

    def __init__(
        self,
        base_resolver: ColumnVectorResolver,
        *,
        call_mojo: MojoCaller,
        fill_rates: dict[tuple[str, str], float] | None = None,
        binary_path: Path | None = None,
    ) -> None:
        self._base_resolver = base_resolver
        self._call_mojo = call_mojo
        self._fill_rates = fill_rates or {}
        self._binary_path = binary_path
        self._entry_lookup = {
            (entry.source, entry.name): entry for entry in self._base_resolver._entries
        }
        self._resident_entries: list[dict[str, Any]] = []
        self._resident_generation = 0
        self._resident_session_key: str | None = None
        self._resident_init_payload: dict[str, Any] | None = None
        self._refresh_resident_session_from_entries(
            [
                {
                    "id": idx,
                    "source": entry.source,
                    "column": entry.name,
                    "source_id": int(entry.source_id),
                    "role_id": int(entry.role_id),
                }
                for idx, entry in enumerate(self._base_resolver._entries)
            ]
        )

    def _set_resident_session_state(self) -> None:
        self._resident_session_key = None
        self._resident_init_payload = None
        if self._binary_path is None:
            return
        if not self._resident_entries:
            return
        self._resident_generation += 1
        self._resident_session_key = (
            f"{id(self):x}:{self._resident_generation:x}:{len(self._resident_entries):x}"
        )
        self._resident_init_payload = {
            "type": "column_rank_init",
            "engine_type": "column_rank_init",
            "entries": self._resident_entries,
        }

    def _refresh_resident_session_from_entries(
        self,
        entries: list[dict[str, Any]],
    ) -> None:
        self._resident_entries = list(entries)
        self._set_resident_session_state()

    def append_planner_graph_source(
        self,
        source: str,
        columns: dict[str, Any],
        *,
        fill_rates: dict[tuple[str, str], float] | None = None,
    ) -> bool:
        handled = self._base_resolver.append_planner_graph_source(
            source,
            columns,
            fill_rates=fill_rates,
        )
        if not handled:
            return False
        if fill_rates:
            self._fill_rates.update(fill_rates)
        new_resident_entries: list[dict[str, Any]] = []
        for entry in self._base_resolver._entries:
            if entry.source != source:
                continue
            self._entry_lookup[(entry.source, entry.name)] = entry
            new_resident_entries.append(
                {
                    "id": int(entry.column_id),
                    "source": entry.source,
                    "column": entry.name,
                    "source_id": int(entry.source_id),
                    "role_id": int(entry.role_id),
                }
            )
        if new_resident_entries:
            self._resident_entries.extend(new_resident_entries)
            self._set_resident_session_state()
        return True

    def resolve(
        self,
        hint: str,
        preferred_source: str | None = None,
        role_hint: str | None = None,
        top_k: int = 5,
    ) -> VectorResolverResult | None:
        if not self._base_resolver._entries or self._base_resolver._vocab is None:
            return None

        query_src = _SOURCE_MAP.get((preferred_source or "").lower(), SOURCE_UNKNOWN)
        query_role = _ROLE_MAP.get((role_hint or "").lower(), ROLE_OTHER)
        query_token_ids = make_query_token_ids(self._base_resolver._vocab, hint)
        query_tokens = tokenize_name(hint)
        query_tokens_ex = {
            token for token, _weight in expand_tokens(query_tokens, self._base_resolver._aliases)
        }

        candidate_indices, fallback_used = self._base_resolver._prefilter(
            query_token_ids,
            query_src,
            query_role,
        )
        steps = [f"[prefilter] shortlist={len(candidate_indices)} fallback={fallback_used}"]
        if not candidate_indices:
            return None

        ranked = self._rank_candidates(
            hint=hint,
            preferred_source=preferred_source,
            role_hint=role_hint,
            query_src=query_src,
            query_role=query_role,
            candidate_indices=candidate_indices,
            top_k=top_k,
        )
        result = self._build_vector_result(
            hint=hint,
            preferred_source=preferred_source,
            role_hint=role_hint,
            top_k=top_k,
            query_tokens_ex=query_tokens_ex,
            candidate_indices=candidate_indices,
            fallback_used=fallback_used,
            steps=steps,
            ranked=ranked,
        )
        if result is not None:
            return result
        fallback = self._base_resolver.resolve(hint, preferred_source, role_hint, top_k)
        if fallback is None:
            return None
        fallback.steps.insert(0, "[mojo_column_rank] unavailable -> python_resolver")
        return fallback

    def resolve_batch(
        self,
        requests: list[tuple[str, str | None, str | None]],
        top_k: int = 5,
    ) -> list[VectorResolverResult | None]:
        if self._resident_init_payload is None or self._binary_path is None:
            return [self.resolve(hint, src, role, top_k) for hint, src, role in requests]

        slot_specs: list[dict[str, Any]] = []
        result_slots: list[dict[str, Any] | None] = []
        for hint, preferred_source, role_hint in requests:
            if not self._base_resolver._entries or self._base_resolver._vocab is None:
                result_slots.append(None)
                continue
            query_src = _SOURCE_MAP.get((preferred_source or "").lower(), SOURCE_UNKNOWN)
            query_role = _ROLE_MAP.get((role_hint or "").lower(), ROLE_OTHER)
            query_token_ids = make_query_token_ids(self._base_resolver._vocab, hint)
            query_tokens = tokenize_name(hint)
            query_tokens_ex = {
                token
                for token, _weight in expand_tokens(
                    query_tokens,
                    self._base_resolver._aliases,
                )
            }
            candidate_indices, fallback_used = self._base_resolver._prefilter(
                query_token_ids,
                query_src,
                query_role,
            )
            steps = [f"[prefilter] shortlist={len(candidate_indices)} fallback={fallback_used}"]
            if not candidate_indices:
                result_slots.append(None)
                continue
            slot_specs.append(
                {
                    "hint": hint,
                    "preferred_source": preferred_source,
                    "role_hint": role_hint,
                    "candidate_indices": candidate_indices,
                    "fallback_used": fallback_used,
                    "query_tokens_ex": query_tokens_ex,
                    "steps": steps,
                    "query_src": query_src,
                    "query_role": query_role,
                }
            )
            result_slots.append({"pending": True})

        if not slot_specs:
            return [None for _ in requests]

        payload = {
            "type": "column_rank_batch",
            "engine_type": "column_rank_batch",
            "requests": [
                {
                    "hint": spec["hint"],
                    "source_id": int(spec["query_src"]),
                    "role_id": int(spec["query_role"]),
                    "candidate_ids": spec["candidate_indices"],
                    "top_k": top_k,
                }
                for spec in slot_specs
            ],
        }
        result = invoke_column_rank(
            payload,
            binary_path=self._binary_path,
            session_key=self._resident_session_key,
            init_payload=self._resident_init_payload,
            timeout=1.0,
        )
        if result is None or not isinstance(result.get("results"), list):
            return [self.resolve(hint, src, role, top_k) for hint, src, role in requests]

        resolved_results: list[VectorResolverResult | None] = []
        batch_results = result["results"]
        batch_index = 0
        for slot in result_slots:
            if slot is None:
                resolved_results.append(None)
                continue
            assert batch_index < len(slot_specs)
            spec = slot_specs[batch_index]
            ranked_payload = (
                batch_results[batch_index]
                if batch_index < len(batch_results)
                else None
            )
            resolved_results.append(
                self._build_vector_result(
                    hint=spec["hint"],
                    preferred_source=spec["preferred_source"],
                    role_hint=spec["role_hint"],
                    top_k=top_k,
                    query_tokens_ex=spec["query_tokens_ex"],
                    candidate_indices=spec["candidate_indices"],
                    fallback_used=spec["fallback_used"],
                    steps=list(spec["steps"]),
                    ranked=(ranked_payload or {}).get("ranked")
                    if isinstance(ranked_payload, dict)
                    else None,
                )
            )
            batch_index += 1
        return resolved_results

    def resolve_plan_fields(
        self,
        *,
        metric: tuple[str, str | None, str | None] | None = None,
        group_by: tuple[str, str | None, str | None] | None = None,
        date: tuple[str, str | None, str | None] | None = None,
        filter_: tuple[str, str | None, str | None] | None = None,
        top_k: int = 5,
    ) -> dict[str, VectorResolverResult | None]:
        slot_map: dict[str, tuple[str, str | None, str | None] | None] = {
            "metric": metric,
            "group_by": group_by,
            "date": date,
            "filter": filter_,
        }
        ordered_requests: list[tuple[str, str | None, str | None]] = []
        field_names: list[str] = []
        for field_name, request in slot_map.items():
            if request is None:
                continue
            field_names.append(field_name)
            ordered_requests.append(request)
        resolved = self.resolve_batch(ordered_requests, top_k=top_k)
        results: dict[str, VectorResolverResult | None] = {
            "metric": None,
            "group_by": None,
            "date": None,
            "filter": None,
        }
        for field_name, result in zip(field_names, resolved, strict=False):
            results[field_name] = result
        return results

    def _build_vector_result(
        self,
        *,
        hint: str,
        preferred_source: str | None,
        role_hint: str | None,
        top_k: int,
        query_tokens_ex: set[str],
        candidate_indices: list[int],
        fallback_used: bool,
        steps: list[str],
        ranked: list[dict[str, Any]] | None,
    ) -> VectorResolverResult | None:
        if not ranked:
            return None

        candidate_lookup_by_id = {
            index: self._base_resolver._entries[index]
            for index in candidate_indices
        }
        best = ranked[0]
        best_entry = self._ranked_item_entry(best, candidate_lookup_by_id)
        if best_entry is None:
            return None
        best_source = best_entry.source
        best_column = best_entry.name

        best_score = float(best.get("score", 0.0) or 0.0)
        gap = float(best.get("confidence_gap", 0.0) or 0.0)
        ranked_count = len(ranked)
        gap_ok = gap >= self._base_resolver.GAP_THRESHOLD or ranked_count < 2
        score_ok = best_score >= self._base_resolver.ACCEPT_THRESHOLD
        ambiguous = not gap_ok and ranked_count >= 2
        confident = score_ok and gap_ok
        meta_reason = _meta_reason(hint, best_score)
        weak = (
            not confident
            and not ambiguous
            and best_score >= self._base_resolver.WEAK_ACCEPT_THRESHOLD
            and gap_ok
        )

        if meta_reason is not None:
            phrase_based = meta_reason == "meta_phrase"
            definite_meta = best_score < DEFINITE_META_THRESHOLD
            if phrase_based or gap_ok or definite_meta:
                outcome = ResolverOutcome.META_QUERY
                reason = ResolverReason(meta_reason)
            else:
                outcome = ResolverOutcome.AMBIGUOUS
                reason = ResolverReason.AMBIGUOUS_GAP
        elif confident:
            outcome = ResolverOutcome.COLUMN_MATCH
            reason = ResolverReason.DIRECT_MATCH
        elif ambiguous:
            outcome = ResolverOutcome.AMBIGUOUS
            reason = ResolverReason.AMBIGUOUS_GAP
        elif weak:
            outcome = ResolverOutcome.WEAK_MATCH
            reason = ResolverReason.WEAK_MATCH
        else:
            outcome = ResolverOutcome.NO_COLUMN_MATCH
            reason = ResolverReason.NO_SIGNAL

        confident = outcome == ResolverOutcome.COLUMN_MATCH
        ambiguous = outcome == ResolverOutcome.AMBIGUOUS
        steps.append(
            f"[mojo_column_rank] ranked={ranked_count} top={best_source}.{best_column}"
        )
        steps.append(
            f"[score] {best_source}.{best_column}  score={best_score:.3f}  "
            f"gap={gap:.3f}  outcome={outcome.value}  reason={reason.value}"
        )

        result_top_k = [
            TopKEntry(
                source=entry.source,
                column=entry.name,
                score=round(float(item.get("score", 0.0) or 0.0), 4),
                name_sim=round(float(item.get("name_sim", 0.0) or 0.0), 4),
                type_boost=round(float(item.get("type_boost", 0.0) or 0.0), 4),
            )
            for item in ranked[:top_k]
            for entry in [self._ranked_item_entry(item, candidate_lookup_by_id)]
            if entry is not None
        ]

        return VectorResolverResult(
            source=best_source,
            column=best_column,
            score=round(best_score, 4),
            confidence_gap=round(gap, 4),
            outcome=outcome,
            reason=reason,
            confident=confident,
            ambiguous=ambiguous,
            fallback_used=fallback_used,
            token_overlap=_token_overlap(query_tokens_ex, best_entry.tokens_expanded),
            top_k=result_top_k,
            steps=steps,
        )

    def _ranked_item_entry(
        self,
        item: dict[str, Any],
        candidate_lookup_by_id: dict[int, Any],
    ) -> Any | None:
        item_id = item.get("id")
        if item_id is not None:
            try:
                entry_id = int(item_id)
            except (TypeError, ValueError):
                entry_id = -1
            entry = candidate_lookup_by_id.get(entry_id)
            if entry is None and 0 <= entry_id < len(self._base_resolver._entries):
                entry = self._base_resolver._entries[entry_id]
            if entry is not None:
                return entry

        source = str(item.get("source", "") or "")
        column = str(item.get("column", "") or "")
        if not source or not column:
            return None
        return self._entry_lookup.get((source, column))

    def _rank_candidates(
        self,
        *,
        hint: str,
        preferred_source: str | None,
        role_hint: str | None,
        query_src: int,
        query_role: int,
        candidate_indices: list[int],
        top_k: int,
    ) -> list[dict[str, Any]] | None:
        if self._binary_path is not None and self._resident_init_payload is not None:
            result = invoke_column_rank(
                {
                    "type": "column_rank_query",
                    "engine_type": "column_rank_query",
                    "hint": hint,
                    "source_id": int(query_src),
                    "role_id": int(query_role),
                    "candidate_ids": candidate_indices,
                    "top_k": top_k,
                },
                binary_path=self._binary_path,
                session_key=self._resident_session_key,
                init_payload=self._resident_init_payload,
                timeout=1.0,
            )
        else:
            payload = {
                "engine_type": "column_rank",
                "hint_words": tokenize_name(hint),
                "candidates": [
                    {
                        "source": entry.source,
                        "column": entry.name,
                        "role": _ROLE_ID_TO_NAME.get(entry.role_id, "other"),
                        "fill_rate": self._fill_rates.get((entry.source, entry.name), 1.0),
                    }
                    for entry in (
                        self._base_resolver._entries[index] for index in candidate_indices
                    )
                ],
                "context": {
                    "source_type": preferred_source or "",
                    "query_role": role_hint or "",
                },
                "top_k": top_k,
            }
            result = self._call_mojo(payload, 5)
        if result is None:
            return None
        ranked = result.get("ranked")
        if not isinstance(ranked, list):
            return None
        return ranked
