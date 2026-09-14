# A1 Backend Capsules — Plan de implementación

**Base:** A0 RC2 Profile Defaults  
**Copyright © 2026 Dr. Magdiel Torres Vanegas.**

A0 termina en la selección transparente del perfil y en defaults de UI verificables.
A1 NO cambia esos rangos: añade una cápsula de runtime por backend/perfil.

## Cápsulas objetivo

| Backend | Perfil | Estado A1 inicial |
|---|---|---|
| CUDA_STABLE | LITE | benchmark/certificación |
| CUDA_STABLE | STANDARD | benchmark/certificación |
| CUDA_STABLE | PREMIUM | benchmark/certificación |
| CUDA_STABLE | PREMIUM_PLUS | benchmark/certificación |
| CUDA_STABLE | WORKSTATION | benchmark/certificación |
| DIRECTML_COMPAT | AMD/Intel compatibles | rama separada, experimental hasta PASS |
| CPU_FALLBACK | DIAGNOSTIC | diagnóstico; generación solo si se certifica |

## Variables de cápsula

- estrategia de VRAM;
- flags de launch;
- resolución máxima por workflow;
- política unload/reload ControlNet/IP-Adapter;
- batch/concurrencia;
- peak VRAM;
- timeouts;
- fallback seguro ante OOM.

## Gate A1

Cada cápsula debe demostrar:
1. arranque;
2. generación real;
3. peak VRAM registrado;
4. 0 OOM en su workflow objetivo;
5. 0 fallback silencioso CPU;
6. tiempos registrados;
7. PASS reproducible.

No se activa una cápsula por heurística solamente.
