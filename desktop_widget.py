import tkinter as tk
from tkinter import ttk
import requests
import sqlite3
import json
from datetime import datetime, date
import threading
import time
import os
import sys
import psutil  # Für Prozess-Management

# --------------------------
# Single-Instance Check
# --------------------------
def check_single_instance():
    """
    Prüft ob bereits eine Instanz des Desktop-Widgets läuft.
    """
    script_name = "desktop_widget.py"
    current_pid = os.getpid()
    
    running_instances = []
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Prüfe auf Python-Prozesse
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    cmdline = proc.info['cmdline']
                    if cmdline and len(cmdline) > 1:
                        # Prüfe ob desktop_widget.py in der Kommandozeile steht
                        full_cmdline = ' '.join(cmdline)
                        if script_name in full_cmdline and proc.info['pid'] != current_pid:
                            running_instances.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        if running_instances:
            print(f"INFO: Andere Python-Prozesse gefunden: {running_instances}")
            print("Starte trotzdem - möglicherweise andere Scripts.")
        else:
            print("Keine andere Desktop-Widget-Instanz gefunden.")
            
    except Exception as e:
        print(f"Warnung: Single-Instance-Check fehlgeschlagen: {e}")
        print("Starte trotzdem...")

# --------------------------
# Konfiguration
# --------------------------
API_TOKEN = "391abfcd2e31d30fe065d9d96d4478144ca21891"
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}
DB_PATH = "tasks_history.db"
UPDATE_INTERVAL = 300  # 5 Minuten in Sekunden

class TaskDesktopWidget:
    def __init__(self):
        self.root = tk.Tk()
        
        # Auto-Hide System
        self.visible_alpha = 0.6  # 60% Transparenz wenn sichtbar
        self.is_visible = False
        self.mouse_in_corner_start = None
        self.hide_timer = None
        self.corner_size = 50  # Pixel-Bereich für obere rechte Ecke
        self.mouse_over_widget = False
        self.mouse_left_widget_time = None
        self.shutdown_flag = False  # Flag für sauberes Beenden
        
        self.setup_window()
        self.setup_ui()
        self.start_update_thread()
        self.start_mouse_tracking()
        
    def setup_window(self):
        """
        Konfiguriert das Hauptfenster als transparentes Desktop-Widget.
        """
        # Fenster-Eigenschaften
        self.root.title("Todoist Tasks")
        
        # Initial unsichtbar
        self.root.attributes('-alpha', 0.0)
        
        # Fenster immer im Vordergrund
        self.root.attributes('-topmost', True)
        
        # Fenster-Rahmen entfernen für cleanes Aussehen
        self.root.overrideredirect(True)
        
        # Hintergrundfarbe (dunkel für bessere Lesbarkeit)
        self.root.configure(bg='#2b2b2b')
        
        # Initiale Größe setzen (wird später dynamisch angepasst)
        self.window_width = 450  # Breiter für längere Texte
        self.window_height = 200  # Initial klein, wird angepasst
        
        # Fenster initial positionieren
        self.position_window()
        
    def position_window(self, task_count=0):
        """
        Positioniert das Fenster oben rechts auf dem Bildschirm mit dynamischer Höhe.
        """
        # Bildschirmgröße ermitteln
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Höhe basierend auf Anzahl Tasks berechnen
        # Jede Zeile ca. 20px + Header (80px) + Footer (40px) + Padding (20px)
        line_height = 20
        header_footer_height = 140
        min_height = 200
        
        calculated_height = header_footer_height + (task_count * line_height)
        self.window_height = max(min_height, min(calculated_height, screen_height - 100))
        
        # Fensterposition berechnen (oben rechts mit etwas Abstand)
        x = screen_width - self.window_width - 20  # 20px vom rechten Rand
        y = 50  # 50px vom oberen Rand
        
        self.root.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")
        
    def setup_ui(self):
        """
        Erstellt die Benutzeroberfläche.
        """
        # Hauptcontainer
        main_frame = tk.Frame(self.root, bg='#2b2b2b')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Titel - als separates Widget für Drag-Funktionalität
        self.title_frame = tk.Frame(main_frame, bg='#2b2b2b')
        self.title_frame.pack(fill=tk.X)
        
        self.title_label = tk.Label(
            self.title_frame, 
            text="📋 Todoist Tasks", 
            font=('Arial', 14, 'bold'),
            bg='#2b2b2b', 
            fg='white'
        )
        self.title_label.pack(side=tk.LEFT, pady=(0, 10))
        
        # Schließen-Button (kleines X oben rechts)
        close_button = tk.Button(
            self.title_frame,
            text="✕",
            command=self.close_app,
            bg='#ff4444',
            fg='white',
            font=('Arial', 10, 'bold'),
            relief=tk.FLAT,
            width=3
        )
        close_button.pack(side=tk.RIGHT)
        
        # Text-Widget für Tasks (ohne Scrollbar, da Fenster angepasst wird)
        self.task_text = tk.Text(
            main_frame,
            bg='#1e1e1e',
            fg='white',
            font=('Consolas', 9),
            relief=tk.FLAT,
            wrap=tk.NONE,  # Kein Zeilenumbruch, da wir Text abschneiden
            state=tk.DISABLED,
            height=1,  # Wird dynamisch angepasst
            width=50   # Feste Breite für konsistente Anzeige
        )
        self.task_text.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # Status-Label
        self.status_label = tk.Label(
            main_frame,
            text="Lade Tasks...",
            font=('Arial', 8),
            bg='#2b2b2b',
            fg='#888888'
        )
        self.status_label.pack(pady=(5, 0))
        
        # Maus-Events für Fenster-Bewegung
        self.setup_mouse_events()
        
    def setup_mouse_events(self):
        """
        Ermöglicht das Ziehen des Fensters nur über die Titelleiste.
        Doppelklick auf Titelleiste blendet Widget aus.
        """
        def start_move(event):
            self.root.x = event.x
            self.root.y = event.y

        def stop_move(event):
            self.root.x = None
            self.root.y = None

        def do_move(event):
            x = (event.x_root - self.root.x)
            y = (event.y_root - self.root.y)
            self.root.geometry(f"+{x}+{y}")
            
        def double_click_hide(event):
            """Versteckt das Widget bei Doppelklick auf Titelleiste."""
            self.manual_hide_widget()

        # Bind mouse events NUR zur Titelleiste (Frame und Label)
        for widget in [self.title_frame, self.title_label]:
            # Drag-Funktionalität
            widget.bind('<Button-1>', start_move)
            widget.bind('<ButtonRelease-1>', stop_move)
            widget.bind('<B1-Motion>', do_move)
            
            # Doppelklick zum Ausblenden
            widget.bind('<Double-Button-1>', double_click_hide)
        
    def close_app(self):
        """
        Schließt die Anwendung ordentlich.
        """
        print("Schließe Desktop-Widget...")
        self.shutdown_flag = True
        
        # Timer stoppen
        if self.hide_timer:
            self.root.after_cancel(self.hide_timer)
        
        # GUI beenden
        self.root.quit()
        self.root.destroy()
        print("Desktop-Widget geschlossen.")
        
    # --------------------------
    # Auto-Hide System
    # --------------------------
    def start_mouse_tracking(self):
        """
        Startet das kontinuierliche Mouse-Tracking.
        """
        def mouse_tracker():
            while not self.shutdown_flag:
                try:
                    self.check_mouse_position()
                    time.sleep(0.1)  # Alle 100ms prüfen
                except:
                    break
        
        mouse_thread = threading.Thread(target=mouse_tracker, daemon=True)
        mouse_thread.start()
        
    def check_mouse_position(self):
        """
        Prüft die Mausposition und aktiviert Widget bei Bedarf.
        """
        try:
            # Mausposition abrufen (Windows-spezifisch)
            import win32gui
            x, y = win32gui.GetCursorPos()
            
            # Bildschirmgröße
            screen_width = self.root.winfo_screenwidth()
            
            # Prüfen ob Maus in oberer rechter Ecke ist
            in_corner = (x >= screen_width - self.corner_size and y <= self.corner_size)
            
            # Prüfen ob Maus über dem Widget ist (wenn Widget sichtbar)
            mouse_over_widget_now = False
            if self.is_visible:
                try:
                    widget_x = self.root.winfo_x()
                    widget_y = self.root.winfo_y()
                    widget_width = self.root.winfo_width()
                    widget_height = self.root.winfo_height()
                    
                    mouse_over_widget_now = (
                        widget_x <= x <= widget_x + widget_width and
                        widget_y <= y <= widget_y + widget_height
                    )
                except:
                    mouse_over_widget_now = False
            
            # Mouse-Over-Widget Status verwalten
            if mouse_over_widget_now != self.mouse_over_widget:
                if mouse_over_widget_now:
                    # Maus ist über Widget gekommen
                    self.on_mouse_enter_widget()
                else:
                    # Maus hat Widget verlassen
                    self.on_mouse_leave_widget()
                    
                self.mouse_over_widget = mouse_over_widget_now
            
            # Corner-Trigger verwalten
            current_time = time.time()
            
            if in_corner:
                if self.mouse_in_corner_start is None:
                    # Maus ist gerade in die Ecke gekommen
                    self.mouse_in_corner_start = current_time
                elif current_time - self.mouse_in_corner_start >= 1.0:
                    # Maus war 1 Sekunde in der Ecke
                    self.show_widget()
                    self.mouse_in_corner_start = None  # Reset
            else:
                # Maus ist nicht in der Ecke
                self.mouse_in_corner_start = None
                
        except ImportError:
            # Fallback ohne win32gui
            pass
        except:
            pass
            
    def on_mouse_enter_widget(self):
        """
        Wird aufgerufen wenn Maus über das Widget kommt.
        """
        if self.is_visible:
            # Hide-Timer stoppen, da Maus über Widget ist
            if self.hide_timer:
                self.root.after_cancel(self.hide_timer)
                self.hide_timer = None
                
    def on_mouse_leave_widget(self):
        """
        Wird aufgerufen wenn Maus das Widget verlässt.
        """
        if self.is_visible:
            self.mouse_left_widget_time = time.time()
            # 1 Sekunde warten nach Mouse-Leave
            self.hide_timer = self.root.after(1000, self.hide_widget)
            
    def show_widget(self):
        """
        Zeigt das Widget für 10 Sekunden an.
        """
        if not self.is_visible:
            self.is_visible = True
            self.root.attributes('-alpha', self.visible_alpha)
            
            # Alten Hide-Timer stoppen falls vorhanden
            if self.hide_timer:
                self.root.after_cancel(self.hide_timer)
            
            # Neuen Hide-Timer für 10 Sekunden starten
            self.hide_timer = self.root.after(10000, self.hide_widget)
            
    def hide_widget(self):
        """
        Versteckt das Widget nur wenn Maus nicht darüber ist (Timer-Aufruf).
        """
        # Doppelt prüfen ob Maus wirklich nicht mehr über Widget ist
        if not self.mouse_over_widget:
            self.is_visible = False
            self.root.attributes('-alpha', 0.0)
            self.hide_timer = None
        # Wenn Maus noch über Widget ist, nicht verstecken - Timer wird durch mouse_leave neu gesetzt
            
    def manual_hide_widget(self):
        """
        Versteckt das Widget manuell (z.B. durch Doppelklick), unabhängig von Mausposition.
        """
        # Widget ausblenden
        self.is_visible = False
        self.root.attributes('-alpha', 0.0)
        
        # Timer stoppen falls aktiv
        if self.hide_timer:
            self.root.after_cancel(self.hide_timer)
            self.hide_timer = None
            
        # Mouse-Status zurücksetzen
        self.mouse_over_widget = False
        
    # --------------------------
    # Datenbank-Funktionen (vereinfacht)
    # --------------------------
    def init_database(self):
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

    def get_db_tasks(self):
        """
        Ruft alle Tasks aus der Datenbank ab.
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

    def get_projects(self):
        """
        Ruft alle Projekte ab.
        """
        url = "https://api.todoist.com/rest/v2/projects"
        try:
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 200:
                return response.json()
            else:
                return []
        except Exception as e:
            return []

    def get_inbox_project_id(self):
        """
        Findet die Projekt-ID des Posteingangs.
        """
        projects = self.get_projects()
        
        for project in projects:
            if project.get('is_inbox_project', False):
                return project['id']
        
        if projects:
            return projects[0]['id']
        
        return None

    def insert_new_task(self, task_id, task_name):
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

    def update_task_name(self, task_id, new_name):
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

    def delete_task(self, task_id):
        """
        Entfernt einen Task aus der Datenbank.
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
        
        conn.commit()
        conn.close()

    def sync_tasks_to_database(self, todoist_tasks):
        """
        Synchronisiert Todoist-Tasks mit der lokalen Datenbank.
        """
        # Bestehende Tasks aus DB abrufen
        db_tasks = self.get_db_tasks()
        
        # Set der aktuellen Todoist Task-IDs
        current_task_ids = set()
        
        # Durch alle Todoist-Tasks gehen
        for task in todoist_tasks:
            task_id = int(task.get('id'))  # Sicherstellen, dass task_id ein Integer ist
            task_name = task.get('content', 'Unbekannt')
            current_task_ids.add(task_id)
            
            if task_id not in db_tasks:
                # Neuer Task
                self.insert_new_task(task_id, task_name)
            else:
                # Existierender Task - prüfen ob Name geändert
                if db_tasks[task_id]['name'] != task_name:
                    self.update_task_name(task_id, task_name)
                # Wenn Name gleich ist, nichts tun
        
        # Tasks aus DB entfernen, die nicht mehr in Todoist existieren
        db_task_ids = set(db_tasks.keys())
        deleted_task_ids = db_task_ids - current_task_ids
        
        for task_id in deleted_task_ids:
            self.delete_task(task_id)
            
    def get_inbox_todos(self):
        """
        Ruft alle aktiven Todos aus dem Posteingang ab.
        """
        inbox_id = self.get_inbox_project_id()
        
        if not inbox_id:
            return []
        
        url = f"https://api.todoist.com/rest/v2/tasks"
        params = {'project_id': inbox_id}
        
        try:
            response = requests.get(url, headers=HEADERS, params=params)
            if response.status_code != 200:
                return []
            
            return response.json()
            
        except Exception as e:
            return []
        """
        Ruft alle aktiven Todos aus dem Posteingang ab.
        """
        inbox_id = self.get_inbox_project_id()
        
        if not inbox_id:
            return []
        
        url = f"https://api.todoist.com/rest/v2/tasks"
        params = {'project_id': inbox_id}
        
        try:
            response = requests.get(url, headers=HEADERS, params=params)
            if response.status_code != 200:
                return []
            
            return response.json()
            
        except Exception as e:
            return []
            
    def sync_and_display_tasks(self):
        """
        Synchronisiert Tasks und aktualisiert die Anzeige.
        """
        try:
            # Status aktualisieren
            self.update_status("Synchronisiere...")
            
            # Datenbank initialisieren
            self.init_database()
            
            # Tasks laden
            todoist_tasks = self.get_inbox_todos()
            
            if not todoist_tasks:
                self.update_status("Keine Tasks gefunden")
                self.display_tasks([])
                return
            
            # WICHTIG: Tasks mit Datenbank synchronisieren
            self.sync_tasks_to_database(todoist_tasks)
            
            # Aktualisierte DB-Daten laden
            db_tasks = self.get_db_tasks()
            
            # Tasks für Anzeige vorbereiten
            display_tasks = []
            
            for i, task in enumerate(todoist_tasks, 1):
                task_id_raw = task.get('id')
                task_id = int(task_id_raw) if task_id_raw else 0
                content = task.get('content', 'Unbekannte Aufgabe')
                
                # Datum ermitteln - sollte jetzt immer existieren
                display_date = "Unbekannt"
                if task_id in db_tasks:
                    first_seen = db_tasks[task_id]['first_seen']
                    last_changed = db_tasks[task_id]['last_changed']
                    
                    relevant_date = last_changed if first_seen != last_changed else first_seen
                    
                    try:
                        date_obj = datetime.strptime(relevant_date, '%Y-%m-%d')
                        display_date = date_obj.strftime('%d.%m.%Y')
                    except:
                        display_date = relevant_date
                else:
                    # Das sollte jetzt nie passieren, da wir synchronisiert haben
                    display_date = "FEHLER"
                
                display_tasks.append({
                    'number': i,
                    'date': display_date,
                    'content': content
                })
            
            # Anzeige aktualisieren
            self.display_tasks(display_tasks)
            self.update_status(f"Letztes Update: {datetime.now().strftime('%H:%M:%S')} ({len(display_tasks)} Tasks)")
            
        except Exception as e:
            self.update_status(f"Fehler: {str(e)}")
            
    def display_tasks(self, tasks):
        """
        Zeigt die Tasks im Text-Widget an.
        """
        # Fenstergröße an Anzahl Tasks anpassen
        self.position_window(len(tasks))
        
        self.task_text.config(state=tk.NORMAL)
        self.task_text.delete(1.0, tk.END)
        
        if not tasks:
            self.task_text.insert(tk.END, "Keine Tasks im Posteingang.")
        else:
            for task in tasks:
                # Text auf 30 Zeichen begrenzen
                content = task['content']
                if len(content) > 30:
                    content = content[:30].strip()
                
                line = f"{task['number']:2d}. {task['date']} - {content}\n"
                self.task_text.insert(tk.END, line)
        
        self.task_text.config(state=tk.DISABLED)
        
    def update_status(self, message):
        """
        Aktualisiert die Status-Anzeige.
        """
        self.status_label.config(text=message)
        
    def start_update_thread(self):
        """
        Startet den Background-Thread für automatische Updates.
        """
        def update_worker():
            # Sofortiges erstes Update
            self.root.after(0, self.sync_and_display_tasks)
            
            while not self.shutdown_flag:
                try:
                    time.sleep(UPDATE_INTERVAL)
                    if not self.shutdown_flag:  # Doppelt prüfen
                        self.root.after(0, self.sync_and_display_tasks)
                except:
                    break
        
        update_thread = threading.Thread(target=update_worker, daemon=True)
        update_thread.start()
        
    def run(self):
        """
        Startet die GUI-Anwendung.
        """
        self.root.mainloop()

# --------------------------
# Hauptprogramm
# --------------------------
if __name__ == "__main__":
    print("Todoist Desktop Widget - Single Instance Check...")
    
    # Prüfe ob bereits eine Instanz läuft
    check_single_instance()
    
    print("Starte Todoist Desktop Widget...")
    app = TaskDesktopWidget()
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("\nWidget durch Benutzer beendet.")
    except Exception as e:
        print(f"Fehler beim Ausführen des Widgets: {e}")
    finally:
        print("Widget beendet.")
