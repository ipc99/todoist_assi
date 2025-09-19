import sqlite3
from datetime import datetime

DB_PATH = "tasks_history.db"

def find_changed_task():
    """
    Sucht nach dem geänderten Aldi Gutschein Task.
    """
    print("SUCHE NACH GEÄNDERTEM TASK")
    print("=" * 40)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Suche nach Tasks mit "Aldi" im Namen
    cursor.execute("SELECT task_id, task_name, first_seen, last_changed FROM tasks WHERE task_name LIKE '%Aldi%'")
    aldi_tasks = cursor.fetchall()
    
    print("Tasks mit 'Aldi' im Namen:")
    for task in aldi_tasks:
        task_id, name, first_seen, last_changed = task
        print(f"  ID: {task_id}")
        print(f"  Name: {name}")
        print(f"  Erstellt: {first_seen}")
        print(f"  Geändert: {last_changed}")
        if first_seen != last_changed:
            print(f"  >>> TASK WURDE GEÄNDERT! <<<")
        print("  ---")
    
    # Alle Tasks wo first_seen != last_changed
    print("\nAlle geänderten Tasks:")
    cursor.execute("SELECT task_id, task_name, first_seen, last_changed FROM tasks WHERE first_seen != last_changed")
    changed_tasks = cursor.fetchall()
    
    if changed_tasks:
        for task in changed_tasks:
            task_id, name, first_seen, last_changed = task
            print(f"  ID: {task_id} - {name}")
            print(f"    Erstellt: {first_seen}, Geändert: {last_changed}")
    else:
        print("  Keine geänderten Tasks gefunden.")
    
    conn.close()

if __name__ == "__main__":
    find_changed_task()
