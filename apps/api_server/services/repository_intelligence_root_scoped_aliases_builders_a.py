# ruff: noqa: I001
from __future__ import annotations
import re
from pathlib import Path
from apps.api_server.services.repository_intelligence_shared import _stable_identifier
from apps.api_server.services.repository_intelligence_indexing import (
    _normalize_repository_relative_path,
)
from apps.api_server.services.repository_intelligence_root_scoped_aliases import (
    abap_adapter,
    abapcds_adapter,
    ada_adapter,
    agda_adapter,
    aiken_adapter,
    alloy_adapter,
    answer_set_programming_adapter,
    apex_adapter,
    asciidoc_adapter,
    asl_adapter,
    aspnet_adapter,
    astro_adapter,
    ats_adapter,
    autohotkey_adapter,
    autoit_adapter,
    awk_adapter,
    batchfile_adapter,
    cairo_adapter,
    cfml_adapter,
    cmake_adapter,
    coffeescript_adapter,
    cuda_adapter,
    cython_adapter,
    d_language_adapter,
    dockerfile_adapter,
    emacslisp_adapter,
    fennel_adapter,
    fish_adapter,
    fortran_adapter,
    four_d_adapter,
    fsharp_adapter,
    gams_adapter,
    gleam_adapter,
    graphql_adapter,
    hlsl_adapter,
    hy_adapter,
    idris_adapter,
    julia_adapter,
    just_adapter,
    lisp_adapter,
    lua_adapter,
    luau_adapter,
    makefile_adapter,
    meson_adapter,
    modelica_adapter,
    mql5_adapter,
    nim_adapter,
    nix_adapter,
    nushell_adapter,
    odin_adapter,
    onec_enterprise_adapter,
    opencl_adapter,
    openscad_adapter,
    org_adapter,
    pkl_adapter,
    protobuf_adapter,
    puppet_adapter,
    purescript_adapter,
    qmake_adapter,
    qml_adapter,
    qsharp_adapter,
    r_language_adapter,
    racket_adapter,
    raku_adapter,
    reasonml_adapter,
    rescript_adapter,
    roc_adapter,
    rst_adapter,
    sass_adapter,
    scheme_adapter,
    shaderlab_adapter,
    squirrel_adapter,
    stan_adapter,
    svelte_adapter,
    sway_adapter,
    tex_adapter,
    typst_adapter,
    vala_adapter,
    vue_adapter,
    vyper_adapter,
    wgsl_adapter,
    wren_adapter,
)
def _nim_declared_symbol_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return nim_adapter.declared_symbol_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
    )
def _camelize_identifier(value: str) -> str:
    normalized_value = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    if not normalized_value:
        return ""
    return "".join(piece.capitalize() for piece in normalized_value.split("_") if piece)
def _r_package_context_for_path(
    *,
    root_path: Path,
    file_path: str,
) -> tuple[str | None, str | None]:
    return r_language_adapter.package_context_for_path(
        root_path=root_path,
        file_path=file_path,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )
def _julia_package_context_for_path(
    *,
    root_path: Path,
    file_path: str,
) -> tuple[str | None, str | None]:
    return julia_adapter.package_context_for_path(
        root_path=root_path,
        file_path=file_path,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )
def _r_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return r_language_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )
def _julia_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return julia_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )

def _lisp_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return lisp_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _puppet_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return puppet_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _emacslisp_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return emacslisp_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _fish_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return fish_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _racket_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return racket_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _scheme_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return scheme_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )


def _lua_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return lua_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path)


def _luau_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return luau_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path)


def _normalize_fortran_name(raw_name: str) -> str:
    return fortran_adapter.normalize_name(raw_name)


def _normalize_ada_unit_name(raw_name: str) -> str:
    return ada_adapter.normalize_unit_name(raw_name)


def _strip_ada_comments(text: str) -> str:
    return ada_adapter.strip_comments(text)


def _collect_ada_symbol_entries(
    text: str,
    *,
    file_path: str,
) -> list[dict[str, Any]]:
    return ada_adapter.collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _normalize_d_module_name(raw_name: str) -> str:
    return d_language_adapter.normalize_module_name(raw_name)


def _strip_d_comments(text: str) -> str:
    return d_language_adapter.strip_comments(text)


def _d_statement_entries(text: str) -> tuple[tuple[int, str], ...]:
    return d_language_adapter.statement_entries(text)


def _collect_d_symbol_entries(
    text: str,
    *,
    file_path: str,
) -> list[dict[str, Any]]:
    return d_language_adapter.collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _is_fortran_declared_symbol_alias(value: str) -> bool:
    return fortran_adapter.is_declared_symbol_alias(value)


def _fortran_statement_entries(text: str) -> tuple[tuple[int, str], ...]:
    return fortran_adapter.statement_entries(text)


def _collect_fortran_symbol_entries(
    text: str,
    *,
    file_path: str,
) -> list[dict[str, Any]]:
    return fortran_adapter.collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _collect_fsharp_symbol_entries(
    text: str,
    *,
    file_path: str,
) -> list[dict[str, Any]]:
    return fsharp_adapter.collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _fsharp_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return fsharp_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        # F# resolves qualified member references (e.g. `RequestOps.render`) and the
        # corresponding references_symbol graph edges through the module index, so the
        # index must carry the module-member / symbol aliases. Skipping them drops the
        # `references`/`references_symbol` edges the snapshot graph relies on.
        include_symbol_aliases=True,
    )


def _abap_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return abap_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _abapcds_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    if not abapcds_adapter.has_abapcds_path_hints(Path(file_path)):
        return set()
    return abapcds_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _onec_enterprise_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    if not onec_enterprise_adapter.has_onec_enterprise_path_hints(Path(file_path)):
        return set()
    return onec_enterprise_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _alloy_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    if not alloy_adapter.has_alloy_path_hints(Path(file_path)):
        return set()
    return alloy_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _aiken_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    if not aiken_adapter.has_aiken_path_hints(Path(file_path)):
        return set()
    return aiken_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _answer_set_programming_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
) -> set[str]:
    if not answer_set_programming_adapter.has_answer_set_programming_path_hints(
        Path(file_path)
    ):
        return set()
    return answer_set_programming_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _asl_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    if not asl_adapter.has_asl_path_hints(Path(file_path)):
        return set()
    return asl_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _ats_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    if not ats_adapter.has_ats_path_hints(Path(file_path)):
        return set()
    return ats_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _aspnet_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    if not aspnet_adapter.has_aspnet_path_hints(Path(file_path)):
        return set()
    return aspnet_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _ada_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return ada_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )
def _four_d_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return four_d_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )
def _apex_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return apex_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )
def _awk_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return awk_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _batchfile_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return batchfile_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _makefile_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return makefile_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _just_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return just_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _dockerfile_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return dockerfile_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _cython_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return cython_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )
def _cuda_module_aliases_for_path(*, root_path: Path, file_path: str, text: str | None = None) -> set[str]: return cuda_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier, text=text)  # noqa: E501
def _hlsl_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return hlsl_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _wgsl_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return wgsl_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _shaderlab_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return shaderlab_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
        include_shader_name_aliases=False,
    )
def _stan_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return stan_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _protobuf_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return protobuf_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )
def _tex_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return tex_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _rst_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return rst_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )
def _asciidoc_module_aliases_for_path(*, root_path: Path, file_path: str, text: str | None = None) -> set[str]: return asciidoc_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier, text=text)  # noqa: E501
def _org_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return org_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )
def _typst_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return typst_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )
def _cmake_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return cmake_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _meson_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return meson_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _qmake_module_aliases_for_path(*, root_path: Path, file_path: str, text: str | None = None) -> set[str]: return qmake_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier, text=text)  # noqa: E501
def _qml_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return qml_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )
def _vue_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return vue_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _astro_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return astro_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _svelte_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return svelte_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _odin_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return odin_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )
def _autohotkey_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return autohotkey_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )
def _autoit_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return autoit_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _squirrel_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return squirrel_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )
def _cfml_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return cfml_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )
def _coffeescript_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return coffeescript_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )


def _vala_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return vala_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _mql5_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return mql5_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _gams_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return gams_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _nix_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return nix_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _nushell_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return nushell_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )

def _openscad_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return openscad_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        # OpenSCAD resolves symbol references (references_symbol graph edges) through
        # the module index, which therefore must carry symbol-level aliases.
        include_symbol_aliases=True,
    )
def _purescript_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return purescript_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        include_symbol_aliases=False,
        text=text,
    )
def _cairo_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return cairo_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _reasonml_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return reasonml_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _rescript_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return rescript_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _sway_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return sway_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
_modelica_module_aliases_for_path = lambda *, root_path, file_path: modelica_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_roc_module_aliases_for_path = lambda *, root_path, file_path: roc_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
def _agda_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return agda_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )
def _idris_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return idris_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _raku_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return raku_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _gleam_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return gleam_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )
_hy_module_aliases_for_path = lambda *, root_path, file_path: hy_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_wren_module_aliases_for_path = lambda *, root_path, file_path: wren_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_fennel_module_aliases_for_path = lambda *, root_path, file_path: fennel_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
def _vyper_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return vyper_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )
_sass_module_aliases_for_path = lambda *, root_path, file_path: sass_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_qsharp_module_aliases_for_path = lambda *, root_path, file_path: qsharp_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
def _opencl_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return opencl_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )
_graphql_module_aliases_for_path = lambda *, root_path, file_path: graphql_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_pkl_module_aliases_for_path = lambda *, root_path, file_path: pkl_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
