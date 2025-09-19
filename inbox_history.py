import requests
import sqlite3
import json
from datetime import datetime, date
import os

# --------------------------
# Konfiguration
# --------------------------
API_TOKEN = "391abfcd2e31d30fe065d9d96d4478144ca21891"
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}
DB_PATH = "tasks_history.db"

# --------------------------
# Datenbank-Funktionen
# --------------------------
def init_database():
    """
    Erstellt die SQLite-Datenbank und die Tasks-Tabelle, falls sie nicht existiert.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY,
            task_name TEXT NOT NULL,
            first_seen DATE NOT NULL,
            last_changed DATE NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"Datenbank '{DB_PATH}' initialisiert.")

def get_db_tasks():
    """
    Ruft alle Tasks aus der Datenbank ab.
    Gibt ein Dictionary zurück: {task_id: {'name': name, 'first_seen': date, 'last_changed': date}}
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT task_id, task_name, first_seen, last_changed FROM tasks')
    rows = cursor.fetchall()
    
    conn.close()
    
    db_tasks = {}
    for row in rows:
        task_id, name, first_seen, last_changed = row
        db_tasks[task_id] = {
            'name': name,
            'first_seen': first_seen,
            'last_changed': last_changed
        }
    
    return db_tasks

def insert_new_task(task_id, task_name):
    """
    Fügt einen neuen Task in die Datenbank ein.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    today = date.today().isoformat()
    
    cursor.execute('''
        INSERT INTO tasks (task_id, task_name, first_seen, last_changed)
        VALUES (?, ?, ?, ?)
    ''', (task_id, task_name, today, today))
    
    conn.commit()
    conn.close()
    print(f"   [NEU] Task hinzugefügt: ID {task_id} - {task_name}")

def update_task_name(task_id, new_name):
    """
    Aktualisiert den Namen eines Tasks und setzt last_changed auf heute.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    today = date.today().isoformat()
    
    cursor.execute('''
        UPDATE tasks 
        SET task_name = ?, last_changed = ?
        WHERE task_id = ?
    ''', (new_name, today, task_id))
    
    conn.commit()
    conn.close()
    print(f"   [GEÄNDERT] Task aktualisiert: ID {task_id} - {new_name}")

def delete_task(task_id):
    """
    Entfernt einen Task aus der Datenbank.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Hole den Namen für die Ausgabe
    cursor.execute('SELECT task_name FROM tasks WHERE task_id = ?', (task_id,))
    result = cursor.fetchone()
    name = result[0] if result else "Unbekannt"
    
    cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
    
    conn.commit()
    conn.close()
    print(f"   [ENTFERNT] Task gelöscht: ID {task_id} - {name}")

def days_since_date(date_string):
    """
    Berechnet die Anzahl Tage seit einem gegebenen Datum.
    """
    try:
        task_date = datetime.strptime(date_string, '%Y-%m-%d').date()
        today = date.today()
        return (today - task_date).days
    except:
        return 0

# --------------------------
# Todoist API-Funktionen
# --------------------------
def get_projects():
    """
    Ruft alle Projekte ab und gibt sie zurück.
    """
    url = "https://api.todoist.com/rest/v2/projects"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Fehler beim Abrufen der Projekte: {response.status_code}")
            return []
    except Exception as e:
        print(f"Fehler beim Abrufen der Projekte: {e}")
        return []

def get_inbox_project_id():
    """
    Findet die Projekt-ID des Posteingangs (Inbox).
    """
    projects = get_projects()
    
    for project in projects:
        if project.get('is_inbox_project', False):
            return project['id']
    
    if projects:
        return projects[0]['id']
    
    return None

def get_inbox_todos():
    """
    Ruft alle aktiven (nicht erledigten) Todos aus dem Posteingang ab.
    """
    inbox_id = get_inbox_project_id()
    
    if not inbox_id:
        print("Konnte Posteingang nicht finden!")
        return []
    
    # Nur aktive Tasks abrufen (is_completed=false ist Standard)
    url = f"https://api.todoist.com/rest/v2/tasks"
    params = {'project_id': inbox_id}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code != 200:
            print(f"Fehler beim Abrufen der Aufgaben: {response.status_code}")
            return []
        
        return response.json()
        
    except Exception as e:
        print(f"Fehler beim Abrufen der Aufgaben: {e}")
        return []

# --------------------------
# Hauptlogik
# --------------------------
def sync_tasks():
    """
    Synchronisiert Todoist-Tasks mit der lokalen Datenbank.
    """
    print("=" * 80)
    print("TASK-SYNCHRONISATION")
    print("=" * 80)
    
    # Aktuelle Tasks aus Todoist abrufen
    todoist_tasks = get_inbox_todos()
    print(f"Todoist Tasks geladen: {len(todoist_tasks)}")
    
    # Bestehende Tasks aus DB abrufen
    db_tasks = get_db_tasks()
    print(f"DB Tasks geladen: {len(db_tasks)}")
    
    # Set der aktuellen Todoist Task-IDs
    current_task_ids = set()
    
    print("\nSynchronisation:")
    
    # Durch alle Todoist-Tasks gehen
    for task in todoist_tasks:
        task_id = int(task.get('id'))  # Sicherstellen, dass task_id ein Integer ist
        task_name = task.get('content', 'Unbekannt')
        current_task_ids.add(task_id)
        
        if task_id not in db_tasks:
            # Neuer Task
            insert_new_task(task_id, task_name)
        else:
            # Existierender Task - prüfen ob Name geändert
            if db_tasks[task_id]['name'] != task_name:
                update_task_name(task_id, task_name)
            # Wenn Name gleich ist, nichts tun
    
    # Tasks aus DB entfernen, die nicht mehr in Todoist existieren
    db_task_ids = set(db_tasks.keys())
    deleted_task_ids = db_task_ids - current_task_ids
    
    for task_id in deleted_task_ids:
        delete_task(task_id)
    
    print(f"\nSynchronisation abgeschlossen!")
    print(f"- Aktive Tasks in Todoist: {len(current_task_ids)}")
    print(f"- Neue Tasks: {len(current_task_ids - db_task_ids)}")
    print(f"- Geänderte Tasks: wird während Sync angezeigt")
    print(f"- Entfernte Tasks: {len(deleted_task_ids)}")

def show_inbox_with_history():
    """
    Zeigt die Posteingang-Tasks mit Historie-Informationen an.
    """
    print("\n" + "=" * 80)
    print("POSTEINGANG MIT HISTORIE")
    print("=" * 80)
    
    # Aktuelle Tasks aus Todoist
    tasks = get_inbox_todos()
    
    if not tasks:
        print("Keine Tasks im Posteingang gefunden.")
        return
    
    # Historie-Daten aus DB
    db_tasks = get_db_tasks()
    
    print(f"\nTodos im Posteingang ({len(tasks)} Aufgaben):")
    print("-" * 80)
    
    for i, task in enumerate(tasks, 1):
        task_id_raw = task.get('id')
        task_id = int(task_id_raw) if task_id_raw else 0
        content = task.get('content', 'Unbekannte Aufgabe')
        
        # Datum für die Anzeige ermitteln
        display_date = "Unbekannt"
        if task_id in db_tasks:
            first_seen = db_tasks[task_id]['first_seen']
            last_changed = db_tasks[task_id]['last_changed']
            
            # Verwende das relevante Datum:
            # - Bei Änderungen: last_changed (zeigt wann zuletzt geändert)
            # - Ohne Änderungen: first_seen (zeigt Erstellungsdatum)
            relevant_date = last_changed if first_seen != last_changed else first_seen
            
            try:
                date_obj = datetime.strptime(relevant_date, '%Y-%m-%d')
                display_date = date_obj.strftime('%d.%m.%Y')
            except:
                display_date = relevant_date
        
        print(f"{i:2d}. {display_date} - {content}")
    
    print("-" * 80)
    
    # Statistik über "alte" Tasks
    if db_tasks:
        old_tasks = []
        for task_id, data in db_tasks.items():
            days = days_since_date(data['last_changed'])
            if days > 30:  # Mehr als 30 Tage unverändert
                old_tasks.append((task_id, data['name'], days))
        
        if old_tasks:
            print(f"\n⚠️  Tasks ohne Änderung > 30 Tage ({len(old_tasks)}):")
            old_tasks.sort(key=lambda x: x[2], reverse=True)  # Nach Tagen sortieren
            for task_id, name, days in old_tasks[:10]:  # Top 10
                print(f"   - {name} ({days} Tage)")

# --------------------------
# Hauptprogramm
# --------------------------
if __name__ == "__main__":
    print("Todoist Task-Historie-Manager")
    print("=" * 40)
    
    # Datenbank initialisieren
    init_database()
    
    # Tasks synchronisieren
    sync_tasks()
    
    # Posteingang mit Historie anzeigen
    show_inbox_with_history()
