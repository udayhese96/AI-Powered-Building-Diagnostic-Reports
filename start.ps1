# DDR Report Generator — Startup Script
# Run this script to start both the FastAPI server and Streamlit UI
# Usage: .\start.ps1

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  DDR Report Generator - Startup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check .env exists
if (-Not (Test-Path ".env")) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    Write-Host "  Please create a .env file with your OPENAI_API_KEY."
    Write-Host "  Example: Copy-Item .env.example .env"
    exit 1
}

# Check Python available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found in PATH." -ForegroundColor Red
    exit 1
}

# Check key packages
Write-Host "Checking dependencies..." -ForegroundColor Yellow
$packages = @("fastapi", "uvicorn", "streamlit", "fitz", "openai", "docx")
foreach ($pkg in $packages) {
    $check = python -c "import $pkg" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Missing: $pkg — run: pip install -r requirements.txt" -ForegroundColor Red
    } else {
        Write-Host "  OK: $pkg" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Starting FastAPI server on http://localhost:8000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit -Command `"cd 'd:\Coding Area\DDR Report Genrator'; uvicorn server:app --reload --port 8000`""

Start-Sleep -Seconds 3

Write-Host "Starting Streamlit UI on http://localhost:8501 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit -Command `"cd 'd:\Coding Area\DDR Report Genrator'; streamlit run app.py --server.port 8501`""

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Both services started!" -ForegroundColor Green
Write-Host "  FastAPI  → http://localhost:8000" -ForegroundColor Green
Write-Host "  FastAPI Docs → http://localhost:8000/docs" -ForegroundColor Green
Write-Host "  Streamlit → http://localhost:8501" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
