/* ================================================
   EchaBot – App JS (redesigned, all functions intact)
   ================================================ */

const messagesEl    = document.querySelector("#messages");
const chatForm      = document.querySelector("#chatForm");
const messageInput  = document.querySelector("#messageInput");
const datasetInput  = document.querySelector("#dataset");
const uploadBtn     = document.querySelector("#uploadBtn");
const sampleBtn     = document.querySelector("#sampleBtn");
const fileLabel     = document.querySelector("#fileLabel");
const statusIdle    = document.querySelector("#statusIdle");
const statusLoaded  = document.querySelector("#statusLoaded");
const datasetName   = document.querySelector("#datasetName");
const datasetMeta   = document.querySelector("#datasetMeta");
const sidebarToggle = document.querySelector("#sidebarToggle");
const backdrop      = document.querySelector("#backdrop");
const newChatBtn    = document.querySelector("#newChatBtn");
const historyList   = document.querySelector("#historyList");
const welcomeScreen = document.querySelector("#welcomeScreen");

// Modal Elements
const deleteModal      = document.querySelector("#deleteModal");
const cancelDeleteBtn  = document.querySelector("#cancelDeleteBtn");
const confirmDeleteBtn = document.querySelector("#confirmDeleteBtn");

let currentSessionId = null;
let sessionToDelete = null;
let chatHistory = [];
let isGenerating = false;
let currentAbortController = null;

/* ── SIDEBAR TOGGLE ─────────────────────────────── */
function setSidebarOpen(open) {
  document.body.classList.toggle("sidebar-open", open);
  if (backdrop) backdrop.setAttribute("aria-hidden", open ? "false" : "true");
}

sidebarToggle?.addEventListener("click", () => {
  setSidebarOpen(!document.body.classList.contains("sidebar-open"));
});
backdrop?.addEventListener("click", () => setSidebarOpen(false));
window.addEventListener("keydown", e => { if (e.key === "Escape") setSidebarOpen(false); });

/* ── FILE LABEL UPDATE ───────────────────────────── */
datasetInput?.addEventListener("change", () => {
  const file = datasetInput.files[0];
  if (fileLabel) fileLabel.textContent = file ? file.name : "Pilih file CSV / Excel";
});

/* ── HTML HELPERS ────────────────────────────────── */
function escapeHtml(v) {
  return String(v ?? "")
    .replaceAll("&",  "&amp;")
    .replaceAll("<",  "&lt;")
    .replaceAll(">",  "&gt;")
    .replaceAll('"',  "&quot;")
    .replaceAll("'",  "&#039;");
}

function formatInlineMd(text) {
  let h = escapeHtml(text);
  h = h.replace(/`([^`]+)`/g, "<code>$1</code>");
  h = h.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  h = h.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
  return h;
}

function renderRichText(container, text) {
  const lines = String(text ?? "").split(/\r?\n/);
  let ul = null;

  const flushUl = () => {
    if (ul) { container.appendChild(ul); ul = null; }
  };

  lines.forEach(line => {
    const trimmed = line.trim();
    const isBullet = /^[-*]\s+/.test(trimmed);

    if (isBullet) {
      if (!ul) ul = document.createElement("ul");
      const li = document.createElement("li");
      li.innerHTML = formatInlineMd(trimmed.replace(/^[-*]\s+/, ""));
      ul.appendChild(li);
      return;
    }

    flushUl();

    if (!trimmed) { container.appendChild(document.createElement("br")); return; }

    const p = document.createElement("p");
    p.innerHTML = formatInlineMd(line);
    container.appendChild(p);
  });

  flushUl();
}

/* ── TABLE RENDERERS ─────────────────────────────── */
function renderKeyValueTable(data) {
  const table = document.createElement("table");
  table.className = "data-table";
  Object.entries(data).forEach(([k, v]) => {
    const row = table.insertRow();
    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = k.replaceAll("_", " ");
    row.append(th);
    row.insertCell().textContent = v;
  });
  return table;
}

function renderRowsTable(rows) {
  const table = document.createElement("table");
  table.className = "data-table";
  if (!rows.length) return table;

  const header = table.insertRow();
  Object.keys(rows[0]).forEach(k => {
    const th = document.createElement("th");
    th.textContent = k.replaceAll("_", " ");
    header.appendChild(th);
  });

  rows.forEach(item => {
    const row = table.insertRow();
    Object.values(item).forEach(val => { row.insertCell().textContent = val; });
  });

  return table;
}

/* ── APPEND MESSAGE ──────────────────────────────── */
function appendMessage(role, payload) {
  if (welcomeScreen) welcomeScreen.style.display = "none";

  const msg    = document.createElement("div");
  msg.className = `message ${role}`;

  /* Avatar – only for bot */
  if (role === "bot") {
    const av = document.createElement("div");
    av.className = "msg-avatar";
    av.setAttribute("aria-hidden", "true");
    const img = document.createElement("img");
    img.src = "/static/logo.png";
    img.alt = "";
    av.appendChild(img);
    msg.appendChild(av);
  }

  const body   = document.createElement("div");
  body.className = "msg-body";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";

  const text = typeof payload === "string" ? payload : payload.message;
  renderRichText(bubble, text);

  /* key-value table */
  if (payload?.table)    bubble.appendChild(renderKeyValueTable(payload.table));
  /* rows table */
  if (payload?.rows)     bubble.appendChild(renderRowsTable(payload.rows));
  /* chart image */
  if (payload?.image_url) {
    const img = document.createElement("img");
    img.src   = payload.image_url;
    img.alt   = payload.message || "Grafik analisis data";
    img.className = "analysis-img";
    bubble.appendChild(img);

    const link = document.createElement("a");
    link.href       = payload.download_url;
    link.className  = "download-link";
    link.setAttribute("download", "");
    link.innerHTML  = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>Simpan PNG`;
    bubble.appendChild(link);
  }

  body.appendChild(bubble);
  msg.appendChild(body);
  messagesEl.appendChild(msg);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

/* ── LOADING INDICATOR ───────────────────────────── */
function showLoading() {
  const bubble = document.createElement("div");
  bubble.className = "message loading-bubble bot";
  bubble.id = "loadingBubble";

  const av = document.createElement("div");
  av.className = "msg-avatar";
  av.setAttribute("aria-hidden", "true");
  const avImg = document.createElement("img");
  avImg.src = "/static/logo.png";
  avImg.alt = "";
  av.appendChild(avImg);
  bubble.appendChild(av);

  const typing = document.createElement("div");
  typing.className = "bot-typing";

  const dots = document.createElement("div");
  dots.className = "typing-dots";
  for (let i = 0; i < 3; i++) dots.appendChild(document.createElement("span"));

  typing.appendChild(dots);

  const body = document.createElement("div");
  body.className = "msg-body";
  body.appendChild(typing);
  bubble.appendChild(body);

  messagesEl.appendChild(bubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideLoading() {
  document.querySelector("#loadingBubble")?.remove();
}

/* ── DATASET STATUS UI ───────────────────────────── */
function updateDatasetInfo(data) {
  const report = data.report || {};

  statusIdle.style.display   = "none";
  statusLoaded.style.display = "block";

  /* truncate filename */
  const raw = data._filename || data.message || "Dataset aktif";
  datasetName.textContent    = raw.length > 28 ? raw.slice(0, 25) + "…" : raw;

  const fields = [
    { label: "Baris Awal",      value: report.initial_rows ?? "—" },
    { label: "Baris Aktif",     value: report.final_rows ?? "—" },
    { label: "Duplikat Hapus",  value: report.duplicate_rows_removed ?? "—" },
    { label: "Missing Value",   value: report.missing_values_handled ?? "—" },
  ];

  datasetMeta.innerHTML = "";
  fields.forEach(f => {
    const item = document.createElement("div");
    item.className = "meta-item";
    item.innerHTML = `<div class="mi-label">${f.label}</div><div class="mi-value">${f.value}</div>`;
    datasetMeta.appendChild(item);
  });
}

/* ── UPLOAD DATASET ──────────────────────────────── */
async function uploadDataset() {
  const file = datasetInput.files[0];
  if (!file) { appendMessage("bot", "Pilih file CSV atau Excel dulu ya."); return; }

  const formData = new FormData();
  formData.append("file", file);

  setLoading(true);
  try {
    const res  = await fetch("/upload", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) { appendMessage("bot", data.message || "Upload gagal."); return; }

    chatHistory = [];
    data._filename = file.name;
    updateDatasetInfo(data);
    appendMessage("bot", { message: data.message, rows: data.preview || [] });
    if (sampleBtn) sampleBtn.textContent = "Ganti ke Sample Walmart";
    fetchHistory();
  } catch (err) {
    appendMessage("bot", { message: "Koneksi error saat upload." });
  } finally {
    setLoading(false);
  }
}

/* ── SAMPLE DATASET ──────────────────────────────── */
async function useSampleDataset() {
  setLoading(true);
  try {
    const res  = await fetch("/use-sample", { method: "POST" });
    const data = await res.json();
    if (!res.ok) { appendMessage("bot", data.message || "Sample gagal dimuat."); return; }

    chatHistory = [];
    data._filename = "Walmart_Sales.csv";
    updateDatasetInfo(data);
    appendMessage("bot", data.message);
    fetchHistory();
  } catch (err) {
    appendMessage("bot", { message: "Koneksi error saat load sample." });
  } finally {
    setLoading(false);
  }
}

/* ── SEND MESSAGE ────────────────────────────────── */
async function sendMessage(message) {
  appendMessage("user", message);
  setLoading(true);
  isGenerating = true;
  currentAbortController = new AbortController();

  try {
    const res  = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: chatHistory }),
      signal: currentAbortController.signal
    });
    const data = await res.json();
    appendMessage("bot", data);

    chatHistory.push({ role: "user", content: message });
    const botContent = typeof data === "string" ? data : (data.message || "");
    chatHistory.push({ role: "assistant", content: botContent });
    fetchHistory();
  } catch (err) {
    if (err.name === "AbortError") {
      appendMessage("bot", { message: "Tanggapan dibatalkan oleh pengguna." });
    } else {
      appendMessage("bot", { message: "Maaf, terjadi kesalahan koneksi." });
    }
  } finally {
    setLoading(false);
    isGenerating = false;
    currentAbortController = null;
    messageInput.focus();
  }
}

/* ── LOADING STATE ───────────────────────────────── */
function setLoading(on) {
  const sendIcon  = document.getElementById("sendIcon");
  const stopIcon  = document.getElementById("stopIcon");

  if (on) {
    showLoading();
    if (sendIcon) sendIcon.style.display = "none";
    if (stopIcon) stopIcon.style.display = "block";
    uploadBtn.disabled = true;
    sampleBtn.disabled = true;
  } else {
    hideLoading();
    if (sendIcon) sendIcon.style.display = "block";
    if (stopIcon) stopIcon.style.display = "none";
    uploadBtn.disabled = false;
    sampleBtn.disabled = false;
  }
}

/* ── EVENT LISTENERS ─────────────────────────────── */
uploadBtn.addEventListener("click", uploadDataset);
sampleBtn.addEventListener("click", useSampleDataset);
if (newChatBtn) newChatBtn.addEventListener("click", createNewChat);

chatForm.addEventListener("submit", e => {
  e.preventDefault();
  
  if (isGenerating) {
    if (currentAbortController) currentAbortController.abort();
    return;
  }
  
  const msg = messageInput.value.trim();
  if (!msg) return;
  messageInput.value = "";
  messageInput.style.height = "auto";
  sendMessage(msg);
});

/* allow Shift+Enter for multiline in future; plain Enter sends */
messageInput.addEventListener("input", function() {
  this.style.height = "auto";
  this.style.height = this.scrollHeight + "px";
});

messageInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!isGenerating) {
      chatForm.dispatchEvent(new Event("submit", { cancelable: true }));
    }
  }
});

/* ── HISTORY MANAGEMENT ──────────────────────────── */
async function fetchHistory() {
  if (!historyList) return;
  try {
    const res = await fetch("/api/sessions");
    const data = await res.json();
    if (data.ok) {
      historyList.innerHTML = "";
      if (data.sessions.length === 0) {
        historyList.innerHTML = '<div class="status-idle">Belum ada riwayat</div>';
        return;
      }
      data.sessions.forEach(session => {
        const item = document.createElement("div");
        item.className = "history-item";
        if (session.id === currentSessionId) item.classList.add("active");
        
        item.innerHTML = `
          <div class="history-item-title">${escapeHtml(session.title)}</div>
          <button class="history-item-del" title="Hapus Chat">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
          </button>
        `;
        
        item.querySelector(".history-item-title").addEventListener("click", () => loadSession(session.id));
        item.querySelector(".history-item-del").addEventListener("click", (e) => {
          e.stopPropagation();
          sessionToDelete = session.id;
          if (deleteModal) deleteModal.classList.add("show");
        });
        
        historyList.appendChild(item);
      });
    }
  } catch (err) {
    console.error("Failed to fetch history:", err);
  }
}

async function loadSession(sessionId) {
  setLoading(true);
  try {
    const res = await fetch(`/api/sessions/${sessionId}`);
    const data = await res.json();
    if (data.ok) {
      currentSessionId = sessionId;
      chatHistory = data.session.history || [];
      
      messagesEl.innerHTML = "";
      if (welcomeScreen) welcomeScreen.style.display = "none";
      
      if (data.session.dataset_name) {
        data.session._filename = data.session.dataset_name;
        data.session.report = { final_rows: "Dimuat Ulang" }; 
        updateDatasetInfo(data.session);
        if (sampleBtn) sampleBtn.textContent = "Ganti ke Sample Walmart";
      } else {
        statusIdle.style.display = "flex";
        statusLoaded.style.display = "none";
      }

      chatHistory.forEach(msg => {
         if (msg.role === "user") appendMessage("user", msg.content);
         else appendMessage("bot", msg.content);
      });
      
      fetchHistory();
      if (window.innerWidth <= 820) setSidebarOpen(false);
    }
  } catch (err) {
    appendMessage("bot", { message: "Gagal memuat sesi chat." });
  } finally {
    setLoading(false);
  }
}

async function createNewChat() {
  try {
    const res = await fetch("/api/sessions/new", { method: "POST" });
    const data = await res.json();
    if (data.ok) {
      currentSessionId = data.session_id;
      chatHistory = [];
      messagesEl.innerHTML = "";
      if (welcomeScreen) welcomeScreen.style.display = "flex";

      statusIdle.style.display = "flex";
      statusLoaded.style.display = "none";
      if (datasetInput) datasetInput.value = "";
      if (fileLabel) fileLabel.textContent = "Pilih file CSV / Excel";
      if (sampleBtn) sampleBtn.textContent = "Pakai Sample Walmart";
      fetchHistory();
      if (window.innerWidth <= 820) setSidebarOpen(false);
    }
  } catch (err) {
    console.error("Failed to create new chat:", err);
  }
}

// Modal Handlers
if (cancelDeleteBtn) {
  cancelDeleteBtn.addEventListener("click", () => {
    sessionToDelete = null;
    if (deleteModal) deleteModal.classList.remove("show");
  });
}

if (confirmDeleteBtn) {
  confirmDeleteBtn.addEventListener("click", async () => {
    if (!sessionToDelete) return;
    
    // Disable button to prevent double clicks
    confirmDeleteBtn.disabled = true;
    confirmDeleteBtn.textContent = "Menghapus...";
    
    try {
      await fetch(`/api/sessions/${sessionToDelete}`, { method: "DELETE" });
      if (sessionToDelete === currentSessionId) createNewChat();
      else fetchHistory();
    } catch (err) {
      console.error("Gagal menghapus sesi:", err);
    } finally {
      sessionToDelete = null;
      if (deleteModal) deleteModal.classList.remove("show");
      confirmDeleteBtn.disabled = false;
      confirmDeleteBtn.textContent = "Ya, Hapus";
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  // Always initialize a new chat session state on load if there's no chat history
  createNewChat();
});
