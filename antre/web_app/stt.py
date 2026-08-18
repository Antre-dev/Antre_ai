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
