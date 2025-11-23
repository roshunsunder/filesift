#!/usr/bin/env python3
"""
Test script for LM Studio integration.
This script tests both text completion (for code summarization) 
and verifies the SDK is working correctly.
"""

import sys
from pathlib import Path

try:
    import lmstudio as lms
except ImportError:
    print("ERROR: lmstudio package not installed. Install it with: pip install lmstudio")
    sys.exit(1)

def extract_text(result):
    """Extract text from a PredictionResult or other response object"""
    if hasattr(result, 'text'):
        return result.text
    elif hasattr(result, 'content'):
        return result.content
    elif hasattr(result, 'message'):
        # If it has a message attribute, try to get content from it
        msg = result.message
        if hasattr(msg, 'content'):
            return msg.content
        return str(msg)
    else:
        return str(result)

def test_basic_completion():
    """Test basic text completion"""
    print("=" * 60)
    print("Test 1: Basic Text Completion")
    print("=" * 60)
    
    try:
        # Initialize model - you may need to adjust the model name
        # Check what models you have loaded in LM Studio
        model = lms.llm()
        print("✓ Model initialized successfully")
        
        # Test simple completion
        prompt = "Summarize the purpose of the following code:\n```\ndef hello():\n    print('Hello, World!')\n```"
        print(f"\nPrompt: {prompt[:50]}...")
        
        completion = model.complete(prompt)
        
        # Extract text from PredictionResult object
        text = extract_text(completion)
        
        # Debug: show object structure if needed
        if not text or len(text) < 10:
            print(f"\nDebug - Completion object type: {type(completion)}")
            print(f"Debug - Completion object attributes: {[a for a in dir(completion) if not a.startswith('_')]}")
        
        print(f"\nCompletion: {text}")
        print("✓ Basic completion test passed\n")
        return True
        
    except Exception as e:
        print(f"✗ Basic completion test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\nTroubleshooting:")
        print("1. Make sure LM Studio is running")
        print("2. Make sure a model is loaded in LM Studio")
        print("3. Try specifying a model: model = lms.llm('model-name')")
        return False

def test_chat_completion():
    """Test chat-style completion (similar to OpenAI ChatCompletion)"""
    print("=" * 60)
    print("Test 2: Chat Completion")
    print("=" * 60)
    
    try:
        model = lms.llm()
        print("✓ Model initialized successfully")
        
        # Test chat functionality - inspect Chat object structure
        try:
            chat = lms.Chat("You are a helpful assistant that summarizes code.")
            print(f"Chat object type: {type(chat)}")
            print(f"Chat object attributes: {dir(chat)}")
            
            chat.add_user_message("Summarize the purpose of the following code:\n```\ndef hello():\n    print('Hello, World!')\n```")
            
            # Try to access messages if available
            if hasattr(chat, 'messages'):
                print(f"\nUser message: {chat.messages[-1].content[:50]}...")
            elif hasattr(chat, 'history'):
                print(f"\nChat history available")
            else:
                print(f"\nChat object structure inspected")
            
            response = model.respond(chat)
            
            # Extract text from response
            response_text = extract_text(response)
            
            print(f"\nAssistant response: {response_text}")
            print("✓ Chat completion test passed\n")
            return True
        except AttributeError as e:
            # Chat API might work differently - try alternative approach
            print(f"\nNote: Chat API structure: {e}")
            print("Trying alternative chat approach...")
            
            # Alternative: use complete with chat-style prompt
            prompt = "You are a helpful assistant that summarizes code.\n\nUser: Summarize the purpose of the following code:\n```\ndef hello():\n    print('Hello, World!')\n```\n\nAssistant:"
            response = model.complete(prompt)
            
            response_text = extract_text(response)
            
            print(f"\nAssistant response (via complete): {response_text}")
            print("✓ Chat completion test passed (using complete method)\n")
            return True
        
    except Exception as e:
        print(f"✗ Chat completion test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_code_summarization():
    """Test code summarization (mimics CodeProcessor usage)"""
    print("=" * 60)
    print("Test 3: Code Summarization (CodeProcessor simulation)")
    print("=" * 60)
    
    try:
        model = lms.llm()
        print("✓ Model initialized successfully")
        
        # Simulate what CodeProcessor does
        code = """
def process_file(file_path: Path) -> Optional[Document]:
    try:
        processor = self.get_processor(file_path)
        if not processor:
            return None
        result = processor.process(file_path)
        return Document(page_content=result["content"], metadata=result["metadata"])
    except Exception as e:
        self.logger.error(f"Error processing {file_path}: {str(e)}")
        return None
"""
        
        prompt = f"Summarize the purpose of the following code:\n```\n{code}\n```"
        
        # Method 1: Direct completion (this is what we'll use)
        print("\nMethod 1: Direct completion")
        completion = model.complete(prompt)
        
        # Extract text from PredictionResult
        result_text = extract_text(completion)
        
        print(f"Result: {result_text[:200]}...")
        
        # Method 2: Try chat completion if available
        print("\nMethod 2: Chat completion (if available)")
        try:
            chat = lms.Chat()
            chat.add_user_message(prompt)
            response = model.respond(chat)
            
            response_text = extract_text(response)
            
            print(f"Result: {response_text[:200]}...")
        except Exception as chat_error:
            print(f"Chat method not available: {chat_error}")
            print("(This is okay - we'll use direct completion)")
        
        print("\n✓ Code summarization test passed")
        return True
        
    except Exception as e:
        print(f"✗ Code summarization test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_model_listing():
    """Test listing available models"""
    print("=" * 60)
    print("Test 4: Model Information")
    print("=" * 60)
    
    try:
        # Try to get model info
        model = lms.llm()
        print("✓ Model initialized")
        print(f"Model type: {type(model)}")
        print("\nNote: Check LM Studio UI to see which model is currently loaded")
        return True
    except Exception as e:
        print(f"✗ Could not get model info: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("LM Studio Integration Test Suite")
    print("=" * 60)
    print("\nPrerequisites:")
    print("1. LM Studio must be installed and running")
    print("2. A model must be loaded in LM Studio")
    print("3. lmstudio package must be installed: pip install lmstudio")
    print("\n")
    
    results = []
    
    # Run tests
    results.append(("Basic Completion", test_basic_completion()))
    results.append(("Chat Completion", test_chat_completion()))
    results.append(("Code Summarization", test_code_summarization()))
    results.append(("Model Information", test_model_listing()))
    
    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed! LM Studio integration is working.")
    else:
        print("✗ Some tests failed. Please check the errors above.")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())

