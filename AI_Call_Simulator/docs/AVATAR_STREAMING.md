# Avatar streaming architecture

## Overview

The simulator uses a **split architecture** optimized for low-latency talking-head video:

| Layer | Role |
|-------|------|
| **HTML + JS** (`simulation.html`, `avatar_client.js`) | UI, Web Speech, OpenRouter LLM |
| **FastAPI** (`web/avatar_server/`, port **8767**) | TTS + WebSocket avatar pipeline |
| **MuseTalk** (GPU worker, port 8780) | Lip sync from portrait + audio |
| **LivePortrait / Hallo2** (GPU worker, port 8781) | Idle blinks + head motion |
| **Streamlit** (optional) | Dashboard, history, exam export — embeds HTML iframe |

Streamlit is **not** used for real-time video. The iframe loads `simulation.html`, which connects directly to FastAPI via WebSocket.

## Quick start (local)

```bash
cd AI_Call_Simulator/web
./start.sh
```

Open http://localhost:8080/simulation.html

- **Health:** http://127.0.0.1:8767/health
- **WebSocket:** ws://127.0.0.1:8767/ws/avatar

Without GPU, `AVATAR_BACKEND=stub` (default) streams TTS audio and keeps the existing idle/speaking loop videos.

## Enable MuseTalk

1. Install [MuseTalk](https://github.com/TMElyralab/MuseTalk) on a GPU machine.
2. Expose an HTTP endpoint:

   `POST /infer` — multipart: `image` (PNG portrait), `audio` (MP3) → `video/mp4` or JSON `{ "video_b64": "..." }`

3. Start the avatar server:

```bash
export AVATAR_BACKEND=musetalk
export MUSETALK_URL=http://127.0.0.1:8780
python3 run_avatar_server.py
```

Portraits are read from `web/assets/prospect-female-calm.png` and `prospect-male-calm.png`.

## Enable LivePortrait idle motion

1. Install [LivePortrait](https://github.com/KwaiVGI/LivePortrait) or [Hallo2](https://github.com/fudan-generative-vision/hallo2).
2. Expose:

   `POST /idle/stream` — multipart: `image` → chunked JPEG frames

3. Combined pipeline:

```bash
export AVATAR_BACKEND=musetalk+liveportrait
export MUSETALK_URL=http://127.0.0.1:8780
export LIVEPORTRAIT_URL=http://127.0.0.1:8781
python3 run_avatar_server.py
```

## WebSocket protocol

**Client → server**

```json
{ "type": "speak", "text": "Bonjour", "voice": "fr-FR-DeniseNeural", "tone": "calm", "portrait": "female" }
{ "type": "idle", "portrait": "female" }
{ "type": "ping" }
```

**Server → client**

```json
{ "type": "session_start", "session_id": "..." }
{ "type": "audio", "data": "<base64>", "mime": "audio/mpeg" }
{ "type": "video_chunk", "data": "<base64>", "mime": "video/mp4" }
{ "type": "fallback_loop" }
{ "type": "done", "session_id": "..." }
```

When `fallback_loop` is sent, the frontend uses pre-rendered MP4 loops (`build_avatar_videos.py`).

## Streamlit Cloud (no GPU)

**You do not need a local GPU.** Two options:

### Option A — Free, instant (default)

Browser **audio-reactive lip sync** (`viseme_lipsync.js`):

- Analyses TTS audio volume in real time
- Animates a mouth overlay on the portrait PNG
- Works with Streamlit-hosted edge-tts and browser voice
- No extra cost, no latency

Enabled automatically on Streamlit — no configuration required.

### Option B — Photorealistic lip sync (cloud GPU)

Use **Replicate Wav2Lip** — GPU runs on Replicate's servers, not yours.

1. Create account at [replicate.com](https://replicate.com)
2. Add to Streamlit Secrets:

```toml
REPLICATE_API_TOKEN = "r8_..."
```

3. Redeploy — each prospect reply generates a lip-synced MP4 (~15–45 s wait, ~$0.01–0.05 per reply)

The app shows a spinner: *Voix + lip-sync cloud*.

### Other cloud APIs (manual integration)

| Service | Quality | Latency | Cost |
|---------|---------|---------|------|
| **Replicate Wav2Lip** | Good | 15–45 s | ~$0.01/call |
| **D-ID** | Excellent | 10–30 s | ~$0.05+/call |
| **fal.ai sync-lipsync** | Very good | 10–20 s | pay per use |

## When you get a local GPU later

Keep Streamlit for dashboards. Inject the avatar API URL into the iframe config:

```python
# simulator_host.py
config["avatarApiUrl"] = "https://your-gpu-host.example.com/avatar-api"
```

The HTML component connects to FastAPI over WebSocket; Streamlit only bridges save/TTS when needed on Cloud.

## Migration from legacy `tts_server.py`

Port **8767** exposes the same `GET /tts?text=...` as the old port 8765. The frontend prefers 8767 when `/health` reports `websocket: true`.

Legacy `tts_server.py` remains available for minimal setups without FastAPI.

## Files

| File | Purpose |
|------|---------|
| `web/run_avatar_server.py` | Uvicorn entrypoint |
| `web/avatar_server/main.py` | FastAPI app + WebSocket |
| `web/avatar_server/pipeline.py` | TTS → avatar orchestration |
| `web/avatar_server/backends/musetalk.py` | MuseTalk HTTP adapter |
| `web/avatar_server/backends/liveportrait.py` | Idle animation adapter |
| `web/avatar_client.js` | Browser WebSocket client |
