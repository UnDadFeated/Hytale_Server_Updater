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
import webbrowser
import version

JAVA_VERSION_REQ = 25
SERVER_JAR = "HytaleServer.jar"
UPDATER_ZIP_URL = "https://downloader.hytale.com/hytale-downloader.zip"
UPDATER_ZIP_FILE = "hytale-downloader.zip"
IS_WINDOWS = platform.system() == "Windows"
UPDATER_EXECUTABLE = "hytale-downloader.exe" if IS_WINDOWS else "hytale-downloader"
ASSETS_FILE = "Assets.zip"
AOT_FILE = "HytaleServer.aot"
LOG_FILE = "hytale_server_manager.log"
CONFIG_FILE = "hytale_server_manager_config.json"
BACKUP_DIR = "universe/backups"
WORLD_DIR = "universe/worlds"

def load_config():
    """Loads the server configuration from the JSON file."""
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
        "restart_interval": 12,
        "server_memory": "8G",
        "max_backups": 3,
        "manager_auto_update": True
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
    """Saves the current configuration to the JSON file."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

class HytaleUpdaterCore:
    """Core logic for managing, updating, and monitoring the Hytale server."""
    
    def __init__(self, log_callback, input_callback=None, config=None, status_callback=None):
        self.log_callback = log_callback
        self.input_callback = input_callback
        self.status_callback = status_callback
        self.config = config if config else load_config()
        
        self.server_process = None
        self.stop_requested = False
        self.restart_timer = None
        self.monitor_thread = None
        self.start_time = None

    def log(self, message, tag=None):
        self.log_callback(message, tag)

    def update_status(self, status):
        """Updates the status via the callback."""
        if self.status_callback:
            self.status_callback(status)

    def check_java_version(self):
        """Verifies if Java 25 is installed and available."""
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
        """Checks if the required assets file exists, asking the user if missing."""
        self.log(f"Checking for {ASSETS_FILE}...")
        cwd = os.getcwd()
        assets_path = os.path.join(cwd, ASSETS_FILE)
        
        if os.path.exists(assets_path):
            self.log(f"Found {ASSETS_FILE} at {assets_path}")
            return assets_path
        
        self.log(f"{ASSETS_FILE} not found in {cwd}")
        
        if self.input_callback:
            user_path = self.input_callback(f"Please enter the full path to {ASSETS_FILE}: ")
            if hasattr(user_path, 'get'):
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
        """Ensures the Hytale updater executable is available."""
        if os.path.exists(UPDATER_EXECUTABLE):
            return [f"./{UPDATER_EXECUTABLE}"] if not IS_WINDOWS else [UPDATER_EXECUTABLE]
        
        if os.path.exists("hytale-downloader.jar"):
            return ["java", "-jar", "hytale-downloader.jar"]

        self.log(f"Updater not found or checking for cache. Target: {UPDATER_ZIP_FILE}")
        
        should_download = True
        if os.path.exists(UPDATER_ZIP_FILE):
             try:
                 self.log(f"Found cached {UPDATER_ZIP_FILE}, checking remote size...")
                 req = urllib.request.Request(UPDATER_ZIP_URL, method='HEAD', headers={'User-Agent': 'Mozilla/5.0'})
                 with urllib.request.urlopen(req) as response:
                     remote_size = int(response.headers.get('Content-Length', 0))
                     local_size = os.path.getsize(UPDATER_ZIP_FILE)
                     
                     if remote_size > 0 and remote_size == local_size:
                         self.log("Local zip matches remote size. Skipping download.")
                         should_download = False
                     else:
                         self.log(f"Size mismatch (Local: {local_size}, Remote: {remote_size}). Redownloading...")
             except Exception as e:
                 self.log(f"Error checking remote size: {e}. forcing download.")

        if should_download:
            self.log(f"Downloading updater from {UPDATER_ZIP_URL}...")
            try:
                req = urllib.request.Request(UPDATER_ZIP_URL, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    with open(UPDATER_ZIP_FILE, "wb") as f:
                        f.write(response.read())
            except Exception as e:
                 self.log(f"Download failed: {e}")
                 return None

        try:
            with zipfile.ZipFile(UPDATER_ZIP_FILE, 'r') as zip_ref:
                zip_ref.extractall(".")
            
            if os.path.exists(UPDATER_EXECUTABLE):
                if not IS_WINDOWS: os.chmod(UPDATER_EXECUTABLE, 0o755)
                return [f"./{UPDATER_EXECUTABLE}"] if not IS_WINDOWS else [UPDATER_EXECUTABLE]
            
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

    def resolve_command_path(self, cmd_list):
        """Resolves absolute paths for command execution."""
        new_cmd = cmd_list.copy()
        if not new_cmd: return new_cmd
        
        if new_cmd[0].startswith("./") or os.path.exists(new_cmd[0]):
             new_cmd[0] = os.path.abspath(new_cmd[0])
        
        if len(new_cmd) > 2 and "java" in new_cmd[0] and new_cmd[1] == "-jar":
             if os.path.exists(new_cmd[2]):
                 new_cmd[2] = os.path.abspath(new_cmd[2])
        return new_cmd

    def stop_existing_server_process(self):
        """Detects and stops any running instance of the Hytale server."""
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
        """Queries the updater for the latest remote server version."""
        try:
            cmd = updater_cmd + ["-print-version"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None

    def check_self_update(self):
        """Checks for updates to the manager script from git master branch via HTTP."""
        if not self.config.get("manager_auto_update", True):
             return

        VERSION_URL = "https://raw.githubusercontent.com/UnDadFeated/Hytale_Server_Manager/master/version.py"
        MANAGER_URL = "https://raw.githubusercontent.com/UnDadFeated/Hytale_Server_Manager/master/hytale_server_manager.py"
        
        try:
            req = urllib.request.Request(VERSION_URL, headers={'User-Agent': 'HytaleManagerUpdater'})
            with urllib.request.urlopen(req) as response:
                remote_version_content = response.read().decode('utf-8')
            
            remote_version = None
            for line in remote_version_content.splitlines():
                if line.startswith("__version__"):
                    remote_version = line.split('"')[1]
                    break
            
            if not remote_version:
                self.log("Could not parse remote version.")
                return

            local_version = version.__version__
            
            # Semantic version comparison
            def parse_ver(v): return [int(x) for x in v.split('.')]
            
            if parse_ver(remote_version) > parse_ver(local_version):
                self.log(f"New manager version found ({remote_version}). Downloading...")
                
                # Download files
                req_ver = urllib.request.Request(VERSION_URL, headers={'User-Agent': 'HytaleManagerUpdater'})
                with urllib.request.urlopen(req_ver) as response:
                    with open("version.py.new", "wb") as f: f.write(response.read())
                    
                req_mgr = urllib.request.Request(MANAGER_URL, headers={'User-Agent': 'HytaleManagerUpdater'})
                with urllib.request.urlopen(req_mgr) as response:
                    with open("hytale_server_manager.py.new", "wb") as f: f.write(response.read())
                
                self.log("Files downloaded. Preparing installer...")
                self.run_update_installer()
            else:
                self.log("Manager is up to date.")

        except Exception as e:
            self.log(f"Failed to check/update manager: {e}")

    def run_update_installer(self):
        """Generates and runs the separate installer script."""
        installer_code = f'''
import os
import time
import sys
import subprocess

pid = {os.getpid()}
print(f"Waiting for parent process {{pid}} to close...")

try:
    while True:
        try:
            os.kill(pid, 0)
            time.sleep(1)
        except OSError:
            break
            
    print("Updating files...")
    time.sleep(1) # Extra buffer
    
    if os.path.exists("version.py.new"):
        if os.path.exists("version.py"): os.remove("version.py")
        os.rename("version.py.new", "version.py")
        print("Updated version.py")
        
    if os.path.exists("hytale_server_manager.py.new"):
        if os.path.exists("hytale_server_manager.py"): os.remove("hytale_server_manager.py")
        os.rename("hytale_server_manager.py.new", "hytale_server_manager.py")
        print("Updated hytale_server_manager.py")
        
    print("Files updated. Restarting manager...")
    subprocess.Popen([sys.executable, "hytale_server_manager.py"])
    
except Exception as e:
    print(f"Update failed: {{e}}")
    input("Press Enter to exit...")
'''
        with open("updater_installer.py", "w") as f:
            f.write(installer_code)
            
        self.log("Launching installer and exiting...")
        subprocess.Popen([sys.executable, "updater_installer.py"])
        sys.exit(0)

    def update_server(self):
        """Handles the server update process using the Hytale downloader."""
        updater_cmd = self.ensure_updater()
        
        if not updater_cmd:
            self.log("Cannot run update, updater not available.")
            return

        self.log("Checking for updates...")

        resolved_cmd = self.resolve_command_path(updater_cmd)

        remote_version = self.get_remote_server_version(resolved_cmd)
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
            staging_dir = os.path.abspath("updater_staging")
            if os.path.exists(staging_dir): shutil.rmtree(staging_dir)
            os.makedirs(staging_dir)
            
            self.log(f"Downloading update to staging: {staging_dir}...")
            
            process = subprocess.Popen(resolved_cmd, cwd=staging_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in iter(process.stdout.readline, ''):
                if line: self.log(f"[Updater] {line.strip()}")
            process.wait()
            
            if process.returncode == 0:
                self.log("Update download complete. Applying files...")
                
                search_roots = [staging_dir]
                if os.path.exists(os.path.join(staging_dir, "Server")):
                    search_roots.append(os.path.join(staging_dir, "Server"))
                
                found_server = False
                
                for root_path in search_roots:
                    jar_path = os.path.join(root_path, SERVER_JAR)
                    if os.path.exists(jar_path):
                        found_server = True
                        
                        replacements = [SERVER_JAR, AOT_FILE, ASSETS_FILE, "Licenses"]
                        for item in replacements:
                            src = os.path.join(root_path, item)
                            if os.path.exists(src):
                                dest = os.path.join(os.getcwd(), item)
                                try:
                                    if os.path.isdir(src):
                                        if os.path.exists(dest): shutil.rmtree(dest)
                                        shutil.copytree(src, dest)
                                    else:
                                        shutil.copy2(src, dest)
                                    self.log(f"Updated {item}")
                                except Exception as e:
                                    self.log(f"Failed to update {item}: {e}")
                        break
                
                if not found_server:
                    self.log("WARNING: Updated HytaleServer.jar not found in staging!")

                if remote_version:
                     self.config["last_server_version"] = remote_version
                     save_config(self.config)
                     self.log(f"Updated local version record to {remote_version}")

            else:
                 self.log(f"Updater exited with code {process.returncode}")
            
            if os.path.exists(staging_dir): 
                 try: 
                     shutil.rmtree(staging_dir)
                     self.log(f"Cleaned up staging: {staging_dir}")
                 except Exception as e:
                     self.log(f"Failed to clean staging: {e}")

            artifacts = ["QUICKSTART.md", "hytale-downloader-windows-amd64.exe", "hytale-downloader-linux-amd64", "hytale-downloader"]
            for f in artifacts:
                if os.path.exists(f):
                    try: 
                        os.remove(f)
                    except: pass

        except Exception as e:
            self.log(f"Update failed: {e}")
            self.log(traceback.format_exc())
            if os.path.exists(staging_dir): 
                 try: 
                     shutil.rmtree(staging_dir)
                 except Exception as e:
                     self.log(f"Failed to clean staging after error: {e}")

    def send_command(self, command):
        """Sends a console command to the running server process."""
        if self.server_process and self.server_process.poll() is None:
            try:
                self.log(f"> {command}")
                msg = (command + "\n").encode('utf-8')
                self.server_process.stdin.write(msg)
                self.server_process.stdin.flush()
            except Exception as e:
                self.log(f"Failed to send command: {e}")
        else:
             self.log("Server is not running.")

    def backup_world(self):
        """Creates a backup of the world directory."""
        if not self.config.get("enable_backups", True): return
        
        if not os.path.exists(WORLD_DIR):
             self.log(f"Backup skipped: World directory not found at {WORLD_DIR}")
             return

        self.log(f"Creating world backup from {WORLD_DIR}...")
        if not os.path.exists(BACKUP_DIR): os.makedirs(BACKUP_DIR)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_name = os.path.join(BACKUP_DIR, f"world_backup_{timestamp}")
        
        try:
            shutil.make_archive(backup_name, 'zip', WORLD_DIR)
            self.log(f"Backup created: {backup_name}.zip")
            
            max_b = int(self.config.get("max_backups", 3))
            backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("world_backup_") and f.endswith(".zip")])
            if len(backups) > max_b:
                for old in backups[:-max_b]:
                    try: os.remove(os.path.join(BACKUP_DIR, old))
                    except: pass
        except Exception as e:
            self.log(f"Backup failed: {e}")

    def send_discord_webhook(self, message):
        """Sends a status message to the configured Discord webhook."""
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
        """Initiates the server startup sequence in a separate thread."""
        t = threading.Thread(target=self._start_server_thread)
        t.daemon = True
        t.start()

    def _start_server_thread(self):
        """Internal method to handle the server startup steps."""
        self.stop_requested = False
        
        if not self.check_java_version(): return

        assets_path = self.check_assets()
        if not assets_path: return

        self.stop_existing_server_process()

        self.check_self_update()
        if self.config.get("check_updates", True):
            self.update_server()

        self.backup_world()

        self.log("Starting Server...")
        self.send_discord_webhook("🟢 Hytale Server Starting...")

        memory = self.config.get("server_memory", "4G")
        
        env = os.environ.copy()
        env["_JAVA_OPTIONS"] = f"-Xmx{memory}"
        
        cmd = ["java", f"-Xmx{memory}"]
        if os.path.exists(AOT_FILE):
             self.log(f"Using AOT Cache: {AOT_FILE}")
             cmd.append(f"-XX:AOTCache={AOT_FILE}")
        cmd.extend(["-jar", SERVER_JAR, "--assets", assets_path])

        try:
            startupinfo = subprocess.STARTUPINFO() if IS_WINDOWS else None
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0
            
            self.server_process = subprocess.Popen(
                cmd, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE,
                startupinfo=startupinfo, creationflags=creationflags
            )
            self.start_time = datetime.datetime.now()
            self.update_status({"state": "Running", "pid": self.server_process.pid})

            threading.Thread(target=self._read_stream, args=(self.server_process.stdout, "stdout"), daemon=True).start()
            threading.Thread(target=self._read_stream, args=(self.server_process.stderr, "stderr"), daemon=True).start()
            
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            
            if self.config.get("enable_schedule", False):
                self._schedule_restart()

        except Exception as e:
            self.log(f"Failed to start server: {e}")
            self.update_status({"state": "Stopped"})

    def _read_stream(self, stream, tag):
        """Reads output from the server process stdout/stderr."""
        try:
            for line_bytes in iter(stream.readline, b''):
                if line_bytes:
                    line = line_bytes.decode('utf-8', errors='replace').strip()
                    if line: self.log(line, tag)
        except: pass
        finally: stream.close()

    def _monitor_loop(self):
        """Monitors the server process status."""
        if not self.server_process: return
        
        while self.server_process and self.server_process.poll() is None:
            if self.start_time:
                uptime = datetime.datetime.now() - self.start_time
                uptime_str = str(uptime).split('.')[0]
                self.update_status({
                    "state": "Running",
                    "pid": self.server_process.pid,
                    "uptime": uptime_str
                })
            
            time.sleep(1)

        rc = self.server_process.returncode
        self.log(f"Server exited with code {rc}")
        self.server_process = None
        self.update_status({"state": "Stopped"})
        self.send_discord_webhook(f"🔴 Server Stopped (Code {rc})")

        if rc != 0 and not self.stop_requested and self.config.get("enable_auto_restart", True):
             self.log("Crash detected! Restarting in 10 seconds...")
             self.send_discord_webhook("⚠️ Crash detected. Restarting in 10s...")
             time.sleep(10)
             self.start_server_sequence()

    def stop_server(self):
        """Stops the running server process."""
        self.stop_requested = True
        if self.restart_timer:
            self.restart_timer.cancel()

        if self.server_process:
            self.log("Stopping server...")
            try:
                self.server_process.stdin.write(b"stop\n")
                self.server_process.stdin.flush()
            except:
                if self.server_process: 
                    self.server_process.kill()
    
    def _schedule_restart(self):
        """Schedules an automatic restart after a configured interval."""
        hours = float(self.config.get("restart_interval", 12))
        seconds = hours * 3600
        self.log(f"Scheduled restart in {hours} hours.")
        
        def restart_task():
            self.log("Executing scheduled restart...")
            self.send_discord_webhook("⏰ Executing scheduled restart...")
            self.stop_server()
            time.sleep(10)
            self.start_server_sequence()

        self.restart_timer = threading.Timer(seconds, restart_task)
        self.restart_timer.start()


def run_console_mode():
    """Runs the updater in console-only mode."""
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

def run_gui_mode():
    """Starts the graphical user interface."""
    import tkinter as tk
    from tkinter import scrolledtext, messagebox, ttk, filedialog

    class HytaleGUI:
        """Tkinter-based GUI for the Hytale Server Manager."""
        def __init__(self, root):
            self.root = root
            self.root.title(f"Hytale Server Manager v{version.__version__}")
            
            self.root.geometry("1000x800")
            self.root.state("normal")

            self.config = load_config()
            self.is_dark = self.config.get("dark_mode", True)
            
            self.var_logging = tk.BooleanVar(value=self.config.get("enable_logging", True))
            self.var_check_upd = tk.BooleanVar(value=self.config.get("check_updates", True))
            self.var_autostart = tk.BooleanVar(value=self.config.get("auto_start", False))
            self.var_backup = tk.BooleanVar(value=self.config.get("enable_backups", True))
            self.var_discord = tk.BooleanVar(value=self.config.get("enable_discord", False))
            self.var_restart = tk.BooleanVar(value=self.config.get("enable_auto_restart", True))
            self.var_schedule = tk.BooleanVar(value=self.config.get("enable_schedule", False))
            self.var_discord_url = tk.StringVar(value=self.config.get("discord_webhook", ""))
            self.var_schedule_time = tk.StringVar(value=str(self.config.get("restart_interval", 12)))
            self.var_memory = tk.StringVar(value=self.config.get("server_memory", "8G"))
            self.var_max_backups = tk.StringVar(value=str(self.config.get("max_backups", 3)))
            
            self.var_memory.trace_add("write", self.on_config_change)

            self.status_var = tk.StringVar(value="Status: Stopped")
            self.uptime_var = tk.StringVar(value="Uptime: 00:00:00")

            self.log_queue = queue.Queue()
            self.core = HytaleUpdaterCore(self.log_queue_wrapper, self.ask_file, self.config, self.update_stats)

            self.setup_ui()
            self.apply_theme()
            self.update_log_loop()

            if self.var_autostart.get():
                self.root.after(1000, self.start_server)

        def setup_ui(self):
            header = ttk.Frame(self.root, padding="5")
            header.pack(fill=tk.X)
            
            title = ttk.Label(header, text=f"Hytale Server Manager v{version.__version__}", font=("Segoe UI", 16, "bold"))
            title.pack(side=tk.LEFT)
            
            desc = ttk.Label(header, text=" | Comprehensive Server Management Tool", font=("Segoe UI", 10))
            desc.pack(side=tk.LEFT, padx=10, pady=(4,0))
            
            controls_frame = ttk.LabelFrame(self.root, text="Controls & Configuration", padding="5")
            controls_frame.pack(fill=tk.X, padx=10, pady=2)
            
            left_container = ttk.Frame(controls_frame)
            left_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            options_row = ttk.Frame(left_container)
            options_row.pack(fill=tk.X, anchor="w")

            c_col1 = ttk.Frame(options_row)
            c_col1.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
            
            ttk.Checkbutton(c_col1, text="Enable File Logging", variable=self.var_logging, command=self.save).pack(anchor="w")
            ttk.Checkbutton(c_col1, text="Auto-Start Server", variable=self.var_autostart, command=self.save).pack(anchor="w")
            ttk.Checkbutton(c_col1, text="Auto-Restart on Crash", variable=self.var_restart, command=self.save).pack(anchor="w")
            
            c_col2 = ttk.Frame(options_row)
            c_col2.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
            
            ttk.Checkbutton(c_col2, text="Check for new server updates at start", variable=self.var_check_upd, command=self.save).pack(anchor="w")
            ttk.Label(c_col2, text="(Uncheck if modded)", font=("Segoe UI", 8), foreground="gray").pack(anchor="w", padx=(20, 0))
            
            bkp_frame = ttk.Frame(c_col2)
            bkp_frame.pack(anchor="w")
            ttk.Checkbutton(bkp_frame, text="Backup World on Start", variable=self.var_backup, command=self.save).pack(side=tk.LEFT)
            ttk.Label(bkp_frame, text="Max:").pack(side=tk.LEFT, padx=(5,2))
            ttk.Entry(bkp_frame, textvariable=self.var_max_backups, width=3).pack(side=tk.LEFT)

            c_col3_center = ttk.Frame(options_row)
            c_col3_center.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

            dsc_frame = ttk.Frame(c_col3_center)
            dsc_frame.pack(anchor="w", pady=2)
            ttk.Checkbutton(dsc_frame, text="Discord Webhook", variable=self.var_discord, command=self.save).pack(side=tk.LEFT)
            ttk.Entry(dsc_frame, textvariable=self.var_discord_url, width=20).pack(side=tk.LEFT, padx=5)
            
            sch_frame = ttk.Frame(c_col3_center)
            sch_frame.pack(anchor="w", pady=2)
            ttk.Checkbutton(sch_frame, text="Schedule Restart (Hrs)", variable=self.var_schedule, command=self.save).pack(side=tk.LEFT)
            ttk.Entry(sch_frame, textvariable=self.var_schedule_time, width=5).pack(side=tk.LEFT, padx=5)
            
            mem_frame = ttk.Frame(c_col3_center)
            mem_frame.pack(anchor="w", pady=2)
            ttk.Label(mem_frame, text="Server RAM:").pack(side=tk.LEFT)
            ttk.Entry(mem_frame, textvariable=self.var_memory, width=6).pack(side=tk.LEFT, padx=5)
            self.lbl_reboot = ttk.Label(mem_frame, text="⚠ Reboot Required", foreground="orange")

            c_col3 = ttk.Frame(controls_frame)
            c_col3.pack(side=tk.RIGHT, fill=tk.Y)
            
            def open_dir(path):
                try:
                    p = os.path.abspath(path)
                    if not os.path.exists(p): os.makedirs(p)
                    os.startfile(p) if IS_WINDOWS else subprocess.run(["xdg-open", p])
                except Exception as e:
                    messagebox.showerror("Error", f"Could not open directory: {e}")

            qa_buttons_frame = ttk.Frame(c_col3)
            qa_buttons_frame.grid(row=0, column=0, sticky="n", padx=(0, 10), pady=0)
            
            action_buttons_frame = ttk.Frame(c_col3)
            action_buttons_frame.grid(row=0, column=1, sticky="n", pady=0)

            ttk.Button(qa_buttons_frame, text="Server", width=10, command=lambda: open_dir(".")).pack(fill=tk.X, pady=1)
            ttk.Button(qa_buttons_frame, text="Worlds", width=10, command=lambda: open_dir(WORLD_DIR)).pack(fill=tk.X, pady=1)
            ttk.Button(qa_buttons_frame, text="Backups", width=10, command=lambda: open_dir(BACKUP_DIR)).pack(fill=tk.X, pady=1)

            self.btn_start = ttk.Button(action_buttons_frame, text="START SERVER", command=self.start_server, width=20)
            self.btn_start.pack(pady=1)
            self.btn_stop = ttk.Button(action_buttons_frame, text="STOP SERVER", command=self.stop_server, state=tk.DISABLED, width=20)
            self.btn_stop.pack(pady=1)

            self.lbl_status = ttk.Label(c_col3, textvariable=self.status_var, font=("Consolas", 9))
            self.lbl_status.grid(row=1, column=0, pady=2)
            
            self.lbl_uptime = ttk.Label(c_col3, textvariable=self.uptime_var, font=("Consolas", 9))
            self.lbl_uptime.grid(row=1, column=1, pady=2)
            
            self.console = scrolledtext.ScrolledText(self.root, font=("Consolas", -10), state=tk.DISABLED)
            self.console.pack(fill=tk.BOTH, expand=True, padx=10, pady=(2, 0))
            self.setup_tags()

            input_frame = ttk.Frame(self.root)
            input_frame.pack(fill=tk.X, padx=10, pady=(2, 5))
            
            self.input_var = tk.StringVar()
            self.entry_cmd = ttk.Entry(input_frame, textvariable=self.input_var)
            self.entry_cmd.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.entry_cmd.bind("<Return>", lambda e: self.send_command_ui())
            
            footer = ttk.Frame(self.root, padding="10")
            footer.pack(fill=tk.X)
            
            theme_btn = ttk.Button(footer, text="Toggle Theme", command=self.toggle_theme)
            theme_btn.pack(side=tk.LEFT)
            
            self.var_mgr_update = tk.BooleanVar(value=self.config.get("manager_auto_update", True))
            ttk.Checkbutton(footer, text="Auto-Update Manager", variable=self.var_mgr_update, command=self.save).pack(side=tk.LEFT, padx=10)
            
            donate_frame = ttk.Frame(footer)
            donate_frame.pack(side=tk.RIGHT)
            
            ttk.Label(donate_frame, text="☕ Buy me a coffee:").pack(side=tk.LEFT, padx=5)
            
            pp_url = "https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=jscheema@gmail.com&item_name=Hytale%20Server%20Updater&amount=5.00&currency_code=USD"
            btn_pp = ttk.Button(donate_frame, text="PayPal ($5)", command=lambda: webbrowser.open(pp_url))
            btn_pp.pack(side=tk.LEFT, padx=2)

        def send_command_ui(self):
            cmd = self.input_var.get().strip()
            if cmd:
                self.core.send_command(cmd)
                self.input_var.set("")
                self.entry_cmd.focus()

        def on_config_change(self, *args):
            self.save()
            if self.core.server_process:
                 self.lbl_reboot.pack(side=tk.LEFT, padx=5)
            else:
                 self.lbl_reboot.pack_forget()

        def start_server(self):
            self.lbl_reboot.pack_forget()
            self.save()
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            self.core.start_server_sequence()

        def stop_server(self):
            self.core.stop_server()
            self.btn_stop.config(state=tk.DISABLED)

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
                "discord_webhook": self.var_discord_url.get(),
                "restart_interval": self.var_schedule_time.get(),
                "server_memory": self.var_memory.get(),
                "server_memory": self.var_memory.get(),
                "max_backups": int(self.var_max_backups.get()) if self.var_max_backups.get().isdigit() else 3,
                "manager_auto_update": self.var_mgr_update.get()
            })
            self.core.config = self.config
            save_config(self.config)

        def update_stats(self, status):
            state = status.get("state", "Unknown")
            if state == "Stopped":
                 self.root.after(0, lambda: self.btn_start.config(state=tk.NORMAL))
                 self.root.after(0, lambda: self.btn_stop.config(state=tk.DISABLED))
                 self.root.after(0, lambda: self.status_var.set("Status: Stopped"))
                 self.root.after(0, lambda: self.uptime_var.set("Uptime: 00:00:00"))
            elif state == "Running":
                 uptime = status.get("uptime", "00:00:00")
                 self.root.after(0, lambda: self.status_var.set("Status: Running"))
                 self.root.after(0, lambda: self.uptime_var.set(f"Uptime: {uptime}"))

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
                
                # Prevent memory leaks by limiting the buffer size
                num_lines = float(self.console.index('end-1c'))
                if num_lines > 1000:
                    self.console.delete('1.0', '50.0')
                
                self.console.see(tk.END)
                self.console.config(state=tk.DISABLED)
            self.root.after(100, self.update_log_loop)

        def insert_colored(self, text, tag):
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

        def toggle_theme(self):
            self.is_dark = not self.is_dark
            self.config["dark_mode"] = self.is_dark
            self.apply_theme()
            self.save()

    root = tk.Tk()
    app = HytaleGUI(root)
    root.mainloop()

def print_help():
    """Prints the help message."""
    abs_config_path = os.path.abspath(CONFIG_FILE)
    print(f"Hytale Server Manager v{version.__version__}")
    print("=" * 60)
    print("Usage: python hytale_server_manager.py [options]")
    print("\nCommand Line Options:")
    print("  -nogui       : Run in console-only mode (headless). Useful for servers.")
    print("  -help, --help: Show this help message.")
    print("\nDescription:")
    print("  Manages the Hytale Dedicated Server life-cycle.")
    print("  Features: Auto-Updates, Crash Detection, Auto-Restarts, World Backups, Discord Webhooks.")
    
    print("\nConfiguration File:")
    print(f"  Location: {abs_config_path}")
    print("\n  The configuration is a JSON file with the following options:")
    print("  - last_server_version : Tracks the installed server version.")
    print("  - dark_mode           : (GUI) Enable dark theme. [true/false]")
    print("  - enable_logging      : Write logs to hytale_server_manager.log. [true/false]")
    print("  - check_updates       : Check for updates on startup. [true/false]")
    print("  - auto_start          : Automatically start the server when this script runs. [true/false]")
    print("  - enable_backups      : Zip the world folder before starting. [true/false]")
    print("  - max_backups         : Number of backups to keep. [Integer]")
    print("  - enable_discord      : Enable Discord Webhook notifications. [true/false]")
    print("  - discord_webhook     : The Discord Webhook URL. [String]")
    print("  - enable_auto_restart : Restart server automatically on crash/stop. [true/false]")
    print("  - enable_schedule     : Enable scheduled periodic restarts. [true/false]")
    print("  - restart_interval    : Hours between scheduled restarts. [Float]")
    print("  - server_memory       : Java Heap Size (e.g., '4G', '8G'). [String]")
    print("=" * 60)
    sys.exit(0)

def main():
    """Main entry point."""
    # Cleanup temporary update files
    if os.path.exists("updater_installer.py"):
        try: os.remove("updater_installer.py")
        except: pass
        
    for f in ["version.py.new", "hytale_server_manager.py.new"]:
         if os.path.exists(f):
             try: os.remove(f)
             except: pass

    if "-help" in sys.argv or "--help" in sys.argv:
        print_help()

    if "-nogui" in sys.argv:
        run_console_mode()
    else:
        try:
            run_gui_mode()
        except ImportError:
            run_console_mode()
        except Exception:
             traceback.print_exc()
             input("GUI Start Failed! Press Enter to exit...")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        input("Critical Crash! Press Enter to exit...")
