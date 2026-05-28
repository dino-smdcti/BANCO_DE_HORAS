import sqlite3

def run_migration():
    conn = sqlite3.connect('banco_de_horas.db')
    cursor = conn.cursor()
    
    try:
        # Add columns to work_schedules
        cursor.execute("ALTER TABLE work_schedules ADD COLUMN schedule_type TEXT DEFAULT 'standard'")
        cursor.execute("ALTER TABLE work_schedules ADD COLUMN rotation_start_date DATE")
        
        # Add columns to journey_types
        cursor.execute("ALTER TABLE journey_types ADD COLUMN schedule_type TEXT DEFAULT 'standard'")
        
        conn.commit()
        print("Schema update successful.")
    except sqlite3.OperationalError as e:
        print(f"Error (column might already exist): {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
