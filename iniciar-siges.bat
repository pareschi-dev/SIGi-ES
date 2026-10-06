@echo off
setlocal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar-siges.ps1" %*
set "exitCode=%ERRORLEVEL%"

if not "%exitCode%"=="0" (
    echo.
    echo O SIG-ES nao foi iniciado. Confira os requisitos e a mensagem de erro acima.
    pause
)

exit /b %exitCode%
