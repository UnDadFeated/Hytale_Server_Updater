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

import version

# --- Configuration ---
JAVA_VERSION_REQ = 25
SERVER_JAR = "HytaleServer.jar" 
UPDATER_ZIP_URL = "https://downloader.hytale.com/hytale-downloader.zip"
UPDATER_ZIP_FILE = "hytale-downloader.zip"
IS_WINDOWS = platform.system() == "Windows"
UPDATER_EXECUTABLE = "hytale-downloader.exe" if IS_WINDOWS else "hytale-downloader"
ASSETS_FILE = "Assets.zip"
SERVER_MEMORY = "4G" 
AOT_FILE = "HytaleServer.aot"
LOG_FILE = "hytale_updater.log"

# --- Core Logic ---
class HytaleUpdaterCore:
    def __init__(self, log_callback, input_callback=None):
        self.log_callback = log_callback
        self.input_callback = input_callback # Used for assets path request in console mode
        self.server_process = None
        
    def log(self, message, tag=None):
        self.log_callback(message, tag)

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
                self.log("Please install Java 25: https://adoptium.net/temurin/releases/?version=25")
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
            if user_path and os.path.exists(user_path) and os.path.basename(user_path) == ASSETS_FILE:
                 try:
                     shutil.copy(user_path, cwd)
                     self.log(f"Copied {ASSETS_FILE} to server directory.")
                     return os.path.join(cwd, ASSETS_FILE)
                 except Exception as e:
                     self.log(f"Error copying file: {e}")
                     return None
            else:
                self.log(f"ERROR: {ASSETS_FILE} not found and not provided by user.")
                return None
        return None

    def ensure_updater(self):
        if os.path.exists(UPDATER_EXECUTABLE):
            self.log(f"Updater executable '{UPDATER_EXECUTABLE}' found.")
            return [f"./{UPDATER_EXECUTABLE}"] if not IS_WINDOWS else [UPDATER_EXECUTABLE]
        
        if os.path.exists("hytale-downloader.jar"):
            self.log("Updater jar found.")
            return ["java", "-jar", "hytale-downloader.jar"]

        self.log(f"Downloading updater from {UPDATER_ZIP_URL}...")
        try:
            urllib.request.urlretrieve(UPDATER_ZIP_URL, UPDATER_ZIP_FILE)
            self.log("Download complete. Extracting...")
            with zipfile.ZipFile(UPDATER_ZIP_FILE, 'r') as zip_ref:
                zip_ref.extractall(".")
            
            if os.path.exists(UPDATER_ZIP_FILE): os.remove(UPDATER_ZIP_FILE)

             # Logic to find the executable similar to before...
            if os.path.exists(UPDATER_EXECUTABLE):
                if not IS_WINDOWS: os.chmod(UPDATER_EXECUTABLE, 0o755)
                return [f"./{UPDATER_EXECUTABLE}"] if not IS_WINDOWS else [UPDATER_EXECUTABLE]
            elif os.path.exists("hytale-downloader.jar"):
                 return ["java", "-jar", "hytale-downloader.jar"]
            else:
                 # Fallback search
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
            except Exception as e:
                self.log(f"Error checking/stopping server: {e}")
        else:
             try:
                cmd = ["pgrep", "-f", SERVER_JAR]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    for pid in result.stdout.strip().splitlines():
                        self.log(f"Found running server (PID: {pid}). Stopping...")
                        subprocess.run(["kill", pid])
                    time.sleep(2)
             except Exception as e:
                self.log(f"Error checking/stopping server: {e}")

    def update_server(self):
        updater_cmd = self.ensure_updater()
        if not updater_cmd:
            self.log("Cannot run update, updater not available.")
            return

        self.log("Running Hytale Downloader...")
        try:
            process = subprocess.Popen(updater_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()
            if stdout: self.log(stdout)
            if stderr: self.log(stderr, "stderr")
            
            if process.returncode == 0:
                self.log("Update process completed successfully.")
            else:
                self.log("Update process reported an issue.")
        except Exception as e:
            self.log(f"Failed to execute update: {e}")

# --- Console Mode ---
def run_console_mode():
    def console_logger(message, tag=None):
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        print(f"{timestamp} {message}")
        with open(LOG_FILE, "a") as f:
            f.write(f"{timestamp} {message}\n")

    def console_input(prompt):
        return input(prompt).strip('"')

    core = HytaleUpdaterCore(console_logger, console_input)
    core.log(f"--- Hytale Server Updater v{version.__version__} (Console Mode) ---")
    
    if not core.check_java_version():
        core.log("CRITICAL: Java requirement not met.")
        return

    assets_path = core.check_assets()
    if not assets_path: return

    core.stop_existing_server_process()
    core.update_server()
    
    core.log("Starting Hytale server...")
    if not os.path.exists(SERVER_JAR):
        core.log(f"ERROR: Server jar '{SERVER_JAR}' not found!")
        return

    cmd = ["java", f"-Xmx{SERVER_MEMORY}"]
    if os.path.exists(AOT_FILE):
         core.log(f"Found AOT cache ({AOT_FILE}). Optimizing startup...")
         cmd.append(f"-XX:AOTCache={AOT_FILE}")
    cmd.extend(["-jar", SERVER_JAR, "--assets", assets_path])

    try:
        subprocess.run(cmd)
    except Exception as e:
        core.log(f"Failed to start server: {e}")

def main():
    if "-nogui" in sys.argv:
        run_console_mode()
    else:
        try:
            import tkinter as tk
            from tkinter import scrolledtext, messagebox, ttk
            from tkinter import filedialog
        except ImportError:
            print("Error: Tkinter not found. Please install it or run with -nogui.")
            return

        global HytaleUpdaterApp # make it available if we keep the class definition global? 
        # Actually, the class definition uses `tk` etc. so it will fail at parse time if those are missing globally usually in some languages, but in Python specific execution flow matters.
        # BUT, if the class definition lines 166+ use `tk.BooleanVar` as default values or in method bodies, we need those names defined.
        # We can move the class definition INSIDE a function or just ensure imports are top level but wrapped?
        # Python executes top to bottom. If `HytaleUpdaterApp` class is defined at top level, it executes the class body.
        # If `tk` is not defined, it will error at `self.enable_logging_var = tk.BooleanVar(value=True)` inside `__init__`.
        # `__init__` is only called when instantiated.
        # However, decorators or inheritance would fail immediately.
        # Logic: We should import `tk` globally but wrapped in try/except or just assume if user runs without -nogui they have it.
        # BUT the issue is: If I run `-nogui`, I don't want to require tk.
        # If I keep imports at top, script fails on headless.
        # If I remove imports from top, the class definition `class HytaleUpdaterApp` might fail if I use `ttk.Frame` in signature? No, I use it in body.
        # Wait, I use `ttk.Frame` inside `create_widgets`.
        # I use `tk.BooleanVar` inside `__init__`.
        # So as long as I don't instantiate `HytaleUpdaterApp`, I might be safe IF the names are resolved at runtime.
        # BUT... I need the modules imported for the names to exist when `__init__` runs.
        # So, I should import them inside `main`'s `else` logic, AND `HytaleUpdaterApp` needs to access them.
        # So I should make them global there, or import them inside `HytaleUpdaterApp` methods?
        # Cleaner: Move `HytaleUpdaterApp` class definition INSIDE a `run_gui_mode` function.
        run_gui_mode()

def run_gui_mode():
    import tkinter as tk
    from tkinter import scrolledtext, messagebox, ttk
    from tkinter import filedialog
    
    class HytaleUpdaterApp:
        def __init__(self, root):
            self.root = root
            self.root.title(f"Hytale Server Updater v{version.__version__}")
            self.root.geometry("800x600")

            self.enable_logging_var = tk.BooleanVar(value=True)
            self.check_updates_var = tk.BooleanVar(value=True)
            self.is_server_running = False
            
            self.create_widgets()
            self.log_queue = queue.Queue()
            self.update_log_from_queue()
            
            self.core = HytaleUpdaterCore(self.log_queue_wrapper, None) 

        def log_queue_wrapper(self, message, tag=None):
            timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
            full_msg = f"{timestamp} {message}\n"
            self.log_queue.put((full_msg, tag))
            if self.enable_logging_var.get():
                with open(LOG_FILE, "a") as f:
                    f.write(full_msg)

        def create_widgets(self):
            control_frame = ttk.Frame(self.root, padding="10")
            control_frame.pack(fill=tk.X)
            ttk.Checkbutton(control_frame, text="Enable File Logging", variable=self.enable_logging_var).pack(side=tk.LEFT, padx=5)
            ttk.Checkbutton(control_frame, text="Check for Updates", variable=self.check_updates_var).pack(side=tk.LEFT, padx=5)
            self.start_button = ttk.Button(control_frame, text="Start Server", command=self.run_full_process)
            self.start_button.pack(side=tk.RIGHT, padx=5)
            self.stop_button = ttk.Button(control_frame, text="Stop Server", command=self.stop_server_handler, state=tk.DISABLED)
            self.stop_button.pack(side=tk.RIGHT, padx=5)
            self.console_area = scrolledtext.ScrolledText(self.root, state=tk.DISABLED, font=("Consolas", 10))
            self.console_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            self.console_area.tag_config("stderr", foreground="red")
            self.console_area.tag_config("stdout", foreground="black")

        def update_log_from_queue(self):
            while not self.log_queue.empty():
                msg, tag = self.log_queue.get()
                self.console_area.config(state=tk.NORMAL)
                self.console_area.insert(tk.END, msg, tag)
                self.console_area.see(tk.END)
                self.console_area.config(state=tk.DISABLED)
            self.root.after(100, self.update_log_from_queue)

        def run_full_process(self):
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            t = threading.Thread(target=self._process_thread)
            t.daemon = True
            t.start()

        def _process_thread(self):
            self.core.log(f"--- Hytale Server Updater v{version.__version__} Started ---")
            
            if not self.core.check_java_version():
                self.core.log("CRITICAL: Java requirement not met.")
                self.reset_ui_state()
                return

            self.core.input_callback = self.ask_file_ui 
            
            assets_path = self.core.check_assets()
            if not assets_path:
                self.reset_ui_state()
                return

            self.core.stop_existing_server_process()

            if self.check_updates_var.get():
                self.core.update_server()
            else:
                self.core.log("Skipping update check per user request.")

            self.start_server(assets_path)

        def ask_file_ui(self, prompt):
            result_queue = queue.Queue()
            def ask():
                 path = filedialog.askopenfilename(title=prompt, filetypes=[("Zip Files", "*.zip")])
                 result_queue.put(path)
            self.root.after(0, ask)
            return result_queue.get()

        def start_server(self, assets_path):
            self.core.log("Starting Hytale server...")
            if not os.path.exists(SERVER_JAR):
                self.core.log(f"ERROR: Server jar '{SERVER_JAR}' not found!")
                self.reset_ui_state()
                return

            cmd = ["java", f"-Xmx{SERVER_MEMORY}"]
            if os.path.exists(AOT_FILE):
                 self.core.log(f"Found AOT cache ({AOT_FILE}). Optimizing startup...")
                 cmd.append(f"-XX:AOTCache={AOT_FILE}")
            cmd.extend(["-jar", SERVER_JAR, "--assets", assets_path])
            
            try:
                startupinfo = None
                if IS_WINDOWS:
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                self.server_process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                    text=True, bufsize=1, universal_newlines=True, startupinfo=startupinfo
                )
                self.is_server_running = True
                
                threading.Thread(target=self._read_stream, args=(self.server_process.stdout, "stdout"), daemon=True).start()
                threading.Thread(target=self._read_stream, args=(self.server_process.stderr, "stderr"), daemon=True).start()
                threading.Thread(target=self._monitor_server, daemon=True).start()
            except Exception as e:
                self.core.log(f"Failed to start server: {e}")
                self.reset_ui_state()

        def _read_stream(self, stream, tag):
            for line in iter(stream.readline, ''):
                if line: self.core.log(line.strip(), tag)
            stream.close()

        def _monitor_server(self):
            if self.server_process:
                self.server_process.wait()
                self.core.log(f"Server process ended with code {self.server_process.returncode}")
                self.server_process = None
                self.reset_ui_state()

        def stop_server_handler(self):
            if self.server_process and self.is_server_running:
                self.core.log("Stopping server...")
                self.server_process.terminate()
            else:
                self.core.log("No server process managed by this tool is running.")

        def reset_ui_state(self):
            self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_button.config(state=tk.DISABLED))
            self.is_server_running = False

    root = tk.Tk()
    app = HytaleUpdaterApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

