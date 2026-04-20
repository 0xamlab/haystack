---
sidebar_position: 5
---

# Power Automate

Use the Decision Engine custom connector in Microsoft Power Automate flows.

## Setup

1. Download the connector definition: [`examples/power-automate/connector_definition.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/power-automate/connector_definition.json)
2. In Power Automate, go to **Data → Custom Connectors → New custom connector → Import an OpenAPI file**
3. Upload the file and configure your API key
4. Add the **Decision Engine - Run Simulation** action to any flow

## Usage in a flow

1. Add trigger (e.g., "When a form is submitted")
2. Add **Decision Engine - Run Simulation** action
3. Map form fields to `revenue.low`, `revenue.high`, etc.
4. Add condition: if `recommended_action` = `proceed` → send approval email

Full connector spec: [`examples/power-automate/connector_definition.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/power-automate/connector_definition.json)
