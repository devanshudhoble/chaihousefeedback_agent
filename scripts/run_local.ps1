$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
$env:UV_CACHE_DIR = Join-Path $repoRoot ".uv-cache"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $repoRoot ".uv-python"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

$lanAddress = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
    Sort-Object -Property InterfaceMetric |
    Select-Object -First 1 -ExpandProperty IPAddress

if (-not $lanAddress) {
    $lanAddress = ipconfig | Select-String -Pattern 'IPv4 Address' |
        ForEach-Object { $_.ToString().Split(':')[-1].Trim() } |
        Where-Object { $_ -and $_ -notlike "127.*" -and $_ -notlike "169.254.*" } |
        Select-Object -First 1
}

if ($lanAddress -and -not $env:APP_PUBLIC_URL) {
    $env:APP_PUBLIC_URL = "http://$lanAddress`:8000"
}

Write-Host "Chai House dashboard: http://127.0.0.1:8000/"
if ($env:APP_PUBLIC_URL) {
    Write-Host "Phone / QR URL: $($env:APP_PUBLIC_URL)/feedback"
} else {
    Write-Host "No LAN address detected; the QR will use 127.0.0.1. Set APP_PUBLIC_URL for phone scanning."
}
Write-Host "Press Ctrl+C to stop the local prototype."

uv run --python 3.11 uvicorn app.main:app --host 0.0.0.0 --port 8000
