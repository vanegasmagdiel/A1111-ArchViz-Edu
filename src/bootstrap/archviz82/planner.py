"""Pure planning primitives for ArchViz v8.2-A0.

This module intentionally has no Windows-specific imports so its decision logic
can be cleanroom-tested outside the target machine.

Copyright (c) 2026 Dr. Magdiel Torres Vanegas.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Optional

VERSION = "8.2.0-A0-ALPHA1"


@dataclass(frozen=True)
class GPU:
    name: str
    vendor: str
    vram_gib: float = 0.0
    nvidia_smi: bool = False


@dataclass(frozen=True)
class Compatibility:
    backend: str
    profile: str
    install_enabled: bool
    reason: str

    def to_dict(self):
        return asdict(self)


def normalize_vendor(name: str, vendor_hint: str = "") -> str:
    text = f"{vendor_hint} {name}".lower()
    if "nvidia" in text or "geforce" in text or "quadro" in text or "rtx" in text:
        return "NVIDIA"
    if "amd" in text or "radeon" in text or "advanced micro devices" in text:
        return "AMD"
    if "intel" in text or "arc" in text or "iris" in text:
        return "INTEL"
    return "OTHER"


def profile_for_vram(vram_gib: float) -> str:
    v = max(0.0, float(vram_gib or 0.0))
    if v >= 24:
        return "WORKSTATION"
    if v >= 16:
        return "PREMIUM_PLUS"
    if v >= 10:
        return "PREMIUM"
    if v >= 8:
        return "STANDARD"
    if v >= 4:
        return "LITE"
    return "DIAGNOSTIC"


def choose_compatibility(gpus: Iterable[GPU], windows_x64: bool = True) -> Compatibility:
    if not windows_x64:
        return Compatibility("UNSUPPORTED", "DIAGNOSTIC", False, "Windows x64 requerido por A0")
    gpus = list(gpus)
    nvidia = [g for g in gpus if normalize_vendor(g.name, g.vendor) == "NVIDIA" and g.nvidia_smi]
    if nvidia:
        best = max(nvidia, key=lambda g: g.vram_gib)
        return Compatibility("CUDA_STABLE", profile_for_vram(best.vram_gib), True,
                             f"NVIDIA + nvidia-smi; GPU seleccionada: {best.name}")
    if any(normalize_vendor(g.name, g.vendor) in {"AMD", "INTEL"} for g in gpus):
        best = max(gpus, key=lambda g: g.vram_gib, default=GPU("unknown", "OTHER"))
        return Compatibility("DIRECTML_COMPAT", profile_for_vram(best.vram_gib), False,
                             "GPU AMD/Intel detectada; backend separado pendiente de certificación A1")
    return Compatibility("CPU_FALLBACK", "DIAGNOSTIC", False,
                         "No se detectó backend GPU certificado; diagnóstico disponible")


def safe_reuse_state(has_certificate: bool, certificate_valid: bool, asset_drift: bool,
                     partial: bool = False, corrupt: bool = False) -> str:
    if corrupt:
        return "CORRUPT"
    if partial:
        return "PARTIAL"
    if not has_certificate:
        return "UNVERIFIED"
    if not certificate_valid:
        return "UNVERIFIED"
    if asset_drift:
        return "VERIFIED_WITH_ASSET_DRIFT"
    return "VERIFIED"


def unique_target_name(base: str, existing: Iterable[str]) -> str:
    existing_lower = {x.lower() for x in existing}
    if base.lower() not in existing_lower:
        return base
    i = 2
    while f"{base}-{i}".lower() in existing_lower:
        i += 1
    return f"{base}-{i}"
