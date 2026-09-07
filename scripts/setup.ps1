$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".venv")) {
    py -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

python -m card_scanner.cli init-db
python -m card_scanner.cli demo
