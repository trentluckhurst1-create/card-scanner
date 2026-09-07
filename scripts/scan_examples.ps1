$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& .\.venv\Scripts\Activate.ps1

# Cherry — one page / conservative V1 pull
python -m card_scanner.cli scan-cherry --sport NFL --limit 50
python -m card_scanner.cli scan-cherry --sport NBA --limit 50
python -m card_scanner.cli scan-cherry --sport MLB --limit 50
python -m card_scanner.cli scan-cherry --sport AFL --limit 50

# eBay examples — uncomment after credentials are added to .env
# python -m card_scanner.cli scan-ebay --sport NFL --query "rookie auto /50" --limit 100
# python -m card_scanner.cli scan-ebay --sport NBA --query "rookie auto /25" --limit 100
# python -m card_scanner.cli scan-ebay --sport MLB --query "1st Bowman auto /50" --limit 100
# python -m card_scanner.cli scan-ebay --sport AFL --query "Select AFL rookie auto" --limit 100
