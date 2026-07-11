---
icon: file-excel
description: Run a governed Decision Pack from an Excel task pane over your own decision gateway — selection-only, preview-first, results to new sheets
---

# Excel Decision Add-in

The Excel Decision Add-in is a native task pane that turns a selected range into the assumptions for a governed Decision Pack, runs the analysis against **your** deployed decision gateway, and writes the results back into new worksheets. Analysts stay in the workbook they already trust; the compute happens in the customer-controlled Azure decision plane, not in the spreadsheet.

It is built for a single, auditable loop: sign in with Entra SSO, choose a range, see exactly what will be sent, run the analysis, review the results on fresh sheets, and — as a deliberate, separate action — approve the resulting plan.

{% hint style="info" %}
Your selection is sent only to the **Gateway URL** you deploy in your own Azure subscription — there is no Algenta-operated shared service in the path. Sign-in and the Office surface are handled by Microsoft, since Entra and Excel are Microsoft-hosted. See [Deploy the decision gateway to your Azure](../azure/gateway.md).
{% endhint %}

## Trust behavior, by design

These properties are enforced by the add-in itself, not by policy:

- **Selection-only.** Only the range you highlight is read. Formulas, hidden sheets, and unrelated ranges never leave the workbook — the add-in sends *formula results* for the selected cells and nothing else.
- **Preview before any call.** The pane shows a "data to be sent" summary — the range address, the cell count, and the number of accounts parsed — before a single byte is transmitted. No preview, no request.
- **Compute in your Azure.** The governed analysis runs in your organization's decision runtime behind your gateway. Excel and Entra are Microsoft-hosted; the decision compute runs in your customer-controlled Azure plane, which you operate and reach over the network like any other Azure workload.
- **Results write to new sheets, never overwrite.** Each run creates fresh worksheets — `Algenta Decision`, `Allocation Plan`, `Sensitivity`, and `Evidence` — with a unique suffix. Existing cells are left untouched.
- **Edit-and-rerun is a new artifact.** Change an assumption and run again and you get a new immutable analysis run and a new set of sheets. Nothing is silently mutated in place, so every run stays traceable.
- **Approval is a separate, explicit click.** Approving a recommendation is its own action that carries the plan hash and a single-use nonce issued for that run. Those values travel with the approval request — they are never read from, or written to, a worksheet cell.

## What the range should contain

Select a header row plus at least one data row. The add-in maps these columns (matched case-insensitively) for the [Renewal Capacity Allocation pack](../../guides/renewal-capacity-allocation.md):

| Column | Required | Meaning |
| --- | --- | --- |
| `account_id` | Yes | Stable account identifier |
| `name` | Yes | Account display name |
| `arr` | Yes | Annual recurring revenue |
| `renewal_date` | Yes | Upcoming renewal date |
| `health_score` | Optional | Account health signal |
| `segment` | Optional | Segment label (defaults to `standard`) |

## Admin setup

Setting up the add-in for your organization is a normal enterprise admin task. You host the add-in's files, register it with Entra, and distribute it through the tools your tenant already uses.

{% stepper %}
{% step %}
### Host the add-in over HTTPS

Publish the add-in package's static files (the task pane HTML/JS and its icon assets) to an HTTPS endpoint your users can reach. Set that host as the task pane source URL and icon URLs in the add-in manifest.
{% endstep %}

{% step %}
### Register Entra SSO

In the add-in manifest, set the SSO application id to the client id of your gateway's Entra app registration, and set the resource to `api://$GATEWAY_AUDIENCE` — the audience your gateway validates. Pre-authorize the Office client ids and grant admin consent for the `access_as_user` scope so the pane can obtain a token whose audience is your gateway API.
{% endstep %}

{% step %}
### Validate the manifest

Confirm the manifest is well-formed before distributing it:

```bash
npx office-addin-manifest validate ./manifest.xml
```
{% endstep %}

{% step %}
### Sideload or publish

Sideload the add-in for testing, or upload it to the Microsoft 365 admin center to deploy it to the organization.
{% endstep %}
{% endstepper %}

{% hint style="warning" %}
The gateway app registration audience in the manifest must match the audience your deployed gateway validates. If they differ, the pane will sign in but the gateway will reject the token.
{% endhint %}

## Run a decision from Excel

{% stepper %}
{% step %}
### Sign in

Open the task pane in Excel. When prompted, sign in with your Entra account. The pane requests a token scoped to your gateway API.
{% endstep %}

{% step %}
### Point at your gateway

Enter your deployed **Gateway URL** in the pane. This is the endpoint produced when you deployed the decision gateway to your Azure subscription.
{% endstep %}

{% step %}
### Select the range

Highlight the header row plus your account rows. Choose the Decision Pack and give the run a title.
{% endstep %}

{% step %}
### Preview what will be sent

Click **Preview**. The pane shows the range address, cell count, and account count — exactly what will be sent. Confirm it matches your intent before continuing.
{% endstep %}

{% step %}
### Run the governed analysis

Click **Run**. The pane opens a decision case, starts an analysis run, and polls until it completes. The compute happens behind your gateway, in your Azure decision plane.
{% endstep %}

{% step %}
### Review the new sheets

The add-in writes `Algenta Decision`, `Allocation Plan`, `Sensitivity`, and `Evidence` to new worksheets. Read them to understand the recommendation and its provenance — observed facts, your assumptions, estimated parameters, and simulated outcomes.
{% endstep %}

{% step %}
### Approve

If the recommendation is feasible, click **Approve** as a separate, explicit action. The approval carries the plan hash and single-use nonce for that run. An owner then publishes the approved plan with Execute.
{% endstep %}
{% endstepper %}

### Expected result

You will see four new worksheets appended to your workbook, each stamped with a unique suffix so nothing you had is overwritten:

- **Algenta Decision** — the recommended scenario, feasibility, and model version, along with a confidence expressed as the percentage of the defined scenario set in which the plan met its goal. All figures are model-estimated under your stated assumptions.
- **Allocation Plan** — the per-account allocation (hours, a model-estimated renewal outlook and retained-ARR estimate, and the reason for each).
- **Sensitivity** — the parameters the recommendation is most sensitive to.
- **Evidence** — the provenance behind the numbers.

The pane's status reads "Recommendation ready. Review the new sheets, then Approve." Change an assumption and run again and you get another immutable run and another set of sheets — the earlier analysis stays intact for the record.

{% hint style="info" %}
If no feasible solution exists, the add-in leaves Approve disabled and the `Algenta Decision` sheet names the binding constraint so you can adjust the inputs and rerun.
{% endhint %}

## Next steps

- [Deploy the decision gateway to your Azure](../azure/gateway.md)
- [Renewal Capacity Allocation pack](../../guides/renewal-capacity-allocation.md)
- [Decision Agent in Copilot & Teams](copilot-teams.md)