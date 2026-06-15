from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_aspnet_parser_dispatch as repository_aspnet_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    aspnet_analysis_support as repository_aspnet_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    aspnet_primitives as repository_aspnet_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_aspnet_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["asp.net"] is (
        repository_aspnet_parser_dispatch._parse_aspnet_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["asp.net"] is (
        repository_aspnet_parser_dispatch._parse_aspnet_dependencies_only
    )


def test_repository_intelligence_aspnet_helpers_are_modularized() -> None:
    assert repository_service.aspnet_adapter.strip_comments is (
        repository_aspnet_primitives.strip_comments
    )
    assert repository_service.aspnet_adapter.has_aspnet_path_hints is (
        repository_aspnet_primitives.has_aspnet_path_hints
    )
    assert repository_service.aspnet_adapter.iter_dependency_entries is (
        repository_aspnet_primitives.iter_dependency_entries
    )
    assert repository_service.aspnet_adapter.iter_reference_entries is (
        repository_aspnet_primitives.iter_reference_entries
    )
    assert repository_service.aspnet_adapter.iter_symbol_entries is (
        repository_aspnet_primitives.iter_symbol_entries
    )
    assert repository_service.aspnet_adapter.resolve_target is (
        repository_aspnet_primitives.resolve_target
    )
    assert repository_service.aspnet_adapter.is_probable_aspnet_source is (
        repository_aspnet_analysis_support.is_probable_aspnet_source
    )
    assert repository_service.aspnet_adapter.module_aliases_for_path is (
        repository_aspnet_analysis_support.module_aliases_for_path
    )
    assert repository_service.aspnet_adapter.parse_dependencies_only is (
        repository_aspnet_analysis_support.parse_dependencies_only
    )
    assert repository_service.aspnet_adapter.parse_file is (
        repository_aspnet_analysis_support.parse_file
    )


def test_aspnet_adapter_module_aliases_include_inherits_and_placeholders(tmp_path: Path) -> None:
    repo_path = tmp_path / "aspnet-alias-repo"
    (repo_path / "Controls").mkdir(parents=True)
    (repo_path / "Site.Master").write_text(
        '<%@ Master Language="C#" Inherits="Demo.SiteLayout" %>\n'
        '<asp:ContentPlaceHolder ID="MainContent" runat="server" />\n',
        encoding="utf-8",
    )

    aliases = repository_service.aspnet_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Site.Master",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Site.Master" in aliases
    assert "Site" in aliases
    assert "Demo.SiteLayout" in aliases
    assert "SiteLayout" in aliases
    assert "MainContent" in aliases


def test_aspnet_adapter_parse_file_resolves_master_controls_codebehind_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "aspnet-parse-repo"
    (repo_path / "Controls").mkdir(parents=True)
    (repo_path / "Pages").mkdir(parents=True)
    (repo_path / "Site.Master").write_text(
        '<%@ Master Language="C#" Inherits="Demo.SiteLayout" %>\n'
        '<asp:ContentPlaceHolder ID="MainContent" runat="server" />\n',
        encoding="utf-8",
    )
    (repo_path / "Controls" / "Nav.ascx").write_text(
        '<%@ Control Language="C#" Inherits="Demo.Controls.Nav" %>\n'
        '<asp:Panel ID="NavRoot" runat="server" />\n',
        encoding="utf-8",
    )
    (repo_path / "Pages" / "Default.aspx.cs").write_text(
        "namespace Demo.Pages { public partial class DefaultPage { } }\n",
        encoding="utf-8",
    )
    (repo_path / "Pages" / "Default.aspx").write_text(
        '<%@ Page Language="C#" MasterPageFile="~/Site.Master" '
        'CodeBehind="Default.aspx.cs" Inherits="Demo.Pages.DefaultPage" %>\n'
        '<%@ Register Src="~/Controls/Nav.ascx" TagPrefix="demo" TagName="Nav" %>\n'
        '<asp:Content ID="BodyContent" ContentPlaceHolderID="MainContent" runat="server">\n'
        "  <demo:Nav ID=\"Navigation\" runat=\"server\" />\n"
        "</asp:Content>\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        [
            "Site.Master",
            "Controls/Nav.ascx",
            "Pages/Default.aspx",
            "Pages/Default.aspx.cs",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "Pages" / "Default.aspx").read_text(encoding="utf-8")

    dependencies = repository_service.aspnet_adapter.parse_dependencies_only(
        "Pages/Default.aspx",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.aspnet_adapter.parse_file(
        "Pages/Default.aspx",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "Site.Master" and dependency.dependency_type == "uses_master_page"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "Controls/Nav.ascx"
        and dependency.dependency_type == "loads_registered_control"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "Pages/Default.aspx.cs"
        and dependency.dependency_type == "loads_codebehind"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "Demo.Pages.DefaultPage" for symbol in symbols)
    assert any(
        reference.target_file == "Controls/Nav.ascx" and reference.target_names == ("Nav",)
        for reference in references
    )
    assert any(
        reference.target_file == "Site.Master" and reference.target_names == ("MainContent",)
        for reference in references
    )
    assert any(reference.target_names == ("Demo.Pages.DefaultPage",) for reference in references)


def test_aspnet_language_detection_supports_web_forms_suffixes_without_overclaiming() -> None:
    assert ".aspx" in repository_service._TEXT_FILE_SUFFIXES
    assert ".master" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("Pages/Default.aspx"),
            text='<%@ Page Language="C#" Inherits="Demo.Pages.DefaultPage" %>\n',
        )
        == "asp.net"
    )
    assert (
        repository_service._language_for_path(
            Path("Site.Master"),
            text="<project><name>master-data</name></project>\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_aspnet_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "aspnet-profile-repo"
    (repo_path / "Controls").mkdir(parents=True)
    (repo_path / "Pages").mkdir(parents=True)
    (repo_path / "Site.Master").write_text(
        '<%@ Master Language="VB" Inherits="Demo.SiteLayout" %>\n'
        '<asp:ContentPlaceHolder ID="MainContent" runat="server" />\n',
        encoding="utf-8",
    )
    (repo_path / "Controls" / "Nav.ascx").write_text(
        '<%@ Control Language="VB" Inherits="Demo.Controls.Nav" %>\n'
        '<asp:Panel ID="NavRoot" runat="server" />\n',
        encoding="utf-8",
    )
    for index in range(5):
        (repo_path / "Pages" / f"Page{index}.aspx").write_text(
            '<%@ Page Language="VB" MasterPageFile="~/Site.Master" '
            f'CodeBehind="Page{index}.aspx.vb" Inherits="Demo.Pages.Page{index}" %>\n'
            '<%@ Register Src="~/Controls/Nav.ascx" TagPrefix="demo" TagName="Nav" %>\n'
            '<asp:Content ID="BodyContent" ContentPlaceHolderID="MainContent" runat="server">\n'
            "  <demo:Nav ID=\"Navigation\" runat=\"server\" />\n"
            "</asp:Content>\n",
            encoding="utf-8",
        )
        (repo_path / "Pages" / f"Page{index}.aspx.vb").write_text(
            f"Partial Class Page{index}\nEnd Class\n",
            encoding="utf-8",
        )
    for index in range(2):
        (repo_path / "Services" / f"Worker{index}.cs").parent.mkdir(parents=True, exist_ok=True)
        (repo_path / "Services" / f"Worker{index}.cs").write_text(
            "namespace Demo.Services { public class Worker { } }\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert any(_e == "asp.net" for _e in seed_plan["detected_ecosystems"])
    assert seed_plan["operational_ecosystems"][0] == "asp.net"
    assert "Pages/Page0.aspx" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_does_not_force_aspnet_first_in_host_dotnet_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "aspnet-mixed-host-repo"
    (repo_path / "Web").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Web" / "Site.Master").write_text(
        '<%@ Master Language="C#" Inherits="Demo.SiteLayout" %>\n'
        '<asp:ContentPlaceHolder ID="MainContent" runat="server" />\n',
        encoding="utf-8",
    )
    (repo_path / "Web" / "Default.aspx").write_text(
        '<%@ Page Language="C#" MasterPageFile="~/Web/Site.Master" '
        'CodeBehind="Default.aspx.cs" Inherits="Demo.Pages.DefaultPage" %>\n'
        '<asp:Content ID="BodyContent" ContentPlaceHolderID="MainContent" runat="server" />\n',
        encoding="utf-8",
    )
    (repo_path / "Web" / "Default.aspx.cs").write_text(
        "namespace Demo.Pages { public partial class DefaultPage { } }\n",
        encoding="utf-8",
    )
    for index in range(18):
        (repo_path / "src" / f"Service{index}.cs").write_text(
            f"namespace Demo.Services {{ public class Service{index} {{ }} }}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert any(_e == "asp.net" for _e in seed_plan["detected_ecosystems"])
    assert seed_plan["operational_ecosystems"][0] != "asp.net"
    assert "cs" in seed_plan["operational_ecosystems"]
