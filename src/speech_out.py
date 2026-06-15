import queue
import subprocess
import threading
from typing import Optional


class SpeechOut:
    def __init__(self, voice: str | None = None, speed: int = 160):
        self.voice = voice
        self.speed = speed
        self._queue: "queue.Queue[Optional[str]]" = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def speak(self, text: str) -> None:
        if not text:
            return
        if not self._running:
            self.start()
        self._queue.put(text)

    def _worker(self) -> None:
        while self._running:
            text = self._queue.get()
            if text is None:
                self._queue.task_done()
                break
            cmd = ["espeak", "-s", str(self.speed)]
            if self.voice:
                cmd += ["-v", self.voice]
            cmd.append(text)
            try:
                subprocess.run(
                    cmd,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except FileNotFoundError:
                pass
            self._queue.task_done()

    def stop(self, wait: bool = True) -> None:
        if not self._running:
            return
        self._running = False
        self._queue.put(None)
        if self._thread is not None and wait:
            self._thread.join(timeout=2.0)
        self._thread = None

