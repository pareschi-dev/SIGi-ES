[CmdletBinding()]
param(
    [string]$DatabaseName = 'SIG-SAMF',
    [string]$DatabaseUser = 'junior.pareschi',
    [string]$DatabaseHostName = 'localhost',
    [ValidateRange(1, 65535)]
    [int]$DatabasePort = 5432,
    [string]$MonitorRoot = 'C:\2026'
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$backendPath = Join-Path $projectRoot 'backend'
$frontendPath = Join-Path $projectRoot 'frontend'
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$backendScript = Join-Path $backendPath 'run-local.ps1'
$frontendPackage = Join-Path $frontendPath 'package.json'

foreach ($requiredPath in @($backendScript, $frontendPackage, $pythonPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Arquivo obrigatório não encontrado: $requiredPath"
    }
}

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'npm não foi encontrado. Instale Node.js 20 ou superior e abra um novo PowerShell.'
}

if (-not (Test-Path -LiteralPath (Join-Path $frontendPath 'node_modules') -PathType Container)) {
    Write-Host 'Dependências do frontend ausentes; executando npm install...'
    Push-Location $frontendPath
    try {
        & npm.cmd install
        if ($LASTEXITCODE -ne 0) {
            throw 'npm install falhou; o frontend não foi iniciado.'
        }
    }
    finally {
        Pop-Location
    }
}

foreach ($port in @(8000, 5173)) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
        throw "A porta $port já está em uso (PID $($listener.OwningProcess)). Pare o serviço existente para evitar usar uma instância ou banco diferente e execute novamente."
    }
}

if ([string]::IsNullOrWhiteSpace($MonitorRoot)) {
    throw 'O monitoramento é obrigatório. Informe uma raiz local autorizada em -MonitorRoot.'
}
$resolvedMonitorRoot = Resolve-Path -LiteralPath $MonitorRoot -ErrorAction Stop
if (-not (Test-Path -LiteralPath $resolvedMonitorRoot.Path -PathType Container)) {
    throw 'MonitorRoot precisa ser uma pasta existente e explicitamente autorizada.'
}
$MonitorRoot = $resolvedMonitorRoot.Path

function ConvertTo-PowerShellLiteral([string]$Value) {
    return "'" + $Value.Replace("'", "''") + "'"
}

$apiArgs = @(
    '-DatabaseName', (ConvertTo-PowerShellLiteral $DatabaseName),
    '-DatabaseUser', (ConvertTo-PowerShellLiteral $DatabaseUser),
    '-HostName', (ConvertTo-PowerShellLiteral $DatabaseHostName),
    '-Port', $DatabasePort,
    '-MonitorRoot', (ConvertTo-PowerShellLiteral $MonitorRoot)
)

$apiCommand = "Set-Location -LiteralPath $(ConvertTo-PowerShellLiteral $backendPath); & $(ConvertTo-PowerShellLiteral $backendScript) $($apiArgs -join ' ')"
$frontendCommand = "Set-Location -LiteralPath $(ConvertTo-PowerShellLiteral $frontendPath); npm.cmd run dev:ui -- --host 127.0.0.1"

$apiEncoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($apiCommand))
$frontendEncoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($frontendCommand))
$powerShellExe = (Get-Command powershell.exe -ErrorAction Stop).Source

Start-Process -FilePath $powerShellExe -WorkingDirectory $projectRoot -ArgumentList @(
    '-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $apiEncoded
) | Out-Null

Start-Process -FilePath $powerShellExe -WorkingDirectory $projectRoot -ArgumentList @(
    '-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $frontendEncoded
) | Out-Null

Write-Host ''
Write-Host 'SIG-ES iniciado em janelas separadas.' -ForegroundColor Green
Write-Host '1. Na janela da API, digite a senha PostgreSQL no prompt oculto.'
Write-Host '2. Aguarde o preflight, as migrações pendentes e a mensagem de API iniciada.'
Write-Host '3. Acesse a interface em http://127.0.0.1:5173/'
Write-Host '4. A saúde do banco pode ser conferida em http://127.0.0.1:8000/api/v1/health'
Write-Host "Monitor de arquivos: ativo em $MonitorRoot."
Write-Host 'Para encerrar, pressione Ctrl+C nas janelas da API e do frontend.'
