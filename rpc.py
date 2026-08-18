import asyncio
import json
import sys
import argparse
from pathlib import Path
import psutil

from discord_rpc_custom.ipc import DiscordIPC

def load_config(path: Path) -> dict:
    """Reads mapping config from file, failing hard on corrupt syntax."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at '{path}'", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON configuration: {e}", file=sys.stderr)
        sys.exit(1)

def find_active_match(config: dict) -> tuple[dict, str] | tuple[None, None]:
    # Get all running process names in one pass to avoid massive process_iter overhead
    running = set()
    for proc in psutil.process_iter(attrs=["name"]):
        try:
            name = proc.info["name"]
            if name:
                running.add(name.lower())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # print(f"Currently running processes: {running}")  # debug trace

    # First matching process entry from mappings list wins
    for item in config.get("mappings", []):
        executable = item.get("exec", "").lower()
        if executable in running:
            return item, executable
    return None, None

async def monitor_loop(config_path: Path, interval: int):
    current_client_id = None
    ipc = None
    last_match_exec = None

    while True:
        # Re-load config each cycle to grab mapping updates on the fly without restarting daemon
        config = load_config(config_path)
        match, exe_name = find_active_match(config)

        if not match:
            if ipc:
                print("No monitored processes active. Clearing presence.")
                try:
                    await ipc.close()
                except Exception:
                    pass
                ipc = None
                current_client_id = None
                last_match_exec = None
        else:
            client_id = str(match.get("client_id", ""))
            if not client_id:
                print(f"Warning: Match for {exe_name} is missing a client_id definition.", file=sys.stderr)
            else:
                # Re-connect when matched process swaps to another profile (using different Client ID)
                if current_client_id != client_id:
                    if ipc:
                        print(f"Switching profile from {last_match_exec} to {exe_name}")
                        try:
                            await ipc.close()
                        except Exception:
                            pass
                        ipc = None

                    print(f"Initializing connection to Discord for {exe_name} ({client_id})")
                    ipc = DiscordIPC(client_id)
                    try:
                        await ipc.connect()
                        current_client_id = client_id
                    except Exception as e:
                        # Typically means Discord is completely closed, or target client id is unregistered
                        print(f"Unable to establish Discord IPC connection: {e}", file=sys.stderr)
                        ipc = None
                        current_client_id = None

                if ipc:
                    activity = {
                        "details": match.get("details"),
                        "state": match.get("state"),
                        "assets": {}
                    }
                    if match.get("large_image"):
                        activity["assets"]["large_image"] = match["large_image"]
                    if match.get("large_text"):
                        activity["assets"]["large_text"] = match["large_text"]
                    if match.get("small_image"):
                        activity["assets"]["small_image"] = match["small_image"]
                    if match.get("small_text"):
                        activity["assets"]["small_text"] = match["small_text"]

                    # TODO: add flag to auto-generate start timestamp for current run session

                    try:
                        await ipc.set_activity(activity)
                        last_match_exec = exe_name
                    except Exception as e:
                        print(f"Lost connection to Discord while updating presence: {e}", file=sys.stderr)
                        ipc = None
                        current_client_id = None
                        last_match_exec = None

        await asyncio.sleep(interval)

def main():
    parser = argparse.ArgumentParser(
        description="Windows daemon matching active processes to Discord Rich Presence profiles dynamically.",
        epilog="Example: rpc.py --config config.json --interval 10"
    )
    parser.add_argument(
        "-c", "--config",
        type=str,
        default="mappings.json",
        help="Path to the JSON mapping config file (default: mappings.json)"
    )
    parser.add_argument(
        "-i", "--interval",
        type=int,
        default=15,
        help="Scanning poll interval in seconds (default: 15)"
    )
    args = parser.parse_args()

    config_file = Path(args.config)
    if not config_file.exists():
        print(f"Error: Configuration file '{config_file}' cannot be loaded.", file=sys.stderr)
        sys.exit(1)

    print(f"Launching Discord Process Monitor using configuration: {config_file.resolve()}")
    try:
        asyncio.run(monitor_loop(config_file, args.interval))
    except KeyboardInterrupt:
        print("\nDeactivating daemon.")
        sys.exit(0)

if __name__ == "__main__":
    main()
