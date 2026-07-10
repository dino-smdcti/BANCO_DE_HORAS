-- Migration: Reset auto-increment sequences for all tables
-- Run this on your Neon PostgreSQL database if you encounter
-- "duplicate key value violates unique constraint" errors.
--
-- Usage:
--   psql "$DATABASE_URL" -f MIGRATIONS.sql

SELECT setval('work_schedules_id_seq',   COALESCE((SELECT MAX(id) FROM work_schedules),   0));
SELECT setval('users_id_seq',            COALESCE((SELECT MAX(id) FROM users),            0));
SELECT setval('daily_pontos_id_seq',     COALESCE((SELECT MAX(id) FROM daily_pontos),     0));
SELECT setval('journey_types_id_seq',    COALESCE((SELECT MAX(id) FROM journey_types),    0));
SELECT setval('audit_logs_id_seq',       COALESCE((SELECT MAX(id) FROM audit_logs),       0));
SELECT setval('correction_requests_id_seq', COALESCE((SELECT MAX(id) FROM correction_requests), 0));
SELECT setval('notifications_id_seq',    COALESCE((SELECT MAX(id) FROM notifications),    0));
SELECT setval('vacations_id_seq',        COALESCE((SELECT MAX(id) FROM vacations),        0));
