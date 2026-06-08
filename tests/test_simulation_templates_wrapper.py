from apps.api_server import simulation_templates


def test_simulation_templates_wrapper_preserves_public_catalog_contract() -> None:
    assert len(simulation_templates.TEMPLATES) == 51
    assert simulation_templates.get_template("finance_npv") is not None
    assert simulation_templates.get_template("nonexistent-template") is None

    finance_templates = simulation_templates.list_templates(domain="finance")
    assert finance_templates
    assert all("finance" in template["domain"].lower() for template in finance_templates)

    domains = simulation_templates.get_all_domains()
    tags = simulation_templates.get_all_tags()
    assert "finance" in domains
    assert "npv" in tags
