#!/bin/bash
# Import a database snapshot into the flight tracker.
# Usage: ./scripts/db-import.sh db-snapshots/flight_tracker_2026-05-12.sql
#
# This will DROP and recreate the database, then load the snapshot.

if [ -z "$1" ]; then
    echo "Usage: ./scripts/db-import.sh <path-to-sql-file>"
    echo ""
    echo "Available snapshots:"
    ls -la db-snapshots/*.sql 2>/dev/null || echo "  (none found)"
    exit 1
fi

SNAPSHOT_FILE="$1"

if [ ! -f "$SNAPSHOT_FILE" ]; then
    echo "✗ File not found: ${SNAPSHOT_FILE}"
    exit 1
fi

echo "Importing ${SNAPSHOT_FILE}..."
echo "⚠ This will REPLACE all existing data in the database."
read -p "Continue? (y/N) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Drop and recreate the database
docker-compose exec -T db psql -U postgres -c "DROP DATABASE IF EXISTS flight_tracker;"
docker-compose exec -T db psql -U postgres -c "CREATE DATABASE flight_tracker;"

# Import the snapshot
docker-compose exec -T db psql -U postgres flight_tracker < "$SNAPSHOT_FILE"

if [ $? -eq 0 ]; then
    echo "✓ Import complete. Restart the app to pick up changes:"
    echo "  docker-compose restart app"
else
    echo "✗ Import failed"
    exit 1
fi
