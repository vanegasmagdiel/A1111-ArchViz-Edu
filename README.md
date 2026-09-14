# A1111 ArchViz v8.2 A0 STABLE — Educational GitHub Edition

**A0 Universal Bootstrap — FROZEN**  
**Copyright © 2026 Dr. Magdiel Torres Vanegas**

A1111 ArchViz is an independent educational/research project that demonstrates a reproducible, hardware-aware Windows bootstrap for AUTOMATIC1111 focused on architectural visualization with SDXL, ControlNet, LoRA and verified model manifests.

> This repository does not redistribute the large third-party model weights. The installer downloads pinned artifacts from upstream sources and verifies them. Every third-party component remains subject to its own license and terms.

## Educational goals

- teach clean-install and portable-runtime architecture;
- show hardware detection and profile assignment;
- document reproducible model hashes/commits;
- expose profile-aware UI defaults transparently;
- preserve QA evidence and release-engineering gates;
- provide an ArchViz baseline for later A1 Backend Capsules research.

## Frozen A0 contract

- clean install only;
- Windows x64 hardware detection;
- NVIDIA `CUDA_STABLE` baseline;
- profile assignment (`DIAGNOSTIC`, `LITE`, `STANDARD`, `PREMIUM`, `PREMIUM_PLUS`, `WORKSTATION`);
- profile-aware A1111 defaults;
- pinned AUTOMATIC1111 v1.10.1;
- pinned ControlNet extension;
- verified model/VAE/LoRA/ControlNet catalog;
- real generation smoke tests before PASS.

## Quick start

1. Download the GitHub Release asset `A1111_ArchViz_v8.2_A0_STABLE_EDU_GH1.zip`.
2. Verify its SHA-256 against the release checksums.
3. Extract it to a new local folder.
4. Run `INSTALAR_A1111_ARCHVIZ.bat`.
5. Review the detected hardware, target directory and profile before confirming.

The installer is intentionally one-BAT for the user; technical detail is written to runtime logs.

## Validated A0 reference platform

- Windows 11 Pro x64;
- Intel Core i9-13900HX;
- 31.75 GiB RAM;
- NVIDIA GeForce RTX 4080 Laptop GPU, ~11.99 GiB VRAM;
- detected profile: `PREMIUM`;
- persisted UI defaults: 1024×1024, 28 steps, CFG 5.5, DPM++ 2M, Automatic scheduler;
- clean install, cold relaunch, batch generation, multi-checkpoint operation and ControlNet smoke tests: PASS.

This is a validated reference platform, not a claim that every hardware combination has already been benchmarked. Cross-hardware runtime optimization belongs to A1.

## Repository layout

```text
src/bootstrap/       universal A0 bootstrap source
src/runtime-core/    portable runtime-core source
release/             release notes and checksums (no large model weights)
docs/                educational, architecture, validation and roadmap material
licenses/            license index and upstream links
.github/              issue templates and build validation
```

## Licensing

The original A1111 ArchViz orchestration and educational materials are covered by `LICENSE.md` and retain:

**Copyright © 2026 Dr. Magdiel Torres Vanegas.**

AUTOMATIC1111, ControlNet, Python, Git, PyTorch, OpenCV, model weights, LoRAs and other third-party components are **not relicensed** by this project. See `THIRD_PARTY_NOTICES.md` and `REFERENCES.md` before use or redistribution.

## Research / citation

See `CITATION.cff` and `REFERENCES.md`.

## Status

`A0 = RELEASE BASELINE FROZEN`  
`NEXT = A1 BACKEND CAPSULES`
