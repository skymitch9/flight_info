#!/bin/bash
# Export the flight tracker database to a SQL dump file.
# Usage: ./scripts/db-export.sh
# Output: db-snapshots/flight_tracker_YYYY-MM-DD.sql

SNAPSHOT_DIR="db-snapshots"
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
FILENAME="${SNAPSHOT_DIR}/flight_tracker_${TIMESTAMP}.sql"

mkdir -p "$SNAPSHOT_DIR"

echo "Exporting database to ${FILENAME}..."
docker-compose exec -T db pg_dump -U postgres flight_tracker > "$FILENAME"

if [ $? -eq 0 ]; then
    echo "✓ Export complete: ${FILENAME}"
    echo "  Size: $(du -h "$FILENAME" | cut -f1)"
    echo ""
    echo "To import on another machine:"
    echo "  1. git pull (to get the snapshot)"
    echo "  2. docker-compose up -d db"
    echo "  3. ./scripts/db-import.sh ${FILENAME}"
else
    echo "✗ Export failed"
    exit 1
fi
