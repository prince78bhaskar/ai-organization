$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root "venv\Scripts\python.exe"
$Activate = Join-Path $Root "venv\Scripts\Activate.ps1"
$Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue

if (-not (Test-Path $Python) -or -not (Test-Path $Activate)) {
    throw "Python environment not found at $Python. Create it and install backend\requirements.txt first."
}
if (-not $Npm) {
    throw "npm was not found. Install Node.js, then try again."
}
if (-not (Test-Path (Join-Path $Root "frontend\node_modules"))) {
    throw "Frontend dependencies are missing. Run 'npm install' from the frontend folder first."
}

. $Activate
$Backend = Start-Process -FilePath $Python `
    -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $Root -PassThru
$Frontend = Start-Process -FilePath $env:ComSpec `
    -ArgumentList @("/c", "npm.cmd run dev") `
    -WorkingDirectory (Join-Path $Root "frontend") -PassThru

Write-Host "AI Organization API: http://127.0.0.1:8000 (PID $($Backend.Id))"
Write-Host "AI Organization UI:  http://localhost:3000 (PID $($Frontend.Id))"
Write-Host "Close these processes with Stop-Process -Id $($Backend.Id),$($Frontend.Id)"
