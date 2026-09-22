# Algenta kernels on the Hugging Face Hub — release stage and support scope

## Release stage: Generally Available

The kernel repositories listed below are **Generally Available (GA)**: ready for production use within the
supported configurations, fully documented on their cards, and covered by the API promise below. GA does not
change the licence: use is governed by the Algenta Community License, and every published library enforces
the Community worker limit described there.

Stages, as we use the words:

| Stage | Meaning |
|---|---|
| **Generally Available** | Ready for production use at any scale within the supported configurations. Fully supported and documented. Within a major version, API changes are additive only. |
| **Preview** | Complete or near-complete. May change outside a major version, with less notice than GA. Supported on a commercially-reasonable-effort basis. Not recommended for production. |
| **Not supported** | Everything not listed as GA or Preview. It may work; we make no commitment and do not accept issues for it. |

## Supported configurations (GA)

| OS | Architecture | Accelerator | Floor | Repositories |
|---|---|---|---|---|
| macOS | arm64 | CPU | macOS 15.0 (see note) | all 19 families |
| Linux | aarch64 | CPU | glibc 2.35 | all 19 families |
| Linux | x86-64 (x86-64-v3) | CPU | glibc 2.35 | all 19 families |
| macOS | arm64 | Apple Metal | macOS 26 | `algenta-llm` |
| Linux | x86-64 | NVIDIA CUDA sm_75 / sm_80 / sm_89 / sm_90 | driver ≥ 580, glibc 2.35 | `algenta-llm` |

One variant per PyTorch release 2.5 – 2.14; CUDA toolkits per PyTorch release as listed in the release capability
manifest. The umbrella `algenta` repository is a pure-Python dispatcher over the families above.

Operating systems, architectures, accelerators and PyTorch releases not listed above are **not supported**.
Windows is not supported. AMD ROCm is not available. Linux inside the Windows Subsystem for Linux is not
supported. The macOS 15.0 CPU floor is supported on a **discretionary basis**: it is the artifacts' minimum OS
version, measured from their headers, not the result of a macOS 15 hardware run.

## What GA promises

- **API.** Within `v1`, functions may be added; nothing is removed and no signature changes. Removals or
  incompatible changes ship as `v2`. An API-versioning gate compares every release against the published `v1`
  before anything is uploaded.
- **Behaviour.** Every published library enforces **one concurrent native worker per device** (ABI §9), in the
  compiled library, on every platform above. It cannot be configured or disabled; parallel execution requires a
  commercial licence.
- **Integrity.** Every native file is verified by size and SHA-256 against the shipped manifest before it is
  loaded; a truncated or edited file fails closed.
- **Support window.** Support for an operating system or PyTorch release is removed six months after its
  upstream end of life; the affected variants stop being published in the following release.

## What GA does not promise

- **Signature verification at load.** `get_kernel` does not verify signatures. The published artifacts are not
  yet signed; signing is wired into the release workflow and takes effect with the first CI-published release,
  after which verification is available as an opt-in through the `kernels` CLI.
- Anything about ROCm, Windows, or CUDA compute capabilities not listed above.

## Eligibility

Community Use — personal, research or educational use, open-source projects, or internal use at an organization
with fewer than 50 employees and under US$5,000,000 in annual revenue — is free under the Algenta Community
License. Anything beyond that, and any use of more than one concurrent worker per device, requires a commercial
licence — plans and checkout at https://algenta.ai/pricing.

## Getting help

Community: the Algenta Discord (https://discord.gg/w8NDsph9an) or the repository's Community tab on the Hugging Face Hub.
Commercial licences and support: plans and checkout at https://algenta.ai/pricing; enterprise via the "Talk to us" link there.
