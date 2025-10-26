from fastmcp.client.transports import NodeStdioTransport, PythonStdioTransport, SSETransport, StreamableHttpTransport
import os
from fastmcp import FastMCP, Client
from dotenv import load_dotenv
import requests
from vapi import Vapi
import time
import json
from google import genai
from google.genai import types

load_dotenv()
POKE_API_KEY = os.getenv('POKE_API_KEY')
BRIGHT_DATA_API_KEY = os.getenv('BRIGHT_DATA_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
BRIGHT_DATA_MCP_URL = os.getenv('BRIGHT_DATA_MCP_URL')
ass_id = "554cfbbc-f0d0-4e1b-aa88-b460ede9c553"
phone_id = "0efe6b48-3b65-452d-9f4d-789aad9ca65c"


vapi_client = Vapi(token=os.getenv("VAPI_API_KEY"))
mcp = FastMCP("pokesense mcp")
client = genai.Client(
    api_key=GEMINI_API_KEY,
)
@mcp.tool(description="Search the web for information. Use this to get names & phone numbers of businesses to reserve or book something. Example: 'search_web(query='barbers in sf near palace of fine arts')'")
async def search_web(query: str) -> dict:
    # bright data mcp works, but not bright data api? sorry for this convoluted setup
    
    try:
        remote_client = Client(BRIGHT_DATA_MCP_URL)
        async with remote_client:

            result = await remote_client.call_tool(
                "search_engine",
                {
                    "query": query,
                    "engine": "google",  #bing or yandex
                }
            )
            
            search_results = result.content if hasattr(result, 'content') else result
            print(f"Search results for '{query}':")
            print(search_results)
            
            return {
                "status": "success",
                "data": search_results,
                "query": query,
            }
    except Exception as exc:
        print(f"Failed to search using Bright Data MCP server: {exc}")
        return {
            "status": "error",
            "error": str(exc),
        }

@mcp.tool(description="Make a call to a phone number (format: +1XXXXXXXXXX). Use this with the search engine tool to get names & phone numbers of businesses to reserve or book something.")
def make_call(phone_number: str, name: str, call_info_notes_for_agent: str) -> dict:
    #generate first msg w/ gemini flash
    model = "gemini-flash-lite-latest"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=
                f"""Write a two sentence first message for a voice assistant in the format of "Hi! I'm Poke, calling on behalf of (NAME) (REASON)."

Call information notes: {call_info_notes_for_agent}"""),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        thinking_config = types.ThinkingConfig(
            thinking_budget=0,
        ),
        response_mime_type="application/json",
        response_schema=genai.types.Schema(
            type = genai.types.Type.OBJECT,
            required = ["message"],
            properties = {
                "message": genai.types.Schema(
                    type = genai.types.Type.STRING,
                ),
            },
        ),
    )
    first_msg = ""
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        first_msg += chunk.text
    
    print("getting")
    ass = vapi_client.assistants.get(id=ass_id)

    print("\nASKDJSKJD\n")
    try:
        res = vapi_client.calls.create(
            phone_number_id=phone_id,
            customer={"number": "+15109497606"}, #change to phone number in prod
            assistant_id=ass_id,
            assistant_overrides={
                "firstMessage": first_msg,
                "variableValues": {
                    "name": name,
                }
            }
        )
        print(f"Call created: {res.status}")
        call_id = res.id
        added = False
        while True:
            res = vapi_client.calls.get(call_id)
            print(res.status)
            if res.status == "in-progress" and not added:
                print("Call is in progress")

                print("Call info notes for agent added", call_info_notes_for_agent)
                added=True
            if res.status == "ended":
                print("Call ended")
                break
            time.sleep(1)
        
        print(vars(res.analysis))
        try:
            analysis = vars(res.analysis)
        except Exception as e:
            return {
                "status": "error",
                "error": "The other party didn't pick up. Maybe try another time?",
            }
        return {
            "status": res.status,
            "created_at": res.created_at,
            "updated_at": res.updated_at,
            "analysis": vars(res.analysis) if res.analysis else None,
        }
    except Exception as e:
        print(f"Failed to create call: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
        }#ask for specific time from user

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    
    print(f"Starting FastMCP server on {host}:{port}")
    
    mcp.run(
        transport="http",
        host=host,
        port=port,
        stateless_http=True
    )
