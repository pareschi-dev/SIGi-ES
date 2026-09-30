[CmdletBinding()]
param(
    [string]$DatabaseName = 'SIG-SAMF',
    [string]$DatabaseUser = 'junior.pareschi',
    [string]$HostName = 'localhost',
    [ValidateRange(1, 65535)]
    [int]$Port = 5432,
    [string]$MonitorRoot = ''
)

$ErrorActionPreference = 'Stop'
$securePassword = Read-Host 'Digite a senha PostgreSQL (entrada oculta)' -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
$passwordText = $null
$previousDatabaseUrl = $env:SIGES_DATABASE_URL
$previousMonitorRoot = $env:SIGES_MONITOR_ROOT

try {
    $passwordText = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    $safeUser = [Uri]::EscapeDataString($DatabaseUser)
    $safePassword = [Uri]::EscapeDataString($passwordText)
    $safeHost = [Uri]::EscapeDataString($HostName)
    $safeDatabase = [Uri]::EscapeDataString($DatabaseName)
    $env:SIGES_DATABASE_URL = "postgresql+psycopg://${safeUser}:${safePassword}@${safeHost}:$Port/${safeDatabase}"
    if ($MonitorRoot) {
        $resolvedMonitorRoot = (Resolve-Path -LiteralPath $MonitorRoot -ErrorAction Stop).Path
        if (-not (Test-Path -LiteralPath $resolvedMonitorRoot -PathType Container)) {
            throw 'MonitorRoot must be an existing directory.'
        }
        $env:SIGES_MONITOR_ROOT = $resolvedMonitorRoot
    } else {
        Remove-Item Env:SIGES_MONITOR_ROOT -ErrorAction SilentlyContinue
    }

    Push-Location $PSScriptRoot
    try {
        & '..\.venv\Scripts\python.exe' -m app.pg_preflight
        if ($LASTEXITCODE -ne 0) {
            throw 'PostgreSQL preflight failed; no migration was applied.'
        }

        & '..\.venv\Scripts\python.exe' -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) {
            throw 'SIG-ES migration failed. Review the error without sharing credentials.'
        }

        Write-Output 'Migração concluída. Iniciando API somente local em 127.0.0.1:8000.'
        & '..\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($null -ne $bstr -and $bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    $passwordText = $null
    $safePassword = $null
    $env:SIGES_DATABASE_URL = $previousDatabaseUrl
    $env:SIGES_MONITOR_ROOT = $previousMonitorRoot
}
