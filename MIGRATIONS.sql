-- Database Migration: Add missing columns to support new features
-- Run these commands in your Neon SQL Editor

-- 1. Add anomaly tracking columns to daily_pontos
ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS arrival_late BOOLEAN DEFAULT FALSE;
ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS lunch_start_late BOOLEAN DEFAULT FALSE;
ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS lunch_end_late BOOLEAN DEFAULT FALSE;
ALTER TABLE daily_pontos ADD COLUMN IF NOT EXISTS departure_early BOOLEAN DEFAULT FALSE;

-- 2. Add email notification setting to users
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_notifications_enabled BOOLEAN DEFAULT FALSE;

-- 3. Ensure location_data has enough space (if it was created as a smaller VARCHAR)
ALTER TABLE daily_pontos ALTER COLUMN location_data TYPE TEXT;
