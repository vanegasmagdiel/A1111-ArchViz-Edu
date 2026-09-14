# Third-Party Notices and License Map

A1111 ArchViz is an independent educational/research orchestration project. It is **not affiliated with, endorsed by, or sponsored by** AUTOMATIC1111, Stability AI, RunDiffusion, Hugging Face, OpenAI, Meta/PyTorch, OpenCV, Python Software Foundation, Git for Windows, or the authors of the referenced models/extensions.

The GitHub repository and the A0 release package do **not** embed the large third-party model weights. The installer downloads pinned artifacts from their upstream sources and verifies hashes. Users must review and comply with the license terms that apply to each downloaded component.

## Direct software/runtime components

| Component | Pin / role in A0 | Upstream | License / notice |
|---|---|---|---|
| AUTOMATIC1111 Stable Diffusion WebUI | v1.10.1 / commit `82a973c04367123ae98bd9abdf80d9eda9b910e2` | https://github.com/AUTOMATIC1111/stable-diffusion-webui | GNU AGPL-3.0; see upstream `LICENSE.txt` |
| sd-webui-controlnet | commit `56cec5b2958edf3b1807b7e7b2b1b5186dbd2f81` | https://github.com/Mikubill/sd-webui-controlnet | GNU GPL-3.0; see upstream `LICENSE` |
| OpenAI CLIP | commit `d50d76daa670286dd6cacf3bcd80b5e4823fc8e1` | https://github.com/openai/CLIP | MIT License |
| Python 3.10 portable runtime | bootstrap dependency | https://docs.python.org/3.10/license.html | Python Software Foundation License; incorporated components may carry additional licenses |
| Git / Git for Windows | portable bootstrap dependency | https://gitforwindows.org/ and https://github.com/git-for-windows/git | Git core is GPL-2.0; Git for Windows contains additional components under their own licenses |
| PyTorch 2.1.2 / torchvision 0.16.2 | CUDA runtime | https://github.com/pytorch/pytorch | PyTorch main project: BSD-3-Clause; bundled third-party code has additional licenses |
| OpenCV 4.10 | CV provider | https://opencv.org/license/ | Apache License 2.0 for OpenCV 4.5.0+ |

## Model and adapter artifacts

| Asset | Upstream source | License / special note |
|---|---|---|
| RealVisXL V5.0 | https://huggingface.co/SG161222/RealVisXL_V5.0 | OpenRAIL++ per model card |
| Juggernaut XL v9 | https://huggingface.co/RunDiffusion/Juggernaut-XL-v9 | CreativeML Open RAIL-M; the model card also states that paid API deployment requires explicit licensing |
| SDXL VAE FP16 Fix | https://huggingface.co/madebyollin/sdxl-vae-fp16-fix | MIT per model card |
| ControlNet Canny SDXL 1.0 | https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0 | OpenRAIL++ per model card |
| ControlNet Depth SDXL 1.0 | https://huggingface.co/diffusers/controlnet-depth-sdxl-1.0 | OpenRAIL++ per model card |
| Interior MySpace SDXL LoRA | https://huggingface.co/razor7x/sdxl-base-1.0-interior-myspace-lora | CreativeML Open RAIL-M per model card |
| LCM LoRA SDXL | https://huggingface.co/latent-consistency/lcm-lora-sdxl | OpenRAIL++ per model card |
| `vaeapprox-sdxl.pt` | https://github.com/AUTOMATIC1111/stable-diffusion-webui/releases/tag/v1.0.0-pre | Source release preserved; no separate license metadata is asserted here—review upstream notices before redistribution |

## Python package dependencies

A0 installs a pinned Python dependency set. The exact dependency lock is preserved at `src/runtime-core/archviz/dependencies-win310.lock`. Each Python package remains under its own license. This project does not attempt to relicense those packages. A runtime installation should retain package metadata and upstream notices where provided.

## Redistribution policy used by this repository

- Large model weights are not committed to GitHub.
- AUTOMATIC1111 and ControlNet source are fetched from the pinned upstream commits rather than vendored into this repository.
- Python/Git/PyTorch/OpenCV are installed/fetched from their upstream distribution channels.
- The release package contains the A1111 ArchViz orchestration layer, hashes, manifests, documentation, and metadata-only compatibility shims.
- Any redistribution of downloaded third-party artifacts remains subject to their respective licenses.

This notice is informational and is not legal advice.
