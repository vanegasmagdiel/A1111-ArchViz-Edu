param([ValidateSet('install','launch')][string]$Action = 'install')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$base = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $base '_archviz_runtime'
$state = Join-Path $base '_archviz_state'
$expected = '1384f18fdaa3c21bf7bc4976a6bf5a9672b71f25fa7ccf1ae6660ad461b1a42c'
$python = Join-Path $runtime 'system\python\python.exe'
$lockStream = $null
try {
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'Windows x64 requerido.' }
    if ($base -match '[%!^&|<>\r\n]') { throw 'Extraiga en una ruta sin % ! ^ & | < >. Se permiten espacios, parentesis y acentos.' }
    if ($base.StartsWith('\\')) { throw 'Use un disco local, no una ruta UNC/red.' }
    if ($base.Length -gt 130) { throw 'Ruta demasiado larga; use por ejemplo D:\ArchViz.' }
    New-Item -ItemType Directory -Force -Path $state | Out-Null
    $lockStream = [IO.File]::Open((Join-Path $state 'bootstrap.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $manifest = Get-Content -LiteralPath (Join-Path $base 'PACKAGE_SHA256SUMS.txt')
    foreach ($line in $manifest) {
        if ($line -notmatch '^([0-9a-f]{64})  (.+)$') { throw 'Manifiesto invalido.' }
        $hash = $Matches[1]; $relative = $Matches[2]
        $file = [IO.Path]::GetFullPath((Join-Path $base $relative))
        if (-not $file.StartsWith($base + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Ruta fuera del paquete.' }
        if ((Get-FileHash -Algorithm SHA256 -LiteralPath $file).Hash.ToLowerInvariant() -ne $hash) { throw "Paquete modificado/corrupto: $relative" }
    }
    if (-not (Test-Path -LiteralPath $python)) {
        if ($Action -eq 'launch') { throw 'La instalación no está completa. Ejecute primero el instalador universal A1111 ArchViz v8.2.' }
        if (Test-Path -LiteralPath $runtime) { throw 'Runtime incompleto: conserve la carpeta para diagnostico y extraiga el ZIP en una carpeta nueva.' }
        $archive = Join-Path $state 'sd.webui.bootstrap.zip'
        $part = $archive + '.part'
        $url = 'https://github.com/AUTOMATIC1111/stable-diffusion-webui/releases/download/v1.0.0-pre/sd.webui.zip'
        if (-not (Test-Path -LiteralPath $archive)) {
            Write-Host '[BOOTSTRAP] Descargando Python y Git portables oficiales (52.7 MB)...'
            & curl.exe --silent --show-error --location --fail --retry 3 --connect-timeout 30 --continue-at - --output $part $url
            if ($LASTEXITCODE -ne 0) { throw 'Descarga interrumpida. Reejecute para reanudar.' }
            if ((Get-FileHash -Algorithm SHA256 -LiteralPath $part).Hash.ToLowerInvariant() -ne $expected) { throw 'Hash bootstrap incorrecto; archivo .part conservado.' }
            Move-Item -LiteralPath $part -Destination $archive
        }
        if ((Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant() -ne $expected) { throw 'SHA256 bootstrap no coincide.' }
        $stage = Join-Path $state ('extract_' + [guid]::NewGuid().ToString('N'))
        Expand-Archive -LiteralPath $archive -DestinationPath $stage
        $candidate = $stage
        if (-not (Test-Path -LiteralPath (Join-Path $candidate 'system\python\python.exe'))) { $candidate = Join-Path $stage 'sd.webui' }
        if (-not (Test-Path -LiteralPath (Join-Path $candidate 'system\python\python.exe'))) { throw 'Layout bootstrap desconocido.' }
        New-Item -ItemType Directory -Path $runtime | Out-Null
        Move-Item -LiteralPath (Join-Path $candidate 'system') -Destination $runtime
        Write-Host '[BOOTSTRAP] SHA256 PASS. Solo se aprovechan Python/Git; A1111 se descarga aparte.'
    }
    $pyDir = Split-Path -Parent $python
    $gitDir = Join-Path $runtime 'system\git\bin'
    $env:PATH = "$gitDir;$pyDir;$(Join-Path $pyDir 'Scripts');$env:PATH"
    $env:PYTHONHOME = $pyDir
    $env:PYTHONPATH = ''
    $env:PYTHONNOUSERSITE = '1'
    $env:PYTHONUTF8 = '1'
    $env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
    $env:ARCHVIZ_BASE = $base
    & $python (Join-Path $PSScriptRoot 'installer.py') $Action
    $rc = $LASTEXITCODE
    exit $rc
} catch {
    Write-Host ('[BLOCKED] ' + $_.Exception.Message) -ForegroundColor Red
    exit 2
} finally {
    if ($null -ne $lockStream) { $lockStream.Dispose() }
}
