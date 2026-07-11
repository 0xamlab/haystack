---
icon: microsoft
description: Turn enterprise data and operating models into governed decisions across Microsoft 365, powered by a decision runtime in your own Azure subscription
---

# Algenta for Microsoft Cloud

Algenta turns your enterprise data and operating models into **governed decisions** that employees can frame and act on directly inside Microsoft 365 — in Copilot, Teams, and Excel — while the decisions themselves are computed by a decision runtime deployed in your organization's own Azure subscription.

The split is deliberate. Microsoft 365 is where people already work, so that is where a decision is framed, explained, and acted upon. But the logic that turns assumptions into a recommendation, the evidence behind it, and the data it reads should sit under your control. Algenta gives you **one stable Decision API** deployed to your Azure, and then many Microsoft experiences on top of it — with no duplicated decision logic to keep in sync.

{% hint style="info" %}
**Where each part runs.** Microsoft 365 (Copilot, Teams, Office/Excel), Microsoft Graph, and Microsoft Entra are Microsoft-hosted services. The Algenta decision and data plane — the gateway, the decision runtime, and the artifact store — runs in **your** Azure subscription. Running in your subscription puts these components under your control; it does not by itself make them network-private. Employees sign in with their existing Microsoft Entra identity, and the gateway derives their organization, workspace, and role from identity mappings you provision, not from values the client application supplies.
{% endhint %}

## How it fits together

The customer-controlled Azure gateway is the trust foundation. Every Microsoft experience is a thin adapter that calls the same governed decision lifecycle running behind that gateway:

- **Copilot & Teams** frame a request in conversation, run the analysis, and cite the evidence — recommendations only. Approving or executing a plan is always a separate, explicitly credentialed human action, never something the agent does on its own.
- **Excel** lets a user select ranges as a decision's assumptions, preview exactly what will be sent, run the analysis in your Azure, and write results to **new** sheets without overwriting the source.
- **Entra SSO** means there are no separate Algenta credentials — employees authenticate with the Microsoft identity they already have, and admin consent is granted once at the tenant level.

Figures returned to any of these surfaces are **model-estimated under the stated assumptions**, with the supporting evidence available for inspection.

## Explore this section

<table data-view="cards">
<thead>
<tr>
<th></th>
<th></th>
<th></th>
</tr>
</thead>
<tbody>
<tr>
<td><strong><a href="copilot-teams.md">Decision Agent in Copilot &amp; Teams</a></strong></td>
<td>A declarative agent that frames, runs, and explains governed decisions in the tools employees already use.</td>
<td></td>
</tr>
<tr>
<td><strong><a href="excel.md">Excel Decision Add-in</a></strong></td>
<td>Turn selected ranges into a decision's assumptions and write results back into new sheets — with a preview before anything is sent.</td>
<td></td>
</tr>
<tr>
<td><strong><a href="entra-sso.md">Sign in with Microsoft Entra</a></strong></td>
<td>Employees use their existing Microsoft identity; you grant admin consent once and manage access centrally.</td>
<td></td>
</tr>
<tr>
<td><strong><a href="../azure/gateway.md">Deploy the decision gateway to your Azure</a></strong></td>
<td>The customer-controlled foundation every Microsoft experience calls — deployed into your own subscription.</td>
<td></td>
</tr>
<tr>
<td><strong><a href="../../concepts/decision-service.md">The governed decision lifecycle</a></strong></td>
<td>Understand how a decision is framed, run, recommended, and approved before you wire up a surface.</td>
<td></td>
</tr>
</tbody>
</table>

## Next steps

Start with the foundation, then add the experiences your employees will use:

1. [Deploy the decision gateway to your Azure](../azure/gateway.md) — stand up the decision plane in your own subscription.
2. [Sign in with Microsoft Entra](entra-sso.md) — register the app and grant admin consent so employees authenticate with their existing identity.
3. Add the surfaces: the [Decision Agent in Copilot & Teams](copilot-teams.md) and the [Excel Decision Add-in](excel.md).
4. If you are new to the model, read [the governed decision lifecycle](../../concepts/decision-service.md) first.