import requests
import json
from datetime import datetime

# --------------------------
# Konfiguration
# --------------------------
API_TOKEN = "391abfcd2e31d30fe065d9d96d4478144ca21891"
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}

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
    Der Posteingang ist normalerweise das Projekt mit is_inbox_project=True
    oder das erste/Standard-Projekt.
    """
    projects = get_projects()
    
    # Suche nach dem Posteingang
    for project in projects:
        if project.get('is_inbox_project', False):
            return project['id']
    
    # Fallback: Erstes Projekt nehmen (meist der Posteingang)
    if projects:
        return projects[0]['id']
    
    return None

def get_inbox_todos():
    """
    Ruft alle Todos aus dem Posteingang ab und gibt sie aus.
    """
    print("Lade Projekte...")
    inbox_id = get_inbox_project_id()
    
    if not inbox_id:
        print("Konnte Posteingang nicht finden!")
        return
    
    print(f"Posteingang gefunden (ID: {inbox_id})")
    
    # Alle Tasks vom Posteingang abrufen
    url = f"https://api.todoist.com/rest/v2/tasks"
    params = {'project_id': inbox_id}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code != 200:
            print(f"Fehler beim Abrufen der Aufgaben: {response.status_code}")
            return
        
        tasks = response.json()
        
        if not tasks:
            print("\n[POSTEINGANG] Der Posteingang ist leer!")
            return
        
        print(f"\n[POSTEINGANG] Todos im Posteingang ({len(tasks)} Aufgaben):")
        print("=" * 80)
        
        for i, task in enumerate(tasks, 1):
            task_id = task.get('id', 'N/A')
            content = task.get('content', 'Unbekannte Aufgabe')
            print(f"{i:2d}. ID: {task_id} - {content}")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"Fehler beim Abrufen der Aufgaben: {e}")

def show_project_overview():
    """
    Zeigt eine Übersicht aller Projekte an (zur Information).
    """
    print("\n[PROJEKTE] Verfuegbare Projekte:")
    projects = get_projects()
    
    for project in projects:
        inbox_marker = " [POSTEINGANG]" if project.get('is_inbox_project', False) else ""
        print(f"   - {project['name']} (ID: {project['id']}){inbox_marker}")

if __name__ == "__main__":
    print("Todoist Posteingang-Viewer")
    print("=" * 30)
    
    # Zeige zuerst eine Projektübersicht
    show_project_overview()
    
    # Dann die Posteingang-Todos
    get_inbox_todos()
