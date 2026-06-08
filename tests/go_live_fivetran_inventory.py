from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal

import requests

ReleaseClass = Literal["ga", "lite", "beta", "private_preview", "partner_built"]
PlanClass = Literal["standard", "enterprise_only", "unknown"]
ConfidenceClass = Literal["high", "medium", "low"]
ConnectorFamily = Literal["application", "database", "file", "event"]
SourceType = Literal["api", "database", "file", "stream", "other"]
SelectionBucket = Literal[
    "crm_marketing_support",
    "finance_commerce_erp",
    "engineering_product_ops",
    "data_infrastructure",
    "hr_people",
]
Complexity = Literal["low", "medium", "high"]

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_DIR = ROOT / "tests" / "integration"
INVENTORY_LOCK_PATH = INTEGRATION_DIR / "fivetran_inventory.lock.json"
SELECTION_LOCK_PATH = INTEGRATION_DIR / "fivetran_top20.lock.json"
BASELINE_LOCK_PATH = INTEGRATION_DIR / "fivetran_baseline.lock.json"
MANIFEST_EXAMPLE_PATH = INTEGRATION_DIR / "fivetran_wave1_manifest.example.json"
FIVETRAN_DOCS_BASE = "https://fivetran.com"

SELECTION_BUCKET_QUOTAS: dict[SelectionBucket, int] = {
    "crm_marketing_support": 5,
    "finance_commerce_erp": 5,
    "engineering_product_ops": 4,
    "data_infrastructure": 4,
    "hr_people": 2,
}

DIVERSITY_CONSTRAINTS: dict[str, int] = {
    "nested_json": 3,
    "wide_table": 3,
    "high_churn_rest": 2,
    "append_only_event": 2,
}

CATALOG_PAGES: tuple[tuple[str, ConnectorFamily, SourceType], ...] = (
    ("/docs/connectors/applications", "application", "api"),
    ("/docs/connectors/databases", "database", "database"),
    ("/docs/connectors/files", "file", "file"),
    ("/docs/connectors/events", "event", "stream"),
)

IGNORED_DOC_SUFFIXES = {
    "/changelog",
    "/connection-options",
    "/troubleshooting",
    "/tutorials",
}

IGNORED_DOC_PATHS = {
    "/docs/connectors/applications",
    "/docs/connectors/databases",
    "/docs/connectors/files",
    "/docs/connectors/events",
    "/docs/connectors/databases/hva-connectors",
}

ENTERPRISE_ONLY_DOC_PATHS = {
    "/docs/connectors/databases/hva-db2i",
    "/docs/connectors/databases/oracle",
    "/docs/connectors/databases/sap/high-volume-agent",
}

MANUAL_CONNECTOR_OVERRIDES: dict[str, dict[str, Any]] = {
    "/docs/connectors/applications/salesforce": {
        "classification_confidence": "high",
        "selection_bucket": "crm_marketing_support",
        "schema_complexity": "high",
        "join_complexity": "high",
        "nested_json": True,
        "wide_table": True,
        "score_bonus": 40,
    },
    "/docs/connectors/applications/hubspot": {
        "classification_confidence": "high",
        "selection_bucket": "crm_marketing_support",
        "schema_complexity": "high",
        "join_complexity": "high",
        "nested_json": True,
        "wide_table": True,
        "score_bonus": 38,
    },
    "/docs/connectors/applications/marketo": {
        "classification_confidence": "high",
        "selection_bucket": "crm_marketing_support",
        "schema_complexity": "high",
        "join_complexity": "medium",
        "wide_table": True,
        "score_bonus": 34,
    },
    "/docs/connectors/applications/google-ads": {
        "classification_confidence": "high",
        "selection_bucket": "crm_marketing_support",
        "schema_complexity": "medium",
        "join_complexity": "medium",
        "high_churn_rest": True,
        "score_bonus": 28,
    },
    "/docs/connectors/applications/zendesk-chat": {
        "classification_confidence": "high",
        "selection_bucket": "crm_marketing_support",
        "schema_complexity": "medium",
        "join_complexity": "medium",
        "high_churn_rest": True,
        "score_bonus": 24,
    },
    "/docs/connectors/applications/intercom": {
        "classification_confidence": "high",
        "selection_bucket": "crm_marketing_support",
        "schema_complexity": "medium",
        "join_complexity": "medium",
        "high_churn_rest": True,
        "score_bonus": 20,
    },
    "/docs/connectors/applications/shopify": {
        "classification_confidence": "high",
        "selection_bucket": "finance_commerce_erp",
        "schema_complexity": "high",
        "join_complexity": "high",
        "nested_json": True,
        "wide_table": True,
        "score_bonus": 35,
    },
    "/docs/connectors/applications/stripe": {
        "classification_confidence": "high",
        "selection_bucket": "finance_commerce_erp",
        "schema_complexity": "high",
        "join_complexity": "high",
        "nested_json": True,
        "high_churn_rest": True,
        "score_bonus": 36,
    },
    "/docs/connectors/applications/netsuite-suiteanalytics": {
        "classification_confidence": "high",
        "selection_bucket": "finance_commerce_erp",
        "schema_complexity": "high",
        "join_complexity": "high",
        "wide_table": True,
        "score_bonus": 37,
    },
    "/docs/connectors/applications/chargebee": {
        "classification_confidence": "high",
        "selection_bucket": "finance_commerce_erp",
        "schema_complexity": "medium",
        "join_complexity": "high",
        "wide_table": True,
        "score_bonus": 26,
    },
    "/docs/connectors/applications/xero": {
        "classification_confidence": "high",
        "selection_bucket": "finance_commerce_erp",
        "schema_complexity": "medium",
        "join_complexity": "medium",
        "score_bonus": 22,
    },
    "/docs/connectors/applications/github": {
        "classification_confidence": "high",
        "selection_bucket": "engineering_product_ops",
        "schema_complexity": "high",
        "join_complexity": "high",
        "nested_json": True,
        "high_churn_rest": True,
        "append_only_event": True,
        "score_bonus": 36,
    },
    "/docs/connectors/applications/jira": {
        "classification_confidence": "high",
        "selection_bucket": "engineering_product_ops",
        "schema_complexity": "high",
        "join_complexity": "high",
        "nested_json": True,
        "high_churn_rest": True,
        "score_bonus": 34,
    },
    "/docs/connectors/applications/azure-devops": {
        "classification_confidence": "high",
        "selection_bucket": "engineering_product_ops",
        "schema_complexity": "high",
        "join_complexity": "medium",
        "nested_json": True,
        "high_churn_rest": True,
        "append_only_event": False,
        "score_bonus": 32,
    },
    "/docs/connectors/applications/asana": {
        "classification_confidence": "high",
        "selection_bucket": "engineering_product_ops",
        "schema_complexity": "medium",
        "join_complexity": "medium",
        "nested_json": False,
        "high_churn_rest": False,
        "append_only_event": False,
        "score_bonus": 20,
    },
    "/docs/connectors/databases/postgresql": {
        "classification_confidence": "high",
        "selection_bucket": "data_infrastructure",
        "schema_complexity": "medium",
        "join_complexity": "high",
        "score_bonus": 28,
    },
    "/docs/connectors/databases/mongodb": {
        "classification_confidence": "high",
        "selection_bucket": "data_infrastructure",
        "schema_complexity": "high",
        "join_complexity": "medium",
        "nested_json": True,
        "score_bonus": 31,
    },
    "/docs/connectors/files/amazon-s3": {
        "classification_confidence": "high",
        "selection_bucket": "data_infrastructure",
        "schema_complexity": "medium",
        "join_complexity": "medium",
        "score_bonus": 27,
    },
    "/docs/connectors/events/apache-kafka": {
        "classification_confidence": "high",
        "selection_bucket": "data_infrastructure",
        "schema_complexity": "high",
        "join_complexity": "medium",
        "append_only_event": True,
        "score_bonus": 33,
    },
    "/docs/connectors/databases/mysql": {
        "classification_confidence": "high",
        "selection_bucket": "data_infrastructure",
        "schema_complexity": "medium",
        "join_complexity": "medium",
        "score_bonus": 18,
    },
    "/docs/connectors/applications/bamboohr": {
        "classification_confidence": "high",
        "selection_bucket": "hr_people",
        "schema_complexity": "medium",
        "join_complexity": "medium",
        "wide_table": True,
        "score_bonus": 24,
    },
    "/docs/connectors/applications/greenhouse": {
        "classification_confidence": "high",
        "selection_bucket": "hr_people",
        "schema_complexity": "medium",
        "join_complexity": "medium",
        "wide_table": True,
        "score_bonus": 22,
    },
}


@dataclass(frozen=True)
class FivetranInventoryEntry:
    connector_slug: str
    display_name: str
    family: ConnectorFamily
    source_type: SourceType
    docs_path: str
    release_class: ReleaseClass
    plan_class: PlanClass
    classification_confidence: ConfidenceClass
    selection_bucket: SelectionBucket | None
    schema_complexity: Complexity
    join_complexity: Complexity
    nested_json: bool
    wide_table: bool
    high_churn_rest: bool
    append_only_event: bool
    score_bonus: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FivetranSelectionEntry:
    connector_slug: str
    display_name: str
    docs_path: str
    family: ConnectorFamily
    selection_bucket: SelectionBucket
    source_type: SourceType
    score: int
    release_class: ReleaseClass
    plan_class: PlanClass
    classification_confidence: ConfidenceClass
    schema_complexity: Complexity
    join_complexity: Complexity
    nested_json: bool
    wide_table: bool
    high_churn_rest: bool
    append_only_event: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InventoryRefreshError(RuntimeError):
    pass


class _AnchorCollector(HTMLParser):
    def __init__(self, prefix: str) -> None:
        super().__init__(convert_charrefs=True)
        self._prefix = prefix
        self._active_href: str | None = None
        self._active_parts: list[str] = []
        self.links: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href and href.startswith(self._prefix):
            self._active_href = href
            self._active_parts = []

    def handle_data(self, data: str) -> None:
        if self._active_href is not None:
            text = data.strip()
            if text:
                self._active_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._active_href is None:
            return
        text = " ".join(part.strip() for part in self._active_parts if part.strip()).strip()
        if text:
            existing = self.links.get(self._active_href, "")
            if len(text) > len(existing):
                self.links[self._active_href] = text
        self._active_href = None
        self._active_parts = []


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json_dumps(value).encode("utf-8")).hexdigest()


def _connector_slug_from_docs_path(docs_path: str, family: ConnectorFamily) -> str:
    prefix = f"/docs/connectors/{family}s/" if family in {"application", "database"} else None
    if family == "application":
        prefix = "/docs/connectors/applications/"
    elif family == "database":
        prefix = "/docs/connectors/databases/"
    elif family == "file":
        prefix = "/docs/connectors/files/"
    elif family == "event":
        prefix = "/docs/connectors/events/"
    if prefix is None or not docs_path.startswith(prefix):
        raise ValueError(f"Unsupported docs path for {family}: {docs_path}")
    return docs_path[len(prefix) :]


def _fetch_html(path: str) -> str:
    response = requests.get(f"{FIVETRAN_DOCS_BASE}{path}", timeout=30)
    response.raise_for_status()
    return response.text


def _clean_catalog_path(path: str) -> str | None:
    normalized = path.split("#", 1)[0].rstrip("/")
    if normalized in IGNORED_DOC_PATHS:
        return None
    if any(normalized.endswith(suffix) for suffix in IGNORED_DOC_SUFFIXES):
        return None
    if normalized.startswith("/docs/connectors/databases/oracle/"):
        return None
    if normalized.startswith("/docs/connectors/databases/sap/sap-erp-hana"):
        return None
    return normalized


def _collect_catalog_links(path: str, family: ConnectorFamily) -> dict[str, str]:
    prefix = {
        "application": "/docs/connectors/applications/",
        "database": "/docs/connectors/databases/",
        "file": "/docs/connectors/files/",
        "event": "/docs/connectors/events/",
    }[family]
    parser = _AnchorCollector(prefix)
    parser.feed(_fetch_html(path))
    cleaned: dict[str, str] = {}
    for href, display_name in parser.links.items():
        normalized = _clean_catalog_path(href)
        if normalized is None:
            continue
        cleaned[normalized] = display_name
    return cleaned


def _load_next_data_content(path: str) -> list[dict[str, Any]]:
    html = _fetch_html(path)
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if match is None:
        raise InventoryRefreshError(f"Missing __NEXT_DATA__ payload for {path}")
    payload = json.loads(match.group(1))
    article = payload["props"]["pageProps"]["article"]
    return json.loads(article["content"])


def _walk_md_links(nodes: list[dict[str, Any]], *, href_prefix: str) -> dict[str, str]:
    found: dict[str, str] = {}

    def _walk(node: Any) -> None:
        if isinstance(node, list):
            for child in node:
                _walk(child)
            return
        if not isinstance(node, dict):
            return
        if node.get("name") == "a":
            attributes = node.get("attributes", {})
            href = str(attributes.get("href", "")).strip()
            if href.startswith(href_prefix):
                label = "".join(
                    child.strip()
                    for child in node.get("children", [])
                    if isinstance(child, str) and child.strip()
                )
                if label:
                    found[href.rstrip("/")] = label
        for child in node.get("children", []):
            _walk(child)

    _walk(nodes)
    return found


def _collect_lite_docs_paths() -> set[str]:
    content = _load_next_data_content("/docs/connectors/applications/lite-connectors")
    return set(_walk_md_links(content, href_prefix="/docs/connectors/applications/"))


def _default_entry(
    *,
    docs_path: str,
    display_name: str,
    family: ConnectorFamily,
    source_type: SourceType,
) -> FivetranInventoryEntry:
    return FivetranInventoryEntry(
        connector_slug=_connector_slug_from_docs_path(docs_path, family),
        display_name=display_name,
        family=family,
        source_type=source_type,
        docs_path=docs_path,
        release_class="ga",
        plan_class="standard",
        classification_confidence="medium",
        selection_bucket=None,
        schema_complexity="medium",
        join_complexity="medium",
        nested_json=False,
        wide_table=False,
        high_churn_rest=False,
        append_only_event=False,
        score_bonus=0,
    )


def _apply_entry_overrides(
    entry: FivetranInventoryEntry,
    *,
    lite_paths: set[str],
) -> FivetranInventoryEntry:
    data = entry.to_dict()
    if entry.docs_path in lite_paths:
        data["release_class"] = "lite"
        data["classification_confidence"] = "high"
    if entry.docs_path in ENTERPRISE_ONLY_DOC_PATHS:
        data["plan_class"] = "enterprise_only"
        data["classification_confidence"] = "high"
    if entry.docs_path in MANUAL_CONNECTOR_OVERRIDES:
        data.update(MANUAL_CONNECTOR_OVERRIDES[entry.docs_path])
    return FivetranInventoryEntry(**data)


def fetch_catalog_inventory() -> list[FivetranInventoryEntry]:
    lite_paths = _collect_lite_docs_paths()
    entries: dict[str, FivetranInventoryEntry] = {}
    for page_path, family, source_type in CATALOG_PAGES:
        for docs_path, display_name in _collect_catalog_links(page_path, family).items():
            entry = _default_entry(
                docs_path=docs_path,
                display_name=display_name,
                family=family,
                source_type=source_type,
            )
            entries[docs_path] = _apply_entry_overrides(entry, lite_paths=lite_paths)
    return sorted(entries.values(), key=lambda item: item.docs_path)


def build_inventory_lock(entries: list[FivetranInventoryEntry]) -> dict[str, Any]:
    serialized = [entry.to_dict() for entry in entries]
    return {
        "generated_at": _utc_now_iso(),
        "inventory_version": _stable_hash(serialized),
        "entries": serialized,
    }


def _entry_score(entry: FivetranInventoryEntry) -> int:
    score = entry.score_bonus
    if entry.family == "application":
        score += 5
    else:
        score += 4
    if entry.schema_complexity == "high":
        score += 4
    elif entry.schema_complexity == "medium":
        score += 2
    if entry.join_complexity == "high":
        score += 3
    elif entry.join_complexity == "medium":
        score += 1
    if entry.nested_json:
        score += 2
    if entry.wide_table:
        score += 2
    if entry.high_churn_rest:
        score += 2
    if entry.append_only_event:
        score += 2
    return score


def eligible_wave_one_entries(
    entries: list[FivetranInventoryEntry],
) -> list[FivetranInventoryEntry]:
    return [
        entry
        for entry in entries
        if entry.release_class == "ga"
        and entry.plan_class == "standard"
        and entry.classification_confidence == "high"
    ]


def build_selection_lock(
    entries: list[FivetranInventoryEntry], inventory_version: str
) -> dict[str, Any]:
    eligible = eligible_wave_one_entries(entries)
    selected: list[FivetranSelectionEntry] = []
    for bucket, required_count in SELECTION_BUCKET_QUOTAS.items():
        bucket_entries = [entry for entry in eligible if entry.selection_bucket == bucket]
        bucket_entries.sort(
            key=lambda entry: (-_entry_score(entry), entry.display_name.lower(), entry.docs_path),
        )
        if len(bucket_entries) < required_count:
            raise InventoryRefreshError(
                f"Wave 1 selection bucket {bucket} requires {required_count} entries, "
                f"but only {len(bucket_entries)} eligible connectors were available."
            )
        for entry in bucket_entries[:required_count]:
            selected.append(
                FivetranSelectionEntry(
                    connector_slug=entry.connector_slug,
                    display_name=entry.display_name,
                    docs_path=entry.docs_path,
                    family=entry.family,
                    selection_bucket=bucket,
                    source_type=entry.source_type,
                    score=_entry_score(entry),
                    release_class=entry.release_class,
                    plan_class=entry.plan_class,
                    classification_confidence=entry.classification_confidence,
                    schema_complexity=entry.schema_complexity,
                    join_complexity=entry.join_complexity,
                    nested_json=entry.nested_json,
                    wide_table=entry.wide_table,
                    high_churn_rest=entry.high_churn_rest,
                    append_only_event=entry.append_only_event,
                )
            )
    if len(selected) != sum(SELECTION_BUCKET_QUOTAS.values()):
        raise InventoryRefreshError("Wave 1 selection did not produce the expected top-20 size.")
    for attribute, required_count in DIVERSITY_CONSTRAINTS.items():
        actual_count = sum(1 for entry in selected if getattr(entry, attribute))
        if actual_count < required_count:
            raise InventoryRefreshError(
                f"Wave 1 selection requires at least {required_count} connectors with {attribute}, "
                f"but only {actual_count} were selected."
            )
    serialized = [entry.to_dict() for entry in selected]
    return {
        "generated_at": _utc_now_iso(),
        "inventory_version": inventory_version,
        "selection_version": _stable_hash(
            {
                "inventory_version": inventory_version,
                "quotas": SELECTION_BUCKET_QUOTAS,
                "diversity_constraints": DIVERSITY_CONSTRAINTS,
                "selected": serialized,
            }
        ),
        "quotas": dict(SELECTION_BUCKET_QUOTAS),
        "diversity_constraints": dict(DIVERSITY_CONSTRAINTS),
        "selected_connectors": serialized,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_inventory_lock_payload(payload: dict[str, Any]) -> None:
    expected_hash = _stable_hash(payload.get("entries", []))
    actual_hash = str(payload.get("inventory_version", "")).strip()
    if actual_hash != expected_hash:
        raise InventoryRefreshError(
            f"Inventory lock hash mismatch: expected {expected_hash}, found {actual_hash or '<missing>'}."
        )


def validate_selection_lock_payload(
    payload: dict[str, Any],
    *,
    inventory_version: str | None = None,
) -> None:
    if inventory_version is not None and payload.get("inventory_version") != inventory_version:
        raise InventoryRefreshError(
            "Selection lock inventory_version does not match the active inventory lock."
        )
    expected_hash = _stable_hash(
        {
            "inventory_version": payload.get("inventory_version"),
            "quotas": payload.get("quotas", {}),
            "diversity_constraints": payload.get("diversity_constraints", {}),
            "selected": payload.get("selected_connectors", []),
        }
    )
    actual_hash = str(payload.get("selection_version", "")).strip()
    if actual_hash != expected_hash:
        raise InventoryRefreshError(
            f"Selection lock hash mismatch: expected {expected_hash}, found {actual_hash or '<missing>'}."
        )


def refresh_inventory_and_selection_locks() -> tuple[dict[str, Any], dict[str, Any]]:
    inventory_entries = fetch_catalog_inventory()
    inventory_lock = build_inventory_lock(inventory_entries)
    selection_lock = build_selection_lock(
        inventory_entries,
        inventory_version=inventory_lock["inventory_version"],
    )
    _write_json(INVENTORY_LOCK_PATH, inventory_lock)
    _write_json(SELECTION_LOCK_PATH, selection_lock)
    return inventory_lock, selection_lock


def ensure_inventory_and_selection_locks_are_consistent() -> tuple[dict[str, Any], dict[str, Any]]:
    inventory_lock = load_json(INVENTORY_LOCK_PATH)
    selection_lock = load_json(SELECTION_LOCK_PATH)
    validate_inventory_lock_payload(inventory_lock)
    validate_selection_lock_payload(
        selection_lock,
        inventory_version=str(inventory_lock["inventory_version"]),
    )
    return inventory_lock, selection_lock
