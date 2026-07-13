#!/usr/bin/env python3
"""Serveur TTS local pour simulation.html — voix française (gratuit via edge-tts)."""
import asyncio
import os
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    import edge_tts
except ImportError:
    print("Installation requise : pip install edge-tts")
    raise SystemExit(1)

VOICE = "fr-FR-DeniseNeural"
PORT = int(os.getenv("TTS_PORT", "8765"))
BIND_HOST = os.getenv("BIND_HOST", "127.0.0.1")

_loop = asyncio.new_event_loop()


def _run_loop():
    asyncio.set_event_loop(_loop)
    _loop.run_forever()


_thread = threading.Thread(target=_run_loop, daemon=True)
_thread.start()


async def synthesize(text):
    communicate = edge_tts.Communicate(text, VOICE)
    parts = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            parts.append(chunk["data"])
    audio = b"".join(parts)
    if not audio:
        raise RuntimeError("edge-tts n'a renvoyé aucun audio")
    return audio


def synthesize_sync(text):
    future = asyncio.run_coroutine_threadsafe(synthesize(text), _loop)
    return future.result(timeout=45)


class TTSHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(fmt % args)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_HEAD(self):
        if self.path.startswith("/health") or self.path.startswith("/tts"):
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self._cors()
            self.end_headers()
        else:
            self.send_error(404)

    def do_GET(self):
        if self.path.startswith("/health"):
            try:
                synthesize_sync("ok")
            except Exception as e:
                self.send_error(503, f"TTS indisponible: {e}")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self._cors()
            self.end_headers()
            self.wfile.write(b"ok")
            return

        if not self.path.startswith("/tts"):
            self.send_error(404)
            return

        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        text = (qs.get("text") or [""])[0].strip()
        if not text:
            self.send_error(400, "Paramètre text manquant")
            return
        text = text[:500]

        try:
            audio = synthesize_sync(text)
        except Exception as e:
            print("Erreur synthèse:", e)
            self.send_error(500, str(e))
            return

        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self._cors()
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(audio)


if __name__ == "__main__":
    print(f"Test voix…", end=" ", flush=True)
    try:
        synthesize_sync("Bonjour")
        print("OK")
    except Exception as e:
        print(f"ÉCHEC — {e}")
        print("Vérifiez votre connexion Internet (edge-tts utilise Microsoft).")
    print(f"Voix prospect : http://127.0.0.1:{PORT}/tts?text=Bonjour")
    print(f"Santé        : http://127.0.0.1:{PORT}/health")
    print("Laissez ce terminal ouvert pendant la simulation.")
    HTTPServer((BIND_HOST, PORT), TTSHandler).serve_forever()
