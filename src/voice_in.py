import os
import re
import sys
from typing import Optional

try:
    import speech_recognition as sr
except ImportError:
    sr = None


COMMANDS = ("forward", "backward", "left", "right", "stop", "manual", "track")
_COMMAND_SET = set(COMMANDS)

_recognizer = None
_microphone = None


def _normalize_command(text: str) -> Optional[str]:
    cleaned = re.sub(r"[^a-z\s]", " ", text.lower())
    tokens = [t for t in cleaned.split() if t]
    if not tokens:
        return None

    # Common variants mapped to canonical commands.
    if "forward" in tokens or ("go" in tokens and "ahead" in tokens):
        return "forward"
    if "backward" in tokens or "back" in tokens or "reverse" in tokens:
        return "backward"
    if "left" in tokens:
        return "left"
    if "right" in tokens:
        return "right"
    if "stop" in tokens or "halt" in tokens:
        return "stop"
    if "manual" in tokens:
        return "manual"
    if "track" in tokens or "tracking" in tokens:
        return "track"

    for token in tokens:
        if token in _COMMAND_SET:
            return token
    return None


def _init_speech() -> bool:
    global _recognizer, _microphone
    if sr is None:
        return False
    if _recognizer is not None and _microphone is not None:
        return True

    try:
        _recognizer = sr.Recognizer()
        mic_index_str = os.getenv("VOICE_MIC_INDEX")
        mic_index = int(mic_index_str) if mic_index_str is not None else None
        _microphone = sr.Microphone(device_index=mic_index)
        return True
    except Exception:
        _recognizer = None
        _microphone = None
        return False


def _listen_speech(timeout_sec: float) -> Optional[str]:
    if not _init_speech():
        return None

    assert _recognizer is not None
    assert _microphone is not None

    try:
        with _microphone as source:
            _recognizer.adjust_for_ambient_noise(source, duration=0.2)
            audio = _recognizer.listen(
                source,
                timeout=timeout_sec,
                phrase_time_limit=timeout_sec,
            )
        text = _recognizer.recognize_google(audio)
        return _normalize_command(text)
    except Exception:
        return None


def _listen_keyboard(timeout_sec: float) -> Optional[str]:
    prompt = "Command (forward/backward/left/right/stop/manual/track): "
    if os.name == "posix":
        import select

        sys.stdout.write(prompt)
        sys.stdout.flush()
        ready, _, _ = select.select([sys.stdin], [], [], timeout_sec)
        if not ready:
            sys.stdout.write("\n")
            return None
        line = sys.stdin.readline()
        return _normalize_command(line)

    # Windows fallback: blocking input (timeout not supported with standard input()).
    try:
        line = input(prompt)
    except EOFError:
        return None
    return _normalize_command(line)


def listen_command(timeout_sec: float = 3) -> str | None:
    """
    Listen for one command and return a normalized command string or None.

    Primary path: online Google recognition via SpeechRecognition.
    Fallback path: keyboard input for testing.

    Optional env vars:
    - VOICE_IN_MODE=keyboard   # force keyboard mode
    - VOICE_MIC_INDEX=<int>    # USB microphone device index
    """
    mode = os.getenv("VOICE_IN_MODE", "").strip().lower()
    if mode == "keyboard":
        return _listen_keyboard(timeout_sec)

    cmd = _listen_speech(timeout_sec)
    if cmd is not None:
        return cmd
    return _listen_keyboard(timeout_sec)
