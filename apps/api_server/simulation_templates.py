"""
Universal Domain Template Library for Codna.

Templates cover any industry — no restrictions on domain, data type, or variable count.
Each template provides a ready-to-run simulation with realistic variable specifications
that users can customize for their specific context.

Usage:
  from apps.api_server.simulation_templates import TEMPLATES, get_template
  template = get_template("financial_npv")
  payload = template.to_simulate_payload(runs=50000)
"""

from __future__ import annotations

from .simulation_template_catalog_01 import register_catalog as _register_catalog_01
from .simulation_template_catalog_02 import register_catalog as _register_catalog_02
from .simulation_template_catalog_03 import register_catalog as _register_catalog_03
from .simulation_template_catalog_04 import register_catalog as _register_catalog_04
from .simulation_template_catalog_05 import register_catalog as _register_catalog_05
from .simulation_template_models import SimulationTemplate, TemplateVariable

TEMPLATES: dict[str, SimulationTemplate] = {}


def _register(template: SimulationTemplate) -> SimulationTemplate:
    TEMPLATES[template.id] = template
    return template


for _register_catalog in (
    _register_catalog_01,
    _register_catalog_02,
    _register_catalog_03,
    _register_catalog_04,
    _register_catalog_05,
):
    _register_catalog(_register)

del _register_catalog


def get_template(template_id: str) -> SimulationTemplate | None:
    return TEMPLATES.get(template_id)


def list_templates(
    domain: str | None = None,
    industry: str | None = None,
) -> list[dict[str, object]]:
    templates = list(TEMPLATES.values())
    if domain:
        templates = [
            template for template in templates if domain.lower() in template.domain.lower()
        ]
    if industry:
        templates = [
            template for template in templates if industry.lower() in template.industry.lower()
        ]
    return [template.to_dict() for template in templates]


def get_all_domains() -> list[str]:
    return sorted({template.domain for template in TEMPLATES.values()})


def get_all_tags() -> list[str]:
    tags: set[str] = set()
    for template in TEMPLATES.values():
        tags.update(template.tags)
    return sorted(tags)


__all__ = [
    "SimulationTemplate",
    "TemplateVariable",
    "TEMPLATES",
    "get_template",
    "list_templates",
    "get_all_domains",
    "get_all_tags",
]
