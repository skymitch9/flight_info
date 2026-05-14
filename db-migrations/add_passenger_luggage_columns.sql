-- Migration: Add passenger count and luggage columns to trip_requests
-- Description: Adds passenger_count, carry_on_bags, and checked_bags columns
--              with appropriate defaults and CHECK constraints.
-- Requirements: 1.2, 2.3, 2.4, 7.1, 7.2, 7.3
--
-- For existing databases only. New deployments get these columns via
-- SQLAlchemy's create_all() in app/database.py.
--
-- Usage: psql -d <database> -f db-migrations/add_passenger_luggage_columns.sql

BEGIN;

-- Add passenger_count column (default 1 for backward compatibility)
ALTER TABLE trip_requests
  ADD COLUMN IF NOT EXISTS passenger_count INTEGER NOT NULL DEFAULT 1;

-- Add carry_on_bags column (default 1 for backward compatibility)
ALTER TABLE trip_requests
  ADD COLUMN IF NOT EXISTS carry_on_bags INTEGER NOT NULL DEFAULT 1;

-- Add checked_bags column (default 0 for backward compatibility)
ALTER TABLE trip_requests
  ADD COLUMN IF NOT EXISTS checked_bags INTEGER NOT NULL DEFAULT 0;

-- Add CHECK constraints for valid ranges
-- Using DO blocks to avoid errors if constraints already exist

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chk_passenger_count_range'
  ) THEN
    ALTER TABLE trip_requests
      ADD CONSTRAINT chk_passenger_count_range
      CHECK (passenger_count BETWEEN 1 AND 9);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chk_carry_on_bags_range'
  ) THEN
    ALTER TABLE trip_requests
      ADD CONSTRAINT chk_carry_on_bags_range
      CHECK (carry_on_bags BETWEEN 0 AND 2);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chk_checked_bags_range'
  ) THEN
    ALTER TABLE trip_requests
      ADD CONSTRAINT chk_checked_bags_range
      CHECK (checked_bags BETWEEN 0 AND 5);
  END IF;
END $$;

COMMIT;
