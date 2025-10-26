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
        result1 = await client.call_tool("search_web", {
            "query": "barbers in sf near palace of fine arts"
        })
        print(result1)

        '''result = await client.call_tool("make_call", {
            "phone_number": "+15109497606",
            "name": "Devin",
            "call_info_notes_for_agent": "Help Devin book a haircut (low taper fade) for tomorrow at noon"
        })
        print(result)'''
        
       

if __name__ == "__main__":
    asyncio.run(test())