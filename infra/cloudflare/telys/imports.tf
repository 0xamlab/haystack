# ADOPTION of the pre-existing, dashboard-created telys.ai resources.
#
# Every resource below already exists in Cloudflare. These `import` blocks bind them to state at PLAN
# time, so `tofu plan` reports "will be imported" instead of "will be created". That distinction is the
# whole safety property of this file: without it, a first `apply` would try to CREATE a second
# api.telys.ai record (or a duplicate managed-ruleset deployment) alongside the live one.
#
# Resources deliberately absent here — they genuinely do not exist yet and are meant to be created:
#   cloudflare_ruleset.telys_ratelimit  (the rate-limit gap this PR closes; telys.ai had none)
#   cloudflare_ruleset.telys_cache      (telys.ai had no cache ruleset)
#
# Record/ruleset ids captured from the live zone on 2026-07-28. If a record is recreated in the
# dashboard before this is applied its id changes and the import fails loudly (which is the desired
# behaviour — it means live state moved and the plan must be re-reviewed, not force-applied).
# Re-read them with:
#   curl -H "Authorization: Bearer $CF_TOKEN" \
#     "https://api.cloudflare.com/client/v4/zones/$TELYS_ZONE_ID/dns_records?per_page=100"

import {
  to = cloudflare_record.api_v4
  id = "${var.telys_zone_id}/ea2a1e248f6b8dcceecf0a144258e92e"
}

import {
  to = cloudflare_record.api_v6
  id = "${var.telys_zone_id}/9e911f9a2ce0b4d94afa5e59b01b2f54"
}

import {
  to = cloudflare_record.packages
  id = "${var.telys_zone_id}/940229920a49c42cb1e4589643331a7b"
}

import {
  to = cloudflare_record.docs
  id = "${var.telys_zone_id}/972f044471abbf2f1f1a1f9c487d3a13"
}

# The zone's existing managed-ruleset deployment (dashboard-created, named "default").
# NOTE the import id shape for cloudflare_ruleset: the provider wants
# `<resourceLevel>/<resourceIdentifier>/<rulesetID>`, i.e. a literal "zone/" prefix — NOT the bare
# `<zone_id>/<ruleset_id>` that cloudflare_record uses. Getting this wrong fails the plan with
# "invalid import identifier".
import {
  to = cloudflare_ruleset.telys_waf_managed
  id = "zone/${var.telys_zone_id}/2c15e8fbc9644f76b7ce1c580a6e9b7f"
}

# ── NOTE: no zone-settings resource, deliberately ───────────────────────────────────────────────────
# An earlier draft of this module managed `cloudflare_zone_settings_override` to flip the zone to
# ssl=strict + min_tls_version=1.2. That was dropped for two independent reasons found while validating:
#
#   1. The provider does not implement import for it ("resource cloudflare_zone_settings_override
#      doesn't support import"), so it could only ever plan as "will be created" — meaning no prior
#      state is captured and a later `tofu destroy` would not restore the zone's original settings.
#   2. It is zone-wide, so it could not express "harden the API hostname" without also affecting the
#      marketing site and docs.
#
# Both are solved by scoping SSL through a Configuration Rule instead — see tls.tf. Net effect: this
# module now manages ZERO zone-level settings, so applying it makes no client-visible change at all.
