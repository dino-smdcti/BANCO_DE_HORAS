ALTER TABLE daily_pontos ADD COLUMN arrival_late_excused BOOLEAN DEFAULT FALSE;
ALTER TABLE daily_pontos ADD COLUMN lunch_start_late_excused BOOLEAN DEFAULT FALSE;
ALTER TABLE daily_pontos ADD COLUMN lunch_end_late_excused BOOLEAN DEFAULT FALSE;
ALTER TABLE daily_pontos ADD COLUMN departure_early_excused BOOLEAN DEFAULT FALSE;
