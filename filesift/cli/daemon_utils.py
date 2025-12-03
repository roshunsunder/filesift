import requests
import time
import subprocess
import os
import json
from pathlib import Path
from typing import Optional
from filesift._config.config import config_dict
from platformdirs import user_config_dir

APP_NAME = "filesift"
DAEMON_CONFIG_DIR = Path(user_config_dir(APP_NAME))
DAEMON_PID_FILE = DAEMON_CONFIG_DIR / "daemon.pid"

def get_daemon_url() -> str:
    """Get daemon URL from config"""
    daemon_config = config_dict.get("daemon", {})
    host = daemon_config.get("HOST", "127.0.0.1")
    port = daemon_config.get("PORT", 8687)
    return f"http://{host}:{port}"

def is_daemon_running() -> bool:
    """Check if daemon is running by attempting connection"""
    check_start = time.time()
    try:
        url = get_daemon_url()
        response = requests.get(f"{url}/health", timeout=1)
        check_time = time.time() - check_start
        if response.status_code == 200:
            print(f"[CLI] Daemon health check: running (took {check_time:.3f}s)")
            return True
        else:
            print(f"[CLI] Daemon health check: not running (status {response.status_code}, took {check_time:.3f}s)")
            return False
    except Exception as e:
        check_time = time.time() - check_start
        print(f"[CLI] Daemon health check: not running (exception: {type(e).__name__}, took {check_time:.3f}s)")
        return False

def get_daemon_pid() -> Optional[int]:
    """Get the PID of the running daemon from PID file"""
    if not DAEMON_PID_FILE.exists():
        return None
    try:
        with open(DAEMON_PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        # Check if process is actually running
        try:
            os.kill(pid, 0)  # Signal 0 just checks if process exists
            return pid
        except OSError:
            # Process doesn't exist, remove stale PID file
            DAEMON_PID_FILE.unlink()
            return None
    except (ValueError, IOError):
        return None

def save_daemon_pid(pid: int):
    """Save daemon PID to file"""
    DAEMON_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(DAEMON_PID_FILE, 'w') as f:
        f.write(str(pid))

def start_daemon_process() -> bool:
    """Start daemon as a separate process"""
    import sys
    daemon_script = Path(__file__).parent.parent / "_core" / "daemon_main.py"
    
    # Start daemon in background
    try:
        process = subprocess.Popen(
            [sys.executable, str(daemon_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True  # Detach from parent
        )
        save_daemon_pid(process.pid)
        print(f"[CLI] Started daemon process with PID {process.pid}")
        return True
    except Exception as e:
        print(f"[CLI] Failed to start daemon process: {e}")
        return False

def ensure_daemon_running() -> bool:
    """Ensure daemon is running, start if not"""
    ensure_start = time.time()
    
    if is_daemon_running():
        ensure_time = time.time() - ensure_start
        print(f"[CLI] Daemon already running (check took {ensure_time:.3f}s)")
        return True
    
    print(f"[CLI] Daemon not running, starting...")
    start_daemon_start = time.time()
    try:
        if start_daemon_process():
            # Give it a moment to start
            time.sleep(1.0)  # Increased wait time for process startup
            start_daemon_time = time.time() - start_daemon_start
            print(f"[CLI] Daemon start attempt took {start_daemon_time:.2f}s")
            is_running = is_daemon_running()
            ensure_time = time.time() - ensure_start
            print(f"[CLI] ensure_daemon_running() completed in {ensure_time:.2f}s")
            return is_running
        else:
            ensure_time = time.time() - ensure_start
            print(f"[CLI] Failed to start daemon (took {ensure_time:.2f}s)")
            return False
    except Exception as e:
        ensure_time = time.time() - ensure_start
        print(f"[CLI] Failed to start daemon: {e} (took {ensure_time:.2f}s)")
        return False

