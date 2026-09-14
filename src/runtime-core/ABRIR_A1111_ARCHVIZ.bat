@echo off
@rem A1111 ArchViz v8.2 A0 STABLE
@rem Copyright (c) 2026 Dr. Magdiel Torres Vanegas
@rem Educational/research distribution; third-party components retain their own licenses.
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0" || exit /b 2
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0archviz\bootstrap.ps1" -Action launch
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" pause
exit /b %RC%
