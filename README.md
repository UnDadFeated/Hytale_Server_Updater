# Hytale Server Updater

A Python automation script for managing Dedicated Hytale Servers.

## Features

*   **Platform Checks**: Verifies Java 25 installation.
*   **Asset Management**: Checks for `Assets.zip` and prompts to locate/copy it if missing.
*   **Auto-Updater**: Automatically downloads the Hytale Downloader CLI and updates server files.
*   **Auto-Restart**: Stops running server instances and restarts them after updates.
*   **Optimization**: Detects `HytaleServer.aot` to enable Ahead-Of-Time cache for faster startup.

## Requirements
*   **Operating System**: Windows or Linux
*   **Python 3.x**:
    *   **Windows**: [Download from Python.org](https://www.python.org/downloads/windows/) (Ensure "Add Python to PATH" is checked during installation)
    *   **Linux**: Usually pre-installed. If not, use your package manager (e.g., `sudo apt install python3`).
*   **Java 25**: [Download from Adoptium](https://adoptium.net/temurin/releases/?version=25)
*   **Internet Connection**: Required for downloading updates.

## Installation

1.  Clone this repository or download `hytale_updater.py` and `version.py`.
2.  Place the scripts in your desired server folder.

## Usage

Run the script via command line:

```bash
python hytale_updater.py
```

The script will:
1.  Check for Java 25.
2.  Ensure `Assets.zip` is present.
3.  Download the Hytale Downloader tool (if missing).
4.  Stop any running Hytale server.
5.  Run the updater to fetch the latest `HytaleServer.jar`.
6.  Launch the server (with AOT cache if available).

## Configuration

You can modify the constants at the top of `hytale_updater.py` to customize filenames or memory allocation:

```python
SERVER_MEMORY = "4G" # Change to "8G" etc.
```

## Versioning

Current Version: 1.3
See `version.py` for the tracked version number.
