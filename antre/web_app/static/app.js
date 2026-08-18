// ============================================================
// ANTRE — voice-first console
// No chat log. Replies are spoken (TTS), shown on the status
// line, and important things surface as popups.
// ============================================================

const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const typing = document.getElementById("typing");
const typingText = document.querySelector(".typing-text");
const statusLine = document.getElementById("status-line");
const statusText = document.getElementById("status-text");
const micBtn = document.getElementById("mic-btn");
const micLabel = document.getElementById("mic-label");

// ---------------------------------------------------------------
// Status line — the single "last thing said" readout
// ---------------------------------------------------------------

const TYPING_LABELS = [
    "ANTRE is processing...",
    "ANTRE is executing tools...",
    "ANTRE is consulting the web...",
    "ANTRE is thinking, sir...",
];
let _typingIdx = 0;

function setStatus(text, kind = "reply") {
    statusLine.dataset.kind = kind;
    statusText.textContent = text || "";
    statusText.title = text || "";
}

function setTyping(active) {
    typing.classList.toggle("hidden", !active);
    if (active) {
        typingText.textContent = TYPING_LABELS[_typingIdx % TYPING_LABELS.length];
        _typingIdx++;
    }
}

// ---------------------------------------------------------------
// Chime (Web Audio) — notification tones, no audio files needed
// ---------------------------------------------------------------

let _audioCtx = null;

function _ensureAudio() {
    try {
        if (!_audioCtx) {
            const AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) return null;
            _audioCtx = new AC();
        }
        if (_audioCtx.state === "suspended") _audioCtx.resume();
        return _audioCtx;
    } catch (e) {
        return null;
    }
}

// Unlock audio on the first user interaction (browser autoplay policy).
document.addEventListener("pointerdown", () => _ensureAudio(), { once: true });
document.addEventListener("keydown", () => _ensureAudio(), { once: true });

function playChime(kind = "permission") {
    const ctx = _ensureAudio();
    if (!ctx) return;
    const now = ctx.currentTime;
    // Two ascending tones for permissions, a single tone for captures,
    // a low double beep for notices.
    const notes = kind === "permission"
        ? [{ f: 880.0, t: 0.0, d: 0.4 }, { f: 1318.5, t: 0.18, d: 0.55 }]
        : kind === "notice"
        ? [{ f: 587.3, t: 0.0, d: 0.28 }, { f: 440.0, t: 0.22, d: 0.4 }]
        : [{ f: 1046.5, t: 0.0, d: 0.32 }];
    for (const n of notes) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.value = n.f;
        const start = now + n.t;
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(0.16, start + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + n.d);
        osc.connect(gain).connect(ctx.destination);
        osc.start(start);
        osc.stop(start + n.d + 0.05);
    }
}

// ---------------------------------------------------------------
// Notice popup — important stuff (errors, warnings, key events)
// ---------------------------------------------------------------

const noticeModal = document.getElementById("notice-modal");
const noticeTitle = document.getElementById("notice-title");
const noticeBody = document.getElementById("notice-body");

function showNotice(title, html) {
    if (!noticeModal) return;
    if (noticeTitle) noticeTitle.innerHTML = title;
    if (noticeBody) noticeBody.innerHTML = html;
    noticeModal.classList.remove("hidden");
    playChime("notice");
    document.getElementById("notice-ok")?.focus();
}

function hideNotice() {
    noticeModal?.classList.add("hidden");
}

// Which replies deserve a popup (screenshots and permission prompts
// already get their own popups — this is the catch-all for the rest).
const IMPORTANT_MARKERS = [
    "error", "failed", "fault", "warning", "warn",
    "attention", "critical", "important", "denied",
    "unavailable", "connection lost", "cannot", "could not",
    "⚠", "❗",
];

function isImportant(text) {
    if (!text) return false;
    const t = String(text).toLowerCase();
    return IMPORTANT_MARKERS.some((m) => t.includes(m));
}

document.getElementById("notice-ok")?.addEventListener("click", hideNotice);
document.getElementById("notice-close")?.addEventListener("click", hideNotice);
noticeModal?.addEventListener("click", (event) => {
    if (event.target === noticeModal) hideNotice();
});

// ---------------------------------------------------------------
// Permission dialog — approval gate with real buttons
// ---------------------------------------------------------------

const permModal = document.getElementById("perm-modal");

function parsePermissionPrompt(text) {
    if (!text) return null;
    const m = String(text).match(
        /I need your permission to run \*\*([^*]+)\*\* with args `([^`]*)`/
    );
    if (!m) return null;
    return { tool: m[1].trim(), args: m[2] || "—" };
}

function showPermissionModal(tool, args) {
    if (!permModal) return;
    _permissionResponded = false;
    const approveBtn = document.getElementById("perm-approve");
    const denyBtn = document.getElementById("perm-deny");
    if (approveBtn) approveBtn.disabled = false;
    if (denyBtn) denyBtn.disabled = false;
    const toolEl = document.getElementById("perm-tool");
    const argsEl = document.getElementById("perm-args");
    if (toolEl) toolEl.textContent = tool;
    if (argsEl) argsEl.textContent = args || "—";
    permModal.classList.remove("hidden");
    playChime("permission");
    document.getElementById("perm-approve")?.focus();
}

function hidePermissionModal() {
    permModal?.classList.add("hidden");
}

// ---------------------------------------------------------------
// Permission popup buttons — APPROVE / DENY speak for you
// ---------------------------------------------------------------

let _permissionResponded = false;

function _respondToPermission(approved) {
    if (_permissionResponded) return;
    _permissionResponded = true;
    const approveBtn = document.getElementById("perm-approve");
    const denyBtn = document.getElementById("perm-deny");
    if (approveBtn) approveBtn.disabled = true;
    if (denyBtn) denyBtn.disabled = true;
    hidePermissionModal();
    setStatus(approved ? "APPROVED — EXECUTING" : "DENIED — CANCELLED", approved ? "reply" : "error");
    submitText(approved ? "yes" : "no");
}

document.getElementById("perm-approve")?.addEventListener("click", () => _respondToPermission(true));
document.getElementById("perm-deny")?.addEventListener("click", () => _respondToPermission(false));
document.getElementById("perm-close")?.addEventListener("click", () => _respondToPermission(false));

// ---------------------------------------------------------------
// Screenshot viewer
// ---------------------------------------------------------------

const viewerModal = document.getElementById("viewer-modal");
let _viewerImages = [];
let _viewerIdx = 0;

function renderViewer() {
    const img = document.getElementById("viewer-img");
    if (img) img.src = _viewerImages[_viewerIdx] || "";
    const count = document.getElementById("viewer-count");
    if (count) count.textContent = `${_viewerIdx + 1} / ${_viewerImages.length}`;
    const cap = document.getElementById("viewer-caption");
    if (cap) cap.textContent = `CAPTURE ${_viewerIdx + 1}`;
    const prev = document.getElementById("viewer-prev");
    const next = document.getElementById("viewer-next");
    const multi = _viewerImages.length > 1;
    if (prev) prev.style.visibility = multi ? "visible" : "hidden";
    if (next) next.style.visibility = multi ? "visible" : "hidden";
}

function openViewer(images, idx = 0) {
    if (!viewerModal || !images || !images.length) return;
    _viewerImages = images.slice();
    _viewerIdx = Math.max(0, Math.min(idx, _viewerImages.length - 1));
    renderViewer();
    viewerModal.classList.remove("hidden");
    playChime("capture");
}

function hideViewer() {
    viewerModal?.classList.add("hidden");
}

function viewerStep(dir) {
    _viewerIdx = (_viewerIdx + dir + _viewerImages.length) % _viewerImages.length;
    renderViewer();
}

document.getElementById("viewer-close")?.addEventListener("click", hideViewer);
document.getElementById("viewer-prev")?.addEventListener("click", () => viewerStep(-1));
document.getElementById("viewer-next")?.addEventListener("click", () => viewerStep(1));
viewerModal?.addEventListener("click", (event) => {
    if (event.target === viewerModal) hideViewer();
});

// ---------------------------------------------------------------
// Voice — ANTRE speaks replies aloud via edge-tts (/tts endpoint)
// ---------------------------------------------------------------

const voiceToggle = document.getElementById("voice-toggle");
const VOICE_KEY = "antre.voice.enabled";
const _saved = localStorage.getItem(VOICE_KEY);
let voiceEnabled = _saved !== null ? _saved === "1" : true; // default ON
let _currentAudio = null;

function stopSpeech() {
    if (_currentAudio) {
        _currentAudio.pause();
        _currentAudio = null;
    }
}

function setVoiceEnabled(enabled) {
    voiceEnabled = enabled;
    localStorage.setItem(VOICE_KEY, enabled ? "1" : "0");
    voiceToggle.classList.toggle("on", enabled);
    voiceToggle.querySelector(".voice-label").textContent =
        enabled ? "VOICE ON" : "VOICE OFF";
    if (!enabled) stopSpeech();
}

// Voice reads only the FIRST SENTENCE of the reply — the full text
// stays on the status line for reading, and permission text is never
// spoken (the chime + modal are the cue).
function voiceLine(text) {
    const clean = String(text)
        .replace(/```[\s\S]*?```/g, " ")
        .replace(/[#*`_>~|]/g, " ")
        .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
        .replace(/\s+/g, " ")
        .trim();
    if (!clean) return null;
    const m = clean.match(/^.*?[.!?](?:\s|$)/);
    const line = m ? m[0] : clean;
    return line.slice(0, 160);
}

async function speak(text) {
    if (!voiceEnabled || !text) return;
    const line = voiceLine(text);
    if (!line) return;
    stopSpeech();
    try {
        const res = await fetch(`/tts?text=${encodeURIComponent(line)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        _currentAudio = new Audio(URL.createObjectURL(blob));
        _currentAudio.play().catch(() => {});
    } catch (error) {
        console.error("TTS failed:", error);
    }
}

voiceToggle.addEventListener("click", () => setVoiceEnabled(!voiceEnabled));
setVoiceEnabled(voiceEnabled);

// ---------------------------------------------------------------
// ---------------------------------------------------------------
// Code viewer popup — code blocks open here, never inline
// ---------------------------------------------------------------

const codeModal = document.getElementById("code-modal");
const codeTitle = document.getElementById("code-title");
const codeContent = document.getElementById("code-content");
const codeCopyBtn = document.getElementById("code-copy");
let _lastCodeBlocks = [];

// Split a reply into prose + fenced code blocks.
// Returns { text, blocks: [{ lang, code }], title }.
function splitCodeBlocks(text) {
    const blocks = [];
    const src = String(text || "");
    const re = /```([^\n`]*)\n([\s\S]*?)```/g;
    let m;
    while ((m = re.exec(src)) !== null) {
        blocks.push({
            lang: (m[1] || "").trim(),
            code: m[2].replace(/\n$/, ""),
        });
    }
    const textOnly = src.replace(/```[^\n`]*\n[\s\S]*?```/g, " ")
        .replace(/\s+/g, " ").trim();
    return {
        blocks,
        text: textOnly,
        title: blocks.length > 1 ? "CODE — " + blocks.length + " BLOCKS" : "CODE",
    };
}

function codeEscape(s) {
    const div = document.createElement("div");
    div.textContent = s == null ? "" : String(s);
    return div.innerHTML;
}

function showCode(title, blocks) {
    if (!codeModal) return;
    _lastCodeBlocks = blocks;
    if (codeTitle) codeTitle.textContent = title || "CODE";
    if (codeContent) {
        codeContent.innerHTML = blocks.map((b) =>
            '<span class="code-lang">' + codeEscape(b.lang || "code") + "</span>\n" +
            codeEscape(b.code)
        ).join("\n\n");
    }
    codeModal.classList.remove("hidden");
    playChime("notice");
    codeCopyBtn?.focus();
}

function hideCode() {
    codeModal?.classList.add("hidden");
}

function copyCode() {
    if (!_lastCodeBlocks.length) return;
    const all = _lastCodeBlocks.map((b) => b.code).join("\n\n");
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(all).then(() => {
            setStatus("CODE COPIED TO CLIPBOARD", "reply");
        }).catch(() => {});
    }
}

document.getElementById("code-close")?.addEventListener("click", hideCode);
document.getElementById("code-ok")?.addEventListener("click", hideCode);
codeCopyBtn?.addEventListener("click", copyCode);
codeModal?.addEventListener("click", (event) => {
    if (event.target === codeModal) hideCode();
});

// Response dispatch — everything ANTRE says lands here
// ---------------------------------------------------------------

function handleAssistantResponse(text, images) {
    const pending = parsePermissionPrompt(text);
    if (pending) {
        setStatus(`PERMISSION REQUIRED — ${pending.tool}`, "permission");
        showPermissionModal(pending.tool, pending.args);
        return; // permissions stay silent — the chime + modal are the cue
    }

    // Code blocks never sit inline — they open in the code viewer popup,
    // while the status line + voice keep the readable summary.
    const split = splitCodeBlocks(text);
    if (split.blocks.length) {
        showCode(split.title, split.blocks);
        setStatus(split.text || "CODE — OPENED IN VIEWER", "code");
        speak(split.text || "Code opened in the viewer.");
        if (images && images.length) openViewer(images, 0);
        return;
    }

    setStatus(text || "…", "reply");
    speak(text);

    if (images && images.length) {
        // Screenshots are visual — big centered popup.
        openViewer(images, 0);
        return;
    }
    if (isImportant(text)) {
        const html = (window.marked && marked.parse) ? marked.parse(text) : text;
        showNotice("⚠ ANTRE NOTICE", html);
    }
}

// ---------------------------------------------------------------
// Submit — typed commands and mic transcripts both route through here
// ---------------------------------------------------------------

async function submitText(message) {
    if (!message) return;
    hidePermissionModal();
    hideNotice();
    _ensureAudio(); // first user gesture unlocks audio for the chime

    setTyping(true);
    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message }),
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        handleAssistantResponse(data.response, data.images || []);
    } catch (error) {
        console.error(error);
        setStatus("CONNECTION TO CORE LOST", "error");
        showNotice("⚠ CONNECTION LOST", "Retrying transmission... Check that the core server is running.");
    } finally {
        setTyping(false);
        input.focus();
    }
}

form.addEventListener("submit", (event) => {
    event.preventDefault();
    submitText(input.value.trim());
    input.value = "";
});

// Ctrl+Enter also transmits
input.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.key === "Enter") {
        e.preventDefault();
        submitText(input.value.trim());
        input.value = "";
    }
});

// ---------------------------------------------------------------
// Microphone — hold to talk, release to transcribe & send
// ---------------------------------------------------------------

let _micRecording = false;
let _micStart = null;

async function startRecording() {
    if (_micRecording) return;
    _micRecording = true;
    micBtn.classList.add("recording");
    micLabel.textContent = "LISTENING…";
    setStatus("LISTENING — SPEAK NOW", "listen");
    try {
        const res = await fetch("/stt/start", { method: "POST" });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            setStatus("MIC UNAVAILABLE", "error");
            showNotice("⚠ MICROPHONE UNAVAILABLE", (data && data.error) || `HTTP ${res.status}`);
            _micRecording = false;
            micBtn.classList.remove("recording");
            micLabel.textContent = "HOLD TO TALK";
        }
    } catch (error) {
        console.error(error);
        setStatus("MIC UNAVAILABLE", "error");
        showNotice("⚠ MICROPHONE UNAVAILABLE", "Could not reach the STT core.");
        _micRecording = false;
        micBtn.classList.remove("recording");
        micLabel.textContent = "HOLD TO TALK";
    }
}

async function stopRecording() {
    if (!_micRecording) return;
    _micRecording = false;
    micBtn.classList.remove("recording");
    micLabel.textContent = "HOLD TO TALK";
    setStatus("TRANSCRIBING…", "listen");
    try {
        const res = await fetch("/stt/stop", { method: "POST" });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            setStatus("TRANSCRIPTION FAILED", "error");
            showNotice("⚠ TRANSCRIPTION FAILED", (data && data.error) || `HTTP ${res.status}`);
            return;
        }
        const text = String(data.text || "").trim();
        if (text) {
            setStatus(`» ${text}`, "user");
            await submitText(text);
        } else {
            setStatus("NO AUDIO RECOGNIZED — TRY AGAIN", "warn");
        }
    } catch (error) {
        console.error(error);
        setStatus("TRANSCRIPTION FAILED", "error");
        showNotice("⚠ TRANSCRIPTION FAILED", "Could not reach the STT core.");
    } finally {
        input.focus();
    }
}

micBtn.addEventListener("pointerdown", (e) => { e.preventDefault(); startRecording(); });
micBtn.addEventListener("pointerup", stopRecording);
micBtn.addEventListener("pointerleave", stopRecording);
micBtn.addEventListener("pointercancel", stopRecording);

// Hold SPACE to talk while the input is empty (keyboard alternative).
let _spaceTalk = false;
input.addEventListener("keydown", (e) => {
    if (e.code === "Space" && !e.repeat && !input.value) {
        e.preventDefault();
        _spaceTalk = true;
        startRecording();
    }
});
input.addEventListener("keyup", (e) => {
    if (e.code === "Space" && _spaceTalk) {
        _spaceTalk = false;
        stopRecording();
    }
});
input.addEventListener("blur", () => {
    if (_spaceTalk) {
        _spaceTalk = false;
        stopRecording();
    }
});

// Esc closes any open popup.
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        hideViewer();
        hidePermissionModal();
        hideNotice();
        return;
    }
    if (!viewerModal || viewerModal.classList.contains("hidden")) return;
    if (event.key === "ArrowLeft") viewerStep(-1);
    if (event.key === "ArrowRight") viewerStep(1);
});

// ---------------------------------------------------------------
// Status bar / system status
// ---------------------------------------------------------------

// Left-rail telemetry elements (present on wide viewports)
const railUptime = document.getElementById("rail-uptime");
const railMode = document.getElementById("rail-mode");
const railTools = document.getElementById("rail-tools");
const railMemory = document.getElementById("rail-memory");
const railShots = document.getElementById("rail-shots");
const railEvents = document.getElementById("rail-events");
const railMic = document.getElementById("rail-mic");
const railMsgs = document.getElementById("rail-msgs");

async function refreshStatus() {
    try {
        const response = await fetch("/api/status");
        if (!response.ok) return;
        const s = await response.json();

        document.getElementById("sb-uptime").textContent = `UPTIME ${s.uptime_human}`;
        document.getElementById("sb-tools").textContent =
            s.busy ? `TOOLS ${s.active_tools} ACTIVE` : "TOOLS IDLE";
        document.getElementById("sb-memory").textContent = `MEMORY ${s.memory_entries}`;
        document.getElementById("sb-shots").textContent = `SHOTS ${s.screenshots}`;

        const mic = document.getElementById("sb-mic");
        if (mic) {
            mic.textContent = s.stt_available ? "MIC OK" : "MIC N/A";
            mic.classList.toggle("on", !!s.stt_available);
        }

        const statusEl = document.getElementById("nav-status");
        const dot = statusEl.querySelector(".status-dot");
        const txt = statusEl.querySelector(".status-text");
        if (s.busy) {
            statusEl.classList.add("working");
            txt.textContent = "PROCESSING";
        } else {
            statusEl.classList.remove("working");
            txt.textContent = "SYSTEM ONLINE";
        }

        // Left rail — core telemetry
        if (railUptime) railUptime.textContent = s.uptime_human;
        if (railMemory) railMemory.textContent = s.memory_entries;
        if (railShots) railShots.textContent = s.screenshots;
        if (railEvents) railEvents.textContent = s.activity_events;
        if (railMsgs) railMsgs.textContent = `${s.history_messages} MSG`;
        if (railMic) {
            railMic.textContent = s.stt_available ? "OK" : "N/A";
            railMic.classList.toggle("on", !!s.stt_available);
        }
        if (railTools) {
            railTools.textContent = s.busy ? `${s.active_tools} ACTIVE` : "IDLE";
            railTools.classList.toggle("busy", !!s.busy);
        }
        if (railMode) {
            railMode.textContent = s.auto_mode ? "AUTO ON" : "AUTO OFF";
            railMode.classList.toggle("on", !!s.auto_mode);
        }
    } catch (error) {
        // ignore — status is best-effort
    }
}

setInterval(refreshStatus, 4000);
refreshStatus();

// ---------------------------------------------------------------
// AUTO MODE — full-auto permission toggle
// ---------------------------------------------------------------

const modeToggle = document.getElementById("mode-toggle");
const modeLabel = modeToggle?.querySelector(".mode-label");

function setModeUI(auto) {
    if (!modeToggle) return;
    modeToggle.classList.toggle("on", auto);
    modeToggle.setAttribute("aria-pressed", String(auto));
    if (modeLabel) modeLabel.textContent = auto ? "AUTO ON" : "AUTO OFF";
    document.getElementById("nav-status")?.classList.toggle("auto-active", auto);
    const sbAuto = document.getElementById("sb-auto");
    if (sbAuto) {
        sbAuto.textContent = auto ? "AUTO ON" : "AUTO OFF";
        sbAuto.classList.toggle("on", auto);
    }
    if (railMode) {
        railMode.textContent = auto ? "AUTO ON" : "AUTO OFF";
        railMode.classList.toggle("on", auto);
    }
}

async function syncMode() {
    try {
        const r = await fetch("/api/mode");
        if (!r.ok) return;
        const data = await r.json();
        setModeUI(!!data.auto);
    } catch (e) { /* best effort */ }
}

async function toggleMode() {
    if (!modeToggle) return;
    const next = !modeToggle.classList.contains("on");
    modeToggle.disabled = true;
    try {
        const r = await fetch("/api/mode", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ auto: next }),
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        setModeUI(!!data.auto);
        if (data.auto) {
            setStatus("AUTO MODE ENGAGED", "reply");
            showNotice("AUTO MODE ENGAGED",
                "File edits, web browsing, searches and memory ops now run <b>without asking</b>. SSH and destructive commands still require approval.");
        } else {
            setStatus("AUTO MODE DISENGAGED", "reply");
            showNotice("AUTO MODE DISENGAGED",
                "Standard policy restored — dangerous tools ask first.");
        }
    } catch (e) {
        console.error(e);
        setStatus("AUTO MODE SWITCH FAILED", "error");
    } finally {
        modeToggle.disabled = false;
    }
}

modeToggle?.addEventListener("click", toggleMode);
syncMode();



// ============================================================
// HANDS-FREE — voice-activated listening, no button to hold
// Toggle it on, then just talk: it auto-starts on your voice,
// auto-stops when you pause, and submits what you said.
// Say "I'm done" to stand down.
// ============================================================

const hfBtn = document.getElementById("handsfree-btn");
const hfLabel = document.getElementById("handsfree-label");
const HF_KEY = "antre.handsfree.enabled";

let handsFreeOn = false;
let hfSource = null;

// If the mic mangles the phrase, we still catch it:
const HF_OFF_PHRASES = [
    /(?:i'?m|im)\s+(?:done|through|three|free|finished)/i,
    /that'?s\s+(?:it|all)/i,
    /stand\s+by/i,
    /go\s+(?:to\s+)?sleep/i,
    /power\s+down/i,
];

function hfSetUI(on) {
    handsFreeOn = on;
    if (!hfBtn || !hfLabel) return;
    hfBtn.classList.toggle("on", on);
    hfLabel.textContent = on ? "JUST SPEAK" : "HANDS-FREE";
    micBtn.disabled = on;
    micBtn.classList.toggle("muted", on);
    if (on) micLabel.textContent = "HANDS-FREE ACTIVE";
    else micLabel.textContent = "HOLD TO TALK";
}

function hfOnState(state) {
    if (state === "recording") setStatus("HEARD YOU — SPEAKING…", "listen");
    else if (state === "transcribing") setStatus("PROCESSING SPEECH…", "listen");
    else if (state === "listening") setStatus("HANDS-FREE — JUST SPEAK", "listen");
    else if (state === "off") setStatus("HANDS-FREE STANDBY", "reply");
}

function hfOnTranscript(text) {
    text = String(text || "").trim();
    if (!text) return;
    setStatus(`» ${text}`, "user");
    if (HF_OFF_PHRASES.some((re) => re.test(text))) {
        hfToggle(false); // user said "I'm done" — stand down
        return;
    }
    submitText(text);
}

function hfAttachEvents() {
    hfSource = new EventSource("/stt/events");
    hfSource.onmessage = (e) => {
        let ev;
        try { ev = JSON.parse(e.data); } catch (_) { return; }
        if (ev.type === "transcription") hfOnTranscript(ev.text);
        else if (ev.type === "state") hfOnState(ev.state);
    };
    hfSource.onerror = () => setStatus("HANDS-FREE — RECONNECTING…", "warn");
}

async function hfStart() {
    try {
        const res = await fetch("/stt/listen", { method: "POST" });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            setStatus("HANDS-FREE UNAVAILABLE", "error");
            showNotice("⚠ HANDS-FREE UNAVAILABLE", data.error || `HTTP ${res.status}`);
            return false;
        }
        hfAttachEvents();
        setStatus("HANDS-FREE — JUST SPEAK", "listen");
        return true;
    } catch (err) {
        console.error(err);
        setStatus("HANDS-FREE UNAVAILABLE", "error");
        return false;
    }
}

function hfStop() {
    if (hfSource) { hfSource.close(); hfSource = null; }
    fetch("/stt/listen/stop", { method: "POST" }).catch(() => {});
    setStatus("HANDS-FREE STANDBY", "reply");
}

async function hfToggle(force) {
    const next = force !== undefined ? !!force : !handsFreeOn;
    if (next === handsFreeOn) return handsFreeOn;
    if (next) {
        const started = await hfStart();
        hfSetUI(started);
    } else {
        hfStop();
        hfSetUI(false);
    }
    localStorage.setItem(HF_KEY, handsFreeOn ? "1" : "0");
    return handsFreeOn;
}

hfBtn?.addEventListener("click", () => hfToggle());

// Restore state if the page reloads while hands-free was on.
(async () => {
    try {
        const res = await fetch("/stt/listen/status");
        if (!res.ok) return;
        const s = await res.json();
        if (s.listening) {
            hfAttachEvents();
            hfSetUI(true);
            setStatus("HANDS-FREE — JUST SPEAK", "listen");
        }
    } catch (_) { /* core unreachable — stay off */ }
})();


// ---------------------------------------------------------------
// LIVE FEED — right rail activity stream (SSE)
// ---------------------------------------------------------------

const feedList = document.getElementById("feed-list");
const feedEmpty = document.getElementById("feed-empty");
const RAIL_CAT_ICON = {
    terminal: "❯",
    browser: "◈",
    files: "✎",
    memory: "◉",
    search: "⌕",
    chat: "▣",
    system: "⚙",
};

function railEsc(s) {
    const div = document.createElement("div");
    div.textContent = s == null ? "" : String(s);
    return div.innerHTML;
}

function railTime(ts) {
    try {
        return new Date(ts).toLocaleTimeString([], { hour12: false });
    } catch {
        return "";
    }
}

function railArgsPreview(args) {
    try {
        const parsed = JSON.parse(args || "{}");
        const keys = Object.keys(parsed);
        if (!keys.length) return "";
        const k = keys[0];
        let v = String(parsed[k]);
        if (v.length > 42) v = v.slice(0, 42) + "…";
        return `${k}=${v}`;
    } catch {
        return "";
    }
}

function railResultPreview(result) {
    if (!result) return "";
    let s = String(result);
    try {
        const parsed = JSON.parse(result);
        if (parsed && typeof parsed === "object") {
            const pick = parsed.title || parsed.summary || parsed.message || parsed.response;
            if (pick) s = String(pick);
        }
    } catch { /* raw */ }
    if (s.length > 56) s = s.slice(0, 56) + "…";
    return s;
}

function railSummary(event) {
    switch (event.type) {
        case "tool.start":
            return railArgsPreview(event.args) || "RUNNING";
        case "tool.done": {
            const parts = [];
            if (event.duration_ms != null) {
                parts.push(event.duration_ms < 1000
                    ? `${event.duration_ms}ms`
                    : `${(event.duration_ms / 1000).toFixed(2)}s`);
            }
            if (event.url) parts.push(event.url);
            else {
                const res = railResultPreview(event.result);
                if (res) parts.push(res);
            }
            if (!parts.length) parts.push(event.status === "ok" ? "OK" : "ERROR");
            return parts.join(" · ");
        }
        case "permission":
            return "WAITING APPROVAL";
        case "tool.cancel":
            return "CANCELLED";
        case "chat":
            return String(event.content || "").slice(0, 56)
                + (String(event.content || "").length > 56 ? "…" : "");
        case "mode":
            return event.mode === "auto" ? "AUTO ENGAGED" : "MANUAL RESTORED";
        default:
            return "";
    }
}

function railLabel(event) {
    if (event.tool) return event.tool;
    if (event.type === "mode") return "AUTO MODE";
    if (event.type === "chat") return event.role === "user" ? "YOU" : "ANTRE";
    return event.type || "";
}

function railStatusMeta(event) {
    const raw = event.status ||
        (event.type === "chat" ? "chat" :
         event.type === "mode" ? "mode" :
         event.type === "tool.start" ? "run" :
         event.type === "permission" ? "wait" :
         event.type === "tool.cancel" ? "cancel" : "");
    const map = { ok: "ok", error: "err", running: "run", waiting: "wait", cancelled: "cancel" };
    const cls = map[raw] || raw;
    const txt = { ok: "OK", err: "ERR", run: "RUN", wait: "WAIT", cancel: "X", chat: "MSG", mode: "SYS" }[cls]
        || String(raw).toUpperCase();
    return { cls, txt };
}

function addFeedEvent(event) {
    if (!feedList) return;
    const id = event.id;
    if (id != null && feedList.querySelector(`[data-id="${id}"]`)) return;
    if (feedEmpty && feedEmpty.isConnected) feedEmpty.remove();

    const meta = railStatusMeta(event);
    const el = document.createElement("div");
    el.className = `feed-item ${meta.cls}`;
    if (id != null) el.dataset.id = id;

    const icon = RAIL_CAT_ICON[event.category] || "·";
    el.innerHTML =
        `<div class="feed-top">` +
            `<span class="feed-icon">${icon}</span>` +
            `<span class="feed-name">${railEsc(railLabel(event).toUpperCase())}</span>` +
            `<span class="feed-status ${meta.cls}">${meta.txt}</span>` +
        `</div>` +
        `<div class="feed-sub">${railEsc(railSummary(event))}</div>` +
        `<div class="feed-ts">${railEsc(railTime(event.ts))}</div>`;

    feedList.prepend(el);
    while (feedList.children.length > 14) {
        feedList.lastElementChild.remove();
    }
}

async function initFeedRail() {
    if (!feedList) return;
    // Seed with recent history so the rail is populated on load.
    try {
        const res = await fetch("/activity/history?limit=14");
        if (res.ok) {
            const data = await res.json();
            for (const ev of (data.events || []).slice().reverse()) addFeedEvent(ev);
        }
    } catch (_) { /* best effort */ }

    // Live updates via the same SSE the monitor uses.
    const source = new EventSource("/activity/stream");
    source.onmessage = (e) => {
        let ev;
        try { ev = JSON.parse(e.data); } catch (_) { return; }
        if (!ev || !ev.type) return;
        addFeedEvent(ev);
    };
}

initFeedRail();
