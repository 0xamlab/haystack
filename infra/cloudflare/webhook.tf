# ci-webhook.codna.ai -> the Azure ephemeral CI orchestrator (ci-orch, 172.190.6.38), fronted by
# Cloudflare so the GitHub `workflow_job` webhook receiver gets real TLS without provisioning a
# public CA cert directly on the VM. A Cloudflare Origin CA cert (not Let's Encrypt) is the right
# fit here: it's built specifically for a raw origin server behind Cloudflare in Full-Strict mode,
# with no ACME-challenge-interception ordering dance like the Fly-backed records in dns.tf need.
#
# Deliberately its OWN file, isolated from dns.tf's `api`/`app` resources: this module has never
# been applied from a checkout (see backend.tf) and `api`'s live record is an A+AAAA pair, not the
# CNAME dns.tf declares -- an untargeted apply here would risk the same kind of silent drift
# "correction" already flagged as a landmine in ../algenta-control-plane/dns.tf. Apply THIS file
# only, explicitly targeted:
#   tofu apply -target=cloudflare_record.ci_webhook -target=cloudflare_origin_ca_certificate.ci_webhook
#
# The CSR is generated locally (openssl req -newkey rsa:2048 -nodes -keyout ci-webhook.key -out
# ci-webhook.csr -subj "/CN=ci-webhook.codna.ai") and passed in via TF_VAR_ci_webhook_csr -- the
# private key never touches Terraform state or this repo.

variable "ci_webhook_csr" {
  type      = string
  sensitive = true
}

resource "cloudflare_record" "ci_webhook" {
  zone_id = var.cloudflare_zone_id
  name    = "ci-webhook"
  type    = "A"
  content = "172.190.6.38"
  proxied = true
  ttl     = 1
  comment = "Azure ephemeral CI orchestrator (ci-orch) -- GitHub workflow_job webhook receiver"
}

resource "cloudflare_origin_ca_certificate" "ci_webhook" {
  csr                = var.ci_webhook_csr
  hostnames          = ["ci-webhook.codna.ai"]
  request_type       = "origin-rsa"
  requested_validity = 5475 # 15 years, matching Cloudflare's max Origin CA validity
}

output "ci_webhook_cert_pem" {
  value     = cloudflare_origin_ca_certificate.ci_webhook.certificate
  sensitive = true
}
