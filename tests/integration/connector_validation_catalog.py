from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

ValidationTier = Literal["public_no_auth", "credentialed_example", "customer_credentials_required"]
ValidationMode = Literal["register_and_exact_query", "connector_test_only"]


def _follow_data_path(data: Any, data_path: str) -> Any:
    current = data
    if not data_path:
        return current
    for key in data_path.split("."):
        if isinstance(current, dict):
            current = current.get(key, [])
        elif isinstance(current, list) and key.isdigit():
            index = int(key)
            current = current[index] if 0 <= index < len(current) else []
        else:
            return []
    return current


def _load_rest_records(connection: dict[str, Any]) -> list[dict[str, Any]]:
    method = str(connection.get("method", "GET")).upper()
    url = str(connection["url"])
    headers = dict(connection.get("headers", {}))
    params = dict(connection.get("params", {}))
    body = connection.get("body")
    timeout = float(connection.get("timeout", 60))
    data_path = str(connection.get("data_path", ""))

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        if method == "POST":
            response = client.post(url, headers=headers, params=params, json=body)
        else:
            response = client.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = _follow_data_path(response.json(), data_path)
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]
    raise ValueError(f"Expected list[dict] or dict from {url}, got {type(data).__name__}")


@dataclass(frozen=True)
class ConnectorValidationCase:
    case_id: str
    label: str
    ecosystem: str
    example_name: str
    connector_type: str
    tier: ValidationTier
    validation_mode: ValidationMode
    connection: dict[str, Any] = field(default_factory=dict)
    aggregation: str = "count"
    docs_url: str = ""
    enabled_by_default: bool = True
    notes: str = ""

    def build_connection(self) -> dict[str, Any]:
        return copy.deepcopy(self.connection)

    def load_expected_records(self) -> list[dict[str, Any]]:
        if self.connector_type != "rest_api":
            raise ValueError(f"Unsupported validation loader for {self.connector_type}")
        return _load_rest_records(self.build_connection())


THIRD_PARTY_PUBLIC_CASES: tuple[ConnectorValidationCase, ...] = (
    ConnectorValidationCase(
        case_id="fivetran_noaa_stations_co",
        label="Fivetran NOAA example source registration",
        ecosystem="fivetran",
        example_name="noaa",
        connector_type="rest_api",
        tier="public_no_auth",
        validation_mode="register_and_exact_query",
        connection={
            "type": "rest_api",
            "url": "https://api.weather.gov/stations",
            "headers": {
                "User-Agent": "decision-engine-go-live/1.0",
                "Accept": "application/geo+json",
            },
            "params": {"state": "CO"},
            "data_path": "features",
            "timeout": 60,
        },
        docs_url="https://fivetran.com/docs/connector-sdk/examples",
        notes="Public NOAA API used by the Fivetran Connector SDK example.",
    ),
    ConnectorValidationCase(
        case_id="fivetran_npi_registry_denver",
        label="Fivetran NPI Registry example source registration",
        ecosystem="fivetran",
        example_name="npi_registry",
        connector_type="rest_api",
        tier="public_no_auth",
        validation_mode="register_and_exact_query",
        connection={
            "type": "rest_api",
            "url": "https://npiregistry.cms.hhs.gov/api/",
            "params": {
                "version": "2.1",
                "limit": "20",
                "city": "Denver",
                "state": "CO",
            },
            "data_path": "results",
            "timeout": 60,
        },
        docs_url="https://fivetran.com/docs/connector-sdk/examples",
        notes="Public CMS NPI Registry API used by the Fivetran Connector SDK example.",
    ),
    ConnectorValidationCase(
        case_id="dlt_pokeapi_pokemon",
        label="dlt PokeAPI example source registration",
        ecosystem="dlt",
        example_name="pokemon",
        connector_type="rest_api",
        tier="public_no_auth",
        validation_mode="register_and_exact_query",
        connection={
            "type": "rest_api",
            "url": "https://pokeapi.co/api/v2/pokemon",
            "params": {"limit": "25"},
            "data_path": "results",
            "timeout": 60,
        },
        docs_url="https://dlthub.com/docs/tutorial/rest-api",
        notes="Public Pokemon example from the dlt REST API tutorial.",
    ),
    ConnectorValidationCase(
        case_id="dlt_github_issues",
        label="dlt GitHub issues example source registration",
        ecosystem="dlt",
        example_name="github_issues",
        connector_type="rest_api",
        tier="public_no_auth",
        validation_mode="register_and_exact_query",
        connection={
            "type": "rest_api",
            "url": "https://api.github.com/repos/dlt-hub/dlt/issues",
            "headers": {
                "Accept": "application/vnd.github+json",
                "User-Agent": "decision-engine-go-live/1.0",
            },
            "params": {
                "per_page": "25",
                "state": "open",
                "sort": "updated",
                "direction": "desc",
            },
            "timeout": 60,
        },
        docs_url="https://dlthub.com/docs/tutorial/rest-api",
        notes="Public GitHub issues example from the dlt REST API tutorial.",
    ),
)
