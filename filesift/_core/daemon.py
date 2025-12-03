from pathlib import Path
from typing import Dict, Optional
import json
import logging
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from filesift._core.query import QueryDriver
from filesift._config.config import config_dict

class IndexManager:
    """Manages multiple QueryDriver instances, one per directory"""
    def __init__(self):
        self.drivers: Dict[str, QueryDriver] = {}  # path -> QueryDriver
        self.logger = logging.getLogger(__name__)
    
    def get_driver(self, index_path: str) -> Optional[QueryDriver]:
        """Get or load QueryDriver for a given index path"""
        start_time = time.time()
        # Normalize path to ensure consistent cache keys
        normalized_path = str(Path(index_path).resolve())
        
        print(f"[DAEMON] get_driver() called with path: {index_path}")
        print(f"[DAEMON] Normalized path: {normalized_path}")
        print(f"[DAEMON] Cache keys: {list(self.drivers.keys())}")
        
        if normalized_path not in self.drivers:
            print(f"[DAEMON] Index not in cache, loading from disk: {normalized_path}")
            try:
                driver = QueryDriver()
                load_start = time.time()
                driver.load_from_disk(normalized_path)
                load_time = time.time() - load_start
                print(f"[DAEMON] Index loaded from disk in {load_time:.2f}s")
                self.drivers[normalized_path] = driver
                self.logger.info(f"Loaded index: {normalized_path}")
            except Exception as e:
                self.logger.error(f"Failed to load index {normalized_path}: {e}")
                print(f"[DAEMON] Error loading index: {e}")
                return None
        else:
            print(f"[DAEMON] Index found in cache (no disk load needed)")
        total_time = time.time() - start_time
        print(f"[DAEMON] get_driver() completed in {total_time:.2f}s")
        return self.drivers[normalized_path]
    
    def reload_index(self, index_path: str):
        """Reload an index (e.g., after reindexing)"""
        normalized_path = str(Path(index_path).resolve())
        if normalized_path in self.drivers:
            print(f"[DAEMON] Reloading index: {normalized_path}")
            del self.drivers[normalized_path]
        return self.get_driver(index_path)
    
    def unload_index(self, index_path: str):
        """Unload an index to free memory"""
        if index_path in self.drivers:
            del self.drivers[index_path]

class DaemonHandler(BaseHTTPRequestHandler):
    """HTTP request handler for daemon"""
    
    def do_POST(self):
        if self.path == '/search':
            self.handle_search()
        elif self.path == '/reload':
            self.handle_reload()
        else:
            self.send_error(404)
    
    def do_GET(self):
        if self.path == '/health':
            self.handle_health()
        else:
            self.send_error(404)
    
    def handle_search(self):
        """Handle search request - resets inactivity timer"""
        request_start = time.time()
        print(f"[DAEMON] Received search request at {time.strftime('%H:%M:%S')}")
        
        daemon_server.reset_inactivity_timer()
        
        parse_start = time.time()
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        parse_time = time.time() - parse_start
        print(f"[DAEMON] Request parsed in {parse_time:.3f}s")
        
        index_path = data.get('index_path')
        query = data.get('query')
        filters = data.get('filters', {})
        
        if not index_path or not query:
            self.send_error(400, "Missing index_path or query")
            return
        
        get_driver_start = time.time()
        driver = daemon_server.index_manager.get_driver(index_path)
        get_driver_time = time.time() - get_driver_start
        print(f"[DAEMON] Driver retrieval took {get_driver_time:.2f}s")
        
        if not driver:
            self.send_error(404, f"Index not found: {index_path}")
            return
        
        try:
            search_start = time.time()
            results = driver.search(query, filters)
            search_time = time.time() - search_start
            print(f"[DAEMON] Search execution took {search_time:.2f}s")
            
            serialize_start = time.time()
            response = {
                "results": [r.to_dict() for r in results]
            }
            serialize_time = time.time() - serialize_start
            print(f"[DAEMON] Result serialization took {serialize_time:.3f}s")
            
            self.send_json_response(200, response)
            total_time = time.time() - request_start
            print(f"[DAEMON] Total search request handled in {total_time:.2f}s")
        except Exception as e:
            self.send_json_response(500, {"error": str(e)})
            print(f"[DAEMON] Search error: {e}")
    
    def handle_reload(self):
        """Reload an index - resets inactivity timer"""
        daemon_server.reset_inactivity_timer()
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        index_path = data.get('index_path')
        if not index_path:
            self.send_error(400, "Missing index_path")
            return
        
        daemon_server.index_manager.reload_index(index_path)
        self.send_json_response(200, {"status": "reloaded"})
    
    def handle_health(self):
        """Health check - resets inactivity timer"""
        daemon_server.reset_inactivity_timer()
        self.send_json_response(200, {"status": "healthy"})
    
    def send_json_response(self, status_code, data):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass

class DaemonServer:
    def __init__(self):
        # Load config
        daemon_config = config_dict.get("daemon", {})
        self.host = daemon_config.get("HOST", "127.0.0.1")
        self.port = daemon_config.get("PORT", 8687)
        self.inactivity_timeout = daemon_config.get("INACTIVITY_TIMEOUT", 300)
        
        self.index_manager = IndexManager()
        self.server = None
        self.thread = None
        self.shutdown_timer: Optional[threading.Timer] = None
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()  # Protect timer operations
    
    def reset_inactivity_timer(self):
        """Reset the inactivity shutdown timer"""
        if self.inactivity_timeout <= 0:
            return  # Auto-shutdown disabled
        
        with self._lock:
            # Cancel existing timer if any
            if self.shutdown_timer:
                self.shutdown_timer.cancel()
            
            # Start new timer
            self.shutdown_timer = threading.Timer(
                self.inactivity_timeout,
                self._shutdown_after_inactivity
            )
            self.shutdown_timer.daemon = True
            self.shutdown_timer.start()
            self.logger.debug(f"Inactivity timer reset ({self.inactivity_timeout}s)")
    
    def _shutdown_after_inactivity(self):
        """Shutdown daemon after inactivity period"""
        self.logger.info(f"Daemon shutting down after {self.inactivity_timeout}s of inactivity")
        self.stop()
    
    def start(self):
        """Start daemon in background thread"""
        start_time = time.time()
        print(f"[DAEMON] Starting daemon server...")
        self.server = HTTPServer((self.host, self.port), DaemonHandler)
        # Set daemon_server global for handler access
        global daemon_server
        daemon_server = self
        
        def run_server():
            try:
                # Start inactivity timer
                if self.inactivity_timeout > 0:
                    self.reset_inactivity_timer()
                    print(f"[DAEMON] Daemon started on {self.host}:{self.port} (auto-shutdown after {self.inactivity_timeout}s inactivity)")
                    self.logger.info(f"Daemon started on {self.host}:{self.port} (auto-shutdown after {self.inactivity_timeout}s inactivity)")
                else:
                    print(f"[DAEMON] Daemon started on {self.host}:{self.port} (auto-shutdown disabled)")
                    self.logger.info(f"Daemon started on {self.host}:{self.port} (auto-shutdown disabled)")
                
                startup_time = time.time() - start_time
                print(f"[DAEMON] Daemon startup completed in {startup_time:.2f}s")
                self.server.serve_forever()
            except Exception as e:
                self.logger.error(f"Daemon server error: {e}")
                print(f"[DAEMON] Server error: {e}")
        
        self.thread = threading.Thread(target=run_server, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop daemon"""
        with self._lock:
            if self.shutdown_timer:
                self.shutdown_timer.cancel()
                self.shutdown_timer = None
        
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.logger.info("Daemon stopped")

daemon_server = None

