#!/usr/bin/env python3
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

vapi_client = Vapi(token=os.getenv("VAPI_API_KEY"))
mcp = FastMCP("PokeSense MCP Server")
client = genai.Client(
    api_key=GEMINI_API_KEY,
)


@mcp.tool(description="Make a call to a phone number. Use this with the search engine tool to get names & phone numbers of businesses to reserve or book something.")
def make_call(phone_number: str, name: str, call_info_notes_for_agent: str) -> dict:
    #generate first msg w/ gemini flash
    model = "gemini-flash-latest"
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
    try:
        res = vapi_client.calls.create(
            phone_number_id="babd43f2-9da6-4c45-b9be-f143d5f58e10",
            customer={"number": phone_number},
            assistant_id="c28fcf1f-6496-407e-a142-928acc714892",
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
                '''vapi_client.calls.update(call_id, 
                {"messages": [
                    {
                    "role": "system",
                    "message": call_info_notes_for_agent,
                    }
                ]}
                )'''
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
