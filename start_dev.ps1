param(
    [switch]$SoloBackend,
    [switch]$SoloFrontend,
    [switch]$AbrirNavegador
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$logs = Join-Path $env:TEMP "opencode"

function Testing-Puerto($puerto) {
    return [bool](Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue)
}

function Levantar-Backend {
    if (Testing-Puerto 8000) {
        Write-Host "[backend] ya escucha en el puerto 8000 (se omite arranque)"
    }
    else {
        Write-Host "[backend] levantando uvicorn en :8000 ..."
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c cd `"$raiz\backend`" && .venv\Scripts\python.exe -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 > `"$logs\uvicorn.log`" 2>&1" -WindowStyle Hidden
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 1
            if (Testing-Puerto 8000) { break }
        }
    }
    if (Testing-Puerto 8000) {
        Write-Host "[backend] OK -> http://localhost:8000  (log: $logs\uvicorn.log)"
    }
    else {
        Write-Warning "[backend] NO responde en puerto 8000, revisa $logs\uvicorn.log"
    }
}

function Levantar-Frontend {
    if (Testing-Puerto 3000) {
        Write-Host "[frontend] ya escucha en el puerto 3000 (se omite arranque)"
    }
    else {
        Write-Host "[frontend] levantando Nuxt dev en :3000 ..."
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c cd `"$raiz\frontend`" && npm.cmd run dev > `"$logs\nuxt-dev.log`" 2>&1" -WindowStyle Hidden
        for ($i = 0; $i -lt 60; $i++) {
            Start-Sleep -Seconds 1
            if (Testing-Puerto 3000) { break }
        }
    }
    if (Testing-Puerto 3000) {
        Write-Host "[frontend] OK -> http://localhost:3000  (log: $logs\nuxt-dev.log)"
    }
    else {
        Write-Warning "[frontend] NO responde en puerto 3000, revisa $logs\nuxt-dev.log"
    }
}

if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Path $logs -Force | Out-Null }

if (-not $SoloFrontend) { Levantar-Backend }
if (-not $SoloBackend) { Levantar-Frontend }

Write-Host ""
Write-Host "Servicios listos:"
Write-Host "  Frontend  -> http://localhost:3000"
Write-Host "  API       -> http://localhost:8000/docs"
if ($AbrirNavegador) {
    Start-Process "http://localhost:3000"
}