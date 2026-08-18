"""Speech-to-text — fully local, no cloud keys.

Captures the default microphone with `arecord` (alsa-utils) and
transcribes with faster-whisper (CPU, int8). The model downloads
once on first use, then runs offline forever.

Env overrides:
  ANTRE_STT_DEVICE      arecord PCM device (default: "default")
  ANTRE_WHISPER_MODEL   whisper model size (default: "base.en")
  ANTRE_STT_MAX_SECONDS safety cap per recording (default: 60)
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import threading

DEVICE = os.environ.get("ANTRE_STT_DEVICE", "default")
MODEL_SIZE = os.environ.get("ANTRE_WHISPER_MODEL", "base.en")
MAX_SECONDS = int(os.environ.get("ANTRE_STT_MAX_SECONDS", "60"))

_arecord = shutil.which("arecord")

_model = None
_model_lock = threading.Lock()


def available() -> bool:
    """True if a capture backend (arecord) exists on this machine."""
    return _arecord is not None


def _get_model():
    """Lazily load the whisper model (heavy — done only when needed)."""
    global _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel  # lazy: keeps startup fast

            _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
        return _model


def _transcribe(wav_path: str) -> str:
    model = _get_model()
    kwargs = {"language": "en", "beam_size": 1}
    try:
        # Silero VAD skips silence; small extra download on first use.
        segments, _info = model.transcribe(wav_path, vad_filter=True, **kwargs)
    except Exception:
        segments, _info = model.transcribe(wav_path, **kwargs)
    return " ".join(seg.text.strip() for seg in segments).strip()


class MicRecorder:
    """Hold-to-talk recording: start() spawns arecord, stop() transcribes."""

    def __init__(self):
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._wav_path: str | None = None

    @property
    def recording(self) -> bool:
        return self._proc is not None

    def start(self) -> tuple[bool, str]:
        """Begin capturing the mic. Returns (ok, error)."""
        with self._lock:
            if self._proc is not None:
                return False, "already recording"
            if _arecord is None:
                return False, "arecord not found — install alsa-utils (sudo apt install alsa-utils)"

            fd, path = tempfile.mkstemp(suffix=".wav", prefix="antre-mic-")
            os.close(fd)

            cmd = [
                _arecord, "-q",
                "-D", DEVICE,
                "-f", "S16_LE",
                "-r", "16000",
                "-c", "1",
                "-t", "wav",
                "-d", str(MAX_SECONDS),
                path,
            ]
            try:
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as exc:  # pragma: no cover
                try:
                    os.unlink(path)
                except OSError:
                    pass
                return False, f"failed to start arecord: {exc}"

            self._wav_path = path
            return True, ""

    def stop(self) -> str:
        """Stop capturing, transcribe what was heard, return text (may be "")."""
        proc, path = self._take()
        if proc is None:
            return ""
        self._finish(proc)
        try:
            return _transcribe(path)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def cancel(self) -> None:
        """Abort the current recording without transcribing."""
        proc, path = self._take()
        if proc is None:
            return
        self._finish(proc)
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass

    # ----------------------------------------------------------
    # internals
    # ----------------------------------------------------------

    def _take(self) -> tuple[subprocess.Popen | None, str | None]:
        with self._lock:
            proc, path = self._proc, self._wav_path
            self._proc = None
            self._wav_path = None
        return proc, path

    @staticmethod
    def _finish(proc: subprocess.Popen) -> None:
        """Ask arecord to finalize the WAV header, then reap it."""
        if proc.poll() is None:
            try:
                proc.send_signal(signal.SIGINT)
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        else:
            proc.wait(timeout=5)


# Singleton shared across the process.
recorder = MicRecorder()



# ============================================================
# HANDS-FREE LISTENING (voice-activated, no button to hold)
# ============================================================
#
# A long-running arecord process streams raw PCM; a lightweight
# energy-based VAD decides when you start and stop talking. When
# an utterance ends it's transcribed and broadcast to subscribers
# (the browser's SSE feed), which submits it like any command.

import array as _array
import math as _math
import queue as _queue
import time
import wave as _wave

SAMPLE_RATE = 16000
FRAME_BYTES = 960            # 30 ms of S16_LE mono at 16 kHz (960 samples)
MIN_UTTERANCE_FRAMES = 15    # 0.45 s — ignore tiny noise blips
MAX_UTTERANCE_SECONDS = 30   # hard cap per utterance
SILENCE_HANGOVER_FRAMES = 40 # ~1.2 s of quiet ends the utterance
ABS_RMS_FLOOR = 200.0        # below this, never call it speech


def _frame_rms(frame: bytes) -> float:
    """RMS amplitude of one 16 kHz S16_LE frame (0..32768)."""
    try:
        samples = _array.array("h")
        samples.frombytes(frame)
    except Exception:
        return 0.0
    if not samples:
        return 0.0
    total = 0
    for s in samples:
        total += s * s
    return _math.sqrt(total / len(samples))


def _write_wav(path: str, pcm: bytes) -> None:
    with _wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)


class VoiceListener:
    """Continuous mic capture with automatic start/stop on speech.

    Broadcasts {"type": "state", "state": ...} and
    {"type": "transcription", "text": ...} events to subscribers.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._transcriber: threading.Thread | None = None
        self._work_q: _queue.Queue = _queue.Queue()
        self._subs_lock = threading.Lock()
        self._subs: dict[int, tuple] = {}
        self._next_id = 0
        self._state = "off"

    # ----------------------------------------------------------
    # public API
    # ----------------------------------------------------------

    @property
    def active(self) -> bool:
        with self._lock:
            return self._proc is not None

    def state(self) -> str:
        with self._lock:
            return self._state

    def start(self) -> tuple[bool, str]:
        """Begin hands-free listening. Returns (ok, error)."""
        with self._lock:
            if self._proc is not None:
                return False, "hands-free already listening"
            if _arecord is None:
                return False, "arecord not found — install alsa-utils"
            try:
                proc = subprocess.Popen(
                    [_arecord, "-q", "-D", DEVICE,
                     "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1",
                     "-t", "raw"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    bufsize=FRAME_BYTES,
                )
            except Exception as exc:
                return False, f"failed to start arecord: {exc}"
            self._proc = proc
            work_q = _queue.Queue()
            self._work_q = work_q

        self._reader = threading.Thread(
            target=self._read_loop, args=(proc,), daemon=True)
        self._transcriber = threading.Thread(
            target=self._transcribe_loop, args=(work_q,), daemon=True)
        self._reader.start()
        self._transcriber.start()
        self._set_state("listening")
        return True, ""

    def stop(self) -> None:
        """Stop hands-free listening."""
        with self._lock:
            proc, self._proc = self._proc, None
            work_q = self._work_q
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
        finally:
            try:
                if proc.stdout:
                    proc.stdout.close()
            except Exception:
                pass
        work_q.put(None)  # sentinel: transcriber exits
        if self._transcriber is not None:
            self._transcriber.join(timeout=10)
        if self._reader is not None:
            self._reader.join(timeout=5)
        self._set_state("off")

    # ----------------------------------------------------------
    # subscribers (SSE feed)
    # ----------------------------------------------------------

    def subscribe(self, loop, q) -> int:
        with self._subs_lock:
            self._next_id += 1
            self._subs[self._next_id] = (loop, q)
            return self._next_id

    def unsubscribe(self, q) -> None:
        with self._subs_lock:
            for sid, (_, sub_q) in list(self._subs.items()):
                if sub_q is q:
                    del self._subs[sid]
                    return

    def _broadcast(self, event: dict) -> None:
        with self._subs_lock:
            subs = list(self._subs.values())
        for loop, q in subs:
            try:
                loop.call_soon_threadsafe(self._safe_put, q, event)
            except Exception:
                pass

    @staticmethod
    def _safe_put(q, event) -> None:
        try:
            if q.full():
                q.get_nowait()
            q.put_nowait(event)
        except Exception:
            pass

    # ----------------------------------------------------------
    # internals
    # ----------------------------------------------------------

    def _set_state(self, state: str) -> None:
        self._state = state
        self._broadcast({"type": "state", "state": state})

    @staticmethod
    def _read_exact(f, n: int) -> bytes | None:
        chunks = []
        got = 0
        while got < n:
            try:
                data = os.read(f.fileno(), n - got)
            except (OSError, ValueError):
                return None
            if not data:
                return None
            chunks.append(data)
            got += len(data)
        return b"".join(chunks)

    def _read_loop(self, proc: subprocess.Popen) -> None:
        f = proc.stdout
        noise_floor = ABS_RMS_FLOOR
        in_speech = False
        buf = bytearray()
        silence = 0
        utterance_start = 0.0

        while True:
            frame = self._read_exact(f, FRAME_BYTES)
            if frame is None:
                break
            rms = _frame_rms(frame)
            threshold = max(noise_floor * 2.5, ABS_RMS_FLOOR)

            if rms >= threshold:
                # --- speech frame ---
                if not in_speech:
                    in_speech = True
                    buf = bytearray()
                    silence = 0
                    utterance_start = time.monotonic()
                    self._set_state("recording")
                buf += frame
                if (time.monotonic() - utterance_start) >= MAX_UTTERANCE_SECONDS:
                    self._end_utterance(bytes(buf))
                    in_speech = False
                    buf = bytearray()
            else:
                if in_speech:
                    buf += frame
                    silence += 1
                    if silence >= SILENCE_HANGOVER_FRAMES:
                        self._end_utterance(bytes(buf))
                        in_speech = False
                        buf = bytearray()
                else:
                    # adapt the noise floor while idle
                    noise_floor = 0.95 * noise_floor + 0.05 * max(rms, 1.0)

    def _end_utterance(self, pcm: bytes) -> None:
        if len(pcm) < FRAME_BYTES * MIN_UTTERANCE_FRAMES:
            self._set_state("listening")
            return
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="antre-hf-")
        os.close(fd)
        try:
            _write_wav(path, pcm)
        except Exception:
            try:
                os.unlink(path)
            except OSError:
                pass
            self._set_state("listening")
            return
        self._set_state("transcribing")
        self._work_q.put(path)

    def _transcribe_loop(self, work_q: _queue.Queue) -> None:
        while True:
            path = work_q.get()
            if path is None:
                break
            try:
                text = _transcribe(path)
            except Exception:
                text = ""
            finally:
                try:
                    os.unlink(path)
                except OSError:
                    pass
            if text:
                self._broadcast({"type": "transcription", "text": text})
            self._set_state("listening")


# Hands-free singleton shared across the process.
listener = VoiceListener()
