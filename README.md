# Hytale Server Updater

A Python automation script for managing Dedicated Hytale Servers.

## Features

*   **GUI & Console Modes**: 
    *   **GUI**: User-friendly interface with logging toggles, update checks, and integrated console.
    *   **Console**: Headless mode (`-nogui`) for automated environments.
*   **Platform Checks**: Verifies Java 25 installation.
*   **Asset Management**: Checks for `Assets.zip` and prompts to locate/copy it if missing.
*   **Auto-Updater**: Automatically downloads the Hytale Downloader CLI and updates server files.
*   **Auto-Restart**: Stops running server instances and restarts them after updates.
*   **Optimization**: Detects `HytaleServer.aot` to enable Ahead-Of-Time cache for faster startup.

## Requirements
*   **Operating System**: Windows or Linux
*   **Python 3.x**:
    *   **Windows**: [Download from Python.org](https://www.python.org/downloads/windows/) (Ensure "Add Python to PATH" is checked)
    *   **Linux**: Usually pre-installed. (`sudo apt install python3 python3-tk` might be needed for GUI).
*   **Java 25**: [Download from Adoptium](https://adoptium.net/temurin/releases/?version=25)
*   **Internet Connection**: Required for downloading updates.

## Installation

1.  Clone this repository or download `hytale_updater.py` and `version.py`.
2.  Place the scripts in your desired server folder.

## Usage

### Graphical Mode (Default)
Run the script without arguments to open the GUI:
```bash
python hytale_updater.py
```
*   **Enable File Logging**: Toggles saving logs to `hytale_updater.log`.
*   **Check for Updates**: Uncheck to skip the downloader (useful for modded setups).
*   **Start/Stop**: Controls the server process directly.

### Console Mode (Headless)
Run with the `-nogui` argument for CLI-only operation:
```bash
python hytale_updater.py -nogui
```

## Configuration

You can modify the constants at the top of `hytale_updater.py` to customize filenames or memory allocation:

```python
SERVER_MEMORY = "4G" # Change to "8G" etc.
```

## Versioning

Current Version: 1.4
See `version.py` for the tracked version number.
