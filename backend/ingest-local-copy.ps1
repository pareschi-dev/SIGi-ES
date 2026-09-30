[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Root,
    [string]$DatabaseName = 'SIG-SAMF',
    [string]$DatabaseUser = 'junior.pareschi',
    [string]$HostName = 'localhost',
    [ValidateRange(1, 65535)]
    [int]$Port = 5432
)

$ErrorActionPreference = 'Stop'
$resolvedRoot = (Resolve-Path -LiteralPath $Root -ErrorAction Stop).Path
if (-not (Test-Path -LiteralPath $resolvedRoot -PathType Container)) {
    throw 'Root must be an existing directory.'
}

$securePassword = Read-Host 'Digite a senha PostgreSQL (entrada oculta)' -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
$passwordText = $null
$previousDatabaseUrl = $env:SIGES_DATABASE_URL

try {
    $passwordText = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    $safeUser = [Uri]::EscapeDataString($DatabaseUser)
    $safePassword = [Uri]::EscapeDataString($passwordText)
    $safeHost = [Uri]::EscapeDataString($HostName)
    $safeDatabase = [Uri]::EscapeDataString($DatabaseName)
    $env:SIGES_DATABASE_URL = "postgresql+psycopg://${safeUser}:${safePassword}@${safeHost}:$Port/${safeDatabase}"

    Push-Location $PSScriptRoot
    try {
        & '..\.venv\Scripts\python.exe' -m app.pg_preflight
        if ($LASTEXITCODE -ne 0) {
            throw 'PostgreSQL preflight failed; historical ingestion was not started.'
        }
        & '..\.venv\Scripts\python.exe' -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) {
            throw 'Database migration failed; historical ingestion was not started.'
        }
        & '..\.venv\Scripts\python.exe' -u -m app.ingest_local_copy $resolvedRoot
        if ($LASTEXITCODE -ne 0) {
            throw 'Historical ingestion completed with errors; review aggregate report.'
        }
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
}
