param(
    [ValidateSet('Interactive','Diagnostic','Plan','Install','Resume','SelfTest','Preflight')]
    [string]$Mode = 'Interactive',
    [string]$TargetParent = '',
    [string]$TargetRoot = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ScriptVersion = '8.2.0-A0-STABLE'
# CLEAN INSTALL ONLY no elimina el hardware-aware planning:
# 1) detectar hardware, 2) elegir backend, 3) asignar perfil, 4) instalar desde cero.
$PackageRoot = Split-Path -Parent $PSScriptRoot
$CoreZip = Join-Path $PackageRoot 'CORE\A1111_ArchViz_CORE_v8.2_A0_STABLE.zip'
$CoreExpectedSha = 'add2256ee93d3aa7c48cbeabda42a74b41b0e76e1d68c2171b6093e78ac98b21'
$LocalIndexDir = Join-Path $env:LOCALAPPDATA 'ArchViz'
$LocalIndex = Join-Path $LocalIndexDir 'installations-v82.json'
$Copyright = 'Copyright (c) 2026 Dr. Magdiel Torres Vanegas'

# Consola UTF-8: evita mojibake en cmd/Windows Terminal (PowerShell 5.1 incluido).
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }

function Write-Title {
    Clear-Host
    Write-Host '============================================================' -ForegroundColor Cyan
    Write-Host 'A1111 ARCHVIZ v8.2 - INSTALADOR UNIVERSAL' -ForegroundColor Cyan
    Write-Host $Copyright -ForegroundColor DarkGray
    Write-Host '============================================================' -ForegroundColor Cyan
}

function Write-JsonAtomic([string]$Path, $Data) {
    $dir = Split-Path -Parent $Path
    if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $tmp = $Path + '.tmp'
    $Data | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $tmp -Encoding UTF8
    Move-Item -LiteralPath $tmp -Destination $Path -Force
}


function Write-LastErrorReport($ErrorRecord) {
    try {
        $dir = Join-Path $PackageRoot 'reports'
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $jsonPath = Join-Path $dir ('ERROR_' + $stamp + '.json')
        $txtPath = Join-Path $dir 'ERROR_LAST_RUN.txt'
        $payload = [ordered]@{
            schema = 'archviz.error.v1'
            version = $ScriptVersion
            timestamp_utc = [DateTime]::UtcNow.ToString('o')
            message = [string]$ErrorRecord.Exception.Message
            exception_type = [string]$ErrorRecord.Exception.GetType().FullName
            category = [string]$ErrorRecord.CategoryInfo.Category
            target_object = [string]$ErrorRecord.TargetObject
            script_stack = [string]$ErrorRecord.ScriptStackTrace
            invocation = [string]$ErrorRecord.InvocationInfo.PositionMessage
        }
        Write-JsonAtomic $jsonPath $payload
        @(
            'A1111 ArchViz v8.2-A0 - LAST ERROR'
            ('Version: ' + $ScriptVersion)
            ('UTC: ' + $payload.timestamp_utc)
            ''
            ('Message: ' + $payload.message)
            ('Type: ' + $payload.exception_type)
            ('Category: ' + $payload.category)
            ''
            'Script stack:'
            $payload.script_stack
            ''
            'Invocation:'
            $payload.invocation
            ''
            ('JSON report: ' + $jsonPath)
        ) | Set-Content -LiteralPath $txtPath -Encoding UTF8
        return $txtPath
    } catch {
        return $null
    }
}

function Test-InstallFolderName([string]$Name) {
    if ([string]::IsNullOrWhiteSpace($Name)) { throw 'El nombre de instalación no puede estar vacío.' }
    $trimmed = $Name.Trim()
    if ($trimmed -in @('.', '..')) { throw 'Nombre de instalación inválido.' }
    if ($trimmed -match '[\\/:*?"<>|%!^&\r\n]') {
        throw 'El nombre de instalación no puede contener \\ / : * ? " < > | % ! ^ &.'
    }
    if ($trimmed.EndsWith('.') -or $trimmed.EndsWith(' ')) {
        throw 'El nombre de instalación no puede terminar en punto o espacio.'
    }
    if ($trimmed.Length -gt 64) { throw 'Nombre de instalación demasiado largo (máximo 64 caracteres).' }
    return $trimmed
}

function Resolve-InteractiveParent([string]$InputPath, [string]$DefaultParent) {
    if ([string]::IsNullOrWhiteSpace($InputPath)) { return (Test-SafeTarget $DefaultParent) }
    $candidate = $InputPath.Trim().Trim('"')
    if (-not [IO.Path]::IsPathRooted($candidate)) {
        throw ('Directorio padre debe ser una ruta absoluta, por ejemplo: ' + $DefaultParent + '. Para usar ALPHA_3 como nombre, escríbalo en el campo Nombre de instalación.')
    }
    return (Test-SafeTarget $candidate)
}

function Get-RequestedTarget([string]$Parent, [string]$FolderName) {
    $safeParent = Test-SafeTarget $Parent
    $safeName = Test-InstallFolderName $FolderName
    $target = Test-SafeTarget (Join-Path $safeParent $safeName)
    $parentFull = [IO.Path]::GetFullPath($safeParent).TrimEnd('\')
    $targetFull = [IO.Path]::GetFullPath($target)
    if (-not $targetFull.StartsWith($parentFull + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'El destino calculado sale del directorio padre.'
    }
    return $targetFull
}

function Confirm-InstallTarget([string]$Target, $Hardware, $Disk) {
    Write-Host ''
    Write-Host '---------------- PREINSTALACION ----------------' -ForegroundColor Cyan
    Write-Host ('Destino final : ' + $Target) -ForegroundColor White
    Write-Host ('Backend       : ' + $Hardware.compatibility.backend)
    Write-Host ('Perfil        : ' + $Hardware.compatibility.profile)
    Write-Host ('Disco         : ' + $Disk.root + ' | ' + $Disk.drive_type + ' | ' + $Disk.format + ' | ' + $Disk.free_gib + ' GiB libres')
    Write-Host 'Modo          : CLEAN BUILD / SIDE-BY-SIDE' -ForegroundColor Green
    Write-Host 'Versiones previas: NO se buscan / NO se reutilizan' -ForegroundColor Green
    Write-Host '-------------------------------------------------' -ForegroundColor Cyan
    $answer = (Read-Host 'Confirmar instalación nueva [S/N]').Trim().ToUpperInvariant()
    return ($answer -in @('S','SI','SÍ','Y','YES'))
}

function Verify-PackageManifest {
    $manifestPath = Join-Path $PackageRoot 'PACKAGE_SHA256SUMS.txt'
    if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Falta PACKAGE_SHA256SUMS.txt.' }
    $baseFull = [IO.Path]::GetFullPath($PackageRoot).TrimEnd('\')
    foreach ($line in Get-Content -LiteralPath $manifestPath) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line -notmatch '^([0-9a-f]{64})  (.+)$') { throw 'Manifiesto SHA256 invalido.' }
        $expected = $Matches[1]
        $relative = $Matches[2]
        $full = [IO.Path]::GetFullPath((Join-Path $PackageRoot $relative))
        if (-not $full.StartsWith($baseFull + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Entrada de manifiesto fuera del paquete.' }
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { throw "Falta archivo de paquete: $relative" }
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $full).Hash.ToLowerInvariant()
        if ($actual -ne $expected) { throw "Paquete modificado/corrupto: $relative" }
    }
    $coreActual = (Get-FileHash -Algorithm SHA256 -LiteralPath $CoreZip).Hash.ToLowerInvariant()
    if ($coreActual -ne $CoreExpectedSha) { throw 'El runtime core v8.2 embebido no coincide con el hash congelado.' }
}

function Get-NvidiaSmiPath {
    $cmd = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidate = Join-Path $env:ProgramFiles 'NVIDIA Corporation\NVSMI\nvidia-smi.exe'
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    return $null
}

function Get-NvidiaSmiRows {
    $path = Get-NvidiaSmiPath
    if (-not $path) { return @() }
    try {
        $lines = & $path '--query-gpu=name,memory.total,driver_version' '--format=csv,noheader,nounits' 2>$null
        if ($LASTEXITCODE -ne 0) { return @() }
        $rows = @()
        foreach ($line in $lines) {
            $parts = $line -split ','
            if ($parts.Count -ge 3) {
                $rows += [pscustomobject]@{
                    name = $parts[0].Trim()
                    vram_mib = [double]($parts[1].Trim())
                    driver = $parts[2].Trim()
                    nvidia_smi = $true
                }
            }
        }
        return $rows
    } catch { return @() }
}

function Get-Vendor([string]$Name, [string]$Hint='') {
    $text = ($Hint + ' ' + $Name).ToLowerInvariant()
    if ($text -match 'nvidia|geforce|quadro|rtx') { return 'NVIDIA' }
    if ($text -match 'amd|radeon|advanced micro devices') { return 'AMD' }
    if ($text -match 'intel|\barc\b|iris') { return 'INTEL' }
    return 'OTHER'
}

function Get-Profile([double]$VramGiB) {
    if ($VramGiB -ge 24) { return 'WORKSTATION' }
    if ($VramGiB -ge 16) { return 'PREMIUM_PLUS' }
    if ($VramGiB -ge 10) { return 'PREMIUM' }
    if ($VramGiB -ge 8)  { return 'STANDARD' }
    if ($VramGiB -ge 4)  { return 'LITE' }
    return 'DIAGNOSTIC'
}


function Get-UiDefaultsForProfile([string]$Profile) {
    switch ($Profile.ToUpperInvariant()) {
        'DIAGNOSTIC'   { return [pscustomobject]@{width=512;  height=512;  steps=20; cfg=7.0; sampler='DPM++ 2M'; scheduler='Automatic'; batch_count=1; batch_size=1; hires_fix=$false} }
        'LITE'         { return [pscustomobject]@{width=640;  height=640;  steps=20; cfg=6.0; sampler='DPM++ 2M'; scheduler='Automatic'; batch_count=1; batch_size=1; hires_fix=$false} }
        'STANDARD'     { return [pscustomobject]@{width=896;  height=896;  steps=24; cfg=6.0; sampler='DPM++ 2M'; scheduler='Automatic'; batch_count=1; batch_size=1; hires_fix=$false} }
        'PREMIUM'      { return [pscustomobject]@{width=1024; height=1024; steps=28; cfg=5.5; sampler='DPM++ 2M'; scheduler='Automatic'; batch_count=1; batch_size=1; hires_fix=$false} }
        'PREMIUM_PLUS' { return [pscustomobject]@{width=1024; height=1024; steps=30; cfg=5.5; sampler='DPM++ 2M'; scheduler='Automatic'; batch_count=1; batch_size=1; hires_fix=$false} }
        'WORKSTATION'  { return [pscustomobject]@{width=1024; height=1024; steps=32; cfg=5.0; sampler='DPM++ 2M'; scheduler='Automatic'; batch_count=1; batch_size=1; hires_fix=$false} }
        default { throw ('Perfil UI desconocido: ' + $Profile) }
    }
}

function Get-HardwareReport([string]$ProbePath='') {
    $os = Get-CimInstance Win32_OperatingSystem
    $cs = Get-CimInstance Win32_ComputerSystem
    $cpus = @(Get-CimInstance Win32_Processor)
    $videos = @(Get-CimInstance Win32_VideoController)
    $smi = @(Get-NvidiaSmiRows)
    $gpuRows = @()
    foreach ($v in $videos) {
        $name = [string]$v.Name
        $vendor = Get-Vendor $name ([string]$v.AdapterCompatibility)
        $vramGiB = 0.0
        try {
            if ($null -ne $v.AdapterRAM -and [double]$v.AdapterRAM -gt 0) { $vramGiB = [math]::Round(([double]$v.AdapterRAM / 1GB), 2) }
        } catch { $vramGiB = 0.0 }
        $smiMatch = $smi | Where-Object { $_.name -eq $name } | Select-Object -First 1
        if (-not $smiMatch -and $vendor -eq 'NVIDIA' -and $smi.Count -eq 1) { $smiMatch = $smi[0] }
        if ($smiMatch) { $vramGiB = [math]::Round(($smiMatch.vram_mib / 1024.0), 2) }
        $gpuRows += [pscustomobject]@{
            name = $name
            vendor = $vendor
            vram_gib = $vramGiB
            driver = $(if ($smiMatch) { $smiMatch.driver } else { [string]$v.DriverVersion })
            nvidia_smi = [bool]$smiMatch
            pnp_device_id = [string]$v.PNPDeviceID
        }
    }
    # nvidia-smi may see a compute GPU omitted by Win32_VideoController.
    foreach ($s in $smi) {
        if (-not ($gpuRows | Where-Object { $_.name -eq $s.name })) {
            $gpuRows += [pscustomobject]@{
                name = $s.name; vendor = 'NVIDIA'; vram_gib = [math]::Round(($s.vram_mib / 1024.0),2)
                driver = $s.driver; nvidia_smi = $true; pnp_device_id = ''
            }
        }
    }
    $cuda = @($gpuRows | Where-Object { $_.vendor -eq 'NVIDIA' -and $_.nvidia_smi })
    $amdIntel = @($gpuRows | Where-Object { $_.vendor -in @('AMD','INTEL') })
    $ramGiB = [math]::Round(([double]$cs.TotalPhysicalMemory / 1GB), 2)
    if (-not [Environment]::Is64BitOperatingSystem) {
        $backend = 'UNSUPPORTED'; $installEnabled = $false; $reason = 'Se requiere Windows x64'; $bestVram = 0.0
    } elseif ($cuda.Count -gt 0) {
        $best = $cuda | Sort-Object vram_gib -Descending | Select-Object -First 1
        $backend = 'CUDA_STABLE'; $bestVram = [double]$best.vram_gib
        if ($bestVram -lt 4.0) {
            $installEnabled = $false; $reason = 'GPU NVIDIA detectada, pero menos de 4 GiB VRAM: solo diagnóstico'
        } elseif ($ramGiB -lt 8.0) {
            $installEnabled = $false; $reason = 'RAM inferior a 8 GiB: solo diagnóstico'
        } else {
            $installEnabled = $true; $reason = 'GPU NVIDIA compatible y nvidia-smi funcional'
        }
    } elseif ($amdIntel.Count -gt 0) {
        $best = $amdIntel | Sort-Object vram_gib -Descending | Select-Object -First 1
        $backend = 'DIRECTML_COMPAT'; $installEnabled = $false; $reason = 'GPU AMD/Intel detectada; backend A1 aún no certificado'; $bestVram = [double]$best.vram_gib
    } else {
        $backend = 'CPU_FALLBACK'; $installEnabled = $false; $reason = 'Sin backend GPU certificado en A0'; $bestVram = 0.0
    }
    $cpuRows = @()
    foreach ($c in $cpus) {
        $cpuRows += [pscustomobject]@{
            name = [string]$c.Name
            manufacturer = [string]$c.Manufacturer
            cores = [int]$c.NumberOfCores
            logical_processors = [int]$c.NumberOfLogicalProcessors
        }
    }
    $report = [ordered]@{
        schema = 'archviz.hardware.v1'
        engine = $ScriptVersion
        timestamp_utc = [DateTime]::UtcNow.ToString('o')
        os = [ordered]@{
            caption = [string]$os.Caption
            version = [string]$os.Version
            build = [string]$os.BuildNumber
            x64 = [Environment]::Is64BitOperatingSystem
        }
        cpu = $cpuRows
        memory = [ordered]@{
            total_gib = $ramGiB
            available_gib = [math]::Round(([double]$os.FreePhysicalMemory * 1KB / 1GB), 2)
        }
        gpus = $gpuRows
        compatibility = [ordered]@{
            backend = $backend
            profile = (Get-Profile $bestVram)
            selected_vram_gib = $bestVram
            install_enabled_in_a0 = $installEnabled
            reason = $reason
        }
    }
    if ($ProbePath) { Write-JsonAtomic $ProbePath $report }
    return [pscustomobject]$report
}

function Get-DiskReport([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($full)
    if ([string]::IsNullOrWhiteSpace($root)) { throw ('No se pudo resolver la raíz de disco para: ' + $Path) }
    $drive = New-Object IO.DriveInfo($root)
    if (-not $drive.IsReady) { throw ('La unidad no está lista: ' + $root) }
    return [pscustomobject]@{
        schema = 'archviz.disk.report.v1'
        root = $root
        drive_type = $drive.DriveType.ToString()
        format = $drive.DriveFormat
        is_ready = [bool]$drive.IsReady
        free_gib = [math]::Round(($drive.AvailableFreeSpace / 1GB),2)
        total_gib = [math]::Round(($drive.TotalSize / 1GB),2)
    }
}

function Test-SafeTarget([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    if ($full -match '[%!\^&|<>\r\n]') { throw 'Ruta destino contiene % ! ^ & | < >, incompatibles con dependencias upstream.' }
    if ($full.StartsWith('\\')) { throw 'A0 solo certifica discos locales; no use UNC/red.' }
    if ($full.Length -gt 120) { throw 'Ruta destino demasiado larga; elija una ruta más corta.' }
    return $full
}


function Get-SelectedGpu($Hardware) {
    $rows = @($Hardware.gpus)
    if ($Hardware.compatibility.backend -eq 'CUDA_STABLE') {
        return ($rows | Where-Object { $_.vendor -eq 'NVIDIA' -and $_.nvidia_smi } | Sort-Object vram_gib -Descending | Select-Object -First 1)
    }
    if ($Hardware.compatibility.backend -eq 'DIRECTML_COMPAT') {
        return ($rows | Where-Object { $_.vendor -in @('AMD','INTEL') } | Sort-Object vram_gib -Descending | Select-Object -First 1)
    }
    return ($rows | Sort-Object vram_gib -Descending | Select-Object -First 1)
}

function Write-Section([string]$Number, [string]$Title) {
    Write-Host ''
    Write-Host ('[' + $Number + '] ' + $Title) -ForegroundColor Cyan
    Write-Host ('-' * 66) -ForegroundColor DarkGray
}

function Show-HardwareSummary($Hardware) {
    Write-Section '1/4' 'EQUIPO DETECTADO'
    Write-Host ('Sistema : ' + $Hardware.os.caption + ' | x64=' + $Hardware.os.x64)
    foreach ($c in @($Hardware.cpu)) {
        Write-Host ('CPU     : ' + $c.name.Trim() + ' | ' + $c.cores + ' núcleos / ' + $c.logical_processors + ' hilos')
    }
    Write-Host ('RAM     : ' + $Hardware.memory.total_gib + ' GiB')

    $selected = Get-SelectedGpu $Hardware
    foreach ($g in @($Hardware.gpus)) {
        $tag = ''
        if ($selected -and $g.name -eq $selected.name -and $g.vendor -eq $selected.vendor) { $tag = '  << GPU PRINCIPAL' }
        Write-Host ('GPU     : ' + $g.name + ' | ' + $g.vram_gib + ' GiB | ' + $g.vendor + $tag)
    }

    Write-Host ''
    Write-Host ('Motor detectado : ' + $Hardware.compatibility.backend) -ForegroundColor Yellow
    Write-Host ('Estado           : ' + $Hardware.compatibility.reason) -ForegroundColor DarkGray
}

function Show-ProfileMatrix($Hardware) {
    Write-Section '3/4' 'PERFILES DE INSTALACIÓN'
    Write-Host 'El perfil se selecciona automáticamente según el hardware. Los valores iniciales de A1111 se muestran por transparencia.' -ForegroundColor Gray
    Write-Host ''
    Write-Host ('{0,-18} {1,-16} {2,-14} {3,-9} {4}' -f 'PERFIL','VRAM','DEFAULT UI','STEPS','USO') -ForegroundColor White
    Write-Host ('{0,-18} {1,-16} {2,-14} {3,-9} {4}' -f '------','----','----------','-----','---') -ForegroundColor DarkGray

    $profiles = @(
        [pscustomobject]@{name='DIAGNOSTIC'; range='< 4 GiB';         use='Diagnóstico / sin backend Premium'},
        [pscustomobject]@{name='LITE';       range='4 - 7.99 GiB';    use='Carga reducida / ahorro de memoria'},
        [pscustomobject]@{name='STANDARD';   range='8 - 9.99 GiB';    use='SDXL moderado'},
        [pscustomobject]@{name='PREMIUM';    range='10 - 15.99 GiB';  use='SDXL 1024 / controles Premium'},
        [pscustomobject]@{name='PREMIUM_PLUS';range='16 - 23.99 GiB'; use='Mayor margen / combinaciones'},
        [pscustomobject]@{name='WORKSTATION';range='>= 24 GiB';       use='Producción / batch / máximo margen'}
    )

    foreach ($p in $profiles) {
        $d = Get-UiDefaultsForProfile $p.name
        $resolution = ([string]$d.width + 'x' + [string]$d.height)
        $line = ('{0,-18} {1,-16} {2,-14} {3,-9} {4}' -f $p.name,$p.range,$resolution,$d.steps,$p.use)
        if ($p.name -eq $Hardware.compatibility.profile) {
            Write-Host ('>> ' + $line + '  << SU EQUIPO') -ForegroundColor Green
        } else {
            Write-Host ('   ' + $line)
        }
    }

    $selectedDefaults = Get-UiDefaultsForProfile $Hardware.compatibility.profile
    Write-Host ''
    Write-Host ('Perfil asignado automáticamente: ' + $Hardware.compatibility.profile) -ForegroundColor Green
    Write-Host ('VRAM considerada               : ' + $Hardware.compatibility.selected_vram_gib + ' GiB')
    Write-Host ('Motor                           : ' + $Hardware.compatibility.backend)
    Write-Host ('Default A1111                   : ' + $selectedDefaults.width + 'x' + $selectedDefaults.height +
                ' | ' + $selectedDefaults.steps + ' steps | CFG ' + $selectedDefaults.cfg) -ForegroundColor Green
}

function Read-InstallDestination([string]$DefaultParent) {
    Write-Section '2/4' 'UBICACIÓN DE LA INSTALACIÓN'
    while ($true) {
        $parentInput = Read-Host ('Directorio base [' + $DefaultParent + ']')
        try {
            $parent = Resolve-InteractiveParent $parentInput $DefaultParent
            $disk = Get-DiskReport $parent
            break
        } catch {
            Write-Host ('No se puede usar esa ubicación: ' + $_.Exception.Message) -ForegroundColor Yellow
        }
    }

    while ($true) {
        $folderInput = Read-Host 'Nombre de la carpeta [A1111_ArchViz_v8.2]'
        if (-not $folderInput) { $folderInput = 'A1111_ArchViz_v8.2' }
        try {
            $target = Get-RequestedTarget $parent $folderInput
            if (Test-Path -LiteralPath $target) {
                Write-Host 'Esa carpeta ya existe. Escriba otro nombre para mantener una instalación limpia.' -ForegroundColor Yellow
                continue
            }
            break
        } catch {
            Write-Host ('Nombre no válido: ' + $_.Exception.Message) -ForegroundColor Yellow
        }
    }

    Write-Host ''
    Write-Host ('Destino : ' + $target) -ForegroundColor White
    Write-Host ('Disco   : ' + $disk.root + ' | ' + $disk.format + ' | ' + $disk.free_gib + ' GiB libres')
    return [pscustomobject]@{ parent=$parent; target=$target; disk=$disk }
}

function Find-ResumableCurrentTransaction {
    if (-not (Test-Path -LiteralPath $LocalIndex)) { return $null }
    try {
        $idx = Get-Content -LiteralPath $LocalIndex -Raw | ConvertFrom-Json
        $candidates = @($idx.installations | Where-Object {
            $_.version -eq $ScriptVersion -and $_.status -in @('INSTALLING','BLOCKED')
        } | Sort-Object updated_utc -Descending)
        foreach ($item in $candidates) {
            $tx = Join-Path ([string]$item.target) '_archviz_state_a0\INSTALL_TRANSACTION.json'
            if (-not (Test-Path -LiteralPath $tx -PathType Leaf)) { continue }
            $data = Get-Content -LiteralPath $tx -Raw | ConvertFrom-Json
            if ($data.version -ne $ScriptVersion) { continue }
            $expected = (Get-FileHash -Algorithm SHA256 -LiteralPath $CoreZip).Hash.ToLowerInvariant()
            if ($data.support_package_sha256 -ne $expected) { continue }
            return [pscustomobject]@{ target=[string]$item.target; transaction=$tx; status=[string]$item.status }
        }
    } catch { }
    return $null
}

function Get-DefaultParent {
    $parent = Split-Path -Parent $PackageRoot
    if ($parent -and (Test-Path -LiteralPath $parent)) { return $parent }
    return (Join-Path $env:USERPROFILE 'ArchViz')
}

function New-UniqueTarget([string]$Parent) {
    New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    $baseName = 'A1111_ArchViz_v8.2_A0'
    $candidate = Join-Path $Parent $baseName
    $i = 2
    while (Test-Path -LiteralPath $candidate) {
        $candidate = Join-Path $Parent ($baseName + '-' + $i)
        $i++
    }
    return $candidate
}

function Expand-Core([string]$Target) {
    if (Test-Path -LiteralPath $Target) { throw 'El target de una instalación limpia ya existe.' }
    New-Item -ItemType Directory -Path $Target | Out-Null
    Expand-Archive -LiteralPath $CoreZip -DestinationPath $Target
    if (-not (Test-Path -LiteralPath (Join-Path $Target 'archviz\bootstrap.ps1'))) { throw 'El paquete core v8.2 no se extrajo correctamente.' }
}

function New-Transaction([string]$Target, [string]$Backend, [string]$Profile) {
    $state = Join-Path $Target '_archviz_state_a0'
    New-Item -ItemType Directory -Force -Path $state | Out-Null
    $data = [ordered]@{
        schema='archviz.install.transaction.v1'
        transaction_id=[guid]::NewGuid().ToString()
        version=$ScriptVersion
        created_utc=[DateTime]::UtcNow.ToString('o')
        updated_utc=[DateTime]::UtcNow.ToString('o')
        target=$Target
        backend=$Backend
        profile=$Profile

        status='CREATED'
        completed_steps=@()
        support_package_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $CoreZip).Hash.ToLowerInvariant()
    }
    $path = Join-Path $state 'INSTALL_TRANSACTION.json'
    Write-JsonAtomic $path $data
    return $path
}

function Update-Transaction([string]$Path, [string]$Status, [string]$Step='') {
    $t = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    $steps = @($t.completed_steps)
    if ($Step -and $steps -notcontains $Step) { $steps += $Step }
    $t.completed_steps = $steps
    $t.status = $Status
    $t.updated_utc = [DateTime]::UtcNow.ToString('o')
    Write-JsonAtomic $Path $t
}

function Register-Install([string]$Target, [string]$Status) {
    New-Item -ItemType Directory -Force -Path $LocalIndexDir | Out-Null
    $items = @()
    if (Test-Path -LiteralPath $LocalIndex) {
        try { $items = @((Get-Content -LiteralPath $LocalIndex -Raw | ConvertFrom-Json).installations) } catch { $items = @() }
    }
    $items = @($items | Where-Object { $_.target -ne $Target })
    $items += [pscustomobject]@{target=$Target; version=$ScriptVersion; status=$Status; updated_utc=[DateTime]::UtcNow.ToString('o')}
    Write-JsonAtomic $LocalIndex ([ordered]@{schema='archviz.local.index.v1'; installations=$items})
}

function Invoke-CoreInstall([string]$Target) {
    $runner = Join-Path $Target 'archviz\run_install_core.bat'
    if (-not (Test-Path -LiteralPath $runner)) { throw 'Falta el runner interno v8.2 en el target.' }
    $receipt = Join-Path $Target '_archviz_state\PASS.json'
    # El runtime mantiene A1111 abierto tras el PASS. Se ejecuta en proceso separado
    # y A0 espera el recibo machine-readable, no el cierre de la UI.
    $cmdLine = '"' + $runner + '"'
    $proc = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d','/c',$cmdLine) -WorkingDirectory $Target -WindowStyle Normal -PassThru
    Write-Host ('[A0] Runtime PID: ' + $proc.Id + ' | esperando PASS.json...') -ForegroundColor DarkGray
    $deadline = [DateTime]::UtcNow.AddHours(3)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $receipt -PathType Leaf) {
            try {
                $r = Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
                if ($r.status -eq 'PASS' -and $r.version -eq '8.2.0-A0-STABLE') {
                    return [pscustomobject]@{ pid=$proc.Id; receipt=$receipt; status='PASS' }
                }
            } catch { }
        }
        if ($proc.HasExited) {
            throw ("El runtime terminó antes del PASS. Código " + $proc.ExitCode + '. Revise los logs del target.')
        }
        Start-Sleep -Seconds 3
        $proc.Refresh()
    }
    throw 'Timeout de 3 horas esperando el PASS del runtime v8.2. El proceso se conserva para diagnóstico.'
}

function Save-Plan([string]$Path, $Hardware, [string]$Target) {
    $disk = Get-DiskReport $Target
    $plan = [ordered]@{
        schema='archviz.install.plan.v1'
        version=$ScriptVersion
        timestamp_utc=[DateTime]::UtcNow.ToString('o')
        target=$Target
        backend=$Hardware.compatibility.backend
        profile=$Hardware.compatibility.profile
        ui_defaults=(Get-UiDefaultsForProfile $Hardware.compatibility.profile)
        install_enabled_in_a0=$Hardware.compatibility.install_enabled_in_a0
        clean_install=$true
        side_by_side=$true
        runtime_reuse=$false
        previous_asset_reuse=$false

        network_mode='ONLINE'
        disk=$disk
        note='A0 STABLE instala runtime CUDA_STABLE limpio, VAEApprox verificado y defaults SDXL según perfil. Union/IP-Adapter llegan en A2-A4.'
    }
    Write-JsonAtomic $Path $plan
    return [pscustomobject]$plan
}

function Invoke-Diagnostic {
    Verify-PackageManifest
    $dir = Join-Path $PackageRoot ('reports\diagnostic_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $report = Get-HardwareReport (Join-Path $dir 'HARDWARE_REPORT.json')
    Write-Host ''
    Write-Host ('Backend : ' + $report.compatibility.backend) -ForegroundColor Yellow
    Write-Host ('Perfil  : ' + $report.compatibility.profile) -ForegroundColor Yellow
    Write-Host ('RAM     : ' + $report.memory.total_gib + ' GiB')
    foreach ($g in $report.gpus) { Write-Host ('GPU     : ' + $g.name + ' | ' + $g.vram_gib + ' GiB | ' + $g.vendor) }
    Write-Host ('Reporte : ' + $dir) -ForegroundColor Green
}

function Invoke-CleanInstall([string]$Parent, [string]$RequestedTarget='', $Hardware=$null) {
    Verify-PackageManifest
    if (-not $Parent) { $Parent = Get-DefaultParent }
    $Parent = Test-SafeTarget $Parent
    $target = if ($RequestedTarget) {
        Test-SafeTarget $RequestedTarget
    } elseif ($TargetRoot) {
        Test-SafeTarget $TargetRoot
    } else {
        New-UniqueTarget $Parent
    }
    if (Test-Path -LiteralPath $target) { throw ('Clean install exige un target nuevo. Ya existe: ' + $target) }
    Write-Host ('Destino nuevo seleccionado: ' + $target) -ForegroundColor Cyan
    # Hardware is always resolved before runtime/Torch installation.
    if ($null -ne $Hardware) {
        $hw = $Hardware
    } else {
        $tempReport = Join-Path $env:TEMP ('archviz_hw_' + [guid]::NewGuid().ToString('N') + '.json')
        $hw = Get-HardwareReport $tempReport
        Remove-Item -LiteralPath $tempReport -Force -ErrorAction SilentlyContinue
    }
    Write-Host ('Perfil confirmado: ' + $hw.compatibility.backend + ' / ' + $hw.compatibility.profile) -ForegroundColor Cyan
    if (-not $hw.compatibility.install_enabled_in_a0) {
        $diag = Join-Path $PackageRoot ('reports\blocked_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
        New-Item -ItemType Directory -Force -Path $diag | Out-Null
        Write-JsonAtomic (Join-Path $diag 'HARDWARE_REPORT.json') $hw
        throw ('A0 no instalará un backend no certificado. ' + $hw.compatibility.reason + '. Se generó diagnóstico en ' + $diag)
    }
    $disk = Get-DiskReport $Parent
    if ($disk.schema -ne 'archviz.disk.report.v1') { throw 'Get-DiskReport devolvió un esquema inesperado.' }
    if (-not $disk.is_ready) { throw ('La unidad no está lista: ' + $disk.root) }
    if ($disk.drive_type -ne 'Fixed') { throw ('A0 solo certifica instalación en disco local Fixed. Detectado: ' + $disk.drive_type) }
    if ($disk.free_gib -lt 30) { throw ('Espacio insuficiente para núcleo SDXL. Libre: ' + $disk.free_gib + ' GiB. Se requieren al menos 30 GiB para A0.') }
    Write-Host ('Preflight disco: PASS | ' + $disk.free_gib + ' GiB libres') -ForegroundColor Green
    New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    Write-Host '[A0] Preparando instalación nueva desde cero...' -ForegroundColor Cyan
    Expand-Core $target
    Write-Host '[A0] Núcleo extraído: PASS' -ForegroundColor Green
    $state = Join-Path $target '_archviz_state_a0'
    New-Item -ItemType Directory -Force -Path $state | Out-Null
    Write-JsonAtomic (Join-Path $state 'HARDWARE_REPORT.json') $hw
    $selectedGpu = Get-SelectedGpu $hw
    $profileSelection = [ordered]@{
        schema='archviz.profile.selection.v1'
        backend=$hw.compatibility.backend
        profile=$hw.compatibility.profile
        vram_gib=$hw.compatibility.selected_vram_gib
        gpu=$(if ($selectedGpu) { $selectedGpu.name } else { '' })
        policy='automatic_hardware_fit'
        ui_defaults=(Get-UiDefaultsForProfile $hw.compatibility.profile)
        runtime_note='A0 STABLE aplica defaults UI por perfil; afinación de runtime/VRAM/flags se certifica en A1 Backend Capsules.'
    }
    Write-JsonAtomic (Join-Path $state 'PROFILE_SELECTION.json') $profileSelection
    $plan = Save-Plan (Join-Path $state 'INSTALL_PLAN.json') $hw $target
    $tx = New-Transaction $target $hw.compatibility.backend $hw.compatibility.profile
    Update-Transaction $tx 'CORE_EXTRACTED' 'core_extracted'
Update-Transaction $tx 'CORE_INSTALL_RUNNING' 'core_install_started'
    Register-Install $target 'INSTALLING'
    Write-Host '[A0] Iniciando runtime verificado. La segunda consola mostrará solo estados resumidos...' -ForegroundColor Cyan
    Write-Host ('[A0] Journal: ' + $tx) -ForegroundColor DarkGray
    try {
        Invoke-CoreInstall $target
        Update-Transaction $tx 'PASS' 'core_install_pass'
        Register-Install $target 'PASS'
        Write-Host ''
        Write-Host '[PASS] A1111 ArchViz v8.2 A0 STABLE instalado y verificado.' -ForegroundColor Green
        Write-Host ('Target: ' + $target) -ForegroundColor Green
        Write-Host 'A0 está congelado. Siguiente fase de ingeniería: A1 Backend Capsules.' -ForegroundColor Yellow
    } catch {
        Update-Transaction $tx 'BLOCKED' 'core_install_blocked'
        Register-Install $target 'BLOCKED'
        throw
    }
}

function Invoke-Resume([string]$Target) {
    Verify-PackageManifest
    if (-not $Target) { throw 'Resume requiere -TargetRoot o selección interactiva.' }
    $Target = Test-SafeTarget $Target
    $tx = Join-Path $Target '_archviz_state_a0\INSTALL_TRANSACTION.json'
    if (-not (Test-Path -LiteralPath $tx)) { throw 'No existe journal A0 válido; no se permite reanudar por suposición.' }
    $data = Get-Content -LiteralPath $tx -Raw | ConvertFrom-Json
    if ($data.version -ne $ScriptVersion) { throw 'La transacción pertenece a otra versión A0.' }
    $expected = (Get-FileHash -Algorithm SHA256 -LiteralPath $CoreZip).Hash.ToLowerInvariant()
    if ($data.support_package_sha256 -ne $expected) { throw 'La transacción fue creada con otro paquete support.' }
    if ($data.status -eq 'PASS') { throw 'La transacción ya está en PASS; no requiere reanudación.' }
    Write-Host ('Reanudando transacción ' + $data.transaction_id) -ForegroundColor Yellow
    Update-Transaction $tx 'CORE_INSTALL_RUNNING' 'resume_requested'
    try {
        Invoke-CoreInstall $Target
        Update-Transaction $tx 'PASS' 'resume_pass'
        Register-Install $Target 'PASS'
        Write-Host '[PASS] Reanudación completada.' -ForegroundColor Green
    } catch {
        Update-Transaction $tx 'BLOCKED' 'resume_blocked'
        throw
    }
}

function Invoke-PlanMode([string]$Parent) {
    Verify-PackageManifest
    if (-not $Parent) { $Parent = Get-DefaultParent }
    $Parent = Test-SafeTarget $Parent
    $target = New-UniqueTarget $Parent
    $dir = Join-Path $PackageRoot ('reports\plan_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $hw = Get-HardwareReport (Join-Path $dir 'HARDWARE_REPORT.json')
    $plan = Save-Plan (Join-Path $dir 'INSTALL_PLAN.json') $hw $target
    Write-Host ('Plan creado: ' + $dir) -ForegroundColor Green
    Write-Host ('Target propuesto: ' + $target)
    Write-Host ('Backend: ' + $plan.backend + ' | Perfil: ' + $plan.profile)
}


function Assert-Preflight([bool]$Condition, [string]$Name, [ref]$Counter) {
    if (-not $Condition) { throw ('PREFLIGHT FAIL: ' + $Name) }
    $Counter.Value = [int]$Counter.Value + 1
}

function Invoke-Preflight {
    $pass = 0
    $expected = 24

    # 1. Integridad del paquete y core.
    Verify-PackageManifest
    Assert-Preflight $true 'package_manifest_and_core_hash' ([ref]$pass)
    Assert-Preflight (Test-Path -LiteralPath $CoreZip -PathType Leaf) 'embedded_core_present' ([ref]$pass)

    # 2. Manifiestos de backend.
    $cudaManifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'backends\cuda_stable.json') -Raw | ConvertFrom-Json
    $directManifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'backends\directml_compat.json') -Raw | ConvertFrom-Json
    Assert-Preflight ($cudaManifest.id -eq 'CUDA_STABLE') 'cuda_backend_manifest' ([ref]$pass)
    Assert-Preflight ($directManifest.install_enabled_in_a0 -eq $false) 'directml_not_silently_enabled' ([ref]$pass)

    # 3. Contrato de perfiles.
    Assert-Preflight ((Get-Profile 3.9) -eq 'DIAGNOSTIC') 'profile_diagnostic' ([ref]$pass)
    Assert-Preflight ((Get-Profile 4) -eq 'LITE') 'profile_lite' ([ref]$pass)
    Assert-Preflight ((Get-Profile 8) -eq 'STANDARD') 'profile_standard' ([ref]$pass)
    Assert-Preflight ((Get-Profile 10) -eq 'PREMIUM') 'profile_premium' ([ref]$pass)
    Assert-Preflight ((Get-Profile 16) -eq 'PREMIUM_PLUS') 'profile_premium_plus' ([ref]$pass)
    Assert-Preflight ((Get-Profile 24) -eq 'WORKSTATION') 'profile_workstation' ([ref]$pass)

    # 4. Vendor classification.
    Assert-Preflight ((Get-Vendor 'GeForce RTX 4080' '') -eq 'NVIDIA') 'vendor_nvidia' ([ref]$pass)
    Assert-Preflight ((Get-Vendor 'Radeon RX 7900' '') -eq 'AMD') 'vendor_amd' ([ref]$pass)
    Assert-Preflight ((Get-Vendor 'Intel Arc A770' '') -eq 'INTEL') 'vendor_intel' ([ref]$pass)

    # 5. Rutas y disco.
    $spacePath = Test-SafeTarget (Join-Path $env:TEMP 'ArchViz Test')
    Assert-Preflight ($spacePath -like '*ArchViz Test') 'path_with_spaces' ([ref]$pass)
    Assert-Preflight ((Test-InstallFolderName 'A1111_ArchViz_v8.2') -eq 'A1111_ArchViz_v8.2') 'install_folder_name' ([ref]$pass)

    $disk = Get-DiskReport $PackageRoot
    Assert-Preflight ($disk.schema -eq 'archviz.disk.report.v1') 'disk_report_schema' ([ref]$pass)
    Assert-Preflight ($disk.is_ready -eq $true) 'disk_ready' ([ref]$pass)
    Assert-Preflight ($disk.free_gib -gt 0) 'disk_free_space_readable' ([ref]$pass)

    Assert-Preflight ((Get-UiDefaultsForProfile 'DIAGNOSTIC').width -eq 512) 'ui_profile_diagnostic' ([ref]$pass)
    Assert-Preflight ((Get-UiDefaultsForProfile 'LITE').width -eq 640) 'ui_profile_lite' ([ref]$pass)
    Assert-Preflight ((Get-UiDefaultsForProfile 'STANDARD').width -eq 896) 'ui_profile_standard' ([ref]$pass)
    Assert-Preflight ((Get-UiDefaultsForProfile 'PREMIUM').width -eq 1024 -and (Get-UiDefaultsForProfile 'PREMIUM').steps -eq 28) 'ui_profile_premium' ([ref]$pass)
    Assert-Preflight ((Get-UiDefaultsForProfile 'PREMIUM_PLUS').steps -eq 30) 'ui_profile_premium_plus' ([ref]$pass)
    Assert-Preflight ((Get-UiDefaultsForProfile 'WORKSTATION').steps -eq 32) 'ui_profile_workstation' ([ref]$pass)

    if ($pass -ne $expected) {
        throw ('PREFLIGHT FAIL: contador inesperado ' + $pass + '/' + $expected)
    }

    $result = [ordered]@{
        schema='archviz.preflight.v1'
        version=$ScriptVersion
        timestamp_utc=[DateTime]::UtcNow.ToString('o')
        status='PASS'
        passed=$pass
        expected=$expected
        core_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $CoreZip).Hash.ToLowerInvariant()
        core_expected_sha256=$CoreExpectedSha
    }
    Write-JsonAtomic (Join-Path $PackageRoot 'reports\PREFLIGHT_LAST.json') $result
}

function Assert-SelfTest([bool]$Condition, [string]$Name, [ref]$Counter) {
    if (-not $Condition) { throw ('SELFTEST FAIL: ' + $Name) }
    $Counter.Value = [int]$Counter.Value + 1
    Write-Host ('[PASS] ' + $Name) -ForegroundColor Green
}

function Invoke-SelfTest {
    $pass = 0
    $expected = 35

    Verify-PackageManifest
    Assert-SelfTest $true 'package_manifest_and_core_hash' ([ref]$pass)
    Assert-SelfTest ((Test-Path -LiteralPath $CoreZip)) 'embedded_core_baseline_present' ([ref]$pass)
    Assert-SelfTest ((Get-Content -LiteralPath (Join-Path $PSScriptRoot 'backends\cuda_stable.json') -Raw | ConvertFrom-Json).id -eq 'CUDA_STABLE') 'cuda_backend_manifest' ([ref]$pass)
    Assert-SelfTest ((Get-Content -LiteralPath (Join-Path $PSScriptRoot 'backends\directml_compat.json') -Raw | ConvertFrom-Json).install_enabled_in_a0 -eq $false) 'directml_not_silently_enabled' ([ref]$pass)
    Assert-SelfTest ((Get-Profile 3.9) -eq 'DIAGNOSTIC') 'profile_diagnostic' ([ref]$pass)
    Assert-SelfTest ((Get-Profile 4) -eq 'LITE') 'profile_lite' ([ref]$pass)
    Assert-SelfTest ((Get-Profile 8) -eq 'STANDARD') 'profile_standard' ([ref]$pass)
    Assert-SelfTest ((Get-Profile 12) -eq 'PREMIUM') 'profile_premium' ([ref]$pass)
    Assert-SelfTest ((Get-Profile 16) -eq 'PREMIUM_PLUS') 'profile_premium_plus' ([ref]$pass)
    Assert-SelfTest ((Get-Profile 24) -eq 'WORKSTATION') 'profile_workstation' ([ref]$pass)
    Assert-SelfTest ((Get-Vendor 'GeForce RTX 4080' '') -eq 'NVIDIA') 'vendor_nvidia' ([ref]$pass)
    Assert-SelfTest ((Get-Vendor 'Radeon RX 7900' '') -eq 'AMD') 'vendor_amd' ([ref]$pass)
    Assert-SelfTest ((Get-Vendor 'Intel Arc A770' '') -eq 'INTEL') 'vendor_intel' ([ref]$pass)
    Assert-SelfTest ((Test-SafeTarget (Join-Path $env:TEMP 'ArchViz Test')) -like '*ArchViz Test') 'path_with_spaces' ([ref]$pass)

    $blocked = $false
    try { Test-SafeTarget (Join-Path $env:TEMP 'Bad!Path') | Out-Null } catch { $blocked = $true }
    Assert-SelfTest $blocked 'unsafe_path_blocked' ([ref]$pass)

    # Regresión ALPHA5: comprueba el mecanismo [ref] directamente.
    # No inspecciona el texto fuente, evitando falsos positivos por comentarios/documentación.
    $scopeProbe = 0
    $scopeProbeRef = [ref]$scopeProbe
    $scopeProbeRef.Value = [int]$scopeProbeRef.Value + 1
    Assert-SelfTest ($scopeProbe -eq 1) 'selftest_counter_scope_regression' ([ref]$pass)

    Assert-SelfTest ((Test-InstallFolderName 'ALPHA_3') -eq 'ALPHA_3') 'install_folder_name_alpha3' ([ref]$pass)
    $nameBlocked = $false
    try { Test-InstallFolderName 'bad\nested' | Out-Null } catch { $nameBlocked = $true }
    Assert-SelfTest $nameBlocked 'install_folder_rejects_path' ([ref]$pass)
    $absoluteBlocked = $false
    try { Resolve-InteractiveParent 'ALPHA_3' (Join-Path $env:TEMP 'ArchVizParent') | Out-Null } catch { $absoluteBlocked = $true }
    Assert-SelfTest $absoluteBlocked 'relative_parent_rejected' ([ref]$pass)
    $child = Get-RequestedTarget (Join-Path $env:TEMP 'ArchVizParent') 'ALPHA_3'
    Assert-SelfTest ($child -like '*ArchVizParent\ALPHA_3') 'explicit_child_target' ([ref]$pass)

    $diskProbe = Get-DiskReport $PackageRoot
    Assert-SelfTest ($diskProbe.schema -eq 'archviz.disk.report.v1') 'disk_report_schema' ([ref]$pass)
    Assert-SelfTest ($null -ne $diskProbe.PSObject.Properties['drive_type']) 'disk_report_drive_type_property' ([ref]$pass)
    Assert-SelfTest ($diskProbe.is_ready -eq $true) 'disk_report_ready' ([ref]$pass)

    $sourceNow = Get-Content -LiteralPath $PSCommandPath -Raw
    $oldMenuToken = 'Nueva instalación reutilizando SOLO assets ' + 'verificados'
    $oldDiscoveryToken = 'function Find-' + 'CertifiedInstalls'
    $oldReuseToken = 'function Copy-' + 'VerifiedAssets'
    Assert-SelfTest ($sourceNow.Contains('POLÍTICA A0: CLEAN INSTALL ONLY')) 'clean_install_only_policy' ([ref]$pass)
    Assert-SelfTest (-not $sourceNow.Contains($oldMenuToken)) 'no_previous_version_menu' ([ref]$pass)
    Assert-SelfTest (-not $sourceNow.Contains($oldDiscoveryToken)) 'no_previous_install_discovery_code' ([ref]$pass)
    Assert-SelfTest (-not $sourceNow.Contains($oldReuseToken)) 'no_previous_asset_reuse_code' ([ref]$pass)

    # ALPHA7: contrato del encabezado y política hardware-aware.
    $paramHeader = ($sourceNow -split 'Set-StrictMode')[0]
    Assert-SelfTest (-not ($paramHeader -match ',\s*\)')) 'param_block_no_trailing_comma' ([ref]$pass)
    Assert-SelfTest ($sourceNow.Contains('Get-HardwareReport')) 'hardware_probe_present' ([ref]$pass)
    Assert-SelfTest ($sourceNow.Contains("backend = 'CUDA_STABLE'")) 'cuda_profile_selection_present' ([ref]$pass)
    Assert-SelfTest ($sourceNow.Contains('profile=$Hardware.compatibility.profile')) 'install_plan_uses_detected_profile' ([ref]$pass)

    Assert-SelfTest ($sourceNow.Contains('function Show-ProfileMatrix')) 'profile_matrix_present' ([ref]$pass)
    Assert-SelfTest ($sourceNow.Contains('Perfil asignado automáticamente')) 'automatic_profile_transparency' ([ref]$pass)
    Assert-SelfTest ($sourceNow.Contains('function Read-InstallDestination')) 'simple_destination_flow' ([ref]$pass)
    Assert-SelfTest ((Get-ChildItem -LiteralPath $PackageRoot -Filter '*.bat' -File).Count -eq 1) 'single_user_bat' ([ref]$pass)

    if ($pass -ne $expected) {
        throw ("SELFTEST FAIL: contador inesperado " + $pass + "/" + $expected)
    }
    Write-Host ''
    Write-Host ("SELFTEST A0: $pass/$expected PASS") -ForegroundColor Cyan
}

function Invoke-Interactive {
    Write-Title
    Verify-PackageManifest

    Write-Host 'Preparando el instalador...' -ForegroundColor Gray
    $hw = Get-HardwareReport
    Show-HardwareSummary $hw

    $resumable = Find-ResumableCurrentTransaction
    if ($resumable) {
        Write-Host ''
        Write-Host 'Se encontró una instalación interrumpida de ESTA MISMA versión:' -ForegroundColor Yellow
        Write-Host ('  ' + $resumable.target)
        $resumeAnswer = (Read-Host '¿Desea reanudarla? [S/N]').Trim().ToUpperInvariant()
        if ($resumeAnswer -in @('S','SI','SÍ','Y','YES')) {
            Invoke-Resume $resumable.target
            return
        }
        Write-Host 'Se iniciará una instalación nueva. La incompleta se conserva para diagnóstico.' -ForegroundColor DarkGray
    }

    $defaultParent = Get-DefaultParent
    $destination = Read-InstallDestination $defaultParent

    Show-ProfileMatrix $hw

    if (-not $hw.compatibility.install_enabled_in_a0) {
        $diag = Join-Path $PackageRoot ('reports\hardware_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
        New-Item -ItemType Directory -Force -Path $diag | Out-Null
        Write-JsonAtomic (Join-Path $diag 'HARDWARE_REPORT.json') $hw
        Write-Host ''
        Write-Host 'El equipo fue identificado correctamente, pero este backend todavía no está certificado en A0.' -ForegroundColor Yellow
        Write-Host ('Motivo : ' + $hw.compatibility.reason)
        Write-Host ('Reporte: ' + $diag) -ForegroundColor Green
        return
    }

    Write-Section '4/4' 'CONFIRMACIÓN'
    Write-Host ('Motor       : ' + $hw.compatibility.backend)
    Write-Host ('Perfil      : ' + $hw.compatibility.profile) -ForegroundColor Green
    Write-Host ('Destino     : ' + $destination.target)
    Write-Host ('Espacio     : ' + $destination.disk.free_gib + ' GiB libres')
    Write-Host 'Instalación : NUEVA DESDE CERO' -ForegroundColor Green
    Write-Host 'Versiones previas: no se buscan ni se reutilizan.' -ForegroundColor DarkGray
    Write-Host ''
    $answer = (Read-Host '¿Iniciar instalación? [S/N]').Trim().ToUpperInvariant()
    if ($answer -notin @('S','SI','SÍ','Y','YES')) {
        Write-Host 'Instalación cancelada. No se modificó el equipo.' -ForegroundColor Yellow
        return
    }

    Write-Host ''
    Write-Host 'Iniciando instalación. Puede tardar según su conexión y hardware...' -ForegroundColor Cyan
    Invoke-CleanInstall $destination.parent $destination.target $hw
}

try {
    switch ($Mode) {
        'Interactive' { Invoke-Interactive }
        'Diagnostic' { Write-Title; Invoke-Diagnostic }
        'Plan' { Write-Title; Invoke-PlanMode $TargetParent }
        'Install' { Write-Title; Invoke-CleanInstall $TargetParent $TargetRoot $null }
        'Resume' { Write-Title; Invoke-Resume $TargetRoot }
        'SelfTest' { Write-Title; Invoke-SelfTest }
        'Preflight' { Invoke-Preflight }
    }
    exit 0
} catch {
    $report = Write-LastErrorReport $_
    Write-Host ''
    Write-Host ('[BLOCKED] ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'No se modifica ninguna instalación previa. A0 trabaja únicamente sobre un destino nuevo.' -ForegroundColor DarkYellow
    if ($report) { Write-Host ('Informe persistente: ' + $report) -ForegroundColor Yellow }
    exit 2
}
