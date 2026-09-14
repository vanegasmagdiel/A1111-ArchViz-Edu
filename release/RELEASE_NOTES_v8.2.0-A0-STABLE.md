# Release notes — v8.2.0-A0-STABLE / GH-EDU-1

Educational GitHub publication of the frozen A0 baseline.

- functional A0 runtime policy unchanged;
- canonical frozen source restored and SHA-256 gated in CI;
- BAT copyright headers preserve `Copyright © 2026 Dr. Magdiel Torres Vanegas`;
- third-party license map, upstream references, SBOM and citation metadata are included;
- large model weights are not committed or redistributed by this repository;
- the complete educational source tree is exposed in `src/`;
- Windows CI validates repository policy, canonical source hashes, Python syntax, PowerShell parsing, planner tests and profile-default tests.

## Validated reference platform

Windows 11 Pro x64 / Intel Core i9-13900HX / 31.75 GiB RAM / NVIDIA RTX 4080 Laptop ~11.99 GiB VRAM / `CUDA_STABLE` / `PREMIUM`.

The A0 runtime was separately validated on the reference machine with clean installation, cold relaunch, persisted profile defaults, ControlNet, manual generation, batch generation and multi-checkpoint operation.

## Distribution boundary

GitHub automatically provides source archives for this tagged release. The previously audited one-click installer distribution candidate is tracked by its checksum in `release/SHA256SUMS.txt`; it is not reconstructed from GitHub source because A0 is frozen and the packaged CORE hash is part of the frozen bootstrap contract. Rebuilding that binary package would create a new packaging revision rather than silently changing A0.
