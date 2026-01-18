import os
import sys
import subprocess
import time
import datetime
import shutil
import urllib.request
import zipfile

import version

import platform

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

def log(message):
    """Prints a message with a timestamp to the console."""
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {message}")

def check_java_version():
    """Checks if the installed Java version is 25."""
    log("Checking Java version...")
    try:
        result = subprocess.run(["java", "-version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        output = result.stdout
        
        if 'version "25' in output or 'version "1.25' in output:
             log("Java 25 detected.")
             return True
        else:
            log(f"WARNING: Java 25 not detected. Output:\n{output}")
            log("Please install Java 25. Download it here: https://adoptium.net/temurin/releases/?version=25")
            return False
            
    except FileNotFoundError:
        log("ERROR: Java not found in PATH.")
        log("Please install Java 25. Download it here: https://adoptium.net/temurin/releases/?version=25")
        return False

def check_assets():
    """Checks if Assets.zip exists, prompts user if not."""
    log(f"Checking for {ASSETS_FILE}...")
    cwd = os.getcwd()
    assets_path = os.path.join(cwd, ASSETS_FILE)
    
    if os.path.exists(assets_path):
        log(f"Found {ASSETS_FILE} at {assets_path}")
        return assets_path
    
    log(f"{ASSETS_FILE} not found in {cwd}")
    while True:
        user_path = input(f"{datetime.datetime.now().strftime('[%Y-%m-%d %H:%M:%S]')} Please enter the full path to {ASSETS_FILE}: ").strip('"')
        if os.path.exists(user_path) and os.path.basename(user_path) == ASSETS_FILE:
             log(f"Confirmed {ASSETS_FILE} at {user_path}")
             try:
                 shutil.copy(user_path, cwd)
                 log(f"Copied {ASSETS_FILE} to server directory.")
                 return os.path.join(cwd, ASSETS_FILE)
             except Exception as e:
                 log(f"Error copying file: {e}")
        else:
            log("Invalid path or filename. Please try again.")

def ensure_updater():
    """Checks for downloader tool, downloads if missing. Returns command to run it."""
    
    if os.path.exists(UPDATER_EXECUTABLE):
        log(f"Updater executable '{UPDATER_EXECUTABLE}' found.")
        return [f"./{UPDATER_EXECUTABLE}"] if not IS_WINDOWS else [UPDATER_EXECUTABLE]
    
    if os.path.exists("hytale-downloader.jar"):
        log("Updater jar found.")
        return ["java", "-jar", "hytale-downloader.jar"]

    log(f"Updater CLI not found. Downloading the download cli from {UPDATER_ZIP_URL}...")
    
    try:
        urllib.request.urlretrieve(UPDATER_ZIP_URL, UPDATER_ZIP_FILE)
        log("Download complete. Extracting...")
        
        with zipfile.ZipFile(UPDATER_ZIP_FILE, 'r') as zip_ref:
            zip_ref.extractall(".")
            
        log("Extraction complete.")
        
        if os.path.exists(UPDATER_ZIP_FILE):
             os.remove(UPDATER_ZIP_FILE)
             
        if os.path.exists(UPDATER_EXECUTABLE):
            # On Linux, make it executable
            if not IS_WINDOWS:
                os.chmod(UPDATER_EXECUTABLE, 0o755)
                log("Made updater executable.")
                return [f"./{UPDATER_EXECUTABLE}"]
            return [UPDATER_EXECUTABLE]
            
        elif os.path.exists("hytale-downloader.jar"):
            return ["java", "-jar", "hytale-downloader.jar"]
        else:
            log(f"WARNING: No recognized updater file found after extraction.")
            files = os.listdir('.')
            log(f"Files: {files}")
            # Try to guess
            for f in files:
                if "hytale-downloader" in f:
                    if f.endswith(".jar"):
                         return ["java", "-jar", f]
                    if IS_WINDOWS and f.endswith(".exe"):
                        return [f]
                    if not IS_WINDOWS and "." not in f: # binary usually has no extension on linux
                        os.chmod(f, 0o755)
                        return [f"./{f}"]
            return None

    except Exception as e:
        log(f"Failed to download/extract updater: {e}")
        return None

def stop_server():
    """Checks for running Hytale server process and stops it."""
    log("Checking for running Hytale server...")
    
    if IS_WINDOWS:
        try:
            cmd = 'wmic process where "name=\'java.exe\'" get commandline, processid'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            
            found = False
            for line in result.stdout.splitlines():
                if SERVER_JAR in line:
                    parts = line.split()
                    if parts:
                        pid = parts[-1].strip()
                        if pid.isdigit():
                            log(f"Found running server (PID: {pid}). Stopping...")
                            subprocess.run(f"taskkill /PID {pid} /F", shell=True)
                            found = True
            
            if not found:
                log("No running Hytale server instance found.")
            else:
                time.sleep(5) 
                
        except Exception as e:
            log(f"Error checking/stopping server: {e}")
            
    else: # Linux/Unix
        try:
            # pgrep -f matches against full command line
            cmd = ["pgrep", "-f", SERVER_JAR]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().splitlines()
                for pid in pids:
                    log(f"Found running server (PID: {pid}). Stopping...")
                    subprocess.run(["kill", pid])
                
                # Wait loop for it to close
                time.sleep(5)
            else:
                 log("No running Hytale server instance found.")
                 
        except Exception as e:
            log(f"Error checking/stopping server: {e}")

def countdown(seconds, message="Continuing in"):
    """Displays a countdown timer on the same line."""
    for i in range(seconds, 0, -1):
        print(f"\r{message} {i}s...", end="")
        time.sleep(1)
    print("\r" + " " * (len(message) + 10) + "\r", end="") # Clear line

def update_server():
    """Runs the Hytale update command."""
    updater_cmd = ensure_updater()
    if not updater_cmd:
        log("Cannot run update, updater not available.")
        return

    log("Checking for updates (Running Hytale Downloader)...")
    
    try:
        # Run the downloader. We let stdout/stderr flow to the console so the user sees real-time progress.
        # Arguments: None required for default "Download latest release" behavior as per docs.
        cmd = updater_cmd
        
        log(f"Executing: {' '.join(cmd)}")
        log("--- Hytale Downloader Output Start ---")
        process = subprocess.run(cmd, text=True)
        log("--- Hytale Downloader Output End ---")
        
        if process.returncode == 0:
            log("Update process completed successfully.")
        else:
            log("Update process reported an issue (non-zero exit code).")
            
        # Pause so user can read the output
        print() # Newline
        log("Review the above output for update status.")
        countdown(10, "Starting server in")
        print() # Newline

    except Exception as e:
        log(f"Failed to execute update: {e}")

def start_server(assets_path):
    """Starts the Hytale server."""
    log("Starting Hytale server...")
    
    if not os.path.exists(SERVER_JAR):
        log(f"ERROR: Server jar '{SERVER_JAR}' not found! Cannot start.")
        return

    try:
        # Base command
        cmd = ["java", f"-Xmx{SERVER_MEMORY}"]
        
        # Check for AOT cache
        if os.path.exists(AOT_FILE):
            log(f"Found AOT cache ({AOT_FILE}). Optimizing startup...")
            cmd.append(f"-XX:AOTCache={AOT_FILE}")
            
        cmd.extend(["-jar", SERVER_JAR, "--assets", assets_path])
        
        if IS_WINDOWS:
            creationflags = subprocess.CREATE_NEW_CONSOLE
            subprocess.Popen(cmd, creationflags=creationflags)
            log(f"Server launched in new console.")
        else:
            # On Linux, verify if we should detach or run in foreground.
            # "no gui" usually means headless.
            # If we just Popen, it shares current stdout/stderr or goes background.
            # start_new_session=True makes it leader of new session (detach from tty).
            subprocess.Popen(cmd, start_new_session=True)
            log(f"Server launched (background process). check logs/ folder for output.")
        
    except Exception as e:
        log(f"Failed to start server: {e}")

def main():
    log(f"--- Hytale Server Updater v{version.__version__} Started ---")
    
    if not check_java_version():
        log("CRITICAL: Java requirement not met.")
        input("Press Enter to exit...") 
        return

    assets_path = check_assets()
    stop_server()
    update_server()
    start_server(assets_path)
    
    log("--- Hytale Server Updater Finished ---")
    time.sleep(3)

if __name__ == "__main__":
    main()
