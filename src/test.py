from fastmcp import Client
from server import mcp
import asyncio


async def test():
    
    client = Client(mcp)


    async with client:
        result = await client.call_tool("make_call", {
            "phone_number": "+15109497606",
            "name": "Devin",
            "call_info_notes_for_agent": "Help Devin book a haircut (low taper fade) for tomorrow at noon"
        })
        print(result)


if __name__ == "__main__":
    asyncio.run(test())