"""
Multi-hop public-client flow example.

This module demonstrates the Cloud Managed public-client path by default. In
`self_hosted` and `air_gapped`, keep `ALGENTA_API_KEY` / `DE_API_KEY`
pointed at the API key provisioned by your self-hosted operator deployment and
configure an explicit self-hosted `ALGENTA_BASE_URL` / `DE_BASE_URL` / `ALGENTA_API_URL`
instead. Private profiles fail closed and do not silently fall back to Algenta cloud.
"""

from __future__ import annotations

from decision_engine import AlgentaClient
from examples.shared.privacy_profile import resolve_example_api_base_url, resolve_example_api_key


def _client() -> AlgentaClient:
    return AlgentaClient(
        api_key=resolve_example_api_key(
            component="Multi-hop Python public client example",
        ),
        base_url=resolve_example_api_base_url(
            component="Multi-hop Python public client example",
        ),
    )


def main() -> None:
    client = _client()

    # Mission ensure_governed_dataset -> public connect_data()
    connected = client.connect_data(
        {
            "connection_type": "database",
            "provider": "postgres",
            "dataset_name": "NpsScoresDataset",
            "connection_name": "Analytics Warehouse",
            "connection_config": {
                "host": "db.example.internal",
                "port": 5432,
                "database": "analytics",
                "user": "analytics_reader",
                "password": "replace_me",
            },
            "selection": {"table": "public.nps_scores"},
            "visibility": "private",
        }
    )
    print("connect_data status:", connected.status)

    # Mission list_data -> public list_datasets()
    datasets = client.list_datasets(search="nps_scores", compact=True)
    if not datasets.datasets:
        raise RuntimeError("No governed datasets matched 'nps_scores'.")

    dataset_id = datasets.datasets[0].dataset_id

    # Mission get_data_schema -> public get_dataset_summary()
    summary = client.get_dataset_summary(dataset_id)
    print("dataset summary:", summary.dataset_id, summary.name)

    # Mission query_data on a bridge-table metric -> public query_with_metadata()
    exact_result = client.query_with_metadata(
        {
            "source_name": "nps_scores",
            "metric_column": "nps_score",
            "group_column": "origin_airport_code",
            "aggregation": "avg",
            "limit": 10,
            "order": "asc",
            "join_path": {
                "base_source": "nps_scores",
                "group_source": "airports",
                "edges": [
                    {
                        "left_source": "nps_scores",
                        "right_source": "delay_assignments",
                        "left_key": "flight_id",
                        "right_key": "flight_id",
                        "expected_cardinality": "many_to_one",
                        "allow_many_to_many": False,
                    },
                    {
                        "left_source": "delay_assignments",
                        "right_source": "flights",
                        "left_key": "flight_id",
                        "right_key": "id",
                        "expected_cardinality": "many_to_one",
                        "allow_many_to_many": False,
                    },
                    {
                        "left_source": "flights",
                        "right_source": "airports",
                        "left_key": "origin_airport_id",
                        "right_key": "id",
                        "expected_cardinality": "many_to_one",
                        "allow_many_to_many": False,
                    },
                ],
                "max_hops": 4,
                "min_path_confidence": 0.7,
                "reject_on_ambiguity": True,
                "reject_on_fanout": True,
            },
        }
    )
    print("exact multihop result:", exact_result.result)

    # Mission query_data_batch -> public query_batch()
    batch = client.query_batch(
        {
            "queries": [
                {
                    "key": "lowest_nps_routes",
                    "request": {
                        "source_name": "nps_scores",
                        "metric_column": "nps_score",
                        "group_column": "route_code",
                        "aggregation": "avg",
                        "limit": 10,
                        "order": "asc",
                    },
                },
                {
                    "key": "lowest_nps_airports",
                    "request": {
                        "source_name": "nps_scores",
                        "metric_column": "nps_score",
                        "group_column": "origin_airport_code",
                        "aggregation": "avg",
                        "limit": 10,
                        "order": "asc",
                    },
                },
            ]
        }
    )
    print("batch keys:", [item.key for item in batch.results])

    # Mission query_sql_source / query_sql_report -> public query_sql_report()
    report = client.query_sql_report(
        {
            "sources": [
                {"dataset_id": "dataset_nps_scores", "alias": "nps"},
                {"dataset_id": "dataset_delay_assignments", "alias": "delay"},
                {"dataset_id": "dataset_flights", "alias": "flights"},
            ],
            "sql": (
                "select corr(delay.dep_delay_minutes, nps.nps_score) as delay_nps_correlation, "
                "count(*) as joined_non_null_rows "
                "from nps "
                "join delay on delay.flight_id = nps.flight_id "
                "join flights on flights.id = delay.flight_id "
                "where delay.dep_delay_minutes is not null and nps.nps_score is not null"
            ),
            "max_rows": 10,
        }
    )
    print("sql report rows:", report.row_count)


if __name__ == "__main__":
    main()
