"""
Quick test to verify TTS server is working.
Run this after starting the TTS server with: python src/tts_server.py
"""

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def quick_test():
    """Quick test of the TTS endpoint."""
    
    # Check if API key is set
    if not os.getenv('FISH_API_SECRET'):
        print("❌ ERROR: FISH_API_SECRET environment variable not set!")
        print("Please set your Fish Audio API key in .env file")
        return
    
    print("Testing TTS server at http://localhost:3000...")
    print("-" * 50)
    
    # Test health check
    print("\n1. Health Check...")
    try:
        response = requests.get("http://localhost:3000/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ Health check passed")
            print(f"   {json.dumps(response.json(), indent=6)}")
        else:
            print(f"   ❌ Health check failed: {response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ Cannot connect to server: {e}")
        print("\n   Make sure the server is running:")
        print("   python src/tts_server.py")
        return
    
    # Test TTS endpoint
    print("\n2. TTS Synthesis...")
    payload = {
        "message": {
            "type": "voice-request",
            "text": "Hello! This is a quick test of the TTS system.",
            "sampleRate": 24000
        }
    }
    
    try:
        response = requests.post(
            "http://localhost:3000/api/synthesize",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            audio_data = response.content
            output_file = "quick_test_output.pcm"
            
            with open(output_file, "wb") as f:
                f.write(audio_data)
            
            print(f"   ✅ TTS synthesis successful!")
            print(f"   Audio size: {len(audio_data)} bytes")
            print(f"   Saved to: {output_file}")
            print(f"   Audio duration: {len(audio_data) / (2 * 24000):.2f}s")
            
            print("\n" + "=" * 50)
            print("✅ ALL TESTS PASSED!")
            print("=" * 50)
            print("\nYour TTS server is working correctly!")
            print("You can now use it with VAPI by pointing to:")
            print("http://your-server-url:3000/api/synthesize")
            
        else:
            print(f"   ❌ TTS request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"   ❌ TTS request error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    quick_test()

