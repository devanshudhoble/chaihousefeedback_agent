$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "Starting the token-protected Google Forms intake on 127.0.0.1:8001."
Write-Host "This service exposes only POST /webhooks/google-form."
Write-Host "Run the Cloudflare Tunnel against http://127.0.0.1:8001 in a separate terminal."

& .\.venv\Scripts\python.exe -m uvicorn app.intake:app --host 127.0.0.1 --port 8001
