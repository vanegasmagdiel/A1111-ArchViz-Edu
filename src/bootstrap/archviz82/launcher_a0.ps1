param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Support = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $Support
$Bootstrap = Join-Path $Support 'bootstrap_a0.ps1'
$Reports = Join-Path $Root 'reports'
New-Item -ItemType Directory -Force -Path $Reports | Out-Null

function Stop-Friendly([string]$Title, [string]$Detail='') {
    Write-Host ''
    Write-Host $Title -ForegroundColor Red
    Write-Host 'No se realizó ninguna instalación.' -ForegroundColor Yellow
    if ($Detail) { Write-Host ('Informe: ' + $Detail) -ForegroundColor DarkGray }
    exit 2
}

# Verificación sintáctica interna.
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile($Bootstrap, [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) {
    $syntaxLog = Join-Path $Reports 'INTERNAL_SYNTAX_ERROR.txt'
    @(
        'A1111 ArchViz v8.2 - verificación interna'
        ('Fecha UTC: ' + [DateTime]::UtcNow.ToString('o'))
        ''
        'El paquete contiene un error interno de sintaxis.'
        ($errors | ForEach-Object { $_.Message })
    ) | Set-Content -LiteralPath $syntaxLog -Encoding UTF8
    Stop-Friendly 'El paquete no superó la verificación interna.' $syntaxLog
}

# Preflight de producción. No ejecuta gates de desarrollo/UX.
$preflightLog = Join-Path $Reports 'PREFLIGHT_LAST.txt'
& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $Bootstrap -Mode Preflight *> $preflightLog
if ($LASTEXITCODE -ne 0) {
    $friendly = Join-Path $Reports 'PREFLIGHT_USER_MESSAGE.txt'
    @(
        'A1111 ArchViz v8.2'
        ''
        'La verificación inicial no pudo completarse.'
        'La causa puede ser integridad del paquete, extracción incompleta o una inconsistencia interna.'
        ''
        'Acción recomendada:'
        '1. No modifique ninguna instalación existente.'
        '2. Conserve este informe para soporte.'
        '3. Si el ZIP proviene de una descarga verificada, no es necesario repetir la extracción hasta revisar el informe.'
        ''
        ('Detalle técnico: ' + $preflightLog)
    ) | Set-Content -LiteralPath $friendly -Encoding UTF8

    Write-Host ''
    Write-Host 'La verificación inicial no pudo completarse.' -ForegroundColor Red
    Write-Host 'La instalación se detuvo de forma segura. Consulte el informe indicado.' -ForegroundColor Yellow
    Write-Host ('Informe: ' + $friendly) -ForegroundColor DarkGray
    exit 2
}

Write-Host '[OK] Verificación inicial completada.' -ForegroundColor Green
Start-Sleep -Milliseconds 250

# Experiencia de usuario.
& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $Bootstrap -Mode Interactive
exit $LASTEXITCODE
