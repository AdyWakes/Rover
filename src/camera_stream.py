import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2

if __package__:
    from .camera import Camera
else:
    from camera import Camera


_server: ThreadingHTTPServer | None = None
_server_thread: threading.Thread | None = None
_camera: Camera | None = None
_owns_camera = False
_streaming_enabled = threading.Event()


class _MJPEGHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/":
            self._serve_index()
            return
        if self.path in ("/stream.mjpg", "/stream"):
            self._serve_stream()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def log_message(self, format: str, *args) -> None:
        # Keep console output minimal for low-resource devices.
        return

    def _serve_index(self) -> None:
        body = (
            "<!doctype html>"
            "<html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Camera Stream</title>"
            "<style>body{margin:0;background:#111;color:#eee;font-family:sans-serif;}"
            "main{display:flex;min-height:100vh;align-items:center;justify-content:center;}"
            "img{max-width:100vw;max-height:100vh;height:auto;}</style>"
            "</head><body><main><img src='/stream.mjpg' alt='MJPEG stream'></main></body></html>"
        ).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_stream(self) -> None:
        global _camera
        camera = _camera
        if camera is None:
            self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, "Camera not initialized")
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Age", "0")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()

        frame_interval = 1.0 / max(1, int(camera.fps))

        try:
            while _streaming_enabled.is_set():
                ok, frame = camera.read()
                if not ok or frame is None:
                    time.sleep(0.1)
                    continue

                encoded, jpeg = cv2.imencode(
                    ".jpg",
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 70],
                )
                if not encoded:
                    continue

                jpg = jpeg.tobytes()
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(jpg)}\r\n\r\n".encode("ascii"))
                self.wfile.write(jpg)
                self.wfile.write(b"\r\n")
                if frame_interval > 0:
                    time.sleep(frame_interval)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            return


def start_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    config_path: str | Path | None = None,
    camera: Camera | None = None,
) -> ThreadingHTTPServer:
    global _server, _server_thread, _camera, _owns_camera
    if _server is not None:
        return _server

    if camera is not None:
        _camera = camera
        _owns_camera = False
    else:
        if config_path is None:
            config_path = Path(__file__).resolve().parents[1] / "config" / "camera.yaml"
        _camera = Camera.from_config_file(config_path)
        _owns_camera = True
    _server = ThreadingHTTPServer((host, port), _MJPEGHandler)
    _server.daemon_threads = True
    _streaming_enabled.set()
    _server_thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _server_thread.start()
    return _server


def stop_server() -> None:
    global _server, _server_thread, _camera, _owns_camera
    if _server is not None:
        _streaming_enabled.clear()
        _server.shutdown()
        _server.server_close()
        _server = None
    if _server_thread is not None:
        _server_thread.join(timeout=2.0)
        _server_thread = None
    if _camera is not None and _owns_camera:
        _camera.release()
    _camera = None
    _owns_camera = False


if __name__ == "__main__":
    start_server()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop_server()
