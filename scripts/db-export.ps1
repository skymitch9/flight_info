# Export the flight tracker database to a SQL dump file.
# Usage: .\scripts\db-export.ps1
# Output: db-snapshots\flight_tracker_YYYY-MM-DD.sql

$SnapshotDir = "db-snapshots"
$Timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$Filename = "$SnapshotDir\flight_tracker_$Timestamp.sql"

if (-not (Test-Path $SnapshotDir)) {
    New-Item -ItemType Directory -Path $SnapshotDir | Out-Null
}

Write-Host "Exporting database to $Filename..." -ForegroundColor Cyan
docker-compose exec -T db pg_dump -U postgres flight_tracker > $Filename

if ($LASTEXITCODE -eq 0) {
    $Size = (Get-Item $Filename).Length / 1KB
    Write-Host "✓ Export complete: $Filename ($([math]::Round($Size, 1)) KB)" -ForegroundColor Green
    Write-Host ""
    Write-Host "To import on another machine:" -ForegroundColor Yellow
    Write-Host "  1. git pull (to get the snapshot)"
    Write-Host "  2. docker-compose up -d db"
    Write-Host "  3. .\scripts\db-import.ps1 $Filename"
} else {
    Write-Host "✗ Export failed" -ForegroundColor Red
    exit 1
}
