"""Tests for test_repository_intelligence_public_repo_matrix: default_public_c."""
from __future__ import annotations

from tests._test_repository_intelligence_public_repo_matrix_helpers import *  # noqa: F401,F403




def test_default_public_repository_cases_include_freemarker() -> None:
    freemarker_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "freemarker"
    )

    assert freemarker_case.repository_url == "https://github.com/lenve/CoolMeeting.git"
    assert freemarker_case.expected_primary_ecosystem == "freemarker"


def test_default_public_repository_cases_include_mako() -> None:
    mako_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "mako"
    )

    assert mako_case.repository_url == "https://github.com/sqlalchemy/mako.git"
    assert mako_case.expected_primary_ecosystem == "mako"
    assert mako_case.focus_paths == ("test/templates",)




def test_default_public_repository_cases_include_jsonnet() -> None:
    jsonnet_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "jsonnet"
    )

    assert jsonnet_case.repository_url == "https://github.com/jsonnet-libs/k8s-libsonnet.git"
    assert jsonnet_case.expected_primary_ecosystem == "jsonnet"



def test_default_public_repository_cases_include_apacheconf() -> None:
    apacheconf_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "apacheconf"
    )

    assert apacheconf_case.repository_url == "https://github.com/quangdung92/apache2-config.git"
    assert apacheconf_case.expected_primary_ecosystem == "apacheconf"


def test_default_public_repository_cases_include_aidl() -> None:
    aidl_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "aidl"
    )

    assert aidl_case.repository_url == "https://github.com/nexus-lab/relf-client-aidl.git"
    assert aidl_case.expected_primary_ecosystem == "aidl"


def test_default_public_repository_cases_include_abapcds() -> None:
    abapcds_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "abapcds"
    )

    assert (
        abapcds_case.repository_url
        == "https://github.com/SAP-samples/abap-platform-analytics-data-modeling.git"
    )
    assert abapcds_case.expected_primary_ecosystem == "abapcds"


def test_default_public_repository_cases_include_onec_enterprise() -> None:
    onec_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "1centerprise"
    )

    assert onec_case.repository_url == "https://github.com/oscript-library/opm.git"
    assert onec_case.expected_primary_ecosystem == "1centerprise"



def test_default_public_repository_cases_include_alloy() -> None:
    alloy_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "alloy"
    )

    assert alloy_case.repository_url == "https://github.com/AlloyTools/models.git"
    assert alloy_case.expected_primary_ecosystem == "alloy"


def test_default_public_repository_cases_include_aiken() -> None:
    aiken_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "aiken"
    )

    assert aiken_case.repository_url == "https://github.com/aiken-lang/stdlib.git"
    assert aiken_case.expected_primary_ecosystem == "aiken"


def test_default_public_repository_cases_include_answer_set_programming() -> None:
    asp_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "answer set programming"
    )

    assert asp_case.repository_url == "https://github.com/potassco/guide.git"
    assert asp_case.expected_primary_ecosystem == "answer set programming"
    assert asp_case.focus_paths == ("examples",)


def test_default_public_repository_cases_include_asl() -> None:
    asl_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "asl"
    )

    assert asl_case.repository_url == "https://github.com/jardenliu/XPS15-9560-Ventura.git"
    assert asl_case.expected_primary_ecosystem == "asl"
    assert asl_case.focus_paths == ("OC/ACPI/Origin",)


def test_default_public_repository_cases_include_ats() -> None:
    ats_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "ats"
    )

    assert ats_case.repository_url == "https://github.com/ats-lang/ATS-CodeBook.git"
    assert ats_case.expected_primary_ecosystem == "ats"


def test_default_public_repository_cases_include_aspnet() -> None:
    aspnet_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "asp.net"
    )

    assert (
        aspnet_case.repository_url
        == "https://github.com/nahidbinashraf/An-Online-Examination-System-Project.git"
    )
    assert aspnet_case.expected_primary_ecosystem == "asp.net"
    assert aspnet_case.focus_paths == ("onlinexamsystem",)


def test_default_public_repository_cases_include_angelscript() -> None:
    angelscript_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "angelscript"
    )

    assert angelscript_case.repository_url == "https://github.com/urho3d/Urho3D.git"
    assert angelscript_case.expected_primary_ecosystem == "angelscript"
    assert angelscript_case.focus_paths == ("bin/Data/Scripts",)


def test_default_public_repository_cases_include_apl() -> None:
    apl_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "apl"
    )

    assert apl_case.repository_url == "https://github.com/aplteam/Tatin.git"
    assert apl_case.expected_primary_ecosystem == "apl"
    assert apl_case.focus_paths == ("APLSource",)


def test_default_public_repository_cases_include_aspectj() -> None:
    aspectj_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "aspectj"
    )

    assert aspectj_case.repository_url == "https://github.com/astefanutti/metrics-aspectj.git"
    assert aspectj_case.expected_primary_ecosystem == "aspectj"
    assert aspectj_case.focus_paths == ("impl/src/main/aspect",)


def test_default_public_repository_cases_include_maven() -> None:
    maven_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "maven"
    )

    assert maven_case.repository_url == "https://github.com/apache/maven.git"
    assert maven_case.expected_primary_ecosystem == "maven"
    assert maven_case.focus_paths == ("pom.xml", ".mvn")





def test_default_public_repository_cases_include_clojure() -> None:
    clojure_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "clojure"
    )

    assert clojure_case.repository_url == "https://github.com/babashka/babashka.git"
    assert clojure_case.expected_primary_ecosystem == "clojure"



def test_default_public_repository_cases_include_foxpro() -> None:
    foxpro_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "foxpro"
    )

    assert foxpro_case.repository_url == "https://github.com/Irwin1985/FoxBarcode.git"
    assert foxpro_case.expected_primary_ecosystem == "foxpro"
