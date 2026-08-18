# web_app/app.py

import asyncio
import json
import os
import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from antre.agent import handle_message, history
from antre.activity import store, log_mode_change
from antre.permissions import auto_mode, set_auto_mode
from antre.web_app import stt
from antre.web_app.tts import DEFAULT_VOICE, synthesize


app = FastAPI()

templates = Jinja2Templates(directory="antre/web_app/templates")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCREENSHOT_DIR = os.path.join(PROJECT_ROOT, "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

app.mount(
 "/static",
 StaticFiles(directory="antre/web_app/static"),
 name="static",
)
app.mount(
 "/screenshots",
 StaticFiles(directory=SCREENSHOT_DIR),
 name="screenshots",
)


class ChatRequest(BaseModel):
 message: str


class ModeRequest(BaseModel):
 auto: bool


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
 response = templates.TemplateResponse(
  request=request,
  name="index.html",
 )
 response.headers["Cache-Control"] = "no-store"
 return response


@app.get("/monitor", response_class=HTMLResponse)
async def monitor(request: Request):
 """Live activity monitor — open this in its own tab."""
 return templates.TemplateResponse(
  request=request,
  name="monitor.html",
 )


@app.post("/chat")
async def chat(data: ChatRequest):
 reply, images = await handle_message(data.message)
 return {
  "response": reply,
  "images": images,
 }


# ============================================================
# SPEECH-TO-TEXT (local: arecord + faster-whisper)
# Hold-to-talk flow: POST /stt/start ... speak ... POST /stt/stop
# ============================================================

@app.post("/stt/start")
async def stt_start():
 """Begin capturing the default microphone."""
 if stt.listener.active:
  return JSONResponse(status_code=409, content={"error": "hands-free mode is listening — turn it off first"})
 ok, err = await asyncio.to_thread(stt.recorder.start)
 if not ok:
  return JSONResponse(status_code=503, content={"error": err})
 return {"recording": True}


@app.post("/stt/stop")
async def stt_stop():
 """Stop capturing and transcribe what was heard."""
 try:
  text = await asyncio.to_thread(stt.recorder.stop)
 except Exception as exc:
  return JSONResponse(
   status_code=500,
   content={"error": f"transcription failed: {exc}"},
  )
 return {"recording": False, "text": text}


@app.post("/stt/cancel")
async def stt_cancel():
 """Abort the current recording without transcribing."""
 await asyncio.to_thread(stt.recorder.cancel)
 return {"recording": False}


# ============================================================
# TEXT-TO-SPEECH (edge-tts neural voices)
# ============================================================

@app.get("/tts")
async def tts(text: str, voice: str = DEFAULT_VOICE):
 """Synthesize `text` to MP3 audio via edge-tts.

 Query params:
   text  — text to speak (plain text; markdown is stripped client-side)
   voice — edge-tts voice name (default: en-US-ChristopherNeural)
 """
 audio = await synthesize(text, voice)
 if not audio:
  return Response(status_code=400, content="no audio produced")
 return Response(
  content=audio,
  media_type="audio/mpeg",
  headers={"Cache-Control": "no-store"},
 )


# ============================================================
# AUTO MODE
# ============================================================

@app.get("/api/mode")
async def api_mode_get():
 """Current auto-mode state: {"auto": bool}"""
 return {"auto": auto_mode()}


@app.post("/api/mode")
async def api_mode_set(data: ModeRequest):
 """Flip auto mode on/off.

 ON → file edits, web browsing, searches, memory ops run
 automatically; only genuinely dangerous calls (SSH,
 destructive ops) still stop and ask for approval.
 OFF → the default policy applies to every tool.
 """
 set_auto_mode(data.auto)
 log_mode_change(data.auto)
 return {"auto": auto_mode()}


# ============================================================
# Live activity feed (SSE) for the monitor page
# ============================================================

async def _event_stream():
 q = store.subscribe()
 try:
  yield "event: hello\ndata: {}\n\n"
  while True:
   try:
    event = await asyncio.wait_for(q.get(), timeout=15)
    data = json.dumps(event, ensure_ascii=False)
    yield f"data: {data}\n\n"
   except asyncio.TimeoutError:
    yield ": keepalive\n\n"
 finally:
  store.unsubscribe(q)


@app.get("/activity/stream")
async def activity_stream():
 return StreamingResponse(
  _event_stream(),
  media_type="text/event-stream",
  headers={
   "Cache-Control": "no-cache",
   "X-Accel-Buffering": "no",
   "Connection": "keep-alive",
  },
 )


@app.get("/activity/history")
async def activity_history(limit: int = 200):
 return {"events": store.history(limit=limit)}


# ============================================================
# System status for the UI
# ============================================================

def _memory_count() -> int:
 try:
  mem_path = os.path.join(PROJECT_ROOT, "antre", "memory.json")
  with open(mem_path, "r", encoding="utf-8") as f:
   return len(json.load(f).get("entries", []))
 except Exception:
  return 0


def _screenshot_count() -> int:
 try:
  return len([
   f for f in os.listdir(SCREENSHOT_DIR)
   if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
  ])
 except Exception:
  return 0


@app.get("/api/status")
async def api_status():
 uptime = int(store.uptime_seconds)
 return {
  "online": True,
  "busy": store.busy,
  "active_tools": store.active_tools,
  "uptime_seconds": uptime,
  "uptime_human": _human_uptime(uptime),
  "history_messages": len(history),
  "memory_entries": _memory_count(),
  "screenshots": _screenshot_count(),
  "activity_events": len(store.history(0)),
  "auto_mode": auto_mode(),
  "stt_available": stt.available(),
  "stt_recording": stt.recorder.recording,
 }


def _human_uptime(seconds: int) -> str:
 h, rem = divmod(seconds, 3600)
 m, s = divmod(rem, 60)
 if h:
  return f"{h}h {m:02d}m {s:02d}s"
 if m:
  return f"{m}m {s:02d}s"
 return f"{s}s"


# ============================================================
# HANDS-FREE VOICE (voice-activated listening + SSE feed)
# ============================================================

@app.post("/stt/listen")
async def stt_listen_start():
 """Start hands-free listening — speech is auto-detected, no button."""
 if stt.recorder.recording:
  return JSONResponse(
   status_code=409,
   content={"error": "hold-to-talk recording is in progress — release the mic first"},
  )
 ok, err = await asyncio.to_thread(stt.listener.start)
 if not ok:
  if "already" in err:
   return {"listening": True}
  return JSONResponse(status_code=503, content={"error": err})
 return {"listening": True}


@app.post("/stt/listen/stop")
async def stt_listen_stop():
 """Stop hands-free listening."""
 await asyncio.to_thread(stt.listener.stop)
 return {"listening": False}


@app.get("/stt/listen/status")
async def stt_listen_status():
 """Current hands-free state: {"listening": bool, "state": str}."""
 return {"listening": stt.listener.active, "state": stt.listener.state()}


@app.get("/stt/events")
async def stt_events():
 """SSE feed — state changes and completed transcriptions."""
 loop = asyncio.get_running_loop()
 q = asyncio.Queue(maxsize=64)
 stt.listener.subscribe(loop, q)

 async def gen():
  try:
   yield "event: hello\ndata: {}\n\n"
   while True:
    try:
     event = await asyncio.wait_for(q.get(), timeout=15)
     yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    except asyncio.TimeoutError:
     yield ": keepalive\n\n"
  finally:
   stt.listener.unsubscribe(q)

 return StreamingResponse(
  gen(),
  media_type="text/event-stream",
  headers={
   "Cache-Control": "no-cache",
   "X-Accel-Buffering": "no",
   "Connection": "keep-alive",
  },
 )
