"""
Main entry point for running the daemon as a standalone process
"""
import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import sys
from filesift._core.daemon import DaemonServer

if __name__ == "__main__":
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

