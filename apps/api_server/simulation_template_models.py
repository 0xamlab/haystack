from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TemplateVariable:
    name: str
    distribution: str
    params: dict[str, Any]
    unit: str = ""
    description: str = ""
    domain_hint: str = ""


@dataclass
class SimulationTemplate:
    id: str
    name: str
    domain: str
    industry: str
    description: str
    use_case: str
    variables: list[TemplateVariable]
    objective_function: str
    output_labels: list[str]
    output_units: list[str]
    scoring: dict[str, float]
    tags: list[str] = field(default_factory=list)

    def to_simulate_payload(
        self,
        runs: int = 50000,
        seed: int | None = None,
    ) -> dict[str, Any]:
        return {
            "mode": "expert",
            "simulation_model": "monte_carlo",
            "runs": runs,
            "seed": seed,
            "simulation": {
                "domain": self.domain,
                "domain_template": self.id,
                "variables": [
                    {
                        "name": variable.name,
                        "distribution": variable.distribution,
                        "params": variable.params,
                        "unit": variable.unit,
                        "description": variable.description,
                        "domain_hint": variable.domain_hint,
                    }
                    for variable in self.variables
                ],
                "objective_function": self.objective_function,
                "output_labels": self.output_labels,
                "output_units": self.output_units,
                "scoring": self.scoring,
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "domain": self.domain,
            "industry": self.industry,
            "description": self.description,
            "use_case": self.use_case,
            "objective_function": self.objective_function,
            "output_labels": self.output_labels,
            "output_units": self.output_units,
            "n_variables": len(self.variables),
            "tags": self.tags,
            "variables_preview": [
                {
                    "name": variable.name,
                    "distribution": variable.distribution,
                    "unit": variable.unit,
                }
                for variable in self.variables
            ],
        }


__all__ = ["SimulationTemplate", "TemplateVariable"]
