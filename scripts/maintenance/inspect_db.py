import sqlite3

def check_schema():
    conn = sqlite3.connect('banco_de_horas.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(work_schedules)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"Columns in work_schedules: {columns}")
    conn.close()

if __name__ == "__main__":
    check_schema()
