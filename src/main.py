import time
import threading
from queue import Queue, Empty, Full
from pathlib import Path

if __package__:
    from .camera import Camera
    from .camera_stream import start_server, stop_server
    from .motors import TB6612FNG
    from .speech_out import SpeechOut
    from .vision_track import VisionTracker
    from .voice_in import listen_command
else:
    from camera import Camera
    from camera_stream import start_server, stop_server
    from motors import TB6612FNG
    from speech_out import SpeechOut
    from vision_track import VisionTracker
    from voice_in import listen_command


MODE_MANUAL = "MANUAL"
MODE_TRACK = "TRACK"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _voice_worker(command_queue: "Queue[str]", stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        command = listen_command(timeout_sec=0.8)
        if command:
            try:
                command_queue.put_nowait(command)
            except Full:
                try:
                    command_queue.get_nowait()
                except Empty:
                    pass
                try:
                    command_queue.put_nowait(command)
                except Full:
                    pass


def main() -> None:
    root = _project_root()
    camera_cfg = root / "config" / "camera.yaml"
    pins_cfg = root / "config" / "pins.yaml"
    track_cfg = root / "config" / "track.yaml"

    camera = Camera.from_config_file(camera_cfg)
    motors = TB6612FNG.from_config_file(pins_cfg)
    tracker = VisionTracker.from_config_file(camera, track_cfg)
    speech = SpeechOut()
    mode = MODE_MANUAL
    command_queue: "Queue[str]" = Queue(maxsize=20)
    voice_stop = threading.Event()
    voice_thread = threading.Thread(
        target=_voice_worker,
        args=(command_queue, voice_stop),
        daemon=True,
    )

    start_server(host="0.0.0.0", port=8000, camera=camera)
    voice_thread.start()
    speech.speak("Rover ready. Manual mode.")

    try:
        while True:
            command = None
            try:
                command = command_queue.get_nowait()
            except Empty:
                pass
            if command == "manual":
                mode = MODE_MANUAL
                motors.stop()
                speech.speak("Manual mode")
            elif command == "track":
                mode = MODE_TRACK
                motors.stop()
                speech.speak("Tracking mode")
            elif command == "stop":
                motors.stop()
                mode = MODE_MANUAL
                speech.speak("Stop")
            elif mode == MODE_MANUAL:
                if command == "forward":
                    motors.forward()
                elif command == "backward":
                    motors.backward()
                elif command == "left":
                    motors.left()
                elif command == "right":
                    motors.right()

            if mode == MODE_TRACK:
                _, left_speed, right_speed = tracker.next_control()
                motors.set_speeds(left_speed, right_speed)

            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        voice_stop.set()
        voice_thread.join(timeout=2.0)
        motors.stop()
        motors.cleanup()
        stop_server()
        camera.release()
        speech.stop()


if __name__ == "__main__":
    main()
