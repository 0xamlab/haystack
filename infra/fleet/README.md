# Self-hosted runner fleet — support daemons

Support daemons that keep the self-hosted macOS/arm64 GitHub Actions fleet alive without manual
intervention. The five runner daemons themselves (`actions.runner.thyn-ai.thyn-mac-arm64*`) are
provisioned by the actions-runner installer and self-update; these daemons keep their
dependencies healthy.

## What runs

| Daemon | Label | Purpose |
| --- | --- | --- |
| DNS proxy | `com.algenta.dns-proxy` | Loopback proxy on `127.0.0.1:8899`. The runners route all GitHub traffic through it (`https_proxy` in each runner's `.env`) so a flaky local resolver can't take the fleet offline. Resolves via pinned GitHub IPs → DNS-over-HTTPS → system resolver, whichever works. |
| Watchdog | `com.algenta.fleet-watchdog` | Every 60s: restart the proxy if its port stops accepting; kickstart any runner daemon that vanished; restart a **wedged** runner (GitHub reports it offline while its listener is still alive, confirmed on two consecutive checks); restart a hung Colima VM (docker-socket `/_ping` first, ssh fallback, only after three consecutive failed checks so a busy VM is never killed); warn on VM disk ≥85%/≥95%; **recycle both logs** when they exceed 1 MiB (one `.old` archive kept, so they never accumulate). |

## Install / restore (new machine or after a wipe)

```sh
sudo bash infra/fleet/install_fleet_daemons.sh
```

Idempotent. Deploys the two scripts to `~/bin`, installs both plists into
`/Library/LaunchDaemons` (rewriting the home path for the invoking user), and (re)loads them into
the system domain.

## Verify

```sh
launchctl print system/com.algenta.dns-proxy      | head -3   # active count = 1
launchctl print system/com.algenta.fleet-watchdog | head -3   # 'not running' between 60s ticks is normal
```

Logs (auto-recycled at 1 MiB): `~/Library/Logs/algenta_dns_proxy.log`,
`~/Library/Logs/fleet_watchdog.log`.

## Notes

- The fleet routes GitHub traffic through the proxy, so the proxy is critical path; the watchdog
  restarts it (and the runners retry), so a brief restart is self-recovering.
- The Colima VM hosts the amd64 containers used by the Linux-only jobs; a hung VM is restarted by
  the watchdog. The VM probe answers on the docker socket first (`/_ping`) and only falls back to
  ssh, and a restart needs three consecutive failed checks (~3 min): under heavy docker builds the
  guest sshd is slow, and a 15s one-shot ssh probe once made the watchdog restart healthy VMs
  mid-CI — the watchdog must never be the source of the instability it exists to remove.
