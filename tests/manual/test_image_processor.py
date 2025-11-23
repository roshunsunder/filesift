#!/usr/bin/env python3
"""
Test script for ImageProcessor.
This script tests image file processing using LM Studio VLM for captioning.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any

# Add parent directories to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from src.core.file_processors.image_processor import ImageProcessor
except ImportError as e:
    print(f"ERROR: Could not import ImageProcessor: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

def test_initialization():
    """Test ImageProcessor initialization"""
    print("=" * 60)
    print("Test 1: Initialization")
    print("=" * 60)
    
    try:
        # Test with default model (uses currently loaded model in LM Studio)
        processor = ImageProcessor()
        print("✓ ImageProcessor initialized successfully (default model)")
        print(f"  Supported extensions: {processor.supported_extensions}")
        print(f"  Model name: {processor.model_name or 'Default (uses loaded model)'}")
        
        # Test with specific model name
        try:
            processor_named = ImageProcessor(model_name="qwen2-vl-2b-instruct")
            print("✓ ImageProcessor initialized successfully (named model)")
            print(f"  Model name: {processor_named.model_name}")
        except Exception as e:
            print(f"⚠ Could not initialize with named model (this is okay): {e}")
        
        return True
        
    except ImportError as e:
        print(f"✗ Initialization test failed: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Install lmstudio package: pip install lmstudio")
        return False
    except Exception as e:
        print(f"✗ Initialization test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_can_handle():
    """Test can_handle() method with various file extensions"""
    print("\n" + "=" * 60)
    print("Test 2: can_handle() Method")
    print("=" * 60)
    
    try:
        hf_token = os.getenv("HF_BEARER_TOKEN", "test_token")
        processor = ImageProcessor(hf_bearer_token=hf_token)
        
        # Test supported extensions
        supported_files = [
            Path("test.jpg"),
            Path("test.JPG"),
            Path("test.jpeg"),
            Path("test.png"),
            Path("test.gif"),
            Path("test.bmp"),
            Path("test.webp"),
        ]
        
        print("\nTesting supported extensions:")
        all_supported = True
        for file_path in supported_files:
            can_handle = processor.can_handle(file_path)
            status = "✓" if can_handle else "✗"
            print(f"  {status} {file_path.suffix}: {can_handle}")
            if not can_handle:
                all_supported = False
        
        # Test unsupported extensions
        unsupported_files = [
            Path("test.txt"),
            Path("test.pdf"),
            Path("test.py"),
            Path("test.mp4"),
        ]
        
        print("\nTesting unsupported extensions:")
        all_unsupported = True
        for file_path in unsupported_files:
            can_handle = processor.can_handle(file_path)
            status = "✓" if not can_handle else "✗"
            print(f"  {status} {file_path.suffix}: {can_handle} (should be False)")
            if can_handle:
                all_unsupported = False
        
        if all_supported and all_unsupported:
            print("\n✓ can_handle() test passed")
            return True
        else:
            print("\n✗ can_handle() test failed - some extensions not handled correctly")
            return False
        
    except Exception as e:
        print(f"✗ can_handle() test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_process_with_image():
    """Test process() method with a real image file"""
    print("\n" + "=" * 60)
    print("Test 3: process() Method with Image File")
    print("=" * 60)
    
    try:
        processor = ImageProcessor()
        
        # Look for test images in common locations
        test_image_paths = [
            Path("tests/manual/test_image.jpg"),
            Path("tests/manual/test_image.png"),
            Path("test_image.jpg"),
            Path("test_image.png"),
            Path("frontend/public/logo192.png"),
            Path("frontend/public/logo512.png"),
        ]
        
        image_path = None
        for path in test_image_paths:
            if path.exists():
                image_path = path
                break
        
        if not image_path:
            print("⚠ No test image found. Please provide an image file to test.")
            print("  Place a test image (jpg, png, etc.) in one of these locations:")
            for path in test_image_paths:
                print(f"    - {path}")
            print("\n  Or specify a path manually in the test script.")
            return None
        
        print(f"Using test image: {image_path}")
        print(f"File size: {image_path.stat().st_size} bytes")
        
        # Process the image
        print("\nProcessing image (this may take a few seconds)...")
        result = processor.process(image_path)
        
        # Validate result structure
        print("\nResult structure:")
        print(f"  content: {result.get('content', 'MISSING')[:100]}...")
        print(f"  file_type: {result.get('file_type', 'MISSING')}")
        print(f"  image_type: {result.get('image_type', 'MISSING')}")
        
        metadata = result.get('metadata', {})
        print(f"  metadata:")
        print(f"    path: {metadata.get('path', 'MISSING')}")
        print(f"    size: {metadata.get('size', 'MISSING')}")
        print(f"    modified: {metadata.get('modified', 'MISSING')}")
        
        # Validate required fields
        required_fields = ['content', 'file_type', 'image_type', 'metadata']
        missing_fields = [field for field in required_fields if field not in result]
        
        if missing_fields:
            print(f"\n✗ Missing required fields: {missing_fields}")
            return False
        
        if result['file_type'] != 'image':
            print(f"\n✗ file_type should be 'image', got '{result['file_type']}'")
            return False
        
        if not result['content']:
            print(f"\n✗ content should not be empty")
            return False
        
        print("\n✓ process() test passed")
        return True
        
    except Exception as e:
        print(f"✗ process() test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\nTroubleshooting:")
        print("1. Make sure LM Studio is running")
        print("2. Make sure a VLM (Vision-Language Model) is loaded in LM Studio")
        print("3. Verify the image file exists and is readable")
        print("4. Check that the image format is supported (JPEG, PNG, WebP)")
        print("5. Try specifying a model: processor = ImageProcessor(model_name='qwen2-vl-2b-instruct')")
        return False

def test_error_handling():
    """Test error handling for invalid files and API errors"""
    print("\n" + "=" * 60)
    print("Test 4: Error Handling")
    print("=" * 60)
    
    try:
        processor = ImageProcessor()
        
        # Test with non-existent file
        print("\nTesting with non-existent file:")
        try:
            non_existent = Path("non_existent_image.jpg")
            result = processor.process(non_existent)
            print("✗ Should have raised an exception for non-existent file")
            return False
        except (FileNotFoundError, Exception) as e:
            print(f"✓ Correctly raised exception: {type(e).__name__}")
        
        print("\nTesting with invalid file (non-image):")
        # Create a temporary text file
        test_file = Path("tests/manual/temp_test.txt")
        try:
            test_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.write_text("This is not an image")
            
            # Should fail when trying to process as image
            try:
                result = processor.process(test_file)
                print("⚠ Processing non-image file didn't raise exception")
                print("  (This might be okay if can_handle() filters it out)")
            except Exception as e:
                print(f"✓ Correctly raised exception: {type(e).__name__}")
        finally:
            if test_file.exists():
                test_file.unlink()
        
        print("\n✓ Error handling test passed")
        return True
        
    except Exception as e:
        print(f"✗ Error handling test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_api_response_structure():
    """Test that the LM Studio API response is handled correctly"""
    print("\n" + "=" * 60)
    print("Test 5: LM Studio API Integration")
    print("=" * 60)
    
    try:
        import lmstudio as lms
        
        # Test that we can initialize the model
        print("Testing LM Studio connection...")
        try:
            model = lms.llm()
            print("✓ LM Studio connection successful")
            print(f"  Model type: {type(model)}")
        except Exception as e:
            print(f"⚠ Could not connect to LM Studio: {e}")
            print("  Make sure LM Studio is running and a model is loaded")
            return None
        
        # Test that we can prepare an image (if we have one)
        test_image_paths = [
            Path("frontend/public/logo192.png"),
            Path("frontend/public/logo512.png"),
        ]
        
        image_path = None
        for path in test_image_paths:
            if path.exists():
                image_path = path
                break
        
        if image_path:
            try:
                image_handle = lms.prepare_image(str(image_path))
                print(f"✓ Image preparation successful: {image_path}")
                print(f"  Image handle type: {type(image_handle)}")
            except Exception as e:
                print(f"⚠ Could not prepare image: {e}")
        else:
            print("⚠ No test image found for API structure test")
        
        print("\n✓ LM Studio API integration test (informational)")
        return True
        
    except ImportError:
        print("⚠ Skipping: lmstudio package not installed")
        print("  Install it with: pip install lmstudio")
        return None
    except Exception as e:
        print(f"✗ API integration test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("ImageProcessor Manual Test Suite")
    print("=" * 60)
    print("\nPrerequisites:")
    print("1. LM Studio must be installed and running")
    print("2. A VLM (Vision-Language Model) must be loaded in LM Studio")
    print("   (e.g., qwen2-vl-2b-instruct - download with: lms get qwen2-vl-2b-instruct)")
    print("3. A test image file (jpg, png, webp) for processing tests")
    print("4. lmstudio package installed: pip install lmstudio")
    print("\n")
    
    results = []
    
    # Run tests
    results.append(("Initialization", test_initialization()))
    results.append(("can_handle()", test_can_handle()))
    
    process_result = test_process_with_image()
    if process_result is not None:
        results.append(("process() with Image", process_result))
    else:
        results.append(("process() with Image", None))  # Skipped
    
    results.append(("Error Handling", test_error_handling()))
    
    api_result = test_api_response_structure()
    if api_result is not None:
        results.append(("API Response Structure", api_result))
    else:
        results.append(("API Response Structure", None))  # Skipped
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, passed in results:
        if passed is None:
            status = "⚠ SKIPPED"
        elif passed:
            status = "✓ PASSED"
        else:
            status = "✗ FAILED"
        print(f"{test_name}: {status}")
    
    # Count passed tests (excluding skipped)
    passed_tests = [r for r in results if r[1] is True]
    failed_tests = [r for r in results if r[1] is False]
    skipped_tests = [r for r in results if r[1] is None]
    
    print("\n" + "=" * 60)
    print(f"Total: {len(results)} tests")
    print(f"  Passed: {len(passed_tests)}")
    print(f"  Failed: {len(failed_tests)}")
    print(f"  Skipped: {len(skipped_tests)}")
    print("=" * 60)
    
    if failed_tests:
        return 1
    elif len(passed_tests) > 0:
        return 0
    else:
        return 0  # All skipped is okay for manual tests

if __name__ == "__main__":
    sys.exit(main())

