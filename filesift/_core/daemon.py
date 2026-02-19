from pathlib import Path
from typing import Any, Dict, Optional
import json
import logging
import sys
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from filesift._core.query import QueryDriver
from filesift._core.indexer import Indexer, SEMANTIC_CACHE_DIR
from filesift._core.embeddings import create_embedding_model
from filesift._core.semantic_indexer import SemanticIndexer
from filesift._config.config import config_dict

class IndexManager:
    """Manages multiple QueryDriver instances, one per directory"""
    def __init__(self):
        self.drivers: Dict[str, QueryDriver] = {}
        self.loading_paths: Dict[str, threading.Thread] = {}
        self.indexing_paths: Dict[str, threading.Thread] = {}
        self.indexing_status: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
    
    def _normalize_path(self, index_path: str) -> str:
        path = Path(index_path).resolve()
        if path.name == ".filesift":
            path = path.parent
        return str(path)

    def get_driver(self, index_path: str) -> Optional[QueryDriver]:
        """Get or load QueryDriver for a given index path (blocking)"""
        normalized_path = self._normalize_path(index_path)
        
        with self._lock:
            if normalized_path in self.drivers:
                return self.drivers[normalized_path]
            
            # If it's already loading in background, we might want to wait or return None
            # For simplicity, we'll just return None here if it's already loading
            if normalized_path in self.loading_paths:
                self.logger.debug(f"Index is currently loading in background: {normalized_path}")
                return None

            try:
                # Synchronous load for immediate search needs if not already loading
                driver = QueryDriver()
                driver.load_from_disk(normalized_path)
                self.drivers[normalized_path] = driver
                self.logger.debug(f"Loaded index: {normalized_path}")
                return driver
            except Exception as e:
                self.logger.error(f"Failed to load index {normalized_path}: {e}")
                return None
    
    def reload_index(self, index_path: str) -> bool:
        """Trigger a reload of an index in the background"""
        normalized_path = self._normalize_path(index_path)
        
        with self._lock:
            if normalized_path in self.loading_paths:
                self.logger.debug(f"Reload already in progress for: {normalized_path}")
                return True
            
            thread = threading.Thread(
                target=self._bg_load,
                args=(normalized_path,),
                daemon=True
            )
            self.loading_paths[normalized_path] = thread
            thread.start()
            return True

    def _bg_load(self, path: str):
        """Background worker to load an index"""
        self.logger.debug(f"Starting background load for: {path}")
        try:
            driver = QueryDriver()
            driver.load_from_disk(path)
            with self._lock:
                self.drivers[path] = driver
                self.logger.debug(f"Background load complete: {path}")
        except Exception as e:
            self.logger.error(f"Background load failed for {path}: {e}")
        finally:
            with self._lock:
                if path in self.loading_paths:
                    del self.loading_paths[path]
    
    def unload_index(self, index_path: str):
        """Unload an index to free memory"""
        normalized_path = self._normalize_path(index_path)
        with self._lock:
            if normalized_path in self.drivers:
                del self.drivers[normalized_path]
            # If we were loading it, we let the thread finish but it won't be easily reachable
            # in self.drivers if the user actually wanted it gone. 
            # (In reality, unload usually means 'I don't need this anymore')

            # In reality, unload usually means 'I don't need this anymore')
    
    def trigger_semantic_index(self, index_path: str) -> bool:
        """Trigger background semantic indexing"""
        normalized_path = self._normalize_path(index_path)
        
        with self._lock:
            if normalized_path in self.indexing_paths:
                self.logger.debug(f"Indexing already in progress for: {normalized_path}")
                return True
            
            self.indexing_status[normalized_path] = {"phase": "starting", "percent": 0}
            
            thread = threading.Thread(
                target=self._bg_index,
                args=(normalized_path,),
                daemon=True
            )
            self.indexing_paths[normalized_path] = thread
            thread.start()
            return True

    def _bg_index(self, path: str):
        """Background worker to run semantic indexing"""
        self.logger.info(f"Starting background indexing for: {path}")
        try:
            root = Path(path)
            index_dir = root / ".filesift"

            # Setup callback
            def progress_callback(status):
                with self._lock:
                    self.indexing_status[path] = status

            # Run semantic indexing
            # We partially replicate Indexer logic here to use the callback
            with self._lock:
                self.indexing_status[path] = {"phase": "loading_model", "percent": 0}

            embedding_model = create_embedding_model()
            cache_dir = index_dir / SEMANTIC_CACHE_DIR
            
            indexer = SemanticIndexer(root, embedding_model, cache_dir)
            
            existing_entries = None
            if SemanticIndexer.exists(index_dir):
                loaded = SemanticIndexer.load(index_dir)
                if loaded:
                    _, existing_entries = loaded
            
            faiss_index, entries, stats = indexer.index(
                existing_entries, 
                progress_callback=progress_callback
            )
            
            with self._lock:
                self.indexing_status[path] = {"phase": "saving", "percent": 100}
                
            SemanticIndexer.save(faiss_index, entries, index_dir)
            self.logger.info(f"Background indexing complete for {path}")
            
            # Auto-reload the index driver if it exists
            self.reload_index(path)
            
        except Exception as e:
            import traceback
            self.logger.error(f"Background indexing failed for {path}: {e}")
            self.logger.error(traceback.format_exc())
            with self._lock:
                self.indexing_status[path] = {"phase": "error", "error": str(e)}
        finally:
            with self._lock:
                if path in self.indexing_paths:
                    del self.indexing_paths[path]
                # We optionally keep the status around for a bit, or clear it
                # For now, let's keep "completed" status or clear it if successful?
                # Let's clear it from 'indexing_paths' implies it's done. 
                # But 'indexing_status' might be useful to show "Done".
                # We'll leave it in indexing_status but maybe mark as done.
                if path in self.indexing_status and "error" not in self.indexing_status[path]:
                     self.indexing_status[path] = {"phase": "complete", "percent": 100}

    def get_status(self) -> Dict[str, Any]:
        """Get status of managed indexes"""
        with self._lock:
            # Check staleness for loaded drivers
            stale_status = {}
            for path, driver in self.drivers.items():
                # We can't easily check staleness without checking files.
                # Let's instantiate a lightweight SemanticIndexer to check.
                # Or just assume not stale for now unless we want to do IO here.
                # Better: cache the staleness check?
                # For now, let's just properly report what is known.
                pass

            return {
                "loaded": list(self.drivers.keys()),
                "loading": list(self.loading_paths.keys()),
                "indexing": self.indexing_status
            }

    def is_busy(self) -> bool:
        """Check if any background tasks are running"""
        with self._lock:
             return bool(self.loading_paths) or bool(self.indexing_paths)

class DaemonHandler(BaseHTTPRequestHandler):
    """HTTP request handler for daemon"""
    
    def do_POST(self):
        if self.path == '/search':
            self.handle_search()
        elif self.path == '/reload':
            self.handle_reload()
        elif self.path == '/index':
            self.handle_index()
        else:
            self.send_error(404)
    
    def do_GET(self):
        if self.path == '/health':
            self.handle_health()
        elif self.path == '/status':
            self.handle_status()
        else:
            self.send_error(404)
    
    def handle_search(self):
        """Handle search request - resets inactivity timer"""
        daemon_server.reset_inactivity_timer()
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        index_path = data.get('index_path')
        query = data.get('query')
        filters = data.get('filters', {})
        
        if not index_path or not query:
            self.send_error(400, "Missing index_path or query")
            return
        
        driver = daemon_server.index_manager.get_driver(index_path)
        if not driver:
            self.send_error(404, f"Index not found: {index_path}")
            return
        
        try:
            results = driver.search(query, filters)
            response = {
                "results": [r.to_dict() for r in results],
                "semantic_available": driver.semantic_available,
            }
            self.send_json_response(200, response)
        except Exception as e:
            self.send_json_response(500, {"error": str(e)})
            daemon_server.logger.error(f"Search error: {e}")
    
    def handle_reload(self):
        """Reload an index - returns 202 and loads in background"""
        daemon_server.reset_inactivity_timer()
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        index_path = data.get('index_path')
        if not index_path:
            self.send_error(400, "Missing index_path")
            return
        
        daemon_server.index_manager.reload_index(index_path)
        self.send_json_response(202, {
            "status": "accepted", 
            "message": "Index reload started in background"
        })
    
    def handle_status(self):
        """Get status of managed indexes - resets inactivity timer"""
        daemon_server.reset_inactivity_timer()
        status = daemon_server.index_manager.get_status()
        self.send_json_response(200, status)

    def handle_index(self):
        """Trigger semantic indexing"""
        daemon_server.reset_inactivity_timer()
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        index_path = data.get('index_path')
        if not index_path:
            self.send_error(400, "Missing index_path")
            return
            
        daemon_server.index_manager.trigger_semantic_index(index_path)
        self.send_json_response(202, {
            "status": "accepted",
            "message": "Background indexing started"
        })
    
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
        daemon_config = config_dict.get("daemon", {})
        self.host = daemon_config.get("HOST", "127.0.0.1")
        self.port = daemon_config.get("PORT", 8687)
        self.inactivity_timeout = daemon_config.get("INACTIVITY_TIMEOUT", 300)
        
        self.index_manager = IndexManager()
        self.server = None
        self.thread = None
        self.shutdown_timer: Optional[threading.Timer] = None
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
    
    def reset_inactivity_timer(self):
        """Reset the inactivity shutdown timer"""
        if self.inactivity_timeout <= 0:
            return
        
        with self._lock:
            if self.shutdown_timer:
                self.shutdown_timer.cancel()
            
            self.shutdown_timer = threading.Timer(
                self.inactivity_timeout,
                self._shutdown_after_inactivity
            )
            self.shutdown_timer.daemon = True
            self.shutdown_timer.start()
            self.logger.debug(f"Inactivity timer reset ({self.inactivity_timeout}s)")
    
    def _shutdown_after_inactivity(self):
        """Shutdown daemon after inactivity period"""
        if self.index_manager.is_busy():
             self.logger.info("Inactivity timeout reached, but daemon is busy. Resetting timer.")
             self.reset_inactivity_timer()
             return

        self.logger.debug(f"Daemon shutting down after {self.inactivity_timeout}s of inactivity")
        self.stop()
    
    def start(self):
        """Start daemon in background thread"""
        self.server = ThreadingHTTPServer((self.host, self.port), DaemonHandler)
        global daemon_server
        daemon_server = self
        
        def run_server():
            try:
                if self.inactivity_timeout > 0:
                    self.reset_inactivity_timer()
                    self.logger.debug(f"Daemon started on {self.host}:{self.port} (auto-shutdown after {self.inactivity_timeout}s inactivity)")
                else:
                    self.logger.debug(f"Daemon started on {self.host}:{self.port} (auto-shutdown disabled)")
                
                self.server.serve_forever()
            except Exception as e:
                self.logger.error(f"Daemon server error: {e}")
        
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
            self.logger.debug("Daemon stopped")

daemon_server = None

