# Hytale Server Updater

A Python automation script for managing Dedicated Hytale Servers.

## Features

*   **GUI & Console Modes**: 
    *   **GUI**: Modern Single-Page interface with **Dark/Light Mode Themes**, logging toggles, and direct control.
    *   **Console**: Headless mode (`-nogui`) for automated environments. Supports all robust features (Backups, Webhooks, Restarts).
*   **Robustness**:
    *   **World Backups**: Automatically Zips the `world` folder before server start (keeps last 5).
    *   **Crash Detection**: Automatically detects crashes and restarts the server.
    *   **Scheduled Restarts**: Configurable timer to restart the server periodically (e.g., every 12 hours).
    *   **Discord Integration**: Sends Webhook notifications for Server Start, Stop, and Crashes.
*   **Platform Checks**: Verifies Java 25 installation.
*   **Asset Management**: Checks for `Assets.zip` and prompts to locate/copy it if missing.
*   **Auto-Updater**: Automatically downloads the Hytale Downloader CLI and updates server files.
*   **Smart Updates**: Checks the remote server version before downloading to save bandwidth.
*   **Optimization**: Detects `HytaleServer.aot` to enable Ahead-Of-Time cache for faster startup.

## Requirements
*   **Operating System**: Windows or Linux
*   **Python 3.x**:
    *   **Windows**: [Download from Python.org](https://www.python.org/downloads/windows/) (Ensure "Add Python to PATH" is checked)
    *   **Linux**: Usually pre-installed. (`sudo apt install python3 python3-tk` might be needed for GUI).
    *   **Linux**: Usually pre-installed. (`sudo apt install python3 python3-tk` might be needed for GUI).
*   **Java 25**: [Download from Adoptium](https://adoptium.net/temurin/releases/?version=25)
*   **Internet Connection**: Required for downloading updates and Discord webhooks.

## Installation

1.  Clone this repository or download `hytale_updater.py` and `version.py`.
2.  Place the scripts in your desired server folder.

## Usage

### Graphical Mode (Default)
Run the script without arguments to open the GUI:
```bash
python hytale_updater.py
```
*   **Controls**: Toggle Backups, Discord Webhooks, and Auto-Restart directly from the UI.
*   **Monitoring**: View Server Uptime.

### Console Mode (Headless)
Run with the `-nogui` argument for CLI-only operation:
```bash
python hytale_updater.py -nogui
```
*   Configuration is loaded from `hytale_updater_config.json`. Run GUI once to generate it comfortably, or edit manually.

## Configuration

Settings are saved to `hytale_updater_config.json`. Key features:
```json
{
  "enable_backups": true,
  "enable_discord": true,
  "discord_webhook": "YOUR_WEBHOOK_URL",
  "enable_auto_restart": true,
  "enable_schedule": false,
  "restart_interval": 12 
}
```

## Versioning

Current Version: 1.7.5
See `version.py` for the tracked version number.
