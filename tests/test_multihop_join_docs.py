from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_multihop_docs_are_linked_from_primary_surfaces() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    query_doc = (ROOT / "apps" / "docs" / "docs" / "query.md").read_text(encoding="utf-8")
    api_reference = (
        ROOT / "apps" / "docs" / "docs" / "api-reference" / "index.md"
    ).read_text(encoding="utf-8")
    local_runtime = (
        ROOT / "apps" / "docs" / "docs" / "integrations" / "local-runtime.md"
    ).read_text(encoding="utf-8")
    guide = (
        ROOT / "apps" / "docs" / "docs" / "api-reference" / "multi-hop-joins.md"
    ).read_text(encoding="utf-8")
    examples_readme = (ROOT / "examples" / "multi-hop" / "README.md").read_text(
        encoding="utf-8"
    )
    mojo_status = json.loads(
        (
            ROOT / "examples" / "multi-hop" / "mission_mojo_llm_module_status.json"
        ).read_text(encoding="utf-8")
    )
    mcp_exact_sequence = json.loads(
        (
            ROOT / "examples" / "multi-hop" / "mcp_governed_exact_sequence.json"
        ).read_text(encoding="utf-8")
    )
    mcp_sql_sequence = json.loads(
        (
            ROOT / "examples" / "multi-hop" / "mcp_governed_sql_report_sequence.json"
        ).read_text(encoding="utf-8")
    )
    mcp_runtime_sequence = json.loads(
        (
            ROOT / "examples" / "multi-hop" / "mcp_runtime_library_sequence.json"
        ).read_text(encoding="utf-8")
    )
    mission_surface_map = json.loads(
        (
            ROOT / "examples" / "multi-hop" / "mission_functionality_surface_map.json"
        ).read_text(encoding="utf-8")
    )
    capability_plane_doc = (
        ROOT / "apps" / "docs" / "docs" / "api-reference" / "capability-plane.md"
    ).read_text(encoding="utf-8")

    assert "./apps/docs/docs/api-reference/multi-hop-joins.md" in readme
    assert "./examples/multi-hop/README.md" in readme
    assert "./examples/capability-plane/README.md" in readme
    assert "/api-reference/multi-hop-joins" in query_doc
    assert "/api-reference/multi-hop-joins" in api_reference
    assert "/api-reference/capability-plane" in api_reference
    assert "/v1/capabilities/route" in capability_plane_doc
    assert "/v1/capabilities/execute" in capability_plane_doc
    assert "examples/capability-plane/README.md" in capability_plane_doc
    assert "examples/langgraph/capability_router.py" in capability_plane_doc
    assert "Cloud Managed defaults" in guide
    assert "`self_hosted`" in guide
    assert "`base_url` / `baseUrl`" in guide
    assert "self-hosted operator" in guide
    assert 'ALGENTA_API_KEY="${ALGENTA_API_KEY:-${DE_API_KEY:-}}"' in guide
    assert 'ALGENTA_BASE_URL="${ALGENTA_BASE_URL:-${DE_BASE_URL:-${ALGENTA_API_URL:-https://api.algenta.ai}}}"' in guide
    assert 'api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")' in guide
    assert 'raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")' in guide
    assert "de_live_YOUR_KEY" not in guide
    assert "join_path" in guide
    assert "6` hops (`7` tables)" in guide
    assert "de data query-batch" in guide
    assert "query_sql_report" in guide
    assert "Mission functionality mapping" in guide
    assert "No one-to-one public endpoint today" in guide
    assert "POST /v1/data/connect" in guide
    assert "GET /v1/data/{dataset_id}/summary" in guide
    assert "POST /v1/query/batch" in guide
    assert "POST /v1/query/sql-report" in guide
    assert "MCP tool" in guide
    assert "list_data(search=..., compact=true)" in guide
    assert "connect_data(...)" in guide
    assert "query_batch(...)" in guide
    assert "No one-to-one MCP tool today." in guide
    assert "query_sql_source" in guide
    assert "register_sql_source" in guide
    assert "get_sources_graph" in guide
    assert "map_data_sources" in guide
    assert "Local Runtime" in guide
    assert "Mission Mojo LLM modules: current status" in guide
    assert "Mission declares `22` Mojo LLM modules" in guide
    assert "`19` of those modules" in guide
    assert "`vector_kernels.ranker` appears in lower-level source-ranking helpers" in guide
    assert "`rerank_eval` and `inference_cost_latency` are cataloged" in guide
    assert "python_runtime_library_flow.py" in guide
    assert "typescript_runtime_library_flow.ts" in guide
    assert "data_connect_request.json" in examples_readme
    assert "query_request.json" in examples_readme
    assert "query_batch_request.json" in examples_readme
    assert "sql_report_request.json" in examples_readme
    assert "sql_report_correlation_request.json" in examples_readme
    assert "mcp_governed_exact_sequence.json" in guide
    assert "mcp_governed_sql_report_sequence.json" in guide
    assert "mission_functionality_surface_map.json" in guide
    assert "mission_mojo_llm_module_status.json" in guide
    assert "mcp_governed_exact_sequence.json" in examples_readme
    assert "mcp_governed_sql_report_sequence.json" in examples_readme
    assert "mcp_runtime_library_sequence.json" in examples_readme
    assert "mission_functionality_surface_map.json" in examples_readme
    assert "mission_mojo_llm_module_status.json" in examples_readme
    assert 'ALGENTA_API_KEY="${ALGENTA_API_KEY:-${DE_API_KEY:-}}"' in examples_readme
    assert 'echo "Set ALGENTA_API_KEY or DE_API_KEY before running this example."' in examples_readme
    assert 'ALGENTA_BASE_URL="${ALGENTA_BASE_URL:-${DE_BASE_URL:-${ALGENTA_API_URL:-https://api.algenta.ai}}}"' in examples_readme
    assert 'curl -X POST "${ALGENTA_BASE_URL}/v1/data/connect"' in examples_readme
    assert 'Authorization: Bearer ${ALGENTA_API_KEY}' in examples_readme
    assert "python_public_client_flow.py" in guide
    assert "typescript_public_client_flow.ts" in guide
    assert "python_public_client_flow.py" in examples_readme
    assert "typescript_public_client_flow.ts" in examples_readme
    assert "python_runtime_library_flow.py" in examples_readme
    assert "typescript_runtime_library_flow.ts" in examples_readme
    assert "Mission Mojo LLM module note" in examples_readme
    assert "catalogs `22` Mojo LLM modules" in examples_readme
    assert "only `19` are covered" in examples_readme
    assert "one-to-one public hosted `query_sql_source` endpoint" in examples_readme
    assert "Do **not** look for a public `query_sql_source` route." in guide
    assert "Mission local library tool mapping" in local_runtime
    assert "get_algenta_library_health" in local_runtime
    assert "list_algenta_libraries" in local_runtime
    assert "inspect_algenta_library" in local_runtime
    assert "get_algenta_library_module" in local_runtime
    assert "execute_algenta_library" in local_runtime
    assert "python_runtime_library_flow.py" in local_runtime
    assert "typescript_runtime_library_flow.ts" in local_runtime
    assert "mcp_runtime_library_sequence.json" in local_runtime
    assert "mission_functionality_surface_map.json" in local_runtime
    assert "de runtime status" in local_runtime
    assert "MCP" in local_runtime
    assert "list_runtime_libraries(search=...)" in local_runtime
    assert 'list_runtime_libraries(search="text.tokenizer")' in local_runtime
    assert "execute_runtime_library(module=\"rerank_eval\"" in local_runtime
    assert 'catalog.module("text.tokenizer")' in local_runtime
    mcp_doc = (ROOT / "apps" / "docs" / "docs" / "mcp.md").read_text(encoding="utf-8")
    assert "Mission functionality mapping" in mcp_doc
    assert "query_sql_source" in mcp_doc
    assert "No one-to-one MCP tool today." in mcp_doc
    assert "get_sources_graph" in mcp_doc
    assert "map_data_sources" in mcp_doc
    assert "register_sql_source" in mcp_doc
    assert "get_algenta_library_health" in mcp_doc
    assert "mcp_governed_exact_sequence.json" in mcp_doc
    assert "mcp_governed_sql_report_sequence.json" in mcp_doc
    assert "mcp_runtime_library_sequence.json" in mcp_doc
    assert "mission_functionality_surface_map.json" in mcp_doc
    assert mojo_status["declared_module_count"] == 22
    assert mojo_status["conversation_harness_module_count"] == 19
    assert mojo_status["lower_level_only_module_count"] == 1
    assert mojo_status["catalog_only_module_count"] == 2
    assert mission_surface_map["functionality_count"] == 15
    assert mission_surface_map["category_counts"] == {
        "governed_data_and_query": 10,
        "local_runtime_libraries": 5,
    }
    assert mcp_exact_sequence["sequence_name"] == "mission_governed_exact_query_via_mcp"
    assert mcp_sql_sequence["sequence_name"] == "mission_multihop_statistical_sql_report_via_mcp"
    assert mcp_runtime_sequence["sequence_name"] == "mission_local_runtime_library_via_mcp"


def test_multihop_example_payloads_match_public_contract_limits() -> None:
    data_connect_request = json.loads(
        (ROOT / "examples" / "multi-hop" / "data_connect_request.json").read_text(
            encoding="utf-8"
        )
    )
    query_request = json.loads(
        (ROOT / "examples" / "multi-hop" / "query_request.json").read_text(encoding="utf-8")
    )
    query_batch_request = json.loads(
        (ROOT / "examples" / "multi-hop" / "query_batch_request.json").read_text(
            encoding="utf-8"
        )
    )
    sql_report_request = json.loads(
        (ROOT / "examples" / "multi-hop" / "sql_report_request.json").read_text(
            encoding="utf-8"
        )
    )
    sql_report_correlation_request = json.loads(
        (
            ROOT / "examples" / "multi-hop" / "sql_report_correlation_request.json"
        ).read_text(encoding="utf-8")
    )
    python_flow = (
        ROOT / "examples" / "multi-hop" / "python_public_client_flow.py"
    ).read_text(encoding="utf-8")
    typescript_flow = (
        ROOT / "examples" / "multi-hop" / "typescript_public_client_flow.ts"
    ).read_text(encoding="utf-8")
    python_runtime_flow = (
        ROOT / "examples" / "multi-hop" / "python_runtime_library_flow.py"
    ).read_text(encoding="utf-8")
    typescript_runtime_flow = (
        ROOT / "examples" / "multi-hop" / "typescript_runtime_library_flow.ts"
    ).read_text(encoding="utf-8")
    mojo_status = json.loads(
        (
            ROOT / "examples" / "multi-hop" / "mission_mojo_llm_module_status.json"
        ).read_text(encoding="utf-8")
    )
    mcp_exact_sequence = json.loads(
        (
            ROOT / "examples" / "multi-hop" / "mcp_governed_exact_sequence.json"
        ).read_text(encoding="utf-8")
    )
    mcp_sql_sequence = json.loads(
        (
            ROOT / "examples" / "multi-hop" / "mcp_governed_sql_report_sequence.json"
        ).read_text(encoding="utf-8")
    )
    mcp_runtime_sequence = json.loads(
        (
            ROOT / "examples" / "multi-hop" / "mcp_runtime_library_sequence.json"
        ).read_text(encoding="utf-8")
    )
    mission_surface_map = json.loads(
        (
            ROOT / "examples" / "multi-hop" / "mission_functionality_surface_map.json"
        ).read_text(encoding="utf-8")
    )

    assert data_connect_request["connection_type"] == "database"
    assert data_connect_request["provider"] == "postgres"
    assert data_connect_request["selection"]["table"] == "public.nps_scores"
    assert data_connect_request["visibility"] == "private"

    join_path = query_request["join_path"]
    assert query_request["source_name"] == join_path["base_source"]
    assert query_request["group_column"] == "category_name"
    assert len(join_path["edges"]) == 3
    assert join_path["max_hops"] == 4
    assert len(join_path["edges"]) <= join_path["max_hops"] <= 6
    assert join_path["reject_on_ambiguity"] is True
    assert join_path["reject_on_fanout"] is True

    queries = query_batch_request["queries"]
    assert len(queries) == 1
    assert queries[0]["request"]["join_path"] == join_path

    assert len(sql_report_request["sources"]) == 4
    assert sql_report_request["max_rows"] == 100
    assert "join" in sql_report_request["sql"].lower()

    assert len(sql_report_correlation_request["sources"]) == 3
    assert sql_report_correlation_request["max_rows"] == 10
    lowered_sql = sql_report_correlation_request["sql"].lower()
    assert "corr(" in lowered_sql
    assert "join delay on delay.flight_id = nps.flight_id" in lowered_sql
    assert "join flights on flights.id = delay.flight_id" in lowered_sql

    assert "client.connect_data(" in python_flow
    assert "client.list_datasets(search=\"nps_scores\", compact=True)" in python_flow
    assert "client.get_dataset_summary(dataset_id)" in python_flow
    assert "client.query_with_metadata(" in python_flow
    assert "client.query_batch(" in python_flow
    assert "client.query_sql_report(" in python_flow

    assert "await client.connectData(" in typescript_flow
    assert "resolveExampleApiKey({" in typescript_flow
    assert "await client.listDatasets({ search: \"nps_scores\", compact: true })" in typescript_flow
    assert "await client.getDatasetSummary(datasetId)" in typescript_flow
    assert "await client.queryWithMetadata(" in typescript_flow
    assert "await client.queryBatch(" in typescript_flow
    assert "await client.querySqlReport(" in typescript_flow

    assert "from algenta import MojoRuntime, libraries" in python_runtime_flow
    assert "runtime.health()" in python_runtime_flow
    assert "runtime.list_modules()" in python_runtime_flow
    assert 'runtime.list_functions("text.tokenizer")' in python_runtime_flow
    assert 'runtime.execute(\n        "rerank_eval",' in python_runtime_flow
    assert 'catalog.module("text.tokenizer")' in python_runtime_flow
    assert '.word_tokenize("delay correlation route")' in python_runtime_flow

    assert 'import { MojoRuntime, libraries } from "algenta-sdk";' in typescript_runtime_flow
    assert "await runtime.health()" in typescript_runtime_flow
    assert "await runtime.listModules()" in typescript_runtime_flow
    assert 'await runtime.listFunctions("text.tokenizer")' in typescript_runtime_flow
    assert 'await runtime.execute("rerank_eval", "precision_at_k"' in typescript_runtime_flow
    assert 'catalog.module("text.tokenizer")' in typescript_runtime_flow
    assert 'await textTokenizer.word_tokenize("delay correlation route")' in typescript_runtime_flow

    modules = mojo_status["modules"]
    assert len(modules) == 22
    by_name = {entry["module"]: entry for entry in modules}
    assert by_name["vector_kernels.ranker"]["mission_status"] == "lower_level_only"
    assert by_name["rerank_eval"]["mission_status"] == "catalog_only"
    assert by_name["inference_cost_latency"]["mission_status"] == "catalog_only"
    assert by_name["embeddings"]["mission_status"] == "conversation_harness"
    assert by_name["kv_cache"]["mission_status"] == "conversation_harness"
    assert all(entry["default_for_governed_multihop_sql"] is False for entry in modules)

    functionalities = mission_surface_map["functionalities"]
    assert len(functionalities) == 15
    by_functionality = {
        entry["mission_functionality"]: entry for entry in functionalities
    }
    assert (
        by_functionality["list_data"]["public_hosted_http"]["surface"]
        == "GET /v1/data?search=...&compact=1"
    )
    assert (
        by_functionality["ensure_governed_dataset"]["public_hosted_http"]["surface"]
        == "POST /v1/data/connect"
    )
    assert by_functionality["query_sql_source"]["public_hosted_http"]["supported"] is False
    assert (
        by_functionality["register_sql_source"]["public_hosted_http"]["supported"] is False
    )
    assert (
        by_functionality["get_algenta_library_health"]["python_sdk"]["surface"]
        == 'MojoRuntime(mode="local").health()'
    )
    assert by_functionality["list_data"]["mcp"]["surface"] == 'list_data(search="nps_scores", compact=true)'
    assert by_functionality["query_data"]["mcp"]["surface"] == "query_data(...)"
    assert by_functionality["query_data_batch"]["mcp"]["surface"] == "query_batch(...)"
    assert by_functionality["query_sql_report"]["mcp"]["surface"] == "query_sql_report(...)"
    assert by_functionality["query_sql_source"]["mcp"]["supported"] is False
    assert by_functionality["get_sources_graph"]["mcp"]["supported"] is False
    assert by_functionality["register_sql_source"]["mcp"]["supported"] is False
    assert (
        by_functionality["list_algenta_libraries"]["cli"]["surface"]
        == "de runtime modules --format json"
    )
    assert (
        by_functionality["list_algenta_libraries"]["mcp"]["surface"]
        == "list_runtime_libraries(search=...)"
    )
    assert (
        by_functionality["inspect_algenta_library"]["mcp"]["surface"]
        == 'list_runtime_libraries(search="text.tokenizer")'
    )
    assert by_functionality["get_algenta_library_health"]["mcp"]["supported"] is False
    assert (
        by_functionality["execute_algenta_library"]["public_hosted_http"]["supported"]
        is False
    )
    assert (
        by_functionality["execute_algenta_library"]["mcp"]["surface"]
        == 'execute_runtime_library(module="rerank_eval", function="precision_at_k", args={"relevance": [1, 0, 1, 1], "k": 3})'
    )
    assert all(
        entry["category"] in {"governed_data_and_query", "local_runtime_libraries"}
        for entry in functionalities
    )

    exact_steps = mcp_exact_sequence["steps"]
    assert [step["tool"] for step in exact_steps] == [
        "get_contract",
        "list_data",
        "get_data_summary",
        "query_data",
    ]
    assert exact_steps[-1]["arguments"]["metric"]["role"] == "ratio"
    assert exact_steps[-1]["arguments"]["group_by"] == ["route"]

    sql_steps = mcp_sql_sequence["steps"]
    assert sql_steps[-1]["tool"] == "query_sql_report"
    assert len(sql_steps[-1]["arguments"]["sources"]) == 3
    assert "corr(" in sql_steps[-1]["arguments"]["sql"].lower()
    assert "join delay on delay.flight_id = nps.flight_id" in sql_steps[-1]["arguments"][
        "sql"
    ].lower()

    runtime_steps = mcp_runtime_sequence["steps"]
    assert [step["tool"] for step in runtime_steps] == [
        "list_runtime_libraries",
        "execute_runtime_library",
        "execute_runtime_library",
    ]
    assert runtime_steps[0]["arguments"]["search"] == "text.tokenizer"
    assert runtime_steps[1]["arguments"]["module"] == "text.tokenizer"
    assert runtime_steps[2]["arguments"]["module"] == "rerank_eval"
