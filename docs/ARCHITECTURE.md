# Architecture — A0 Frozen Baseline

```text
ONE BAT
  ↓
package preflight
  ↓
hardware detection
  ↓
backend + profile
  ↓
new target directory
  ↓
portable Python/Git bootstrap
  ↓
pinned A1111 + pinned ControlNet
  ↓
verified model/LoRA/VAE/ControlNet downloads
  ↓
dependency/CUDA checks
  ↓
real image smoke tests
  ↓
PASS + local A1111 UI
```

## Trust boundaries

- A1111 ArchViz owns the orchestration, manifests, profile contract, validation and educational documentation.
- Third-party source and models are fetched from upstream and remain governed by upstream licenses.
- Model weights are not committed to this GitHub repository.
- A0 is frozen; backend-specific optimization belongs to A1.
