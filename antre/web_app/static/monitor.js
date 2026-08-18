// ============================================================
// ANTRE — Live Monitor
// ============================================================

const feed = document.getElementById("feed");
const feedEmpty = document.getElementById("feed-empty");
const autoScrollEl = document.getElementById("auto-scroll");

let currentFilter = "all";
let autoScroll = true;
let eventCount = 0;
let categoryCounts = {};

const CAT_ICON = {
    terminal: "❯",
    browser: "◈",
    files: "✎",
    memory: "◉",
    search: "⌕",
    chat: "▣",
    system: "⚙",
};

// ---------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------

function esc(s) {
    const div = document.createElement("div");
    div.textContent = s == null ? "" : String(s);
    return div.innerHTML;
}

function fmtTime(ts) {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour12: false }) + "." +
        String(d.getMilliseconds()).padStart(3, "0");
}

function fmtDuration(ms) {
    if (ms == null) return "";
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
}

function argsPreview(event) {
    try {
        const parsed = JSON.parse(event.args || "{}");
        const lines = [];
        for (const [k, v] of Object.entries(parsed)) {
            let s = String(v);
            if (s.length > 80) s = s.slice(0, 80) + "…";
            lines.push(`<span class="arg-key">${esc(k)}</span>=<span class="arg-val">${esc(s)}</span>`);
        }
        return lines.join(" ");
    } catch {
        return esc(event.args || "");
    }
}

function resultBody(event) {
    const text = event.result || "";
    if (!text) return "";
    let pretty = text;
    try {
        pretty = JSON.stringify(JSON.parse(text), null, 2);
    } catch { /* keep raw */ }
    return `<pre class="result-body">${esc(pretty)}</pre>`;
}

function makeEventEl(event) {
    const el = document.createElement("div");
    el.classList.add("a-event", `cat-${event.category || "system"}`, `type-${event.type || ""}`);

    const icon = CAT_ICON[event.category] || "·";
    const time = fmtTime(event.ts);

    const header = document.createElement("div");
    header.className = "a-head";

    const left = document.createElement("span");
    left.className = "a-left";
    left.innerHTML = `<span class="a-icon">${icon}</span>
        <span class="a-time">${time}</span>
        <span class="a-tag">${esc((event.tool || event.type || "").toUpperCase())}</span>`;

    const right = document.createElement("span");
    right.className = "a-right";
    right.innerHTML =
        (event.status === "ok" ? `<span class="a-status ok">OK</span>` :
         event.status === "error" ? `<span class="a-status err">ERR</span>` :
         event.status === "running" ? `<span class="a-status run">RUN</span>` :
         event.status === "waiting" ? `<span class="a-status wait">WAIT</span>` :
         event.status === "cancelled" ? `<span class="a-status cancel">X</span>` : "") +
        (event.duration_ms != null ? `<span class="a-dur">${fmtDuration(event.duration_ms)}</span>` : "");

    header.appendChild(left);
    header.appendChild(right);
    el.appendChild(header);

    const body = document.createElement("div");
    body.className = "a-body";
    el.appendChild(body);

    // ---- terminal commands ---------------------------------
    if (event.category === "terminal") {
        const cmd = event.command || argsPreview(event);
        body.innerHTML += `<div class="a-cmd">$ ${esc(event.host ? `${event.user || "user"}@${event.host}` : "ssh")} :: ${esc(cmd)}</div>`;
        body.innerHTML += `<div class="a-args">${argsPreview(event)}</div>`;
        const res = resultBody(event);
        if (res) body.innerHTML += `<details class="a-details"><summary>output</summary>${res}</details>`;
    }

    // ---- browser agent -------------------------------------
    else if (event.category === "browser") {
        const action = event.action || "";
        const url = event.url || "";
        body.innerHTML += `<div class="a-cmd">▸ ${esc(action)}${url ? ` <span class="a-url">${esc(url)}</span>` : ""}</div>`;
        if (event.title) body.innerHTML += `<div class="a-title">${esc(event.title)}</div>`;
        if (event.screenshot_url) {
            body.innerHTML += `<a class="a-shot" href="${esc(event.screenshot_url)}" target="_blank" rel="noopener">
                <img src="${esc(event.screenshot_url)}" alt="screenshot" loading="lazy"></a>`;
        }
        const res = resultBody(event);
        if (res) body.innerHTML += `<details class="a-details"><summary>page data</summary>${res}</details>`;
    }

    // ---- files ---------------------------------------------
    else if (event.category === "files") {
        body.innerHTML += `<div class="a-args">${argsPreview(event)}</div>`;
        const res = resultBody(event);
        if (res) body.innerHTML += `<details class="a-details"><summary>content</summary>${res}</details>`;
    }

    // ---- memory --------------------------------------------
    else if (event.category === "memory") {
        body.innerHTML += `<div class="a-args">${argsPreview(event)}</div>`;
        const res = resultBody(event);
        if (res) body.innerHTML += `<details class="a-details"><summary>result</summary>${res}</details>`;
    }

    // ---- search --------------------------------------------
    else if (event.category === "search") {
        body.innerHTML += `<div class="a-args">${argsPreview(event)}</div>`;
        const res = resultBody(event);
        if (res) body.innerHTML += `<details class="a-details"><summary>results</summary>${res}</details>`;
    }

    // ---- chat ----------------------------------------------
    else if (event.category === "chat") {
        const role = event.role === "user" ? "you" : "antre";
        body.innerHTML += `<div class="a-chat"><span class="a-chat-role ${event.role === "user" ? "user" : "assistant"}">${role}</span> ${esc(event.content || "")}</div>`;
    }

    // ---- permission / system -------------------------------
    else {
        body.innerHTML += `<div class="a-args">${argsPreview(event)}</div>`;
        if (event.message) body.innerHTML += `<div class="a-msg">${esc(event.message)}</div>`;
        const res = resultBody(event);
        if (res) body.innerHTML += `<details class="a-details"><summary>result</summary>${res}</details>`;
    }

    return el;
}

function appendEvent(event, atTop = false) {
    const el = makeEventEl(event);
    if (atTop) {
        feed.prepend(el);
    } else {
        feed.appendChild(el);
        if (autoScroll) feed.scrollTop = feed.scrollHeight;
    }
    return el;
}

// ---------------------------------------------------------------
// Filtering
// ---------------------------------------------------------------

function applyFilter() {
    feed.querySelectorAll(".a-event").forEach((el) => {
        const cat = el.classList.contains("cat-terminal") ? "terminal"
            : el.classList.contains("cat-browser") ? "browser"
            : el.classList.contains("cat-files") ? "files"
            : el.classList.contains("cat-memory") ? "memory"
            : el.classList.contains("cat-search") ? "search"
            : el.classList.contains("cat-chat") ? "chat"
            : "system";
        el.style.display = currentFilter === "all" || cat === currentFilter ? "" : "none";
    });
    feedEmpty.style.display = feed.querySelectorAll(".a-event").length ? "none" : "block";
}

document.getElementById("filter-bar").addEventListener("click", (e) => {
    const btn = e.target.closest(".filter");
    if (!btn) return;
    document.querySelectorAll(".filter").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentFilter = btn.dataset.filter;
    applyFilter();
});

// ---------------------------------------------------------------
// Clear + auto scroll
// ---------------------------------------------------------------

document.getElementById("clear-feed").addEventListener("click", () => {
    feed.querySelectorAll(".a-event").forEach((el) => el.remove());
    eventCount = 0;
    categoryCounts = {};
    updateCounts();
    applyFilter();
});

autoScrollEl.addEventListener("change", () => {
    autoScroll = autoScrollEl.checked;
});

feed.addEventListener("wheel", () => {
    // Pause following when the user scrolls up
    const nearBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 80;
    if (!nearBottom && autoScrollEl.checked) autoScrollEl.checked = false;
});

// ---------------------------------------------------------------
// Category counts
// ---------------------------------------------------------------

function updateCounts() {
    const box = document.getElementById("category-counts");
    box.innerHTML = Object.entries(categoryCounts)
        .sort((a, b) => b[1] - a[1])
        .map(([cat, n]) => `<div class="cat-count"><span class="cat-count-name">${esc(cat)}</span><span class="cat-count-n">${n}</span></div>`)
        .join("");
}

function countEvent(event) {
    const cat = event.category || "system";
    categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
    updateCounts();
}

// ---------------------------------------------------------------
// Status polling
// ---------------------------------------------------------------

async function refreshStatus() {
    try {
        const r = await fetch("/api/status");
        if (!r.ok) return;
        const s = await r.json();

        document.getElementById("stat-uptime").textContent = s.uptime_human;
        const modeEl = document.getElementById("stat-mode");
        if (modeEl) {
            modeEl.textContent = s.auto_mode ? "AUTO" : "SAFE";
            modeEl.classList.toggle("stat-idle", !s.auto_mode);
            modeEl.classList.toggle("stat-auto", !!s.auto_mode);
        }
        document.getElementById("stat-events").textContent = s.activity_events;
        document.getElementById("stat-history").textContent = s.history_messages;
        document.getElementById("stat-memory").textContent = s.memory_entries;
        document.getElementById("stat-shots").textContent = s.screenshots;

        const statusEl = document.getElementById("m-status");
        const dot = statusEl.querySelector(".status-dot");
        const txt = statusEl.querySelector(".status-text");
        const big = document.getElementById("stat-status");
        if (s.busy) {
            statusEl.classList.add("working");
            big.textContent = "WORKING";
            big.classList.remove("stat-idle");
            big.classList.add("stat-busy");
            txt.textContent = `${s.active_tools} TOOL${s.active_tools === 1 ? "" : "S"} ACTIVE`;
        } else {
            statusEl.classList.remove("working");
            big.textContent = "IDLE";
            big.classList.add("stat-idle");
            big.classList.remove("stat-busy");
            txt.textContent = "STANDBY";
        }
    } catch (e) { /* best effort */ }
}

setInterval(refreshStatus, 3000);
refreshStatus();

// ---------------------------------------------------------------
// SSE live stream
// ---------------------------------------------------------------

function connect() {
    const es = new EventSource("/activity/stream");

    es.onopen = () => {
        document.querySelector(".monitor-title h1").textContent = "LIVE ACTIVITY FEED — LINKED";
    };

    es.addEventListener("hello", () => {
        // history is loaded separately
    });

    es.onmessage = (e) => {
        try {
            const event = JSON.parse(e.data);
            appendEvent(event);
            countEvent(event);
            eventCount++;
            feedEmpty.style.display = "none";
            applyFilter();
        } catch (err) {
            console.error("bad event", err);
        }
    };

    es.onerror = () => {
        document.querySelector(".monitor-title h1").textContent = "LIVE ACTIVITY FEED — RECONNECTING";
        es.close();
        setTimeout(connect, 2000);
    };

    window._es = es;
}

// Load recent history first, then attach the live stream
fetch("/activity/history?limit=300")
    .then((r) => r.json())
    .then((data) => {
        (data.events || []).forEach((event) => {
            appendEvent(event);
            countEvent(event);
        });
        applyFilter();
        connect();
    })
    .catch(() => connect());
