import os
import sys
import subprocess
import time
import datetime
import shutil
import urllib.request
import zipfile
import threading
import queue
import platform
import re
import signal
import json
import traceback
import traceback
import webbrowser

import version

# --- Configuration ---
JAVA_VERSION_REQ = 25
SERVER_JAR = "HytaleServer.jar" 
UPDATER_ZIP_URL = "https://downloader.hytale.com/hytale-downloader.zip"
UPDATER_ZIP_FILE = "hytale-downloader.zip"
IS_WINDOWS = platform.system() == "Windows"
UPDATER_EXECUTABLE = "hytale-downloader.exe" if IS_WINDOWS else "hytale-downloader"
ASSETS_FILE = "Assets.zip"
# SERVER_MEMORY removed as constant, now in config
AOT_FILE = "HytaleServer.aot"
LOG_FILE = "hytale_updater.log"
CONFIG_FILE = "hytale_updater_config.json"
BACKUP_DIR = "backups"
WORLD_DIR = "world"

# --- Core Logic ---
def load_config():
    default_config = {
        "last_server_version": "0.0.0",
        "dark_mode": True,
        "enable_logging": True,
        "check_updates": True,
        "auto_start": False, 
        "enable_backups": True,
        "enable_discord": False,
        "discord_webhook": "",
        "enable_auto_restart": True,
        "enable_schedule": False,
        "restart_interval": 12, # Hours
        "server_memory": "8G"
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                loaded = json.load(f)
                default_config.update(loaded)
                return default_config
        except Exception as e:
            print(f"Error loading config: {e}")
    return default_config

def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

class HytaleUpdaterCore:
    def __init__(self, log_callback, input_callback=None, config=None, status_callback=None):
        self.log_callback = log_callback
        self.input_callback = input_callback 
        self.status_callback = status_callback # callback(status_dict)
        self.config = config if config else load_config()
        
        self.server_process = None
        self.stop_requested = False
        self.restart_timer = None
        self.monitor_thread = None
        self.start_time = None

    def log(self, message, tag=None):
        self.log_callback(message, tag)

    def update_status(self, status):
        if self.status_callback:
            self.status_callback(status)

    def check_java_version(self):
        self.log("Checking Java version...")
        try:
            result = subprocess.run(["java", "-version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            output = result.stdout
            if 'version "25' in output or 'version "1.25' in output:
                self.log("Java 25 detected.")
                return True
            else:
                self.log(f"WARNING: Java 25 not detected. Output:\n{output}")
                return False
        except FileNotFoundError:
            self.log("ERROR: Java not found in PATH.")
            return False

    def check_assets(self):
        self.log(f"Checking for {ASSETS_FILE}...")
        cwd = os.getcwd()
        assets_path = os.path.join(cwd, ASSETS_FILE)
        
        if os.path.exists(assets_path):
            self.log(f"Found {ASSETS_FILE} at {assets_path}")
            return assets_path
        
        self.log(f"{ASSETS_FILE} not found in {cwd}")
        
        if self.input_callback:
            user_path = self.input_callback(f"Please enter the full path to {ASSETS_FILE}: ")
            if user_path:
                # Handle qeueue result if it's a queue (GUI) or string (Console)
                if hasattr(user_path, 'get'): 
                    user_path = user_path # It's a string from the GUI wrapper usually? 
                    # Wait, my GUI implementation returned a value from queue. 
                    # Let's assume input_callback returns the string.
                    pass

                if user_path and os.path.exists(user_path) and os.path.basename(user_path) == ASSETS_FILE:
                     try:
                         shutil.copy(user_path, cwd)
                         self.log(f"Copied {ASSETS_FILE} to server directory.")
                         return os.path.join(cwd, ASSETS_FILE)
                     except Exception as e:
                         self.log(f"Error copying file: {e}")
                         return None
        return None

    def ensure_updater(self):
        if os.path.exists(UPDATER_EXECUTABLE):
            return [f"./{UPDATER_EXECUTABLE}"] if not IS_WINDOWS else [UPDATER_EXECUTABLE]
        
        if os.path.exists("hytale-downloader.jar"):
            return ["java", "-jar", "hytale-downloader.jar"]

        self.log(f"Downloading updater from {UPDATER_ZIP_URL}...")
        try:
            req = urllib.request.Request(UPDATER_ZIP_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                with open(UPDATER_ZIP_FILE, "wb") as f:
                    f.write(response.read())

            with zipfile.ZipFile(UPDATER_ZIP_FILE, 'r') as zip_ref:
                zip_ref.extractall(".")
            
            if os.path.exists(UPDATER_ZIP_FILE): os.remove(UPDATER_ZIP_FILE)
            
            if os.path.exists(UPDATER_EXECUTABLE):
                if not IS_WINDOWS: os.chmod(UPDATER_EXECUTABLE, 0o755)
                return [f"./{UPDATER_EXECUTABLE}"] if not IS_WINDOWS else [UPDATER_EXECUTABLE]
            
            # Fallback Search (Restored from v1.6)
            for f in os.listdir('.'):
                if "hytale-downloader" in f:
                    if f.endswith(".jar"): return ["java", "-jar", f]
                    if IS_WINDOWS and f.endswith(".exe"): return [f]
                    if not IS_WINDOWS and "." not in f:
                        os.chmod(f, 0o755)
                        return [f"./{f}"]
            return None
        except Exception as e:
            self.log(f"Failed to download/extract updater: {e}")
            return None

    def stop_existing_server_process(self):
        self.log("Checking for running Hytale server...")
        if IS_WINDOWS:
            try:
                cmd = 'wmic process where "name=\'java.exe\'" get commandline, processid'
                result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
                for line in result.stdout.splitlines():
                    if SERVER_JAR in line:
                        parts = line.split()
                        if parts:
                            pid = parts[-1].strip()
                            if pid.isdigit():
                                self.log(f"Found running server (PID: {pid}). Stopping...")
                                subprocess.run(f"taskkill /PID {pid} /F", shell=True)
            except Exception: pass
        else:
             try:
                cmd = ["pgrep", "-f", SERVER_JAR]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    for pid in result.stdout.strip().splitlines():
                        self.log(f"Found running server (PID: {pid}). Stopping...")
                        subprocess.run(["kill", pid])
             except Exception: pass



    def get_remote_server_version(self, updater_cmd):
        try:
            cmd = updater_cmd + ["-print-version"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None

    def update_server(self):
        updater_cmd = self.ensure_updater()
        if not updater_cmd:
            self.log("Cannot run update, updater not available.")
            return

        self.log("Checking for updates...")
        
        # Smart Update Logic
        remote_version = self.get_remote_server_version(updater_cmd)
        local_version = self.config.get("last_server_version", "0.0.0")

        if remote_version:
            self.log(f"Remote version: {remote_version}")
            if remote_version == local_version:
                self.log(f"Server is up to date (Version {local_version}). Skipping download.")
                return
            else:
                self.log(f"New version available (Old: {local_version}, New: {remote_version}). Downloading...")
        else:
            self.log("Could not determine remote version. Forcing update check...")

        try:
            process = subprocess.Popen(updater_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in iter(process.stdout.readline, ''):
                if line: self.log(line.strip())
            process.wait()
            
            if process.returncode == 0:
                self.log("Update check complete.")
                
                # Update Config
                if remote_version:
                     self.config["last_server_version"] = remote_version
                     save_config(self.config)
                     self.log(f"Updated local version record to {remote_version}")

                if os.path.exists(AOT_FILE):
                     try: os.remove(AOT_FILE)
                     except: pass
        except Exception as e:
            self.log(f"Update failed: {e}")

    def backup_world(self):
        if not self.config.get("enable_backups", True): return
        if not os.path.exists(WORLD_DIR): return

        self.log("Creating world backup...")
        if not os.path.exists(BACKUP_DIR): os.makedirs(BACKUP_DIR)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_name = os.path.join(BACKUP_DIR, f"world_backup_{timestamp}")
        
        try:
            shutil.make_archive(backup_name, 'zip', WORLD_DIR)
            self.log(f"Backup created: {backup_name}.zip")
            # Cleanup
            backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("world_backup_") and f.endswith(".zip")])
            if len(backups) > 5:
                for old in backups[:-5]:
                    try: os.remove(os.path.join(BACKUP_DIR, old))
                    except: pass
        except Exception as e:
            self.log(f"Backup failed: {e}")

    def send_discord_webhook(self, message):
        if not self.config.get("enable_discord", False): return
        url = self.config.get("discord_webhook", "").strip()
        if not url: return

        try:
            data = json.dumps({"content": message}).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', 'User-Agent': 'HytaleUpdater'})
            with urllib.request.urlopen(req) as r: pass
        except Exception as e:
            self.log(f"Discord Webhook Failed: {e}")

    def start_server_sequence(self):
        t = threading.Thread(target=self._start_server_thread)
        t.daemon = True
        t.start()

    def _start_server_thread(self):
        self.stop_requested = False
        
        if not self.check_java_version(): return

        assets_path = self.check_assets()
        if not assets_path: return

        self.stop_existing_server_process()

        if self.config.get("check_updates", True):
            self.update_server()

        self.backup_world()

        self.log("Starting Server...")
        self.send_discord_webhook("🟢 Hytale Server Starting...")

        memory = self.config.get("server_memory", "4G")
        cmd = ["java", f"-Xmx{memory}"]
        if os.path.exists(AOT_FILE):
             self.log(f"Using AOT Cache: {AOT_FILE}")
             cmd.append(f"-XX:AOTCache={AOT_FILE}")
        cmd.extend(["-jar", SERVER_JAR, "--assets", assets_path])

        try:
            startupinfo = subprocess.STARTUPINFO() if IS_WINDOWS else None
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0
            
            self.server_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE,
                text=True, bufsize=1, universal_newlines=True, 
                startupinfo=startupinfo, creationflags=creationflags
            )
            self.start_time = datetime.datetime.now()
            self.update_status({"state": "Running", "pid": self.server_process.pid})

            # Start IO Threads
            threading.Thread(target=self._read_stream, args=(self.server_process.stdout, "stdout"), daemon=True).start()
            threading.Thread(target=self._read_stream, args=(self.server_process.stderr, "stderr"), daemon=True).start()
            
            # Start Monitor
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            
            # Start Schedule
            if self.config.get("enable_schedule", False):
                self._schedule_restart()

        except Exception as e:
            self.log(f"Failed to start server: {e}")
            self.update_status({"state": "Stopped"})

    def _read_stream(self, stream, tag):
        try:
            for line in iter(stream.readline, ''):
                if line: self.log(line.strip(), tag)
        except: pass
        finally: stream.close()

    def _monitor_loop(self):
        if not self.server_process: return
        
        while self.server_process and self.server_process.poll() is None:
            # Update Status (Uptime works even without psutil)
            if self.start_time:
                uptime = datetime.datetime.now() - self.start_time
                uptime_str = str(uptime).split('.')[0]
                self.update_status({
                    "state": "Running",
                    "pid": self.server_process.pid,
                    "uptime": uptime_str
                })
            
            time.sleep(1)

        # Process exited
        rc = self.server_process.returncode
        self.log(f"Server exited with code {rc}")
        self.server_process = None
        self.update_status({"state": "Stopped"})
        self.send_discord_webhook(f"🔴 Server Stopped (Code {rc})")

        # Auto Restart Logic
        if rc != 0 and not self.stop_requested and self.config.get("enable_auto_restart", True):
             self.log("Crash detected! Restarting in 10 seconds...")
             self.send_discord_webhook("⚠️ Crash detected. Restarting in 10s...")
             time.sleep(10)
             self.start_server_sequence()

    def stop_server(self):
        self.stop_requested = True
        if self.restart_timer:
            self.restart_timer.cancel()

        if self.server_process:
            self.log("Stopping server...")
            try:
                self.server_process.stdin.write("stop\n")
                self.server_process.stdin.flush()
            except:
                # Force kill if needed
                if self.server_process: 
                    self.server_process.kill()
    
    def _schedule_restart(self):
        hours = float(self.config.get("restart_interval", 12))
        seconds = hours * 3600
        self.log(f"Scheduled restart in {hours} hours.")
        
        def restart_task():
            self.log("Executing scheduled restart...")
            self.send_discord_webhook("⏰ Executing scheduled restart...")
            self.stop_server()
            # Wait for stop
            time.sleep(10)
            self.start_server_sequence()

        self.restart_timer = threading.Timer(seconds, restart_task)
        self.restart_timer.start()


# --- Console Mode ---
def run_console_mode():
    def console_logger(message, tag=None):
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        print(f"{timestamp} {message}")
        with open(LOG_FILE, "a") as f:
            f.write(f"{timestamp} {message}\n")
    
    config = load_config()
    core = HytaleUpdaterCore(console_logger, input_callback=input, config=config)
    
    print("--- Console Mode ---")
    print("Use Ctrl+C to stop. The script will try to gracefully stop the server.")
    
    core.start_server_sequence()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        core.stop_server()

# --- GUI Mode ---
def run_gui_mode():
    import tkinter as tk
    from tkinter import scrolledtext, messagebox, ttk, filedialog

    class HytaleGUI:
        def __init__(self, root):
            self.root = root
            self.root.title(f"Hytale Server Manager v{version.__version__}")
            
            # Default Size (Not maximized)
            self.root.geometry("1000x800")
            self.root.state("normal")

            self.config = load_config()
            self.is_dark = self.config.get("dark_mode", True)
            
            # Vars
            self.var_logging = tk.BooleanVar(value=self.config.get("enable_logging", True))
            self.var_check_upd = tk.BooleanVar(value=self.config.get("check_updates", True))
            self.var_autostart = tk.BooleanVar(value=self.config.get("auto_start", False))
            self.var_backup = tk.BooleanVar(value=self.config.get("enable_backups", True))
            self.var_discord = tk.BooleanVar(value=self.config.get("enable_discord", False))
            self.var_restart = tk.BooleanVar(value=self.config.get("enable_auto_restart", True))
            self.var_schedule = tk.BooleanVar(value=self.config.get("enable_schedule", False))
            self.var_discord_url = tk.StringVar(value=self.config.get("discord_webhook", ""))
            self.var_schedule_time = tk.StringVar(value=str(self.config.get("restart_interval", 12)))
            self.var_schedule_time = tk.StringVar(value=str(self.config.get("restart_interval", 12)))
            self.var_memory = tk.StringVar(value=self.config.get("server_memory", "8G"))
            
            self.var_memory.trace_add("write", self.on_config_change) # Trace for reboot warning
            
            self.var_memory.trace_add("write", self.on_config_change) # Trace for reboot warning

            self.stats_var = tk.StringVar(value="Status: Stopped")

            # Core
            self.log_queue = queue.Queue()
            self.core = HytaleUpdaterCore(self.log_queue_wrapper, self.ask_file, self.config, self.update_stats)

            self.setup_ui()
            self.apply_theme()
            self.update_log_loop()

            if self.var_autostart.get():
                self.root.after(1000, self.start_server)

        def setup_ui(self):
            # 1. Header (About)
            header = ttk.Frame(self.root, padding="10")
            header.pack(fill=tk.X)
            
            title = ttk.Label(header, text=f"Hytale Server Manager v{version.__version__}", font=("Segoe UI", 16, "bold"))
            title.pack(side=tk.LEFT)
            
            desc = ttk.Label(header, text=" | Comprehensive Server Management Tool", font=("Segoe UI", 10))
            desc.pack(side=tk.LEFT, padx=10, pady=(4,0))
            
            # 2. Controls & Settings Container
            controls_frame = ttk.LabelFrame(self.root, text="Controls & Configuration", padding="10")
            controls_frame.pack(fill=tk.X, padx=10, pady=5)
            
            # Grid Layout for Controls
            # Container for Left side (Options + Quick Access)
            left_container = ttk.Frame(controls_frame)
            left_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # Top Row: Checkboxes
            options_row = ttk.Frame(left_container)
            options_row.pack(fill=tk.X, anchor="w")

            # Left: Toggles
            c_col1 = ttk.Frame(options_row)
            c_col1.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
            
            ttk.Checkbutton(c_col1, text="Enable File Logging", variable=self.var_logging, command=self.save).pack(anchor="w")
            ttk.Checkbutton(c_col1, text="Check Updates on Start", variable=self.var_check_upd, command=self.save).pack(anchor="w")
            ttk.Checkbutton(c_col1, text="Auto-Start Server", variable=self.var_autostart, command=self.save).pack(anchor="w")
            ttk.Checkbutton(c_col1, text="Backup World on Start", variable=self.var_backup, command=self.save).pack(anchor="w")
            
            # Middle: Advanced
            c_col2 = ttk.Frame(options_row)
            c_col2.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))

            ttk.Checkbutton(c_col2, text="Auto-Restart on Crash", variable=self.var_restart, command=self.save).pack(anchor="w")
            
            dsc_frame = ttk.Frame(c_col2)
            dsc_frame.pack(anchor="w", pady=2)
            ttk.Checkbutton(dsc_frame, text="Discord Webhook", variable=self.var_discord, command=self.save).pack(side=tk.LEFT)
            ttk.Entry(dsc_frame, textvariable=self.var_discord_url, width=25).pack(side=tk.LEFT, padx=5)
            
            sch_frame = ttk.Frame(c_col2)
            sch_frame.pack(anchor="w", pady=2)
            ttk.Checkbutton(sch_frame, text="Schedule Restart (Hrs)", variable=self.var_schedule, command=self.save).pack(side=tk.LEFT)
            ttk.Entry(sch_frame, textvariable=self.var_schedule_time, width=5).pack(side=tk.LEFT, padx=5)
            
            mem_frame = ttk.Frame(c_col2)
            mem_frame.pack(anchor="w", pady=2)
            ttk.Label(mem_frame, text="Server RAM:").pack(side=tk.LEFT)
            ttk.Entry(mem_frame, textvariable=self.var_memory, width=5).pack(side=tk.LEFT, padx=5)
            self.lbl_reboot = ttk.Label(mem_frame, text="⚠ Reboot Required", foreground="orange")
            # hidden by default

            # Bottom Row: Quick Access (Moved here)
            qa_row = ttk.Frame(left_container)
            qa_row.pack(fill=tk.X, pady=(10, 0), anchor="w")
            
            ttk.Label(qa_row, text="Quick Access:", font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0,5))
            ttk.Button(qa_row, text="📂 Server", command=lambda: self.open_folder("."), width=8).pack(side=tk.LEFT, padx=1)
            ttk.Button(qa_row, text="📂 World", command=lambda: self.open_folder(WORLD_DIR), width=8).pack(side=tk.LEFT, padx=1)
            ttk.Button(qa_row, text="📂 Backup", command=lambda: self.open_folder(BACKUP_DIR), width=8).pack(side=tk.LEFT, padx=1)
            ttk.Button(qa_row, text="📂 Local", command=lambda: self.open_folder(self.get_local_saves_path()), width=8).pack(side=tk.LEFT, padx=1)

            # Right: Actions & Stats
            c_col3 = ttk.Frame(controls_frame)
            c_col3.pack(side=tk.RIGHT, fill=tk.Y)
            
            self.btn_start = ttk.Button(c_col3, text="START SERVER", command=self.start_server, width=20)
            self.btn_start.pack(pady=2)
            
            self.btn_stop = ttk.Button(c_col3, text="STOP SERVER", command=self.stop_server, state=tk.DISABLED, width=20)
            self.btn_stop.pack(pady=2)

            self.lbl_stats = ttk.Label(c_col3, textvariable=self.stats_var, font=("Consolas", 9))
            self.lbl_stats.pack(pady=5)
            
            # 3. Console
            self.console = scrolledtext.ScrolledText(self.root, font=("Consolas", -10), state=tk.DISABLED)
            self.console.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            self.setup_tags()
            
            # 4. Footer (Donation)
            footer = ttk.Frame(self.root, padding="10")
            footer.pack(fill=tk.X)
            
            theme_btn = ttk.Button(footer, text="Toggle Theme", command=self.toggle_theme)
            theme_btn.pack(side=tk.LEFT)
            
            donate_frame = ttk.Frame(footer)
            donate_frame.pack(side=tk.RIGHT)
            
            ttk.Label(donate_frame, text="☕ Buy me a coffee:").pack(side=tk.LEFT, padx=5)
            
            # PayPal
            pp_url = "https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=jscheema@gmail.com&item_name=Hytale%20Server%20Updater&amount=5.00&currency_code=USD"
            btn_pp = ttk.Button(donate_frame, text="PayPal ($5)", command=lambda: webbrowser.open(pp_url))
            btn_pp.pack(side=tk.LEFT, padx=2)


        def on_config_change(self, *args):
            self.save()
            # Check if running to show reboot warning
            if self.core.server_process:
                 self.lbl_reboot.pack(side=tk.LEFT, padx=5)
            else:
                 self.lbl_reboot.pack_forget()

        def start_server(self):
            self.lbl_reboot.pack_forget() # Clear warning on start
            self.save() # Save check first
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            self.core.start_server_sequence()

        def stop_server(self):
            self.core.stop_server()
            self.btn_stop.config(state=tk.DISABLED) # Prevent double click
            # Enable start handled by monitoring callback when actually stopped

        def save(self):
            self.config.update({
                "enable_logging": self.var_logging.get(),
                "check_updates": self.var_check_upd.get(),
                "auto_start": self.var_autostart.get(),
                "enable_backups": self.var_backup.get(),
                "enable_discord": self.var_discord.get(),
                "enable_auto_restart": self.var_restart.get(),
                "enable_schedule": self.var_schedule.get(),
                "discord_webhook": self.var_discord_url.get(),
                "restart_interval": self.var_schedule_time.get(),
                "server_memory": self.var_memory.get()
            })
            # Also update core config in realtime
            self.core.config = self.config
            save_config(self.config)

        def update_stats(self, status):
            # Callback from core thread
            state = status.get("state", "Unknown")
            if state == "Stopped":
                 self.root.after(0, lambda: self.btn_start.config(state=tk.NORMAL))
                 self.root.after(0, lambda: self.btn_stop.config(state=tk.DISABLED))
                 self.root.after(0, lambda: self.stats_var.set("Status: Stopped"))
            elif state == "Running":
                 uptime = status.get("uptime", "00:00:00")
                 text = f"Status: Running | Uptime: {uptime}"
                 self.root.after(0, lambda: self.stats_var.set(text))

        def log_queue_wrapper(self, msg, tag=None):
            timestamp = datetime.datetime.now().strftime("[%H:%M:%S]")
            self.log_queue.put((f"{timestamp} {msg}\n", tag))
            if self.var_logging.get():
                clean_msg = re.sub(r'\x1b\[[0-9;]*m', '', f"{timestamp} {msg}\n")
                with open(LOG_FILE, "a", encoding="utf-8") as f: f.write(clean_msg)

        def update_log_loop(self):
            while not self.log_queue.empty():
                msg, tag = self.log_queue.get()
                self.console.config(state=tk.NORMAL)
                self.insert_colored(msg, tag)
                self.console.see(tk.END)
                self.console.config(state=tk.DISABLED)
            self.root.after(100, self.update_log_loop)

        def insert_colored(self, text, tag):
             # Simple parser
             parts = re.split(r'(\x1b\[[0-9;]*m)', text)
             current_tag = tag if tag == "stderr" else None
             for part in parts:
                 if part.startswith('\x1b['):
                     code = part.strip()[2:-1]
                     if code == "0": current_tag = None
                     elif code in ["31","91"]: current_tag = "red"
                     elif code in ["32","92"]: current_tag = "green"
                     elif code in ["33","93"]: current_tag = "yellow"
                     elif code in ["36","96"]: current_tag = "cyan"
                 else:
                     if part: self.console.insert(tk.END, part, (current_tag,) if current_tag else ())

        def ask_file(self, prompt):
            # Blocking ask
            return filedialog.askopenfilename(title=prompt, filetypes=[("Zip Files", "*.zip")])

        def setup_tags(self):
            self.console.tag_config("stderr", foreground="#ff5555")
            self.console.tag_config("red", foreground="#ff5555")
            self.console.tag_config("green", foreground="#55ff55" if self.is_dark else "#00aa00")
            self.console.tag_config("yellow", foreground="#ffff55" if self.is_dark else "#aaaa00")
            self.console.tag_config("cyan", foreground="#55ffff" if self.is_dark else "#00aaaa")

        def apply_theme(self):
            bg, fg = ("#1e1e1e", "#d4d4d4") if self.is_dark else ("#f0f0f0", "#000000")
            txt_bg, txt_fg = bg, fg
            
            style = ttk.Style()
            style.theme_use('clam')
            style.configure(".", background=bg, foreground=fg)
            style.configure("TLabel", background=bg, foreground=fg)
            style.configure("TFrame", background=bg)
            style.configure("TLabelFrame", background=bg, foreground=fg)
            style.configure("TButton", background="#3c3c3c" if self.is_dark else "#e0e0e0", foreground=fg, borderwidth=1)
            style.map("TButton", background=[("active", "#0078d7")], foreground=[("active", "white")])
            style.configure("TCheckbutton", background=bg, foreground=fg)
            
            self.root.configure(bg=bg)
            self.console.config(bg=txt_bg, fg=txt_fg, insertbackground=fg)

        def get_local_saves_path(self):
            if IS_WINDOWS:
                return os.path.join(os.getenv('APPDATA'), 'Hytale', 'UserData', 'Saves', 'universe', 'worlds')
            else:
                 return os.path.expanduser("~/.local/share/Hytale/UserData/Saves/universe/worlds")

        def open_folder(self, path):
             path = os.path.abspath(path)
             if not os.path.exists(path):
                 try:
                     os.makedirs(path)
                 except: pass 
             
             try:
                 if IS_WINDOWS:
                     os.startfile(path)
                 else:
                     if platform.system() == "Darwin":
                         subprocess.Popen(["open", path])
                     else:
                         subprocess.Popen(["xdg-open", path])
             except Exception as e:
                 print(f"Error opening folder: {e}")
                 messagebox.showerror("Error", f"Could not open folder:\n{path}\n\n{e}")

        def toggle_theme(self):
            self.is_dark = not self.is_dark
            self.config["dark_mode"] = self.is_dark
            self.apply_theme()
            self.save()

    root = tk.Tk()
    app = HytaleGUI(root)
    root.mainloop()

def print_help():
    print(f"Hytale Server Updater v{version.__version__}")
    print("--------------------------------------------------")
    print("Usage: python hytale_updater.py [options]")
    print("\nOptions:")
    print("  -nogui       : Run in console-only mode (headless).")
    print("  -help, --help: Show this help message.")
    print("\nDescription:")
    print("  Manages the Hytale Dedicated Server, including auto-updates,")
    print("  backups, crash detection, and discord notifications.")
    print("\nConfiguration:")
    print(f"  stored in {CONFIG_FILE} (generated on first run).")
    sys.exit(0)

def main():
    if "-help" in sys.argv or "--help" in sys.argv:
        print_help()

    if "-nogui" in sys.argv:
        run_console_mode()
    else:
        try:
            run_gui_mode()
        except ImportError:
            # Fallback if tkinter is missing
            run_console_mode()
        except Exception:
             # Catch other GUI init errors
             traceback.print_exc()
             input("GUI Start Failed! Press Enter to exit...")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        input("Critical Crash! Press Enter to exit...")
