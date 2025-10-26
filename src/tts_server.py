from __future__ import annotations

import os
import time
import uuid
from threading import Lock
from typing import Optional
import json

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from fish_audio_sdk import Session, TTSRequest
from fish_audio_sdk.exceptions import HttpCodeErr


load_dotenv()

VALID_SAMPLE_RATES = {8000, 16000, 22050, 24000}
DEFAULT_LATENCY = os.getenv("FISH_LATENCY_MODE", "balanced")

FISH_API_KEY = os.getenv("FISH_API_SECRET") or os.getenv("FISH_AUDIO_API_KEY")
FISH_REFERENCE_ID = os.getenv("FISH_REFERENCE_ID")
SERVER_SHARED_SECRET = os.getenv("TTS_SERVER_SECRET")


app = Flask(__name__)


_session_lock = Lock()
_fish_session: Optional[Session] = None

# Call state management for webhook integration
_calls_lock = Lock()
_calls_state: dict[str, dict] = {}  # Stores call data: {call_id: {"status": "...", "data": {...}}}


def get_fish_session() -> Session:
    """Initialise and cache a Fish Audio session."""

    global _fish_session

    if not FISH_API_KEY:
        raise RuntimeError(
            "Fish Audio API key is not configured. Set FISH_API_SECRET or FISH_AUDIO_API_KEY."
        )

    if _fish_session is None:
        with _session_lock:
            if _fish_session is None:
                _fish_session = Session(FISH_API_KEY)

    return _fish_session


def error_response(message: str, status_code: int = 400):
    """Return a JSON error response."""

    return jsonify({"error": message}), status_code


def parse_sample_rate(raw_value) -> Optional[int]:
    """Attempt to coerce the sample rate to an integer."""

    if raw_value is None:
        return None

    if isinstance(raw_value, int):
        return raw_value

    if isinstance(raw_value, str) and raw_value.isdigit():
        return int(raw_value)

    return None


def synthesize_audio(
    text: str,
    sample_rate: int,
    reference_id: Optional[str] = None,
    latency: str = DEFAULT_LATENCY,
) -> bytes:
    """Generate PCM16 mono audio via Fish Audio."""

    session = get_fish_session()

    tts_request = TTSRequest(
        text=text,
        format="pcm",
        sample_rate=sample_rate,
        reference_id=reference_id,
        latency=latency,
    )

    audio = bytearray()

    try:
        for chunk in session.tts(tts_request):
            if chunk:
                audio.extend(chunk)
    except HttpCodeErr:
        raise

    audio_bytes = bytes(audio)

    if len(audio_bytes) % 2 == 1:
        audio_bytes = audio_bytes[:-1]

    return audio_bytes


@app.route("/api/webhooks/call", methods=["POST"])
def call_webhook():
    """Webhook endpoint for Vapi call status updates."""
    try:
        request_body = request.json
        message = request_body.get("message", {})
        message_type = message.get("type")
        status = message.get("status")
        call_id = message.get("call", {}).get("id")
        
        if not call_id:
            print("Warning: Missing call_id in webhook")
            return {"error": "Missing call_id"}, 400
        
        # Only process status-update messages
        if message_type != "status-update":
            print(f"Webhook received: Type={message_type}, Call={call_id} (skipped - not status-update)")
            return {"received": True}, 200
        
        print(f"Webhook received: Type={message_type}, Call={call_id}, Status={status}")
        
        # Store the call state
        with _calls_lock:
            if call_id not in _calls_state:
                _calls_state[call_id] = {}
            
            _calls_state[call_id]["status"] = status
            _calls_state[call_id]["updated_at"] = time.time()
        
        # Handle ended status
        if status == "ended":
            print(f"Call {call_id} ended - analysis will be retrieved via Vapi API")
        else:
            print(f"Call {call_id} status: {status}")
        
        return {"received": True}, 200
    
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {"error": str(e)}, 500


@app.route("/api/calls/<call_id>/status", methods=["GET"])
def get_call_status(call_id: str):
    """Check the status of a specific call."""
    with _calls_lock:
        if call_id not in _calls_state:
            return {"error": "Call not found"}, 404
        
        call_data = _calls_state[call_id]
        return jsonify({
            "call_id": call_id,
            "status": call_data.get("status"),
            "analysis": call_data.get("analysis"),
            "result": call_data.get("result"),
            "updated_at": call_data.get("updated_at")
        }), 200


@app.route("/health", methods=["GET"])
def health_check():
    """Simple health endpoint for monitoring."""

    return jsonify({"status": "ok"})


@app.route("/api/synthesize", methods=["POST"])
def synthesize_endpoint():
    request_id = str(uuid.uuid4())
    started_at = time.time()

    if SERVER_SHARED_SECRET:
        provided_secret = request.headers.get("X-Server-Secret")
        if provided_secret != SERVER_SHARED_SECRET:
            return error_response("Unauthorized", 401)

    payload = request.get_json(silent=True)
    if not payload or "message" not in payload:
        return error_response("Missing message object", 400)

    message = payload["message"]
    if message.get("type") != "voice-request":
        return error_response("Invalid message type", 400)

    text = message.get("text")
    if not text or not isinstance(text, str) or not text.strip():
        return error_response("Invalid or missing text", 400)

    sample_rate = parse_sample_rate(message.get("sampleRate"))
    if sample_rate not in VALID_SAMPLE_RATES:
        return (
            jsonify(
                {
                    "error": "Unsupported sample rate",
                    "supportedSampleRates": sorted(VALID_SAMPLE_RATES),
                }
            ),
            400,
        )

    requested_reference_id = message.get("referenceId") or message.get(
        "voice", {}
    ).get("referenceId")

    reference_id = requested_reference_id or FISH_REFERENCE_ID

    try:
        audio_buffer = synthesize_audio(text.strip(), sample_rate, reference_id)
    except HttpCodeErr as http_err:
        return (
            jsonify(
                {
                    "error": "Fish Audio returned an error",
                    "statusCode": http_err.status_code,
                    "requestId": request_id,
                }
            ),
            502,
        )
    except RuntimeError as runtime_error:
        return (
            jsonify(
                {
                    "error": str(runtime_error),
                    "requestId": request_id,
                }
            ),
            500,
        )
    except Exception:
        return (
            jsonify(
                {
                    "error": "TTS synthesis failed",
                    "requestId": request_id,
                }
            ),
            500,
        )

    if not audio_buffer:
        return (
            jsonify(
                {
                    "error": "TTS synthesis produced no audio",
                    "requestId": request_id,
                }
            ),
            500,
        )

    duration_ms = int((time.time() - started_at) * 1000)

    response = Response(audio_buffer, mimetype="application/octet-stream")
    response.headers["Content-Length"] = str(len(audio_buffer))
    return response


@app.errorhandler(Exception)
def handle_unexpected_error(exc: Exception):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "3000"))
    app.run(host=host, port=port)


