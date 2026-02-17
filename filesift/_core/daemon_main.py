"""
Main entry point for running the daemon as a standalone process
"""
import os
# Disable parallelism for tokenizers and PyTorch to avoid issues in daemon process
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import sys
import logging

# Setup logging - this was removed in commit 6c5890c but is needed for error visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)

from filesift._core.daemon import DaemonServer

if __name__ == "__main__":
    from filesift.cli.daemon_utils import save_daemon_pid
    save_daemon_pid(os.getpid())

    daemon = DaemonServer()
    daemon.start()
    
    try:
        import signal
        def signal_handler(sig, frame):
            print(f"\n[DAEMON] Received signal {sig}, shutting down...")
            daemon.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if daemon.thread:
            daemon.thread.join()
    except KeyboardInterrupt:
        print(f"\n[DAEMON] Keyboard interrupt, shutting down...")
        daemon.stop()
        sys.exit(0)

