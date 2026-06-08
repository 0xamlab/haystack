"""
training/semantic/schema_registry.py — Per-user schema registry with auto-training.

Tracks all known schemas for this user/machine and manages the lifecycle:

    1. register(schema)      → assigns hash, persists entry, fires async training
    2. status(hash)          → "untrained" | "training" | "ready" | "failed"
    3. resolve(schema)       → (artifact_dir | None, tier)   ← 3-tier fallback
    4. list_schemas()        → all registered schemas + their status
    5. build_base_model()    → train the generic fallback (run once per machine)

Registry file: ~/.decision-engine/registry.json
    {
      "<hash>": {
        "schema_hash":    "<8-char hex>",
        "registered_at":  "<ISO timestamp>",
        "status":         "ready",
        "artifact_dir":   "~/.decision-engine/semantic/<hash>/",
        "source_names":   ["POS", "Totals"],
        "column_count":   12,
        "has_aliases":    true
      },
      ...
    }

Usage:
    from training.semantic.schema_registry import SchemaRegistry

    reg = SchemaRegistry()

    # Register a new schema — training fires in the background
    entry = reg.register(schema, domain_aliases=aliases)
    print(entry["status"])    # "training"

    # Resolve best available model right now
    art_dir, tier = reg.resolve(schema, domain_aliases=aliases)
    print(tier)               # "base" (training still in progress)

    # Later, after training completes
    art_dir, tier = reg.resolve(schema, domain_aliases=aliases)
    print(tier)               # "schema"

Self-test:
    python3 training/semantic/schema_registry.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from training.semantic.pipeline import (
    _BASE_HASH,
    ModelTier,
    build_base_model,
    locate_artifacts,
    locate_base_model,
    resolve_artifacts,
    schema_hash,
    train_async,
)

# ── Registry path ─────────────────────────────────────────────────────────────


def _registry_path() -> Path:
    return Path.home() / ".decision-engine" / "registry.json"


def _load_registry() -> dict[str, Any]:
    p = _registry_path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def _save_registry(data: dict[str, Any]) -> None:
    p = _registry_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, default=str))


_REGISTRY_LOCK = threading.Lock()


# ── Status probing ────────────────────────────────────────────────────────────


def _probe_status(entry: dict[str, Any]) -> str:
    """Re-check artifact existence to update a stale 'training' status."""
    if entry.get("status") == "training":
        art_dir = entry.get("artifact_dir")
        if art_dir and (Path(art_dir) / "manifest.json").exists():
            return "ready"
        return "training"
    return entry.get("status", "untrained")


# ── SchemaRegistry ────────────────────────────────────────────────────────────


class SchemaRegistry:
    """
    Per-user schema registry.

    Thread-safe for concurrent register / resolve calls.
    All state is persisted to ~/.decision-engine/registry.json so it
    survives process restarts.
    """

    def __init__(self, base_dir: Path | None = None):
        """
        Args:
            base_dir: Override for artifact storage (tests / CI).
                      Defaults to ~/.decision-engine/semantic/.
        """
        self._base_dir = base_dir

    # ── Registration ─────────────────────────────────────────────────────────

    def register(
        self,
        schema: dict,
        domain_aliases: dict | None = None,
        epochs: int = 80,
        batch_size: int = 32,
        train: bool = True,
    ) -> dict[str, Any]:
        """
        Register a schema and (optionally) fire async training.

        If the schema was previously registered and training is already
        complete, returns the existing entry immediately.

        Returns the registry entry dict with a 'status' field:
            "ready"    — artifacts exist (no training needed)
            "training" — training kicked off in background
            "untrained"— train=False, artifacts will be built on demand
        """
        h = schema_hash(schema, domain_aliases)

        with _REGISTRY_LOCK:
            data = _load_registry()
            entry = data.get(h, {})

            # Re-probe in case artifacts were written since last registration
            current_status = _probe_status(entry)

            if current_status == "ready":
                entry["status"] = "ready"
                data[h] = entry
                _save_registry(data)
                return entry

            # Determine artifact directory
            art_dir = locate_artifacts(schema, domain_aliases, base=self._base_dir)
            if art_dir is not None:
                current_status = "ready"

            # Build or update entry
            source_names = list(schema.keys())
            col_count = sum(len(v) for v in schema.values())

            entry = {
                "schema_hash": h,
                "registered_at": entry.get("registered_at", datetime.now(UTC).isoformat()),
                "updated_at": datetime.now(UTC).isoformat(),
                "status": current_status
                if current_status == "ready"
                else ("training" if train else "untrained"),
                "artifact_dir": str(art_dir) if art_dir else None,
                "source_names": source_names,
                "column_count": col_count,
                "has_aliases": bool(domain_aliases),
            }
            data[h] = entry
            _save_registry(data)

        if train and current_status != "ready":
            # Determine output dir — use base_dir if provided, else default hash dir
            out_dir: Path | None = None
            if self._base_dir is not None:
                out_dir = self._base_dir / h

            future = train_async(
                schema=schema,
                domain_aliases=domain_aliases,
                out_dir=out_dir,
                epochs=epochs,
                batch_size=batch_size,
            )

            # Background thread updates the registry entry when done
            def _on_done(f):
                try:
                    done_dir = f.result()
                    with _REGISTRY_LOCK:
                        d = _load_registry()
                        if h in d:
                            d[h]["status"] = "ready"
                            d[h]["artifact_dir"] = str(done_dir)
                            d[h]["updated_at"] = datetime.now(UTC).isoformat()
                            _save_registry(d)
                except Exception as exc:
                    with _REGISTRY_LOCK:
                        d = _load_registry()
                        if h in d:
                            d[h]["status"] = "failed"
                            d[h]["error"] = str(exc)
                            d[h]["updated_at"] = datetime.now(UTC).isoformat()
                            _save_registry(d)

            future.add_done_callback(_on_done)

        return entry

    # ── Status ────────────────────────────────────────────────────────────────

    def status(self, schema: dict, domain_aliases: dict | None = None) -> str:
        """Return current training status for this schema."""
        h = schema_hash(schema, domain_aliases)
        data = _load_registry()
        if h not in data:
            return "untrained"
        return _probe_status(data[h])

    def get_entry(self, schema: dict, domain_aliases: dict | None = None) -> dict | None:
        """Return the full registry entry for a schema, or None if unknown."""
        h = schema_hash(schema, domain_aliases)
        data = _load_registry()
        entry = data.get(h)
        if entry is None:
            return None
        entry["status"] = _probe_status(entry)
        return entry

    # ── Resolution ────────────────────────────────────────────────────────────

    def resolve(
        self,
        schema: dict,
        domain_aliases: dict | None = None,
        base_model_dir: Path | None = None,
    ) -> tuple[Path | None, ModelTier]:
        """
        3-tier artifact resolution:
            Tier 1  "schema"  — trained schema-specific model
            Tier 2  "base"    — generic base model
            Tier 3  "none"    — no model available

        This is the primary call site for the resolver at inference time.
        """
        schema_base = None
        if self._base_dir is not None:
            h = schema_hash(schema, domain_aliases)
            schema_base = self._base_dir / h

        return resolve_artifacts(
            schema=schema,
            domain_aliases=domain_aliases,
            schema_base=schema_base,
            base_model_dir=base_model_dir,
        )

    # ── Base model ────────────────────────────────────────────────────────────

    def ensure_base_model(self, epochs: int = 80, batch_size: int = 32) -> Path:
        """
        Build the generic base model if it doesn't exist yet.

        Safe to call multiple times — no-ops if the base model is already
        present.  Intended to be called once per machine during first setup.
        """
        base_dir = None if self._base_dir is None else self._base_dir / _BASE_HASH
        existing = locate_base_model(base=base_dir)
        if existing is not None:
            return existing
        return build_base_model(out_dir=base_dir, epochs=epochs, batch_size=batch_size)

    # ── Listing ───────────────────────────────────────────────────────────────

    def list_schemas(self) -> list[dict[str, Any]]:
        """Return all registered schemas with live-probed status."""
        data = _load_registry()
        result = []
        for entry in data.values():
            e = dict(entry)
            e["status"] = _probe_status(e)
            result.append(e)
        return sorted(result, key=lambda e: e.get("registered_at", ""), reverse=True)

    # ── Housekeeping ──────────────────────────────────────────────────────────

    def purge(self, schema: dict, domain_aliases: dict | None = None) -> bool:
        """
        Remove a schema entry from the registry (artifacts are NOT deleted).

        Returns True if the entry existed, False if not found.
        """
        h = schema_hash(schema, domain_aliases)
        with _REGISTRY_LOCK:
            data = _load_registry()
            if h not in data:
                return False
            del data[h]
            _save_registry(data)
        return True


# ── CLI ───────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Schema registry management")
    parser.add_argument("--list", action="store_true", help="List all registered schemas")
    parser.add_argument("--base-model", action="store_true", help="Build/verify base model")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _run_self_test()
        return

    reg = SchemaRegistry()

    if args.list:
        schemas = reg.list_schemas()
        if not schemas:
            print("No schemas registered.")
        else:
            print(f"{'Hash':12} {'Status':12} {'Sources':30} {'Cols':5} {'Registered'}")
            print("-" * 80)
            for e in schemas:
                sources = ", ".join(e.get("source_names", []))[:28]
                reg_at = e.get("registered_at", "")[:19]
                print(
                    f"{e['schema_hash']:12} {e['status']:12} {sources:30} "
                    f"{e.get('column_count', 0):5} {reg_at}"
                )
        return

    if args.base_model:
        print("Building base model...")
        path = reg.ensure_base_model(epochs=args.epochs)
        print(f"Base model ready: {path}")
        return

    parser.print_help()


def _run_self_test():
    import tempfile

    schema = {
        "POS": [
            ["UNIT_PRICE", "unit_measure"],
            ["EXT_PRICE", "derived_measure"],
            ["QTY", "base_measure"],
            ["ORDER_DATE", "other"],
        ],
        "Totals": [
            ["Net_Sales", "derived_measure"],
            ["Guests", "base_measure"],
            ["PPA", "ratio"],
        ],
    }
    domain_aliases = {"ppa": ["per", "person", "average"]}

    fast_opts = {"epochs": 5, "batch_size": 16}

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        reg = SchemaRegistry(base_dir=base)

        # ── Test 1: register → trains in background ───────────────────────────
        print("── Test 1: register + async training")
        entry = reg.register(schema, domain_aliases, train=True, **fast_opts)
        assert entry["status"] in ("training", "ready"), entry
        h = entry["schema_hash"]
        assert len(h) == 8
        print(f"   status={entry['status']}  hash={h}")

        # ── Test 2: status returns known value ────────────────────────────────
        print("── Test 2: status")
        s = reg.status(schema, domain_aliases)
        assert s in ("training", "ready", "untrained"), s
        print(f"   status={s}")

        # ── Test 3: base model ────────────────────────────────────────────────
        print("── Test 3: ensure_base_model")
        base_dir = reg.ensure_base_model(epochs=5, batch_size=16)
        assert (base_dir / "manifest.json").exists(), "base model manifest missing"
        print(f"   base model ready at {base_dir.name}/")

        # ── Test 4: resolve before schema training completes ──────────────────
        print("── Test 4: resolve (base or schema)")
        art_dir, tier = reg.resolve(schema, domain_aliases, base_model_dir=base_dir)
        assert tier in ("schema", "base"), f"Expected schema or base, got {tier!r}"
        print(f"   tier={tier!r}")

        # ── Test 5: wait for training, then resolve to Tier 1 ─────────────────
        print("── Test 5: wait for training + re-resolve")
        # Re-register with train=True to get the future; or wait via polling
        # Since training is already in flight from Test 1, poll the registry
        import time

        for _ in range(60):  # up to 60s
            s = reg.status(schema, domain_aliases)
            if s == "ready":
                break
            time.sleep(1.0)
        assert s == "ready", f"Training did not complete within 60s (status={s!r})"

        art_dir2, tier2 = reg.resolve(schema, domain_aliases)
        assert tier2 == "schema", f"Expected Tier1 after training, got {tier2!r}"
        print(f"   tier={tier2!r}  artifacts at {Path(str(art_dir2)).name}/")

        # ── Test 6: list_schemas ──────────────────────────────────────────────
        print("── Test 6: list_schemas")
        schemas = reg.list_schemas()
        assert any(e["schema_hash"] == h for e in schemas)
        print(f"   {len(schemas)} schema(s) registered")

        # ── Test 7: purge ─────────────────────────────────────────────────────
        print("── Test 7: purge")
        removed = reg.purge(schema, domain_aliases)
        assert removed is True
        assert reg.get_entry(schema, domain_aliases) is None
        print("   PASSED")

    print("\nSelf-test PASSED  (7/7 subtests)")


if __name__ == "__main__":
    main()
