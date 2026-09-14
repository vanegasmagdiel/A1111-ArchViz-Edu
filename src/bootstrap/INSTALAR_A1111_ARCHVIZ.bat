@echo off
@rem A1111 ArchViz v8.2 A0 STABLE
@rem Copyright (c) 2026 Dr. Magdiel Torres Vanegas
@rem Educational/research distribution; third-party components retain their own licenses.
chcp 65001 >nul
setlocal DisableDelayedExpansion
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0archviz82\launcher_a0.ps1"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo La instalacion no pudo continuar. Revise la carpeta reports.
if "%RC%"=="0" echo Proceso finalizado.
pause
exit /b %RC%
