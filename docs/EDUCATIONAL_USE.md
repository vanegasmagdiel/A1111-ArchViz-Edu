# Educational Use Guide

A1111 ArchViz A0 is published as an educational/research package to demonstrate:

- reproducible Windows AI installation design;
- hardware-aware configuration;
- clean-install transaction design;
- package integrity and hash verification;
- profile-driven defaults;
- ControlNet and SDXL architectural-visualization baselines;
- separation of user UX, runtime logs, QA, and release engineering.

## Classroom / laboratory suggestions

Students can examine the project without downloading model weights by reviewing:

1. `src/bootstrap/` — hardware detection and clean-install planning;
2. `src/runtime-core/archviz/catalog.json` — pinned model metadata and hashes;
3. `src/runtime-core/archviz/installer.py` — runtime orchestration;
4. `docs/ARCHITECTURE.md` — architecture and trust boundaries;
5. `docs/PERFILES_UI.md` — profile-to-UI contract;
6. `THIRD_PARTY_NOTICES.md` — licensing boundaries.

The repository intentionally does not vendor the multi-gigabyte model weights.
