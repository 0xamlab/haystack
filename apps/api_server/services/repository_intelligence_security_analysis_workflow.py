"""Security-analyses reachability proof — the engine that earns codna's four honest verdicts.

Built on the SAME snapshot file/symbol graph the existing graph-query uses
(`repository_intelligence_graph._snapshot_file_graph_neighbors`, hydrated
`files[].symbols/dependencies/symbol_references`) and the runtime LANGUAGE matrix
(`repository_runtime_language_route_index`). No new taint backend is required for a correct,
HONEST first version: where the graph cannot prove something, the classifier returns `unknown`
by construction — exactly the contract codna's EngineAdapter enforces client-side.

Verdicts (per finding), and the single rule that governs them:
  exploitable          — an INDEPENDENT validated source->sink path AND a complete sound envelope
  production-reachable — a production entrypoint reaches the vulnerable op (taint NOT proven)
  unreachable          — no violating path, PROVEN within a complete sound envelope
  unknown              — off-matrix language / unresolved edges / no evidence
"no path" + INCOMPLETE envelope => unknown, never unreachable. Confidence is never computed and
never upgrades a verdict. Scanner code_flows are CORROBORATION only — a scanner flow alone never
yields `exploitable`. The independent-taint path-finder is injectable (`taint_path_finder`); the
v1 default is None, so v1 tops out at `production-reachable` (the dedicated taint backend that
raises `exploitable` recall is a later drop-in that changes only the path-finder, not the gates).
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Callable
from typing import Any

from apps.api_server.models.data_connector import DataConnector
from apps.api_server.schemas.repositories import (
    AnalysisEnvelope,
    ProofLocation,
    PropagationEdge,
    ScannerFlowValidation,
    SecurityAnalysisClosureRequest,
    SecurityAnalysisClosureResponse,
    SecurityAnalysisRequest,
    SecurityAnalysisResponse,
    SecurityEngineRef,
    SecurityFinding,
    SecurityProof,
    SecuritySnapshotRef,
)
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)
from apps.api_server.services.repository_intelligence_graph import (
    _resolve_snapshot_file_path,
    _snapshot_file_graph_neighbors,
)
from apps.api_server.services.repository_intelligence_runtime_language_support import (
    repository_runtime_language_route_index,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier

_RequireRepositoryConnector = Callable[[DataConnector], None]
_LoadSnapshotManifest = Callable[..., dict[str, Any]]
_LoadSecurityProofByFinding = Callable[..., dict[str, Any] | None]
_LoadPatchDiffByDigest = Callable[..., str | None]

# Languages with sound-enough symbol/dependency resolution to support absence proofs and (with a
# taint backend) exploitability. Deliberately a CURATED set — being merely on the 250-language
# matrix is NOT sufficient for `is_complete_sound`. Frameworks like Spring demote (reflection).
_SOUND_TAINT_LANGUAGES: frozenset[str] = frozenset(
    {"python", "javascript", "typescript", "java", "go", "ruby", "php", "csharp", "c_sharp"}
)
_REFLECTION_FRAMEWORKS: frozenset[str] = frozenset({"spring", "spring-boot", "guice", "hibernate"})
_TAINT_KINDS: frozenset[str] = frozenset({"taint"})

_MAX_REACH_NODES = 256

_ENTRYPOINT_PATH_RE = re.compile(
    r"(^|/)(main|app|server|wsgi|asgi|index|cmd/|api/|routes?/|controllers?/|handlers?/|views?/|endpoints?/)",
    re.IGNORECASE,
)
_ENTRYPOINT_SYMBOL_NAMES = frozenset({"main", "handler", "handle", "index", "lambda_handler"})
_ENTRYPOINT_SIGNATURE_RE = re.compile(
    r"@(app|router|blueprint|api)\.(route|get|post|put|delete|patch)"
    r"|def\s+main\b|func\s+main\b|HttpServlet|@RestController|@Controller|@RequestMapping|@GetMapping|@PostMapping",
    re.IGNORECASE,
)
_SANITIZER_RE = re.compile(
    r"(parameteri|saniti[sz]e|escape|shlex\.quote|bleach\.clean|html\.escape|quote\("
    r"|prepared\s*statement|bindparam|placeholder|validate|allowlist|whitelist)",
    re.IGNORECASE,
)
_DYNAMIC_REFERENCE_TYPES: frozenset[str] = frozenset({"reflection", "dynamic", "eval", "indirect"})


# --------------------------------------------------------------------------- graph helpers


def _known_paths(manifest: dict[str, Any]) -> tuple[tuple[str, ...], set[str]]:
    paths = tuple(str(f["file_path"]) for f in manifest.get("files", ()))
    return paths, set(paths)


def _files_by_path(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(f["file_path"]): f for f in manifest.get("files", ())}


def _symbols_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for file_entry in manifest.get("files", ()):
        for symbol in file_entry.get("symbols", ()):
            sid = str(symbol.get("symbol_id") or "").strip()
            if sid:
                out[sid] = {**symbol, "file_path": file_entry["file_path"]}
    return out


def discover_entrypoints(manifest: dict[str, Any]) -> dict[str, ProofLocation]:
    """Heuristically mark files as production entrypoints (HTTP handlers, main, framework
    handlers). Conservative + language-agnostic; this is production-callability, never proof
    of attacker control on its own."""
    entrypoints: dict[str, ProofLocation] = {}
    for file_entry in manifest.get("files", ()):
        path = str(file_entry["file_path"])
        hit_symbol_id: str | None = None
        for symbol in file_entry.get("symbols", ()):
            name = str(symbol.get("symbol_name") or "").strip().lower()
            sig = str(symbol.get("signature") or "")
            if name in _ENTRYPOINT_SYMBOL_NAMES or _ENTRYPOINT_SIGNATURE_RE.search(sig):
                hit_symbol_id = str(symbol.get("symbol_id") or "") or None
                break
        if hit_symbol_id or _ENTRYPOINT_PATH_RE.search(path):
            entrypoints[path] = ProofLocation(uri=path, symbol_id=hit_symbol_id)
    return entrypoints


def _backward_reachable(
    op_file: str,
    inbound: dict[str, set[str]],
    entrypoint_files: set[str],
    *,
    max_nodes: int = _MAX_REACH_NODES,
) -> tuple[list[str], list[PropagationEdge], bool]:
    """Backward BFS over caller (inbound) edges from `op_file` to any entrypoint. Returns
    (reached entrypoints, one representative path as edges, budget_exhausted)."""
    if op_file in entrypoint_files:
        return [op_file], [], False
    seen: set[str] = {op_file}
    parent: dict[str, str] = {}
    queue: deque[str] = deque([op_file])
    reached: list[str] = []
    budget_exhausted = False
    while queue:
        if len(seen) > max_nodes:
            budget_exhausted = True
            break
        node = queue.popleft()
        for caller in sorted(inbound.get(node, ())):
            if caller in seen:
                continue
            seen.add(caller)
            parent[caller] = node
            if caller in entrypoint_files:
                reached.append(caller)
                # reconstruct caller -> ... -> op_file as propagation edges
                path: list[PropagationEdge] = []
                cur = caller
                while cur in parent:
                    path.append(
                        PropagationEdge(from_file=cur, to_file=parent[cur], edge_type="reaches")
                    )
                    cur = parent[cur]
                return reached, path, budget_exhausted
            queue.append(caller)
    return reached, [], budget_exhausted


def _file_unresolved_edges(
    file_entry: dict[str, Any],
    known_paths_set: set[str],
    symbols_by_id: dict[str, dict[str, Any]],
) -> list[PropagationEdge]:
    """Edges out of `file_entry` whose target is not a file in the snapshot — these bound
    the soundness of any proof that crosses this file."""
    source = str(file_entry["file_path"])
    unresolved: list[PropagationEdge] = []
    for dep in file_entry.get("dependencies", ()):
        target = dep.get("target_file")
        if target and str(target) not in known_paths_set:
            unresolved.append(
                PropagationEdge(
                    from_file=source,
                    to_file=str(target),
                    edge_type=str(dep.get("dependency_type") or "imports"),
                )
            )
    for ref in file_entry.get("symbol_references", ()):
        target = ref.get("target_file")
        if target is None:
            sym = symbols_by_id.get(str(ref.get("target_symbol_id") or "").strip())
            target = sym.get("file_path") if sym else None
        if target and str(target) not in known_paths_set:
            unresolved.append(
                PropagationEdge(
                    from_file=source,
                    to_file=str(target),
                    edge_type=str(ref.get("reference_type") or "references_symbol"),
                )
            )
    return unresolved


def _has_dynamic_dispatch(file_entry: dict[str, Any]) -> bool:
    for ref in file_entry.get("symbol_references", ()):
        if str(ref.get("reference_type") or "").strip().lower() in _DYNAMIC_REFERENCE_TYPES:
            return True
    return False


# --------------------------------------------------------------------------- classifier


def _envelope(
    language: str | None,
    route_index: dict[str, Any],
    *,
    all_edges_resolved: bool,
    node_budget_exhausted: bool,
    dynamic_dispatch: bool,
    framework: str | None = None,
) -> AnalysisEnvelope:
    on_matrix = bool(language) and language in route_index
    route_kind = getattr(route_index.get(language), "route_kind", None) if on_matrix else None
    sound_language = bool(language) and language in _SOUND_TAINT_LANGUAGES
    reasons: list[str] = []
    if not on_matrix:
        reasons.append("language_off_matrix")
    if on_matrix and not sound_language:
        reasons.append("language_not_in_sound_set")
    if framework and framework.lower() in _REFLECTION_FRAMEWORKS:
        sound_language = False
        reasons.append("reflection_framework")
    if not all_edges_resolved:
        reasons.append("unresolved_edges_on_path")
    if node_budget_exhausted:
        reasons.append("node_budget_exhausted")
    if dynamic_dispatch:
        reasons.append("dynamic_dispatch_on_path")
    complete = (
        on_matrix
        and sound_language
        and all_edges_resolved
        and not node_budget_exhausted
        and not dynamic_dispatch
    )
    return AnalysisEnvelope(
        is_complete_sound=complete,
        language=language,
        framework=framework,
        build_mode=None,
        route_kind=route_kind,
        on_matrix=on_matrix,
        sound_language=sound_language,
        all_edges_resolved=all_edges_resolved,
        node_budget_exhausted=node_budget_exhausted,
        incomplete_reasons=reasons,
    )


def classify_finding(
    finding: SecurityFinding,
    manifest: dict[str, Any],
    *,
    route_index: dict[str, Any],
    inbound: dict[str, set[str]],
    files_by_path: dict[str, dict[str, Any]],
    symbols_by_id: dict[str, dict[str, Any]],
    known_paths: tuple[str, ...],
    known_paths_set: set[str],
    entrypoints: dict[str, ProofLocation],
    taint_path_finder: Callable[..., list[PropagationEdge] | None] | None = None,
) -> SecurityProof:
    kind = finding.finding_kind
    loc = finding.primary_location
    raw_uri = loc.uri if loc else None

    # Step A — resolve the vulnerable op file in the snapshot.
    op_file = (
        _resolve_snapshot_file_path(
            raw_path=raw_uri, known_paths=known_paths, known_paths_set=known_paths_set
        )
        if raw_uri
        else None
    )
    if op_file is None:
        return SecurityProof(
            canonical_finding_id=finding.canonical_id,
            finding_kind=kind,
            classification="unknown",
            proof_type="no_evidence",
            analysis_envelope=AnalysisEnvelope(
                is_complete_sound=False, incomplete_reasons=["finding_file_not_in_snapshot"]
            ),
            assumptions=["op file not present in snapshot"],
        )

    op_entry = files_by_path[op_file]
    language = str(op_entry.get("language") or "") or None

    # Step C — entrypoint reachability (independent of the scanner).
    entrypoint_files = set(entrypoints)
    reached, path_edges, budget = _backward_reachable(op_file, inbound, entrypoint_files)
    reachable = bool(reached)

    # Step B — envelope soundness over the explored path (op file + path files).
    path_files = {op_file} | {e.from_file for e in path_edges} | {e.to_file for e in path_edges}
    unresolved: list[PropagationEdge] = []
    dynamic = False
    for pf in path_files:
        fe = files_by_path.get(pf)
        if fe is None:
            continue
        unresolved.extend(_file_unresolved_edges(fe, known_paths_set, symbols_by_id))
        dynamic = dynamic or _has_dynamic_dispatch(fe)
    envelope = _envelope(
        language,
        route_index,
        all_edges_resolved=not unresolved,
        node_budget_exhausted=budget,
        dynamic_dispatch=dynamic,
    )

    sink_loc = ProofLocation(
        uri=op_file,
        start_line=(loc.start_line if loc else None),
        logical=(loc.logical if loc else None),
    )
    entry_locs = [entrypoints[f] for f in reached if f in entrypoints]
    scanner_flow = _scanner_flow_validation(finding, path_edges)

    # Step D — independent taint path (the ONLY route to `exploitable`). v1 default: None.
    taint_path: list[PropagationEdge] | None = None
    if kind in _TAINT_KINDS and taint_path_finder is not None:
        taint_path = taint_path_finder(
            finding=finding,
            manifest=manifest,
            op_file=op_file,
            entrypoints=entrypoints,
            inbound=inbound,
        )

    # Step E — the decision tree (the contract, exactly).
    if not envelope.on_matrix:
        classification, proof_type = "unknown", "off_matrix"
    elif kind in _TAINT_KINDS and taint_path and envelope.is_complete_sound:
        classification, proof_type = "exploitable", "dataflow"
        path_edges = taint_path
    elif reachable:
        classification, proof_type = "production-reachable", "entrypoint_reachability"
    elif kind in _TAINT_KINDS and envelope.is_complete_sound:
        classification, proof_type = "unreachable", "absence_proof"
    else:
        classification, proof_type = "unknown", "no_evidence"

    assumptions: list[str] = []
    if reachable:
        assumptions.append("graph: production entrypoint reaches the vulnerable op")
    if unresolved:
        assumptions.append(f"unverified: {len(unresolved)} edge(s) leave the snapshot")
    if scanner_flow.provided:
        assumptions.append(
            "scanner_code_flow: corroborates engine path"
            if scanner_flow.corroborates_engine_path
            else "scanner_code_flow: present but does not corroborate an engine path"
        )

    return SecurityProof(
        canonical_finding_id=finding.canonical_id,
        finding_kind=kind,
        classification=classification,
        proof_type=proof_type,
        analysis_envelope=envelope,
        entrypoints=entry_locs,
        sinks=[sink_loc],
        propagation_paths=[path_edges] if path_edges else [],
        sanitizers=[],
        assumptions=assumptions,
        unresolved_edges=unresolved[:32],
        scanner_flow_validation=scanner_flow,
    )


def _scanner_flow_validation(
    finding: SecurityFinding, path_edges: list[PropagationEdge]
) -> ScannerFlowValidation:
    if not finding.code_flows:
        return ScannerFlowValidation(provided=False)
    flow_files = {step.uri for flow in finding.code_flows for step in flow}
    engine_files = {e.from_file for e in path_edges} | {e.to_file for e in path_edges}
    overlap = bool(flow_files & engine_files)
    return ScannerFlowValidation(
        provided=True,
        corroborates_engine_path=overlap,
        note=None if overlap else "scanner flow does not overlap the engine path",
    )


def analyze_findings(
    findings: list[SecurityFinding],
    manifest: dict[str, Any],
    *,
    route_index: dict[str, Any] | None = None,
    taint_path_finder: Callable[..., list[PropagationEdge] | None] | None = None,
) -> list[SecurityProof]:
    """Pure batch classification over a snapshot manifest (build-once / query-many)."""
    route_index = (
        route_index if route_index is not None else repository_runtime_language_route_index()
    )
    inbound, _outbound = _snapshot_file_graph_neighbors(manifest)
    known_paths, known_paths_set = _known_paths(manifest)
    files_by_path = _files_by_path(manifest)
    symbols_by_id = _symbols_by_id(manifest)
    entrypoints = discover_entrypoints(manifest)
    return [
        classify_finding(
            f,
            manifest,
            route_index=route_index,
            inbound=inbound,
            files_by_path=files_by_path,
            symbols_by_id=symbols_by_id,
            known_paths=known_paths,
            known_paths_set=known_paths_set,
            entrypoints=entrypoints,
            taint_path_finder=taint_path_finder,
        )
        for f in findings
    ]


# --------------------------------------------------------------------------- batch entry


def analyze_repository_security_batch(
    *,
    connector: DataConnector,
    request: SecurityAnalysisRequest,
    engine_revision: str,
    require_repository_connector: _RequireRepositoryConnector,
    load_snapshot_manifest: _LoadSnapshotManifest,
    route_index_fn: Callable[[], dict[str, Any]] | None = None,
    taint_path_finder: Callable[..., list[PropagationEdge] | None] | None = None,
) -> SecurityAnalysisResponse:
    require_repository_connector(connector)
    org_id = str(connector.org_id)
    repository_id = str(connector.id)
    if not request.findings:
        raise RepositoryIntelligenceError(
            code="security_analysis_no_findings",
            status_code=422,
            message="security-analyses requires at least one finding.",
        )
    manifest = load_snapshot_manifest(
        org_id=org_id, repository_id=repository_id, snapshot_id=request.snapshot_id
    )
    route_index = (route_index_fn or repository_runtime_language_route_index)()
    proofs = analyze_findings(
        request.findings, manifest, route_index=route_index, taint_path_finder=taint_path_finder
    )
    lookup_payload = {
        "engine_revision": engine_revision,
        "snapshot_id": request.snapshot_id,
        "sarif_digest": request.sarif_digest,
        "policy_digest": request.policy_digest,
        "model_pack_digest": request.model_pack_digest,
        "scanner": request.scanner.model_dump(mode="json"),
        "findings": sorted(f.canonical_id for f in request.findings),
    }
    return SecurityAnalysisResponse(
        analysis_id=_stable_identifier("security_analysis", lookup_payload),
        snapshot=SecuritySnapshotRef(
            id=request.snapshot_id,
            commit=manifest.get("resolved_revision") or manifest.get("commit"),
            tree_digest=manifest.get("content_hash") or manifest.get("tree_digest"),
        ),
        sarif_digest=request.sarif_digest,  # mandatory binding echo
        engine=SecurityEngineRef(
            version=engine_revision, model_pack_digest=request.model_pack_digest
        ),
        proofs=proofs,
    )


# --------------------------------------------------------------------------- closure


def _changed_files_and_added_lines(diff: str) -> tuple[set[str], list[str]]:
    changed: set[str] = set()
    for m in re.finditer(r"^\+\+\+ [ab]/(.+)$", diff, re.MULTILINE):
        p = m.group(1).strip()
        if p != "/dev/null":
            changed.add(p)
    for m in re.finditer(r"^diff --git a/(\S+) b/(\S+)", diff, re.MULTILINE):
        changed.add(m.group(2))
    added = [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    return changed, added


def analyze_repository_security_closure(
    *,
    connector: DataConnector,
    request: SecurityAnalysisClosureRequest,
    engine_revision: str,
    require_repository_connector: _RequireRepositoryConnector,
    load_security_proof_by_finding: _LoadSecurityProofByFinding,
    load_patch_diff_by_digest: _LoadPatchDiffByDigest,
) -> SecurityAnalysisClosureResponse:
    """Re-prove that a patch CLOSES the original finding obligation (a separate judgment from
    reachability — a sanitizer/barrier closes it even if the op stays production-reachable)."""
    require_repository_connector(connector)
    org_id = str(connector.org_id)
    repository_id = str(connector.id)

    if not request.patch_digest:
        return SecurityAnalysisClosureResponse(closure_status="unknown")
    diff = load_patch_diff_by_digest(
        org_id=org_id, repository_id=repository_id, patch_digest=request.patch_digest
    )
    proof = load_security_proof_by_finding(
        org_id=org_id,
        repository_id=repository_id,
        canonical_finding_id=request.canonical_finding_id,
        snapshot_id=request.snapshot_id,
    )
    if not diff or proof is None:
        # cannot bind a patch, or no original obligation to re-test
        return SecurityAnalysisClosureResponse(closure_status="unknown")

    changed_files, added_lines = _changed_files_and_added_lines(diff)
    # The obligation's path files: the sinks + every file on the original propagation paths.
    path_files: set[str] = {s.get("uri") for s in (proof.get("sinks") or []) if s.get("uri")}
    for p in proof.get("propagation_paths") or []:
        for edge in p:
            path_files.add(edge.get("from_file"))
            path_files.add(edge.get("to_file"))
    path_files.discard(None)

    touched_path = bool(path_files & changed_files)
    if not touched_path:
        # the patch didn't touch the obligation's path -> it cannot have closed it
        return SecurityAnalysisClosureResponse(closure_status="open", alternate_path_found=False)

    sanitized = any(_SANITIZER_RE.search(line) for line in added_lines)
    if sanitized:
        # a recognized barrier was inserted on the path -> closed even if still reachable
        return SecurityAnalysisClosureResponse(closure_status="closed", alternate_path_found=False)
    # touched the path but no recognized barrier -> conservatively open (could be a moved sink)
    return SecurityAnalysisClosureResponse(closure_status="open", alternate_path_found=False)
