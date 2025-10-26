"""Flask-based TTS bridge for VAPI requests using Fish Audio SDK."""

from __future__ import annotations

import logging
import os
import time
import uuid
from threading import Lock
from typing import Optional

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from fish_audio_sdk import Session, TTSRequest
from fish_audio_sdk.exceptions import HttpCodeErr


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("pokesense.tts_server")


VALID_SAMPLE_RATES = {8000, 16000, 22050, 24000}
DEFAULT_LATENCY = os.getenv("FISH_LATENCY_MODE", "balanced")

FISH_API_KEY = os.getenv("FISH_API_SECRET") or os.getenv("FISH_AUDIO_API_KEY")
FISH_REFERENCE_ID = os.getenv("FISH_REFERENCE_ID")
SERVER_SHARED_SECRET = os.getenv("TTS_SERVER_SECRET")


# ---------------------------------------------------------------------------
# Flask application setup
# ---------------------------------------------------------------------------

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Fish Audio session management
# ---------------------------------------------------------------------------

_session_lock = Lock()
_fish_session: Optional[Session] = None


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
                logger.info("Creating Fish Audio session")
                _fish_session = Session(FISH_API_KEY)

    return _fish_session


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


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
    except HttpCodeErr as http_err:
        logger.error(
            "Fish Audio request failed (status=%s message=%s)",
            http_err.status_code,
            http_err.message,
        )
        raise

    audio_bytes = bytes(audio)

    # Ensure even number of bytes (16-bit samples)
    if len(audio_bytes) % 2 == 1:
        audio_bytes = audio_bytes[:-1]

    return audio_bytes


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/health", methods=["GET"])
def health_check():
    """Simple health endpoint for monitoring."""

    return jsonify({"status": "ok"})


@app.route("/api/synthesize", methods=["POST"])
def synthesize_endpoint():
    request_id = str(uuid.uuid4())
    started_at = time.time()
    logger.info("TTS request started id=%s", request_id)

    if SERVER_SHARED_SECRET:
        provided_secret = request.headers.get("X-Server-Secret")
        if provided_secret != SERVER_SHARED_SECRET:
            logger.warning("Unauthorized request id=%s", request_id)
            return error_response("Unauthorized", 401)

    payload = request.get_json(silent=True)
    if not payload or "message" not in payload:
        logger.debug("Request missing message object id=%s", request_id)
        return error_response("Missing message object", 400)

    message = payload["message"]
    if message.get("type") != "voice-request":
        logger.debug("Invalid message type id=%s", request_id)
        return error_response("Invalid message type", 400)

    text = message.get("text")
    if not text or not isinstance(text, str) or not text.strip():
        logger.debug("Invalid text payload id=%s", request_id)
        return error_response("Invalid or missing text", 400)

    sample_rate = parse_sample_rate(message.get("sampleRate"))
    if sample_rate not in VALID_SAMPLE_RATES:
        logger.debug(
            "Unsupported sample rate id=%s sample_rate=%s", request_id, sample_rate
        )
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

    if requested_reference_id and requested_reference_id != reference_id:
        logger.info(
            "Using caller-supplied reference id=%s request_id=%s",
            requested_reference_id,
            request_id,
        )

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
        logger.exception("Configuration error id=%s", request_id)
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
        logger.exception("Unexpected error during synthesis id=%s", request_id)
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
        logger.error("Empty audio buffer generated id=%s", request_id)
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
    logger.info(
        "TTS request completed id=%s bytes=%s durationMs=%s",
        request_id,
        len(audio_buffer),
        duration_ms,
    )

    response = Response(audio_buffer, mimetype="application/octet-stream")
    response.headers["Content-Length"] = str(len(audio_buffer))
    return response


@app.errorhandler(Exception)
def handle_unexpected_error(exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "3000"))
    app.run(host=host, port=port)


