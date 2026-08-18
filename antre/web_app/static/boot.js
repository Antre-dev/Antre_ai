/* ============================================================
 * ANTRE — JARVIS-style boot sequence
 * Shows a futuristic boot screen fullscreen, then fades into
 * the chat interface. Skip it with /?skip_boot=1 (useful in dev).
 * ============================================================ */
(async () => {
    "use strict";

    const overlay = document.getElementById("boot");
    const logEl = document.getElementById("boot-log");
    const barFill = document.getElementById("boot-bar-fill");
    const pctEl = document.getElementById("boot-pct");
    const statusEl = document.getElementById("boot-status");
    const input = document.getElementById("message-input");

    const params = new URLSearchParams(location.search);
    const skip =
        params.get("skip_boot") === "1" ||
        sessionStorage.getItem("antre_booted") === "1";

    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

    const finish = () => {
        sessionStorage.setItem("antre_booted", "1");
        overlay.classList.add("boot--done");
        setTimeout(() => overlay.remove(), 900);
        setTimeout(() => input && input.focus(), 1000);
    };

    if (!overlay) return;
    if (skip) {
        overlay.remove();
        input && input.focus();
        return;
    }

    // Standard boot checks
    const LINES = [
        ["> mounting core modules", "OK"],
        ["> calibrating neural interface", "OK"],
        ["> linking web relays", "OK"],
        ["> indexing long-term memory", "OK"],
        ["> syncing activity log", "OK"],
        ["> handshaking with ANTRE CORE", "OK"],
    ];

    // Pull live stats from the server so the boot feels real
    try {
        const r = await fetch("/api/status");
        if (r.ok) {
            const s = await r.json();
            LINES.push([`> memory banks: ${s.memory_entries} entries`, "OK"]);
            LINES.push([`> tools: ${s.active_tools} linked`, s.busy ? "BUSY" : "OK"]);
            LINES.push([`> core uptime: ${s.uptime_human}`, "OK"]);
        }
    } catch (_) { /* best effort — boot proceeds offline */ }

    const setProgress = (pct) => {
        barFill.style.width = pct + "%";
        pctEl.textContent = pct + "%";
    };

    const STEPS = LINES.length + 2; // + finalize + handshake
    let done = 0;

    const typeLine = async (text) => {
        const div = document.createElement("div");
        div.className = "boot-line";
        div.innerHTML =
            '<span class="bl-text"></span>' +
            '<span class="bl-tag ok">[OK]</span>';
        logEl.appendChild(div);
        const span = div.querySelector(".bl-text");
        const tag = div.querySelector(".bl-tag");
        // typewriter effect
        for (let i = 0; i <= text.length; i++) {
            span.textContent = text.slice(0, i);
            await sleep(13);
        }
        tag.classList.add("revealed");
        logEl.scrollTop = logEl.scrollHeight;
        done++;
        setProgress(Math.round((done / STEPS) * 100));
    };

    // Kick off the ring animation + log lines
    statusEl.textContent = "INITIALIZING";
    for (const [text, tag] of LINES) {
        await sleep(280 + Math.random() * 260);
        await typeLine(text);
        // flip tag colour if the check was not clean
        const last = logEl.lastElementChild;
        if (tag !== "OK" && last) {
            last.querySelector(".bl-tag").classList.remove("ok");
            last.querySelector(".bl-tag").classList.add("warn");
            last.querySelector(".bl-tag").textContent = `[${tag}]`;
        }
    }

    await sleep(300);
    statusEl.textContent = "FINALIZING";
    await sleep(450);
    setProgress(100);
    statusEl.textContent = "SYSTEM ONLINE";
    await sleep(650);
    finish();
})();
