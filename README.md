# Rover (Raspberry Pi Zero 2 W)

Voice + vision rover stack for a USB webcam and USB microphone on Raspberry Pi Zero 2 W.

## Modules

- `src/camera.py`: USB webcam capture with reconnect logic.
- `src/camera_stream.py`: MJPEG stream server (`http://<pi-ip>:8000/`).
- `src/voice_in.py`: voice command recognition with keyboard fallback.
- `src/speech_out.py`: asynchronous text-to-speech using `espeak`.
- `src/motors.py`: TB6612FNG motor driver with PWM speed control.
- `src/vision_track.py`: HSV color tracking and steering output.
- `src/main.py`: mode control (`MANUAL` / `TRACK`) and runtime loop.

## Voice Commands

- `forward`
- `backward`
- `left`
- `right`
- `stop`
- `manual`
- `track`

## Config

- `config/camera.yaml`: webcam index, resolution, fps
- `config/pins.yaml`: TB6612FNG GPIO mapping
- `config/track.yaml`: HSV range and steering parameters

## Install

```bash
sudo apt update
sudo apt install -y espeak portaudio19-dev
python3 -m pip install -r requirements.txt
```

If OpenCV wheel install fails on Raspberry Pi OS, install distro OpenCV:

```bash
sudo apt install -y python3-opencv
```

## Run

```bash
python3 src/main.py
```

Open stream viewer:

```text
http://<pi-ip>:8000/
```

## Notes

- `src/main.py` shares one camera instance between tracking and streaming.
- If voice recognition is unavailable, `voice_in.py` falls back to keyboard input.
- To force keyboard testing mode: `VOICE_IN_MODE=keyboard python3 src/main.py`
