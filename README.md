# Hytale Server Updater

A Python automation script for managing Dedicated Hytale Servers.

## Features

*   **GUI & Console Modes**: Use the modern graphical interface or headless console mode (`-nogui`) for flexible management.
*   **Robustness**: Automated crash detection, scheduled restarts, and world backups (zips locally before starting).
*   **Smart Updates**: Checks the remote server version before installing to prevent unnecessary downloads.
*   **Performance**: Detects and enables Ahead-Of-Time (`HytaleServer.aot`) cache for faster startups.
*   **Notifications**: Integrated Discord Webhooks for server status changes (Start, Stop, Crash).
*   **Platform Checks**: auto-detects Java 25 and `Assets.zip` requirements.

## Requirements
*   **Operating System**: Windows or Linux
*   **Python 3.x**:
    *   **Windows**: [Download from Python.org](https://www.python.org/downloads/windows/) (Ensure "Add Python to PATH" is checked)
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
*   **Quick Access**: Open Server, World, and Backup folders.
*   **Themes**: Toggle between Light and Dark mode.

### Console Mode (Headless)
Run with the `-nogui` argument for CLI-only operation:
```bash
python hytale_updater.py -nogui
```
*   Configuration is loaded from `hytale_updater_config.json`.

### Help
View all command line arguments:
```bash
python hytale_updater.py -help
```

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

Current Version: 1.9.0
See `version.py` for the tracked version number.
