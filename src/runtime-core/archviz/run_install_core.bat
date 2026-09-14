@echo off
@rem A1111 ArchViz v8.2 A0 STABLE
@rem Copyright (c) 2026 Dr. Magdiel Torres Vanegas
@rem Educational/research distribution; third-party components retain their own licenses.
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1" -Action install
exit /b %ERRORLEVEL%
