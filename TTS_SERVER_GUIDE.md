# Fish Audio TTS Server for VAPI

A Flask-based Text-to-Speech server that integrates Fish Audio API with VAPI's custom TTS webhook system.

## Features

- ✅ VAPI-compatible custom TTS endpoint
- ✅ Fish Audio integration with voice model support
- ✅ Raw PCM audio output (16-bit, mono, little-endian)
- ✅ Multiple sample rate support (8000, 16000, 22050, 24000 Hz)
- ✅ Comprehensive request validation
- ✅ Error handling and timeout protection
- ✅ Health check endpoint
- ✅ Detailed logging

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
FISH_API_SECRET=your_fish_audio_api_key_here
```

Get your Fish Audio API key from: https://fish.audio/app/api-keys

### 3. Start the Server

```bash
python src/tts_server.py
```

The server will start on `http://localhost:3000`

## Testing

### Quick Test

Run a quick test to verify everything is working:

```bash
python src/quick_test.py
```

### Comprehensive Test Suite

Run the full test suite:

```bash
python src/test_tts_endpoint.py
```

This will test:
- Health check endpoint
- Valid TTS requests
- Different sample rates
- Invalid request handling
- Long text generation

## API Endpoints

### POST /api/synthesize

Main TTS endpoint for VAPI integration.

**Request Format:**
```json
{
  "message": {
    "type": "voice-request",
    "text": "Hello, world!",
    "sampleRate": 24000,
    "timestamp": 1677123456789
  }
}
```

**Response:**
- Status: 200 OK
- Content-Type: application/octet-stream
- Body: Raw PCM audio bytes

**Error Responses:**
- 400: Invalid request (missing fields, invalid format)
- 408: Request timeout
- 500: Server error (Fish Audio API failure)

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "TTS Server",
  "fish_audio_model": "ce7e7e565bc9460db8df2dca666a3b67"
}
```

## VAPI Configuration

Configure your VAPI assistant to use the custom TTS server:

```json
{
  "voice": {
    "provider": "custom-voice",
    "server": {
      "url": "https://your-server-url:3000/api/synthesize",
      "secret": "your-webhook-secret",
      "timeoutSeconds": 30,
      "headers": {
        "Content-Type": "application/json"
      }
    },
    "fallbackPlan": {
      "voices": [
        {
          "provider": "eleven-labs",
          "voiceId": "21m00Tcm4TlvDq8ikWAM"
        }
      ]
    }
  }
}
```

## Configuration

### Environment Variables

- `FISH_API_SECRET` (required): Your Fish Audio API key
- `PORT` (optional): Server port, defaults to 3000

### Server Settings

Edit `src/tts_server.py` to customize:

```python
FISH_MODEL_ID = "ce7e7e565bc9460db8df2dca666a3b67"  # Fish Audio voice model
PORT = 3000                                          # Server port
TIMEOUT_SECONDS = 30                                 # Request timeout
```

## Voice Models

The default voice model ID is `ce7e7e565bc9460db8df2dca666a3b67`.

To use a different voice:
1. Browse voices at https://fish.audio
2. Copy the model ID from the URL (e.g., `https://fish.audio/m/MODEL_ID`)
3. Update `FISH_MODEL_ID` in `src/tts_server.py`

## Audio Format

The server outputs raw PCM audio with these specifications:

- **Format:** Raw PCM (no headers)
- **Channels:** 1 (mono)
- **Bit Depth:** 16-bit signed integer
- **Byte Order:** Little-endian
- **Sample Rate:** Matches the request (8000-24000 Hz)

## Deployment

### Local Testing with ngrok

```bash
# Start the server
python src/tts_server.py

# In another terminal, expose with ngrok
ngrok http 3000
```

Use the ngrok URL in your VAPI configuration.

### Production Deployment

For production, deploy to:
- **Render**: Update `render.yaml` to include TTS server
- **Railway**: One-click deploy
- **Heroku**: Add Procfile with web process
- **DigitalOcean**: Docker container

Make sure to:
- Set `FISH_API_SECRET` environment variable
- Use HTTPS for security
- Configure proper timeout settings
- Set up monitoring and logging

## Troubleshooting

### "FISH_API_SECRET environment variable is not set"

Set your Fish Audio API key in `.env` file or environment variables.

### "Cannot connect to server"

Make sure the server is running:
```bash
python src/tts_server.py
```

### "Fish Audio API error"

Check that:
- Your API key is valid
- You have sufficient credits
- The model ID exists and is accessible

### Audio playback issues

Verify:
- Audio format is raw PCM (no headers)
- Sample rate matches the request
- Audio is mono (1 channel)
- Byte order is little-endian

### Timeout errors

Increase timeout in VAPI configuration:
```json
{
  "voice": {
    "server": {
      "timeoutSeconds": 45
    }
  }
}
```

## Logs

The server logs detailed information:
- Request IDs for tracking
- Synthesis duration
- Audio size
- Errors and warnings

Example log output:
```
2025-10-26 10:30:45 - __main__ - INFO - [req_1677123456789] TTS request started
2025-10-26 10:30:45 - __main__ - INFO - [req_1677123456789] Validated - text_length=25, sample_rate=24000Hz
2025-10-26 10:30:46 - __main__ - INFO - Synthesizing audio: text_length=25, sample_rate=24000Hz
2025-10-26 10:30:46 - __main__ - INFO - Audio synthesis complete: 96000 bytes, 3 chunks
2025-10-26 10:30:46 - __main__ - INFO - [req_1677123456789] Success - 96000 bytes, 1.23s
```

## Support

- Fish Audio Docs: https://fish.audio/docs
- VAPI Custom TTS Guide: https://docs.vapi.ai/customization/custom-voices/custom-tts
- Issues: Contact your development team

## License

MIT License - feel free to modify and use in your projects.

