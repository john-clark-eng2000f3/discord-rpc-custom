# discord-rpc-custom

A lightweight background daemon for Windows that updates your Discord Rich Presence based on what processes you currently have running. It connects directly to Discord's local IPC named pipe, meaning zero bloated dependencies.

I wrote this because Discord's native game detection is unreliable, doesn't support custom assets well for unregistered apps, and I wanted a simple CLI tool that I can launch on startup to set my presence based on tools like Neovim, Reaper, or specific dev environments.

## Installation

Clone the repository and install the single dependency (psutil for process scanning):

```bash
pip install -r requirements.txt
```

## Configuration

Create a configuration file named `rpc-profiles.json` in the same directory as the script. Here is an example mapping process names to Discord client IDs and rich presence details:

```json
{
  "mappings": [
    {
      "process_name": "nvim.exe",
      "client_id": "112233445566778899",
      "details": "Editing configuration files",
      "state": "In Neovim",
      "large_image": "neovim_logo",
      "large_text": "Vim is the way"
    },
    {
      "process_name": "reaper.exe",
      "client_id": "998877665544332211",
      "details": "Mixing a new track",
      "state": "In REAPER",
      "large_image": "reaper_main",
      "large_text": "REAPER v7.0"
    }
  ],
  "default_client_id": "112233445566778899",
  "poll_interval": 15
}
```

You need to register your own applications on the Discord Developer Portal to get a client ID and upload asset keys if you want custom images.

## Running

Start the daemon in monitor mode to scan running processes every 15 seconds:

```bash
python rpc.py --config rpc-profiles.json --monitor
```

Or trigger a single immediate update:

```bash
python rpc.py --config rpc-profiles.json --once
```

<!-- updated: 2026-09-14 -->
