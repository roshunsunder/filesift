#!/usr/bin/env python3
"""
Test script for Indexer and QueryDriver.
This script tests indexing and querying functionality including:
- Index creation and incremental updates
- Chunking
- BM25 and hybrid search
- Metadata enrichment
- Save/load functionality
"""

import sys
import os
import shutil
from pathlib import Path
from typing import List, Dict, Any

# Add parent directories to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from src.core.indexer import Indexer
    from src.core.query import QueryDriver
except ImportError as e:
    print(f"ERROR: Could not import modules: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

# Test configuration
TEST_DIR = Path(__file__).parent / "test_directory"
INDEX_DIR = Path(__file__).parent / "test_directory" / "test_index"
MAX_RESULTS = 10

def cleanup_test_index():
    """Remove test index directory if it exists"""
    if INDEX_DIR.exists():
        shutil.rmtree(INDEX_DIR)
        print(f"  Cleaned up existing test index at {INDEX_DIR}")

def test_initialization():
    """Test Indexer and QueryDriver initialization"""
    print("=" * 60)
    print("Test 1: Initialization")
    print("=" * 60)
    
    try:
        # Test Indexer initialization
        indexer = Indexer(TEST_DIR)
        print("✓ Indexer initialized successfully")
        print(f"  Root directory: {indexer.root}")
        print(f"  Embedding model: BAAI/bge-small-en-v1.5")
        print(f"  Processors: {len(indexer.processors)}")
        print(f"  Chunk size: {indexer.text_splitter._chunk_size}")
        
        # Test QueryDriver initialization
        query_driver = QueryDriver()
        print("✓ QueryDriver initialized successfully")
        print(f"  Embedding model: BAAI/bge-small-en-v1.5")
        print(f"  Cache TTL: {query_driver.cache.ttl}")
        
        return True, indexer, query_driver
        
    except Exception as e:
        print(f"✗ Initialization test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None, None

def test_indexing(indexer: Indexer):
    """Test indexing functionality"""
    print("\n" + "=" * 60)
    print("Test 2: Indexing")
    print("=" * 60)
    
    try:
        if not TEST_DIR.exists():
            print(f"⚠ Test directory {TEST_DIR} does not exist")
            print("  Please populate it with test files")
            return False
        
        # Count files to be indexed
        files_to_index = []
        for file_path in TEST_DIR.rglob("*"):
            if file_path.is_file():
                processor = indexer.get_processor(file_path)
                if processor:
                    files_to_index.append(file_path)
        
        print(f"  Found {len(files_to_index)} processable files in {TEST_DIR}")
        
        if len(files_to_index) == 0:
            print("  ⚠ No processable files found. Add some code or image files to test_directory")
            return False
        
        # Perform indexing
        print("  Indexing files...")
        indexer.index()
        
        # Check results
        if indexer.vector_store is None:
            print("  ✗ Vector store was not created")
            return False
        
        print(f"  ✓ Vector store created")
        print(f"  ✓ Indexed {len(indexer.metadata.indexed_files)} files")
        print(f"  ✓ Last indexed: {indexer.metadata.last_indexed}")
        
        # Check BM25 index
        if indexer.bm25_index is None:
            print("  ⚠ BM25 index was not created")
        else:
            print(f"  ✓ BM25 index created with {len(indexer.bm25_documents)} documents")
        
        # Check chunking
        total_chunks = len(indexer.bm25_documents)
        print(f"  ✓ Total chunks created: {total_chunks}")
        
        # Show some metadata
        if indexer.bm25_documents:
            sample_doc = indexer.bm25_documents[0]
            print(f"  Sample document metadata keys: {list(sample_doc.metadata.keys())}")
            if "filename" in sample_doc.metadata:
                print(f"  Sample filename: {sample_doc.metadata['filename']}")
            if "keywords" in sample_doc.metadata:
                print(f"  Sample keywords: {sample_doc.metadata['keywords']}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Indexing test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_save_load(indexer: Indexer, query_driver: QueryDriver):
    """Test save and load functionality"""
    print("\n" + "=" * 60)
    print("Test 3: Save and Load")
    print("=" * 60)
    
    try:
        cleanup_test_index()
        
        # Save index
        print("  Saving index...")
        indexer.save(INDEX_DIR)
        
        # Check saved files
        expected_files = [
            INDEX_DIR / "faiss_index",
            INDEX_DIR / "metadata.json",
            INDEX_DIR / "bm25_index.pkl",
            INDEX_DIR / "bm25_documents.pkl",
            INDEX_DIR / "bm25_file_mapping.pkl",
        ]
        
        all_exist = True
        for file_path in expected_files:
            exists = file_path.exists() if file_path.is_dir() else file_path.exists()
            status = "✓" if exists else "✗"
            print(f"  {status} {file_path.name}: {'exists' if exists else 'missing'}")
            if not exists:
                all_exist = False
        
        if not all_exist:
            return False
        
        # Create new indexer and load
        print("  Loading index into new Indexer...")
        new_indexer = Indexer(TEST_DIR)
        new_indexer.load(INDEX_DIR)
        
        # Verify loaded data
        if new_indexer.vector_store is None:
            print("  ✗ Vector store was not loaded")
            return False
        
        print(f"  ✓ Vector store loaded")
        print(f"  ✓ Loaded {len(new_indexer.metadata.indexed_files)} indexed files")
        
        if new_indexer.bm25_index is None:
            print("  ⚠ BM25 index was not loaded")
        else:
            print(f"  ✓ BM25 index loaded with {len(new_indexer.bm25_documents)} documents")
        
        # Also test loading into QueryDriver
        print("  Loading index into QueryDriver...")
        query_driver.load_from_disk(str(INDEX_DIR))
        
        if query_driver.vector_store is None:
            print("  ✗ QueryDriver vector store was not loaded")
            return False
        
        print(f"  ✓ QueryDriver vector store loaded")
        if query_driver.bm25_index:
            print(f"  ✓ QueryDriver BM25 index loaded")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Save/Load test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_semantic_search(query_driver: QueryDriver):
    """Test semantic search functionality"""
    print("\n" + "=" * 60)
    print("Test 4: Semantic Search")
    print("=" * 60)
    
    try:
        if query_driver.vector_store is None:
            print("  ⚠ Vector store not loaded. Loading from disk...")
            query_driver.load_from_disk(str(INDEX_DIR))
        
        if query_driver.vector_store is None:
            print("  ✗ Cannot test search - vector store not available")
            return False
        
        # Test queries
        test_queries = [
            "code",
            "function",
            "image",
            "python",
        ]
        
        all_passed = True
        for query in test_queries:
            print(f"\n  Query: '{query}'")
            try:
                results = query_driver.search(query, filters=None)
                print(f"    ✓ Found {len(results)} results")
                
                if len(results) > 0:
                    top_result = results[0]
                    print(f"    Top result: {top_result.path}")
                    print(f"    Score: {top_result.score:.4f}")
                    if "file_type" in top_result.metadata:
                        print(f"    File type: {top_result.metadata['file_type']}")
                else:
                    print(f"    ⚠ No results found")
                    
            except Exception as e:
                print(f"    ✗ Search failed: {str(e)}")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"  ✗ Semantic search test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_hybrid_search(query_driver: QueryDriver):
    """Test hybrid search (BM25 + semantic) functionality"""
    print("\n" + "=" * 60)
    print("Test 5: Hybrid Search (BM25 + Semantic)")
    print("=" * 60)
    
    try:
        if query_driver.bm25_index is None:
            print("  ⚠ BM25 index not loaded. Loading from disk...")
            query_driver.load_from_disk(str(INDEX_DIR))
        
        if query_driver.bm25_index is None:
            print("  ⚠ BM25 index not available - testing semantic-only search")
            return test_semantic_search(query_driver)
        
        # Test queries that should benefit from hybrid search
        test_queries = [
            ("python code", "Should match Python files via BM25"),
            ("image", "Should match image files"),
            ("function", "Should match code with functions"),
        ]
        
        all_passed = True
        for query, description in test_queries:
            print(f"\n  Query: '{query}' ({description})")
            try:
                results = query_driver.search(query, filters=None)
                print(f"    ✓ Found {len(results)} results")
                
                if len(results) > 0:
                    print(f"    Top 3 results:")
                    for i, result in enumerate(results[:3], 1):
                        print(f"      {i}. {Path(result.path).name} (score: {result.score:.4f})")
                        if "file_type" in result.metadata:
                            print(f"         Type: {result.metadata['file_type']}")
                else:
                    print(f"    ⚠ No results found")
                    
            except Exception as e:
                print(f"    ✗ Search failed: {str(e)}")
                import traceback
                traceback.print_exc()
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"  ✗ Hybrid search test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_filtering(query_driver: QueryDriver):
    """Test search filtering functionality"""
    print("\n" + "=" * 60)
    print("Test 6: Search Filtering")
    print("=" * 60)
    
    try:
        if query_driver.vector_store is None:
            query_driver.load_from_disk(str(INDEX_DIR))
        
        # Test file type filter
        print("  Testing file_type filter...")
        results_code = query_driver.search("code", filters={"file_type": "code"})
        results_image = query_driver.search("image", filters={"file_type": "image"})
        
        print(f"    Code files: {len(results_code)} results")
        print(f"    Image files: {len(results_image)} results")
        
        # Verify filters work
        all_code = all(r.metadata.get("file_type") == "code" for r in results_code)
        all_image = all(r.metadata.get("file_type") == "image" for r in results_image)
        
        if results_code:
            print(f"    ✓ Code filter: {'working' if all_code else 'not working'}")
        if results_image:
            print(f"    ✓ Image filter: {'working' if all_image else 'not working'}")
        
        # Test other filters if we have metadata
        if results_code:
            sample = results_code[0].metadata
            print(f"\n  Sample metadata keys: {list(sample.keys())}")
            if "year" in sample:
                print(f"  Testing year filter...")
                results = query_driver.search("code", filters={"min_date": "2020-01-01"})
                print(f"    Results after 2020: {len(results)}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Filtering test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_metadata_enrichment(indexer: Indexer):
    """Test that metadata is properly enriched"""
    print("\n" + "=" * 60)
    print("Test 7: Metadata Enrichment")
    print("=" * 60)
    
    try:
        if not indexer.bm25_documents:
            print("  ⚠ No documents available. Run indexing first.")
            return False
        
        # Check a sample document
        sample_doc = indexer.bm25_documents[0]
        metadata = sample_doc.metadata
        
        required_fields = [
            "path",
            "filename",
            "filename_stem",
            "extension",
            "file_type",
        ]
        
        optional_fields = [
            "parent_dir",
            "full_path",
            "year",
            "keywords",
            "chunk_index",
            "total_chunks",
        ]
        
        print("  Checking required metadata fields:")
        all_present = True
        for field in required_fields:
            present = field in metadata
            status = "✓" if present else "✗"
            value = metadata.get(field, "N/A")
            print(f"    {status} {field}: {value}")
            if not present:
                all_present = False
        
        print("\n  Checking optional metadata fields:")
        for field in optional_fields:
            present = field in metadata
            status = "✓" if present else "○"
            value = metadata.get(field, "N/A")
            if present:
                print(f"    {status} {field}: {value}")
        
        return all_present
        
    except Exception as e:
        print(f"  ✗ Metadata enrichment test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_incremental_indexing(indexer: Indexer):
    """Test incremental indexing (only changed files)"""
    print("\n" + "=" * 60)
    print("Test 8: Incremental Indexing")
    print("=" * 60)
    
    try:
        initial_count = len(indexer.metadata.indexed_files)
        print(f"  Initially indexed: {initial_count} files")
        
        # Run indexing again (should skip unchanged files)
        print("  Running indexing again (should skip unchanged files)...")
        indexer.index()
        
        final_count = len(indexer.metadata.indexed_files)
        print(f"  After second indexing: {final_count} files")
        
        if final_count == initial_count:
            print("  ✓ Incremental indexing working (no new files indexed)")
        else:
            print(f"  ⚠ File count changed (might be expected if files were modified)")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Incremental indexing test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Indexer and QueryDriver Test Suite")
    print("=" * 60)
    print(f"\nTest directory: {TEST_DIR}")
    print(f"Index directory: {INDEX_DIR}")
    print(f"\nNote: Make sure to populate {TEST_DIR} with test files")
    print("      (code files, images, etc.) before running tests.\n")
    
    # Initialize
    success, indexer, query_driver = test_initialization()
    if not success:
        print("\n✗ Failed to initialize. Exiting.")
        return
    
    # Run tests
    tests = [
        ("Indexing", lambda: test_indexing(indexer)),
        ("Save/Load", lambda: test_save_load(indexer, query_driver)),
        ("Semantic Search", lambda: test_semantic_search(query_driver)),
        ("Hybrid Search", lambda: test_hybrid_search(query_driver)),
        ("Filtering", lambda: test_filtering(query_driver)),
        ("Metadata Enrichment", lambda: test_metadata_enrichment(indexer)),
        ("Incremental Indexing", lambda: test_incremental_indexing(indexer)),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} test crashed: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed!")
    else:
        print(f"\n⚠ {total - passed} test(s) failed")
    
    # Cleanup option
    print(f"\n  Test index saved at: {INDEX_DIR}")
    print("  (Remove manually if you want to clean up)")

if __name__ == "__main__":
    main()

