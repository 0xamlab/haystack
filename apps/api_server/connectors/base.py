"""Base connector class and registry."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from apps.api_server.services.data_coercion import coerce_scalar, is_identifier_field


class BaseConnector(ABC):
    """Base class for all data source connectors."""

    connector_type: str = "base"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @abstractmethod
    async def fetch_data(self) -> list[dict[str, Any]]:
        """Fetch raw data from the source. Returns list of records."""
        ...

    async def fetch_table(self) -> Any | None:
        """Optional fast path returning a columnar Arrow table."""
        return None

    @abstractmethod
    async def validate_connection(self) -> tuple[bool, str]:
        """Test connectivity. Returns (success, message)."""
        ...

    async def map_to_simulation(self, data: list[dict], domain: str = "") -> dict[str, Any]:
        """
        Map raw data to a simulation payload using field analysis.

        Analyzes field names and values to auto-detect:
        - Variable names and polarity (positive/negative)
        - Distribution types from value ranges
        - Objective function from field semantics

        Returns a dict ready to POST to /v1/simulate.
        """
        if not data:
            return {"variables": [], "objective_function": ""}

        field_names: list[str] = []
        seen_fields: set[str] = set()
        for row in data:
            for field_name in row.keys():
                if field_name not in seen_fields:
                    seen_fields.add(field_name)
                    field_names.append(field_name)

        variables: list[dict[str, Any]] = []
        positive_fields: list[str] = []
        negative_fields: list[str] = []

        # Keywords for polarity detection (mirrors field_mapper.mojo)
        pos_keywords = {
            "revenue", "profit", "income", "sales", "growth",
            "return", "gain", "value", "benefit", "savings", "yield",
        }
        neg_keywords = {
            "cost", "expense", "loss", "risk", "churn",
            "debt", "liability", "penalty", "fee", "overhead",
        }

        for field_name in field_names:
            if is_identifier_field(field_name):
                continue

            values: list[float] = []
            non_empty = 0
            integer_like = True
            distinct_numeric: set[float] = set()

            for row in data:
                raw_value = row.get(field_name)
                coerced = coerce_scalar(field_name, raw_value, preserve_identifiers=True)
                if coerced == "" or coerced is None:
                    continue
                non_empty += 1
                if isinstance(coerced, bool):
                    continue
                if isinstance(coerced, (int, float)):
                    fv = float(coerced)
                    values.append(fv)
                    distinct_numeric.add(fv)
                    integer_like = integer_like and float(fv).is_integer()

            if not values or non_empty == 0:
                continue
            if len(values) / non_empty < 0.6:
                continue
            if integer_like and len(values) >= 20 and len(distinct_numeric) / len(values) > 0.98:
                continue

            low = min(values)
            high = max(values)
            mean = sum(values) / len(values)

            # Detect distribution
            if low >= 0 and high <= 1:
                dist = "beta"
                params: dict[str, float] = {"alpha": 2.0, "beta": 2.0}
            elif low == high:
                dist = "fixed"
                params = {"value": mean}
            else:
                mid = (low + high) / 2
                dist = "triangular"
                params = {"low": low, "mode": mid, "high": high}

            variables.append({
                "name": field_name,
                "distribution": dist,
                "params": params,
            })

            # Polarity
            lower_name = field_name.lower()
            if any(kw in lower_name for kw in pos_keywords):
                positive_fields.append(field_name)
            elif any(kw in lower_name for kw in neg_keywords):
                negative_fields.append(field_name)
            else:
                positive_fields.append(field_name)

        # Build objective function
        if positive_fields and negative_fields:
            obj = " + ".join(positive_fields) + " - " + " - ".join(negative_fields)
        elif positive_fields:
            obj = " + ".join(positive_fields)
        else:
            obj = variables[0]["name"] if variables else ""

        return {
            "engine_type": "monte_carlo",
            "runs": 10000,
            "variables": variables,
            "objective_function": obj,
            "scoring": {"expected_value": 0.6, "downside_risk": 0.4},
            "_connector_metadata": {
                "source_type": self.connector_type,
                "records_analyzed": len(data),
                "fields_mapped": len(variables),
                "domain": domain,
            },
        }


class ConnectorRegistry:
    """Registry of available connector types."""

    _connectors: dict[str, type[BaseConnector]] = {}

    @classmethod
    def register(cls, connector_class: type[BaseConnector]) -> type[BaseConnector]:
        """Register a connector class by its connector_type."""
        cls._connectors[connector_class.connector_type] = connector_class
        return connector_class

    @classmethod
    def get(cls, connector_type: str) -> type[BaseConnector] | None:
        """Look up a connector class by type string."""
        return cls._connectors.get(connector_type)

    @classmethod
    def available_types(cls) -> list[str]:
        """Return list of registered connector type strings."""
        return list(cls._connectors.keys())

    @classmethod
    def create(cls, connector_type: str, config: dict[str, Any]) -> BaseConnector:
        """Instantiate a connector by type string and config dict."""
        connector_class = cls._connectors.get(connector_type)
        if not connector_class:
            raise ValueError(
                f"Unknown connector type: {connector_type}. "
                f"Available: {cls.available_types()}"
            )
        return connector_class(config)
