const messages = document.querySelector("#messages");
const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const datasetInput = document.querySelector("#dataset");
const uploadBtn = document.querySelector("#uploadBtn");
const sampleBtn = document.querySelector("#sampleBtn");
const datasetStatus = document.querySelector("#datasetStatus");
const datasetMeta = document.querySelector("#datasetMeta");
const sidebarToggle = document.querySelector("#sidebarToggle");
const sidebarClose = document.querySelector("#sidebarClose");
const backdrop = document.querySelector("#backdrop");

let chatHistory = [];

function setSidebarOpen(open) {
  document.body.classList.toggle("sidebar-open", open);
  if (backdrop) backdrop.setAttribute("aria-hidden", open ? "false" : "true");
}

if (sidebarToggle) {
  sidebarToggle.addEventListener("click", () => {
    setSidebarOpen(!document.body.classList.contains("sidebar-open"));
  });
}

if (sidebarClose) {
  sidebarClose.addEventListener("click", () => setSidebarOpen(false));
}

if (backdrop) {
  backdrop.addEventListener("click", () => setSidebarOpen(false));
}

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") setSidebarOpen(false);
});

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatInlineMarkdown(text) {
  let html = escapeHtml(text);

  // inline code: `code`
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  // bold: **text**
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  // italic: *text* (avoid breaking bold)
  html = html.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");

  return html;
}

function renderRichText(container, text) {
  const raw = String(text ?? "");
  const lines = raw.split(/\r?\n/);

  let ul = null;
  const flushUl = () => {
    if (ul) {
      container.appendChild(ul);
      ul = null;
    }
  };

  lines.forEach((line) => {
    const trimmed = line.trim();
    const isBullet = /^[-*]\s+/.test(trimmed);

    if (isBullet) {
      if (!ul) ul = document.createElement("ul");
      const li = document.createElement("li");
      li.innerHTML = formatInlineMarkdown(trimmed.replace(/^[-*]\s+/, ""));
      ul.appendChild(li);
      return;
    }

    flushUl();

    if (!trimmed) {
      container.appendChild(document.createElement("br"));
      return;
    }

    const p = document.createElement("p");
    p.innerHTML = formatInlineMarkdown(line);
    container.appendChild(p);
  });

  flushUl();
}

function appendMessage(role, payload) {
  const bubble = document.createElement("div");
  bubble.className = `message ${role}`;

  const content = document.createElement("div");
  content.className = "message-content";
  const messageText = typeof payload === "string" ? payload : payload.message;
  renderRichText(content, messageText);
  bubble.appendChild(content);

  if (payload.table) {
    bubble.appendChild(renderKeyValueTable(payload.table));
  }

  if (payload.rows) {
    bubble.appendChild(renderRowsTable(payload.rows));
  }

  if (payload.image_url) {
    const image = document.createElement("img");
    image.src = payload.image_url;
    image.alt = payload.message || "Grafik analisis data";
    bubble.appendChild(image);

    const link = document.createElement("a");
    link.href = payload.download_url;
    link.className = "download-link";
    link.textContent = "Save PNG";
    link.setAttribute("download", "");
    bubble.appendChild(link);
  }

  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
}

function renderKeyValueTable(data) {
  const table = document.createElement("table");
  table.className = "data-table";

  Object.entries(data).forEach(([key, value]) => {
    const row = document.createElement("tr");
    const keyCell = document.createElement("th");
    const valueCell = document.createElement("td");
    keyCell.textContent = key.replaceAll("_", " ");
    valueCell.textContent = value;
    row.append(keyCell, valueCell);
    table.appendChild(row);
  });

  return table;
}

function renderRowsTable(rows) {
  const table = document.createElement("table");
  table.className = "data-table";

  if (!rows.length) {
    return table;
  }

  const header = document.createElement("tr");
  Object.keys(rows[0]).forEach((key) => {
    const th = document.createElement("th");
    th.textContent = key.replaceAll("_", " ");
    header.appendChild(th);
  });
  table.appendChild(header);

  rows.forEach((item) => {
    const row = document.createElement("tr");
    Object.values(item).forEach((value) => {
      const td = document.createElement("td");
      td.textContent = value;
      row.appendChild(td);
    });
    table.appendChild(row);
  });

  return table;
}

function showLoading() {
  const bubble = document.createElement("div");
  bubble.className = "message loading-bubble";
  bubble.id = "loadingBubble";
  
  const typing = document.createElement("div");
  typing.className = "bot-typing";
  
  const img = document.createElement("img");
  img.src = "/static/logo.png";
  img.alt = "EchaBot Logo";
  
  const dots = document.createElement("div");
  dots.className = "typing-dots";
  dots.appendChild(document.createElement("span"));
  dots.appendChild(document.createElement("span"));
  dots.appendChild(document.createElement("span"));
  
  typing.appendChild(img);
  typing.appendChild(dots);
  bubble.appendChild(typing);
  
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
}

function hideLoading() {
  const bubble = document.querySelector("#loadingBubble");
  if (bubble) bubble.remove();
}

function updateDatasetInfo(data) {
  datasetStatus.textContent = data.message;
  datasetMeta.innerHTML = "";

  const report = data.report || {};
  const fields = {
    "Baris awal": report.initial_rows,
    "Baris aktif": report.final_rows,
    "Duplikat dihapus": report.duplicate_rows_removed,
    "Missing value": report.missing_values_handled,
  };

  Object.entries(fields).forEach(([label, value]) => {
    const item = document.createElement("div");
    item.textContent = `${label}: ${value ?? "-"}`;
    datasetMeta.appendChild(item);
  });
}

async function uploadDataset() {
  const file = datasetInput.files[0];
  if (!file) {
    appendMessage("bot", "Pilih file CSV atau Excel dulu ya.");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  showLoading();
  const response = await fetch("/upload", {
    method: "POST",
    body: formData,
  });
  const data = await response.json();
  hideLoading();

  if (!response.ok) {
    appendMessage("bot", data.message || "Upload gagal.");
    return;
  }

  chatHistory = [];
  updateDatasetInfo(data);
  appendMessage("bot", {
    message: data.message,
    rows: data.preview || [],
  });
}

async function useSampleDataset() {
  showLoading();
  const response = await fetch("/use-sample", { method: "POST" });
  const data = await response.json();
  hideLoading();

  if (!response.ok) {
    appendMessage("bot", data.message || "Sample gagal dimuat.");
    return;
  }

  chatHistory = [];
  updateDatasetInfo(data);
  appendMessage("bot", data.message);
}

async function sendMessage(message) {
  appendMessage("user", message);
  showLoading();

  const submitBtn = chatForm.querySelector("button[type='submit']");
  const sendIcon = document.getElementById("sendIcon");
  const stopIcon = document.getElementById("stopIcon");

  if (submitBtn) submitBtn.disabled = true;
  if (sendIcon) sendIcon.style.display = "none";
  if (stopIcon) stopIcon.style.display = "block";

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message, history: chatHistory }),
    });

    const data = await response.json();
    hideLoading();
    appendMessage("bot", data);

    chatHistory.push({ role: "user", content: message });
    const botContent = typeof data === "string" ? data : (data.message || "");
    chatHistory.push({ role: "assistant", content: botContent });
  } catch (error) {
    hideLoading();
    appendMessage("bot", { message: "Maaf, terjadi kesalahan koneksi." });
  } finally {
    if (submitBtn) submitBtn.disabled = false;
    if (sendIcon) sendIcon.style.display = "block";
    if (stopIcon) stopIcon.style.display = "none";
    messageInput.focus();
  }
}

uploadBtn.addEventListener("click", uploadDataset);
sampleBtn.addEventListener("click", useSampleDataset);

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) {
    return;
  }

  messageInput.value = "";
  sendMessage(message);
});
