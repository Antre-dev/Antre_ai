# web_app/tts.py

"""Text-to-speech via Microsoft Edge's neural voices (edge-tts).

Free, high-quality neural voices streamed as MP3. Used by the
frontend so ANTRE can speak its replies aloud.
"""

import edge_tts

# Deep, calm male voice — suits the ANTRE persona.
DEFAULT_VOICE = "en-US-ChristopherNeural"

# Keep replies reasonably short so we don't stall the UI or hammer
# the edge endpoint.
MAX_CHARS = 3000


async def synthesize(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """Return MP3 bytes of `text` spoken in `voice`."""
    text = (text or "").strip()
    if not text:
        return b""
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]

    communicate = edge_tts.Communicate(text, voice, rate="+8%")
    audio = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
    return bytes(audio)
