"""D-ID talking-head lip-sync (server-side, API key stays in Secrets)."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request

DID_TALKS_URL = "https://api.d-id.com/talks"

SOURCE_IMAGES = {
    "female": (
        "https://raw.githubusercontent.com/Mahaaa11/Ai-call-simulator/main/"
        "AI_Call_Simulator/web/assets/prospect-female-calm.png"
    ),
    "male": (
        "https://raw.githubusercontent.com/Mahaaa11/Ai-call-simulator/main/"
        "AI_Call_Simulator/web/assets/prospect-male-calm.png"
    ),
}

VOICE_BY_GENDER = {
    "female": "fr-FR-DeniseNeural",
    "male": "fr-FR-HenriNeural",
}


def _auth_headers(api_key: str) -> dict[str, str]:
    token = base64.b64encode(f"{api_key.strip()}:".encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _request_json(
    url: str,
    *,
    api_key: str,
    method: str = "GET",
    payload: dict | None = None,
    timeout: int = 45,
) -> dict:
    data = None
    headers = _auth_headers(api_key)
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"D-ID HTTP {exc.code}: {body[:400]}") from exc


def create_talk_video(
    api_key: str,
    text: str,
    *,
    gender: str = "female",
    poll_timeout: int = 90,
) -> str:
    """Generate a lip-synced MP4 URL via D-ID Talks API."""
    clean = (text or "").strip()
    if not clean:
        raise ValueError("Texte vide pour le lip-sync")
    if len(clean) > 500:
        clean = clean[:500]

    g = "female" if gender == "female" else "male"
    payload = {
        "source_url": SOURCE_IMAGES[g],
        "script": {
            "type": "text",
            "input": clean,
            "provider": {
                "type": "microsoft",
                "voice_id": VOICE_BY_GENDER[g],
            },
        },
        "config": {
            "fluent": True,
            "stitch": True,
        },
    }
    created = _request_json(DID_TALKS_URL, api_key=api_key, method="POST", payload=payload)
    talk_id = created.get("id")
    if not talk_id:
        raise RuntimeError("D-ID: identifiant de talk manquant")

    deadline = time.time() + poll_timeout
    while time.time() < deadline:
        time.sleep(2.0)
        status_payload = _request_json(f"{DID_TALKS_URL}/{talk_id}", api_key=api_key)
        status = status_payload.get("status")
        if status == "done":
            video_url = status_payload.get("result_url")
            if video_url:
                return str(video_url)
            raise RuntimeError("D-ID terminé sans result_url")
        if status == "error":
            raise RuntimeError(status_payload.get("error", "Erreur D-ID"))
    raise TimeoutError("D-ID: délai dépassé (lip-sync)")
