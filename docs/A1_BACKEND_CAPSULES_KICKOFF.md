# A1 Backend Capsules — Kickoff de ingeniería

**Base congelada:** A1111 ArchViz v8.2 A0 STABLE  
**Copyright © 2026 Dr. Magdiel Torres Vanegas.**

A0 ya decide hardware, backend A0, perfil y defaults UI. A1 no reabre esas decisiones.
A1 define **cómo ejecutar** A1111 de forma óptima y segura por backend/perfil.

| Backend | Perfil | Objetivo A1 |
|---|---|---|
| CUDA_STABLE | LITE | mínimo consumo / evitar OOM |
| CUDA_STABLE | STANDARD | equilibrio memoria-rendimiento |
| CUDA_STABLE | PREMIUM | SDXL + ControlNet estable en 10–15.99 GiB |
| CUDA_STABLE | PREMIUM_PLUS | workflows más complejos |
| CUDA_STABLE | WORKSTATION | batch/múltiples controles |
| DIRECTML_COMPAT | compatibles AMD/Intel | rama experimental hasta PASS |
| CPU_FALLBACK | DIAGNOSTIC | diagnóstico; generación solo si se certifica |

Cada cápsula debe declarar launch flags, política VRAM, resolución recomendada/máxima, batch seguro, unload/reload, ControlNet simultáneo, comportamiento OOM, tiempos y picos RAM/VRAM.

## Gate por cápsula

1. hardware reconocido;
2. runtime seleccionado explícitamente;
3. generación real;
4. cero OOM en workflow objetivo;
5. cero fallback silencioso CPU;
6. memoria/tiempo registrados;
7. repetibilidad;
8. `PASS` machine-readable.

## Orden

A1.1 CUDA_PREMIUM → hardware actual de 11.99 GiB.  
A1.2 CUDA_STANDARD.  
A1.3 CUDA_LITE.  
A1.4 CUDA_PREMIUM_PLUS.  
A1.5 CUDA_WORKSTATION.  
A1.6 DIRECTML_COMPAT experimental.

La base A0 permanece congelada durante A1.
