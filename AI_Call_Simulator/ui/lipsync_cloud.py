"""Optional cloud lip-sync (Replicate Wav2Lip) — GPU runs on Replicate, not on your machine."""

from __future__ import annotations

import io
import os
import tempfile
import urllib.request
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
PORTRAITS = {
    "female": WEB_DIR / "assets" / "prospect-female-calm.png",
    "male": WEB_DIR / "assets" / "prospect-male-calm.png",
}

# Pinned Replicate model (Wav2Lip)
WAV2LIP_MODEL = os.getenv(
    "REPLICATE_WAV2LIP_MODEL",
    "devxpy/cog-wav2lip:dd119ff7a14de737f58af04c8cc01d9d218cbf0fabc935d0aba86488bbfb0f8a",
)


def lipsync_available() -> bool:
    return bool(os.getenv("REPLICATE_API_TOKEN", "").strip())


def generate_lipsync_video(audio: bytes, *, gender: str = "female") -> bytes | None:
    """
    Return MP4 bytes with lip-synced face, or None if unavailable/failed.
    Typical latency: 15–45 s per utterance (Replicate cold start).
    """
    token = os.getenv("REPLICATE_API_TOKEN", "").strip()
    if not token:
        return None

    portrait = PORTRAITS.get(gender, PORTRAITS["female"])
    if not portrait.exists():
        return None

    try:
        import replicate
    except ImportError:
        return None

    client = replicate.Client(api_token=token)
    with portrait.open("rb") as face_f:
        audio_io = io.BytesIO(audio)
        audio_io.name = "speech.mp3"
        output = client.run(
            WAV2LIP_MODEL,
            input={
                "face": face_f,
                "audio": audio_io,
                "pads": "0 12 0 0",
                "smooth": True,
                "fps": 25,
                "resize_factor": 2,
            },
        )

    video_url = output if isinstance(output, str) else str(output)
    if not video_url.startswith("http"):
        return None

    with urllib.request.urlopen(video_url, timeout=120) as resp:
        return resp.read()
