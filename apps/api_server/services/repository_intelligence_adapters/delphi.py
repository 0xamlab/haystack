from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    pascal as pascal_adapter,
)

StableIdentifier = Callable[[str, Any], str]

DELPHI_NAMESPACE_RE = re.compile(
    r"\b(?:Vcl|FMX|FireDAC|Winapi|Data\.(?:DB|SqlExpr|Snap|DBX)|Soap|Xml)\.",
    re.IGNORECASE,
)
DELPHI_MODE_RE = re.compile(r"\{\$\s*mode\s+objfpc\b", re.IGNORECASE)
DELPHI_PROJECT_RE = re.compile(
    r"<(?:BorlandProject|Project)\b|<MainSource>|<DCC_UnitSearchPath>|"
    r"<Delphi\.Personality>|<ProjectGuid>",
    re.IGNORECASE,
)
DELPHI_RESOURCE_RE = re.compile(
    r"\{\$\s*R\s+\*\.(?:dfm|fmx|res)\s*\}",
    re.IGNORECASE,
)


def is_probable_delphi_source(*, path: Path, text: str) -> bool:
    suffix = path.suffix.lower()
    if suffix == ".dproj":
        return bool(DELPHI_PROJECT_RE.search(text))
    if suffix in {".dfm", ".fmx"}:
        return bool(
            re.search(
                r"^\s*(?:object|inherited)\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*[A-Za-z_][A-Za-z0-9_]*",
                text,
                flags=re.IGNORECASE | re.MULTILINE,
            )
        )
    if suffix in {".dpr", ".dpk"}:
        if DELPHI_MODE_RE.search(text):
            return False
        return bool(
            re.search(
                r"^\s*(?:program|library|package)\s+[A-Za-z_][A-Za-z0-9_\.]*\s*;",
                text,
                flags=re.IGNORECASE | re.MULTILINE,
            )
        )
    if suffix != ".pas":
        return False
    if DELPHI_MODE_RE.search(text):
        return False
    if DELPHI_RESOURCE_RE.search(text):
        return True
    return bool(DELPHI_NAMESPACE_RE.search(text))


def has_delphi_path_hints(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in {".dpr", ".dpk", ".dfm", ".fmx"}:
        return True
    if suffix == ".pas":
        lowered_stem = path.stem.lower()
        return lowered_stem.endswith(("form", "frame", "datamodule"))
    return False


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    suffix = PurePosixPath(file_path).suffix.lower()
    if suffix in {".dfm", ".fmx"}:
        path = PurePosixPath(file_path)
        without_suffix_path = str(path.with_suffix("")).lower()
        aliases = {
            file_path.lower(),
            path.stem.lower(),
            without_suffix_path,
            without_suffix_path.replace("/", "."),
        }
        return {alias for alias in aliases if alias and alias not in {".", "/"}}
    return pascal_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    suffix = PurePosixPath(file_path).suffix.lower()
    if suffix in {".dfm", ".fmx", ".dproj"}:
        return []
    return pascal_adapter.collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )


normalize_target = pascal_adapter.normalize_target
normalize_symbol_name = pascal_adapter.normalize_symbol_name
strip_comments = pascal_adapter.strip_comments
unit_name = pascal_adapter.unit_name
uses_targets = pascal_adapter.uses_targets
