from pathlib import Path
from typing import Dict, Any, List
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

from ..core.indexer import Indexer
from ..core.query import QueryDriver
from ..config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG_MODE else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Initialize core components
indexer = Indexer(Path(settings.ROOT_PATH))
query_driver = QueryDriver()

def init_components():
    """Initialize indexer and query driver"""
    try:
        # Load existing index if available
        index_path = Path("faiss_index")
        if index_path.exists():
            indexer.load(index_path)
            query_driver.load_from_disk(str(index_path))
        else:
            # Create new index
            indexer.index()
            indexer.save(index_path)
            query_driver.load_from_disk(str(index_path))
    except Exception as e:
        logger.error(f"Error initializing components: {str(e)}")
        raise

@app.before_first_request
def before_first_request():
    """Initialize components before first request"""
    init_components()

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/search', methods=['POST'])
def search():
    """Search endpoint with filtering support"""
    try:
        data = request.json
        if not data or 'query' not in data:
            return jsonify({
                "error": "Missing query parameter"
            }), 400
            
        # Extract query and filters
        query = data['query']
        filters = data.get('filters', {})
        
        # Validate filters
        valid_filters = {
            'file_type', 'min_date', 'max_date',
            'min_size', 'max_size'
        }
        invalid_filters = set(filters.keys()) - valid_filters
        if invalid_filters:
            return jsonify({
                "error": f"Invalid filters: {invalid_filters}"
            }), 400
            
        # Perform search
        results = query_driver.search(query, filters)
        
        return jsonify({
            "results": [r.to_dict() for r in results]
        })
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return jsonify({
            "error": "Internal server error"
        }), 500

@app.route('/reindex', methods=['POST'])
def reindex():
    """Force reindexing of the filesystem"""
    try:
        indexer.index()
        indexer.save(Path("faiss_index"))
        query_driver.load_from_disk("faiss_index")
        
        return jsonify({
            "status": "success",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Reindex error: {str(e)}")
        return jsonify({
            "error": "Internal server error"
        }), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get index statistics"""
    try:
        return jsonify({
            "last_indexed": indexer.metadata.last_indexed.isoformat(),
            "total_files": len(indexer.metadata.indexed_files),
            "index_version": indexer.metadata.version
        })
    except Exception as e:
        logger.error(f"Stats error: {str(e)}")
        return jsonify({
            "error": "Internal server error"
        }), 500

if __name__ == "__main__":
    app.run(
        host=settings.API_HOST,
        port=settings.API_PORT,
        debug=settings.DEBUG_MODE
    ) 