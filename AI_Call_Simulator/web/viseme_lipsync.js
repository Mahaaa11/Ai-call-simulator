/**
 * Audio-reactive lip sync on the prospect portrait (no GPU).
 * Analyses TTS audio amplitude and animates a mouth overlay on the face.
 */
(function (global) {
    "use strict";

    var mouthPositions = {
        female: { top: "58%", left: "50%", width: "18%", height: "6%" },
        male: { top: "60%", left: "50%", width: "20%", height: "7%" },
    };

    function LipSyncOverlay(frameEl, gender) {
        this.frame = frameEl;
        this.gender = gender || "female";
        this.overlay = null;
        this.inner = null;
        this.ctx = null;
        this.analyser = null;
        this.audioCtx = null;
        this.source = null;
        this.raf = null;
        this.active = false;
        this._ensureOverlay();
    }

    LipSyncOverlay.prototype._ensureOverlay = function () {
        if (!this.frame) return;
        var existing = this.frame.querySelector(".lipsync-overlay");
        if (existing) {
            this.overlay = existing;
            this.inner = existing.querySelector(".lipsync-mouth");
            return;
        }
        var pos = mouthPositions[this.gender] || mouthPositions.female;
        var wrap = document.createElement("div");
        wrap.className = "lipsync-overlay";
        wrap.style.cssText =
            "position:absolute;z-index:3;pointer-events:none;" +
            "top:" + pos.top + ";left:" + pos.left + ";" +
            "width:" + pos.width + ";height:" + pos.height + ";" +
            "transform:translate(-50%,-50%);";
        var mouth = document.createElement("div");
        mouth.className = "lipsync-mouth";
        wrap.appendChild(mouth);
        this.frame.appendChild(wrap);
        this.overlay = wrap;
        this.inner = mouth;
    };

    LipSyncOverlay.prototype.setGender = function (gender) {
        this.gender = gender || "female";
        if (this.overlay) this.overlay.remove();
        this.overlay = null;
        this._ensureOverlay();
    };

    LipSyncOverlay.prototype._loop = function () {
        if (!this.active || !this.analyser || !this.inner) return;
        var data = new Uint8Array(this.analyser.frequencyBinCount);
        this.analyser.getByteFrequencyData(data);
        var sum = 0;
        for (var i = 0; i < data.length; i++) sum += data[i];
        var avg = sum / (data.length * 255);
        var open = Math.min(1, Math.pow(avg * 2.8, 0.75));
        var scaleY = 0.35 + open * 1.15;
        var scaleX = 0.85 + open * 0.35;
        this.inner.style.transform = "scale(" + scaleX.toFixed(3) + "," + scaleY.toFixed(3) + ")";
        this.inner.style.opacity = String(0.55 + open * 0.45);
        this.raf = requestAnimationFrame(this._loop.bind(this));
    };

    LipSyncOverlay.prototype.attachAudio = function (audioEl) {
        this.detach();
        if (!audioEl || !this.inner) return false;
        try {
            this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            this.analyser = this.audioCtx.createAnalyser();
            this.analyser.fftSize = 256;
            this.analyser.smoothingTimeConstant = 0.45;
            this.source = this.audioCtx.createMediaElementSource(audioEl);
            this.source.connect(this.analyser);
            this.analyser.connect(this.audioCtx.destination);
            if (this.audioCtx.state === "suspended") this.audioCtx.resume();
        } catch (e) {
            console.warn("LipSync audio context:", e);
            return false;
        }
        this.active = true;
        this.frame && this.frame.classList.add("lipsync-active");
        this._loop();
        return true;
    };

    LipSyncOverlay.prototype.runEstimated = function (durationMs) {
        var self = this;
        this.detach(false);
        if (!this.inner) return;
        this.active = true;
        this.frame && this.frame.classList.add("lipsync-active");
        var start = performance.now();
        var tick = function () {
            if (!self.active) return;
            var t = (performance.now() - start) / 1000;
            if (t * 1000 >= durationMs) {
                self.stop();
                return;
            }
            var open = 0.25 + 0.55 * Math.abs(Math.sin(t * 11)) * (0.6 + 0.4 * Math.sin(t * 3.7));
            self.inner.style.transform = "scale(" + (0.9 + open * 0.3).toFixed(3) + "," + (0.4 + open * 1.1).toFixed(3) + ")";
            self.inner.style.opacity = String(0.5 + open * 0.5);
            self.raf = requestAnimationFrame(tick);
        };
        tick();
    };

    LipSyncOverlay.prototype.detach = function (resetVisual) {
        if (resetVisual === undefined) resetVisual = true;
        this.active = false;
        if (this.raf) cancelAnimationFrame(this.raf);
        this.raf = null;
        try {
            if (this.source) this.source.disconnect();
            if (this.analyser) this.analyser.disconnect();
        } catch (_) {}
        this.source = null;
        this.analyser = null;
        if (resetVisual && this.inner) {
            this.inner.style.transform = "scale(1,0.35)";
            this.inner.style.opacity = "0.5";
        }
        if (resetVisual && this.frame) this.frame.classList.remove("lipsync-active");
    };

    LipSyncOverlay.prototype.stop = function () {
        this.detach(true);
        try {
            if (this.audioCtx && this.audioCtx.state !== "closed") this.audioCtx.close();
        } catch (_) {}
        this.audioCtx = null;
    };

    function LipSyncManager() {
        this.player = null;
    }

    LipSyncManager.prototype.ensure = function (gender) {
        var frame = document.getElementById("prospectFrame");
        if (!frame) return null;
        if (!this.player) this.player = new LipSyncOverlay(frame, gender);
        else this.player.setGender(gender);
        return this.player;
    };

    LipSyncManager.prototype.syncWithAudio = function (audioEl, gender) {
        var p = this.ensure(gender);
        if (!p) return false;
        return p.attachAudio(audioEl);
    };

    LipSyncManager.prototype.syncEstimated = function (text, gender) {
        var p = this.ensure(gender);
        if (!p) return;
        var words = (text || "").split(/\s+/).length;
        var ms = Math.max(1200, Math.min(12000, words * 380));
        p.runEstimated(ms);
    };

    LipSyncManager.prototype.stop = function () {
        if (this.player) this.player.stop();
    };

    global.LipSyncManager = LipSyncManager;
    global.lipSyncManager = new LipSyncManager();
})(typeof window !== "undefined" ? window : globalThis);
