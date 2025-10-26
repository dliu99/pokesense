from fastmcp import Client
from server import mcp
import asyncio
import os
import sys
import uuid

# Add current directory to path to import tts_server module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tts_server import synthesize_audio


async def test():
    
    client = Client(mcp)


    async with client:
        result = await client.call_tool("make_call", {
            "phone_number": "+15109497606",
            "name": "Devin",
            "call_info_notes_for_agent": "Help Devin book a haircut (low taper fade) for tomorrow at noon"
        })
        print(result)
        '''

    # Test synthesize_audio function
    print("=" * 60)
    print("Testing synthesize_audio function")
    print("=" * 60)
    
    api_key = os.getenv("FISH_API_SECRET")
    if not api_key:
        print("ERROR: FISH_API_SECRET environment variable is not set")
        print("Please set your Fish Audio API key before running this test")
        return
    
    test_text = "TESTING ASF HELLOOOOOOOO"
    sample_rate = 16000
    
    print(f"Text: {test_text}")
    print(f"Sample Rate: {sample_rate}Hz")
    print(f"\nCalling synthesize_audio...")
    
    try:
        audio_data = synthesize_audio(test_text, sample_rate)
        
        if audio_data and len(audio_data) > 0:
            print(f"\n✓ Success!")
            print(f"Audio data received: {len(audio_data)} bytes")
            print(f"Audio format: Raw PCM, 16-bit signed, little-endian")
            
            # Optionally save to file for inspection
            output_file = "test_output.pcm"
            with open(output_file, "wb") as f:
                f.write(audio_data)
            print(f"Audio saved to: {output_file}")
        else:
            print(f"\n✗ Failed: No audio data returned")
    
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()'''


if __name__ == "__main__":
    asyncio.run(test())