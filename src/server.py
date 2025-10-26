from fastmcp.client.transports import NodeStdioTransport, PythonStdioTransport, SSETransport, StreamableHttpTransport
import os
import random
import fastmcp
from fastmcp import FastMCP
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
ass_id = "7341414f-3916-49a6-9501-69de1d5690c7"
#"c28fcf1f-6496-407e-a142-928acc714892"#"554cfbbc-f0d0-4e1b-aa88-b460ede9c553"
phone_id = "79421ad1-ee29-4dc1-a6f2-cd83a922486f"
TTS_SERVER_URL = os.getenv("TTS_SERVER_URL", "https://f2ed034e2ba5.ngrok-free.app")

vapi_client = Vapi(token="513d7c4b-27d5-4eb0-9c3d-4c61a2bcf647")
mcp = FastMCP("superdial mcp")
client = genai.Client(
    api_key=GEMINI_API_KEY,
)

def get_call_status_from_webhook(call_id: str, timeout_seconds: int = 400):
    """
    Poll the webhook status endpoint for call updates.
    This queries the tts_server for call status received via webhook.
    """
    start_time = time.time()
    poll_interval = 1  # Check every 1 second
    
    while time.time() - start_time < timeout_seconds:
        try:
            response = requests.get(f"{TTS_SERVER_URL}/api/calls/{call_id}/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                print(f"Webhook status check: {status}")
                
                if status == "ended":
                    print(f"Call {call_id} ended via webhook")
                    return {
                        "status": status,
                        "analysis": data.get("analysis"),
                        "result": data.get("result"),
                        "updated_at": data.get("updated_at")
                    }
            elif response.status_code == 404:
                print(f"Call {call_id} not yet recorded by webhook")
        except Exception as e:
            print(f"Error checking webhook status: {e}")
        
        time.sleep(poll_interval)
    
    # Timeout - return last known status from Vapi
    print(f"Webhook status check timeout after {timeout_seconds}s")
    return None
# cut b/c issues in prod?
'''
@mcp.tool(description="Search the web for information. Use this to get names & phone numbers of businesses to reserve or book something. Example: 'search_web(query='barbers in sf near palace of fine arts')'")
async def search_web(query: str) -> dict:
    # bright data mcp works, but not bright data api? sorry for this convoluted setup
    
    try:
        remote_client = fastmcp.Client(BRIGHT_DATA_MCP_URL)
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
'''
@mcp.tool(description="Make a call to a phone number (format: +1XXXXXXXXXX). Provide background information about your intentions (i.e. to book a haircut at 4pm) to the voice assistant.")
def make_call(phone_number: str, target_name: str, my_name: str, call_info_notes_for_agent: str) -> dict:
    #generate first msg w/ gemini flash
    model = "gemini-flash-lite-latest"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=
                f"""Write a two sentence first message for a voice assistant in the format of "{random.choice(['What\'s good', 'Yooo', 'Sup bro'])} {target_name}! I'm {my_name}, calling {target_name} to (REASON)."
Use the following to complete the (REASON) blank:
Call information notes: {call_info_notes_for_agent}
Target name: {target_name}
My name: {my_name}"""),
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
                    "target_name": target_name,
                    "my_name": my_name,
                }
            }
        )
        print(f"Call created: {res.status}")
        call_id = res.id

        if call_info_notes_for_agent:
            try:
                vapi_client.calls.update(
                    call_id,
                    {"messages": [{"role": "system", "message": call_info_notes_for_agent}]}
                )
                print("Call info notes for agent added", call_info_notes_for_agent)
            except Exception as update_error:
                print(f"Failed to add call info notes: {update_error}")

        # Use webhook-based status checking instead of polling
        webhook_data = get_call_status_from_webhook(call_id, timeout_seconds=400)
        
        if webhook_data:
            return {
                "status": webhook_data.get("status"),
                "analysis": webhook_data.get("analysis"),
                "result": webhook_data.get("result"),
            }
        else:
            # Fallback: Get final status from Vapi if webhook didn't complete
            res = vapi_client.calls.get(call_id)
            try:
                analysis = vars(res.analysis) if res.analysis else None
            except Exception as e:
                analysis = None
            
            return {
                "status": res.status,
                "created_at": res.created_at,
                "updated_at": res.updated_at,
                "analysis": analysis,
            }
    except Exception as e:
        print(f"Failed to create call: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
        }

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
