/**
 * WebSocket client for FastAPI avatar server (MuseTalk / LivePortrait).
 * Falls back gracefully when server is unavailable.
 */
(function (global) {
    "use strict";

    function wsUrlFromHttp(base) {
        const url = String(base || "").replace(/\/$/, "");
        if (!url) return "";
        if (url.startsWith("ws://") || url.startsWith("wss://")) return url + "/ws/avatar";
        return url.replace(/^http/, "ws") + "/ws/avatar";
    }

    function AvatarClient(options) {
        this.httpBase = (options && options.httpBase) || "";
        this.wsUrl = wsUrlFromHttp(this.httpBase);
        this.ws = null;
        this._connectPromise = null;
        this._idleCanvas = null;
        this._liveVideo = null;
        this._liveBlobUrl = null;
    }

    AvatarClient.prototype.isConfigured = function () {
        return !!this.httpBase;
    };

    AvatarClient.prototype.checkHealth = async function () {
        if (!this.httpBase) return false;
        try {
            const res = await fetch(this.httpBase + "/health", { method: "GET" });
            if (!res.ok) return false;
            const data = await res.json();
            return !!(data && data.ok);
        } catch (_) {
            return false;
        }
    };

    AvatarClient.prototype.connect = function () {
        if (!this.wsUrl) return Promise.resolve(null);
        if (this.ws && this.ws.readyState === WebSocket.OPEN) return Promise.resolve(this.ws);
        if (this._connectPromise) return this._connectPromise;

        this._connectPromise = new Promise((resolve, reject) => {
            let ws;
            try {
                ws = new WebSocket(this.wsUrl);
            } catch (err) {
                this._connectPromise = null;
                reject(err);
                return;
            }
            ws.onopen = () => {
                this.ws = ws;
                this._connectPromise = null;
                resolve(ws);
            };
            ws.onerror = () => {
                this._connectPromise = null;
                reject(new Error("WebSocket connection failed"));
            };
            ws.onclose = () => {
                if (this.ws === ws) this.ws = null;
            };
        });
        return this._connectPromise;
    };

    AvatarClient.prototype.ensureLiveVideo = function () {
        if (this._liveVideo) return this._liveVideo;
        const frame = document.getElementById("prospectFrame");
        const media = frame && frame.querySelector(".prospect-media");
        if (!media) return null;

        let vid = document.getElementById("prospectAvatarLive");
        if (!vid) {
            vid = document.createElement("video");
            vid.id = "prospectAvatarLive";
            vid.className = "prospect-video speaking-layer avatar-live";
            vid.playsInline = true;
            vid.muted = false;
            vid.preload = "auto";
            media.appendChild(vid);
        }
        this._liveVideo = vid;
        return vid;
    };

    AvatarClient.prototype.hideLoopVideos = function () {
        const idle = document.getElementById("prospectVideoIdle");
        const speak = document.getElementById("prospectVideoSpeak");
        if (idle) idle.style.opacity = "0";
        if (speak) speak.style.opacity = "0";
        const live = this.ensureLiveVideo();
        if (live) live.style.opacity = "1";
    };

    AvatarClient.prototype.showLoopVideos = function () {
        const idle = document.getElementById("prospectVideoIdle");
        const speak = document.getElementById("prospectVideoSpeak");
        const live = this._liveVideo;
        if (live) {
            live.pause();
            live.removeAttribute("src");
            live.style.opacity = "0";
        }
        if (idle) idle.style.opacity = "1";
        if (speak) speak.style.opacity = "1";
    };

    AvatarClient.prototype.revokeLiveBlob = function () {
        if (this._liveBlobUrl) {
            URL.revokeObjectURL(this._liveBlobUrl);
            this._liveBlobUrl = null;
        }
    };

    AvatarClient.prototype.playVideoBlob = async function (b64, mime) {
        const live = this.ensureLiveVideo();
        if (!live || !b64) return false;
        this.hideLoopVideos();
        this.revokeLiveBlob();
        const bin = atob(b64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        const blob = new Blob([bytes], { type: mime || "video/mp4" });
        this._liveBlobUrl = URL.createObjectURL(blob);
        live.src = this._liveBlobUrl;
        live.load();
        await new Promise((resolve, reject) => {
            live.onended = () => resolve(true);
            live.onerror = () => reject(new Error("Live avatar video failed"));
            const p = live.play();
            if (p && p.catch) p.catch(reject);
        });
        return true;
    };

    AvatarClient.prototype.playAudioB64 = function (b64, mime, settings) {
        return new Promise((resolve, reject) => {
            if (!b64) return resolve(null);
            const bin = atob(b64);
            const bytes = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
            const blob = new Blob([bytes], { type: (mime || "audio/mpeg").split(";")[0] });
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            audio.volume = (settings && settings.volume) || 1;
            audio.playbackRate = (settings && settings.playbackRate) || 1;
            audio.onended = () => {
                URL.revokeObjectURL(url);
                resolve(audio);
            };
            audio.onerror = () => {
                URL.revokeObjectURL(url);
                reject(new Error("Audio playback failed"));
            };
            const p = audio.play();
            if (p && p.catch) p.catch(reject);
        });
    };

    AvatarClient.prototype.speak = async function (payload) {
        await this.connect();
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            throw new Error("Avatar WebSocket not connected");
        }

        const settings = payload.voiceSettings || {};
        let useLoopFallback = false;
        let audioMsg = null;
        let videoMsg = null;

        return new Promise((resolve, reject) => {
            const finish = async () => {
                try {
                    if (videoMsg && videoMsg.data) {
                        this.hideLoopVideos();
                        if (typeof payload.onSpeechStart === "function") payload.onSpeechStart();
                        const audioP = audioMsg
                            ? this.playAudioB64(audioMsg.data, audioMsg.mime, settings)
                            : Promise.resolve(null);
                        const videoP = this.playVideoBlob(videoMsg.data, videoMsg.mime);
                        await Promise.all([audioP, videoP]);
                        if (typeof payload.onSpeechEnd === "function") payload.onSpeechEnd();
                        this.showLoopVideos();
                        resolve({ ok: true, usedLoop: false, videoPlayed: true });
                        return;
                    }

                    if (useLoopFallback && typeof payload.onFallbackLoop === "function") {
                        payload.onFallbackLoop();
                    }
                    if (audioMsg) {
                        if (typeof payload.onSpeechStart === "function") payload.onSpeechStart();
                        await this.playAudioB64(audioMsg.data, audioMsg.mime, settings);
                        if (typeof payload.onSpeechEnd === "function") payload.onSpeechEnd();
                    }
                    resolve({ ok: !!audioMsg, usedLoop: useLoopFallback, videoPlayed: false });
                } catch (err) {
                    if (typeof payload.onSpeechEnd === "function") payload.onSpeechEnd();
                    reject(err);
                }
            };

            const onMessage = async (ev) => {
                let msg;
                try {
                    msg = JSON.parse(ev.data);
                } catch (_) {
                    return;
                }

                if (msg.type === "audio") {
                    audioMsg = msg;
                    return;
                }

                if (msg.type === "fallback_loop") {
                    useLoopFallback = true;
                    return;
                }

                if (msg.type === "video_chunk" && msg.data) {
                    videoMsg = msg;
                    return;
                }

                if (msg.type === "done") {
                    this.ws.removeEventListener("message", onMessage);
                    await finish();
                    return;
                }

                if (msg.type === "error") {
                    this.ws.removeEventListener("message", onMessage);
                    reject(new Error(msg.message || "Avatar error"));
                }
            };

            this.ws.addEventListener("message", onMessage);
            this.ws.send(JSON.stringify({
                type: "speak",
                text: payload.text,
                voice: payload.voice,
                tone: payload.tone || "calm",
                portrait: payload.portrait || payload.gender || "female",
            }));
        });
    };

    global.AvatarClient = AvatarClient;
    global.avatarWsUrlFromHttp = wsUrlFromHttp;
})(typeof window !== "undefined" ? window : globalThis);
