---
sidebar_position: 6
---

# Zapier

Connect Algenta to 5,000+ apps via Zapier's no-code automation platform.

## Setup

1. In Zapier, create a **New Zap**
2. Set your trigger (e.g., "New row in Google Sheets")
3. Add a **Webhooks by Zapier** action:
   - **Method**: POST
   - **URL**: `https://api.algenta.ai/v1/simulate`
   - **Headers**: `Authorization: Bearer de_live_...`
   - **Data**: JSON body with your variables

4. Use the response fields in downstream actions

## Example Zap

**Trigger**: New form submission (Typeform)  
**Action 1**: Algenta simulate  
**Action 2**: Filter — only continue if `recommended_action = proceed`  
**Action 3**: Send Slack message with rationale

See [`examples/zapier/README.md`](https://github.com/decisionengine/decision-engine/tree/main/examples/zapier/README.md) for detailed setup steps.
