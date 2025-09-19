import sqlite3
from datetime import datetime

DB_PATH = "tasks_history.db"

def inspect_database():
    """
    Zeigt den Inhalt der Datenbank an.
    """
    print("DATENBANK-INSPEKTION")
    print("=" * 50)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Anzahl Tasks
    cursor.execute('SELECT COUNT(*) FROM tasks')
    count = cursor.fetchone()[0]
    print(f"Gesamt Anzahl Tasks in DB: {count}")
    
    # Erste 5 Tasks anzeigen
    print(f"\nErste 5 Tasks:")
    cursor.execute('SELECT task_id, task_name, first_seen, last_changed FROM tasks LIMIT 5')
    tasks = cursor.fetchall()
    
    for task in tasks:
        task_id, name, first_seen, last_changed = task
        print(f"  ID: {task_id}")
        print(f"  Name: {name}")
        print(f"  Erstellt: {first_seen}")
        print(f"  Geändert: {last_changed}")
        print("  ---")
    
    # Datum-Statistiken
    print(f"\nDatum-Statistiken:")
    cursor.execute('SELECT first_seen, COUNT(*) as count FROM tasks GROUP BY first_seen ORDER BY first_seen')
    date_stats = cursor.fetchall()
    
    for date_str, count in date_stats:
        print(f"  {date_str}: {count} Tasks")
    
    conn.close()

if __name__ == "__main__":
    inspect_database()
