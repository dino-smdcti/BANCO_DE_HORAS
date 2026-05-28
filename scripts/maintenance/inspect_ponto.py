import sqlite3

def check_ponto_notes(user_id, entry_date):
    conn = sqlite3.connect('banco_de_horas.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, entry_date, manager_notes FROM daily_pontos WHERE user_id = ? AND entry_date = ?", (user_id, entry_date))
    row = cursor.fetchone()
    if row:
        print(f"Ponto ID: {row[0]}, Date: {row[1]}, Manager Notes: {row[2]}")
    else:
        print("No record found.")
    conn.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        check_ponto_notes(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python inspect_ponto.py <user_id> <entry_date>")
