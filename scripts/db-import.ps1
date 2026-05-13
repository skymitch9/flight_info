# Import a database snapshot into the flight tracker.
# Usage: .\scripts\db-import.ps1 db-snapshots\flight_tracker_2026-05-12.sql

param(
    [Parameter(Mandatory=$false)]
    [string]$SnapshotFile
)

if (-not $SnapshotFile) {
    Write-Host "Usage: .\scripts\db-import.ps1 <path-to-sql-file>" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Available snapshots:" -ForegroundColor Cyan
    Get-ChildItem "db-snapshots\*.sql" -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "  $($_.Name) ($([math]::Round($_.Length / 1KB, 1)) KB)"
    }
    if (-not (Test-Path "db-snapshots\*.sql")) {
        Write-Host "  (none found)"
    }
    exit 1
}

if (-not (Test-Path $SnapshotFile)) {
    Write-Host "✗ File not found: $SnapshotFile" -ForegroundColor Red
    exit 1
}

Write-Host "Importing $SnapshotFile..." -ForegroundColor Cyan
Write-Host "⚠ This will REPLACE all existing data in the database." -ForegroundColor Yellow
$confirm = Read-Host "Continue? (y/N)"

if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "Cancelled."
    exit 0
}

# Drop and recreate the database
docker-compose exec -T db psql -U postgres -c "DROP DATABASE IF EXISTS flight_tracker;"
docker-compose exec -T db psql -U postgres -c "CREATE DATABASE flight_tracker;"

# Import the snapshot
Get-Content $SnapshotFile | docker-compose exec -T db psql -U postgres flight_tracker

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Import complete. Restart the app:" -ForegroundColor Green
    Write-Host "  docker-compose restart app"
} else {
    Write-Host "✗ Import failed" -ForegroundColor Red
    exit 1
}
