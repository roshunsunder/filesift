import requests
import subprocess
import os
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
    try:
        url = get_daemon_url()
        response = requests.get(f"{url}/health", timeout=1)
        return response.status_code == 200
    except:
        return False

def get_daemon_pid() -> Optional[int]:
    """Get the PID of the running daemon from PID file"""
    if not DAEMON_PID_FILE.exists():
        return None
    try:
        with open(DAEMON_PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        try:
            os.kill(pid, 0)
            return pid
        except OSError:
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
    
    try:
        process = subprocess.Popen(
            [sys.executable, str(daemon_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        save_daemon_pid(process.pid)
        return True
    except Exception as e:
        return False

def ensure_daemon_running() -> bool:
    """Ensure daemon is running, start if not"""
    if is_daemon_running():
        return True
    
    try:
        if start_daemon_process():
            import time
            time.sleep(1.0)
            return is_daemon_running()
        else:
            return False
    except Exception as e:
        return False

