const categoryLabels = {
  intraoral: "口內照片",
  extraoral: "口外照片",
  xray: "X 光片",
};

const slots = [
  { stage: "before", category: "intraoral", title: "術前 · 口內照片", hint: "正面、側方、咬合面、局部照" },
  { stage: "after", category: "intraoral", title: "術後 · 口內照片", hint: "依術前順序上傳，方便自動配對" },
  { stage: "before", category: "extraoral", title: "術前 · 口外照片", hint: "正面、微笑、側臉、45 度" },
  { stage: "after", category: "extraoral", title: "術後 · 口外照片", hint: "依術前順序上傳，方便自動配對" },
  { stage: "before", category: "xray", title: "術前 · X 光片", hint: "選填：全景、根尖、CBCT 截圖" },
  { stage: "after", category: "xray", title: "術後 · X 光片", hint: "選填：同類型影像依序配對" },
];

const state = {
  images: [],
  papers: [],
};

const $ = selector => document.querySelector(selector);

function init() {
  $("#caseDate").value = new Date().toISOString().slice(0, 10);
  renderUploadBoxes();
  renderPairs();
  $("#generateBtn").addEventListener("click", generatePresentation);
  $("#paperSearchBtn").addEventListener("click", searchPapers);
  $("#clearBtn").addEventListener("click", () => {
    state.images = [];
    renderUploadBoxes();
    renderPairs();
  });
}

function renderUploadBoxes() {
  const grid = $("#uploadGrid");
  const template = $("#uploadTemplate");
  grid.replaceChildren();
  slots.forEach(slot => {
    const node = template.content.cloneNode(true);
    const box = node.querySelector(".upload-box");
    box.classList.add(slot.stage);
    node.querySelector(".box-title").textContent = slot.title;
    node.querySelector(".box-hint").textContent = slot.hint;
    const input = node.querySelector(".file-input");
    input.addEventListener("change", event => handleFiles(event.target.files, slot));
    bindDropZone(box, slot);
    renderThumbs(node.querySelector(".thumb-list"), slot);
    grid.append(node);
  });
}

function bindDropZone(box, slot) {
  const stop = event => {
    event.preventDefault();
    event.stopPropagation();
  };
  ["dragenter", "dragover"].forEach(type => {
    box.addEventListener(type, event => {
      stop(event);
      box.classList.add("drag-over");
    });
  });
  ["dragleave", "drop"].forEach(type => {
    box.addEventListener(type, event => {
      stop(event);
      box.classList.remove("drag-over");
    });
  });
  box.addEventListener("drop", event => handleFiles(event.dataTransfer.files, slot));
}

function renderThumbs(container, slot) {
  const images = state.images.filter(item => item.stage === slot.stage && item.category === slot.category);
  images.forEach(item => {
    const thumb = document.createElement("div");
    thumb.className = "thumb";
    thumb.innerHTML = `<img alt="" src="${item.dataUrl}"><span>${item.name}</span><button type="button">移除</button>`;
    thumb.querySelector("button").addEventListener("click", () => {
      state.images = state.images.filter(image => image.id !== item.id);
      renderUploadBoxes();
      renderPairs();
    });
    container.append(thumb);
  });
}

async function handleFiles(fileList, slot) {
  const files = Array.from(fileList || []).filter(file => file.type.startsWith("image/"));
  if (!files.length) return;
  $("#statusText").textContent = `正在處理 ${files.length} 張影像...`;
  for (const file of files) {
    const dataUrl = await compressImage(file);
    state.images.push({
      id: createId(),
      stage: slot.stage,
      category: slot.category,
      slot: slot.title,
      name: file.name,
      dataUrl,
    });
  }
  renderUploadBoxes();
  renderPairs();
  $("#statusText").textContent = `已加入 ${files.length} 張影像，共 ${state.images.length} 張`;
}

function compressImage(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const image = new Image();
      image.onload = () => {
        const maxEdge = 1800;
        const scale = Math.min(1, maxEdge / Math.max(image.width, image.height));
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(image.width * scale));
        canvas.height = Math.max(1, Math.round(image.height * scale));
        const context = canvas.getContext("2d");
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL("image/jpeg", 0.86));
      };
      image.onerror = reject;
      image.src = reader.result;
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function createId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `id-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function collectForm() {
  return {
    caseTitle: $("#caseTitle").value.trim(),
    patientCode: $("#patientCode").value.trim(),
    doctor: $("#doctor").value.trim(),
    caseDate: $("#caseDate").value,
    treatment: $("#treatment").value.trim(),
    caseType: $("#caseType").value.trim(),
    chiefConcern: $("#chiefConcern").value.trim(),
    clinicalNotes: $("#clinicalNotes").value.trim(),
    comparisonNotes: $("#comparisonNotes").value.trim(),
    finalNotes: $("#finalNotes").value.trim(),
    images: state.images,
    papers: state.papers,
  };
}

function imagePairs(category) {
  const before = state.images.filter(item => item.category === category && item.stage === "before");
  const after = state.images.filter(item => item.category === category && item.stage === "after");
  const count = Math.max(before.length, after.length);
  return Array.from({ length: count }, (_, index) => ({
    before: before[index] || null,
    after: after[index] || null,
  }));
}

function renderPairs() {
  $("#imageCount").textContent = `${state.images.length} 張影像`;
  const preview = $("#pairPreview");
  preview.replaceChildren();

  Object.entries(categoryLabels).forEach(([category, label]) => {
    const pairs = imagePairs(category);
    if (!pairs.length) return;
    const group = document.createElement("article");
    group.className = "pair-group";
    group.innerHTML = `<h3>${label} · ${pairs.length} 組</h3>`;
    pairs.forEach(pair => {
      const row = document.createElement("div");
      row.className = "pair-row";
      row.append(pairTile(pair.before, "Before"));
      row.append(pairTile(pair.after, "After"));
      group.append(row);
    });
    preview.append(group);
  });

  if (!preview.children.length) {
    preview.textContent = "尚未上傳影像。";
  }
}

function pairTile(item, label) {
  const tile = document.createElement("div");
  tile.className = "pair-tile";
  if (!item) {
    tile.innerHTML = `<div class="empty-tile">未提供 ${label}</div><span>${label}</span>`;
    return tile;
  }
  tile.innerHTML = `<img alt="" src="${item.dataUrl}"><span>${label} · ${item.name}</span>`;
  return tile;
}

async function generatePresentation() {
  if (!state.images.length) {
    $("#statusText").textContent = "請先上傳至少一張影像";
    return;
  }
  const button = $("#generateBtn");
  button.disabled = true;
  $("#statusText").textContent = "正在產生 PPT...";
  try {
    if (!state.papers.length) {
      await searchPapers({ silent: true });
    }
    const response = await fetch("/api/presentations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectForm()),
    });
    if (!response.ok) {
      let message = `HTTP ${response.status}`;
      try {
        const errorPayload = await response.json();
        if (errorPayload.error) message = errorPayload.error;
      } catch {
        message = await response.text();
      }
      throw new Error(message || `HTTP ${response.status}`);
    }
    const blob = await response.blob();
    const filename = getFilename(response.headers.get("Content-Disposition")) || "dental-case.pptx";
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
    $("#statusText").textContent = `已產生 ${filename}`;
  } catch (error) {
    $("#statusText").textContent = `產生失敗：${error.message}`;
  } finally {
    button.disabled = false;
  }
}

async function searchPapers(options = {}) {
  const query = paperQuery();
  if (!query) {
    if (!options.silent) $("#statusText").textContent = "請輸入文獻搜尋關鍵字或治療項目";
    return [];
  }
  if (!options.silent) $("#statusText").textContent = "正在搜尋 PubMed...";
  try {
    const response = await fetch(`/api/papers?q=${encodeURIComponent(query)}&limit=8`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.papers = data.papers || [];
    renderPapers();
    if (!options.silent) $("#statusText").textContent = `找到 ${state.papers.length} 篇 PubMed 文獻`;
    return state.papers;
  } catch (error) {
    if (!options.silent) $("#statusText").textContent = `文獻搜尋失敗：${error.message}`;
    return [];
  }
}

function paperQuery() {
  const manual = $("#paperQuery").value.trim();
  if (manual) return manual;
  const treatment = $("#treatment").value.trim();
  const concern = $("#chiefConcern").value.trim();
  const clinical = $("#clinicalNotes").value.trim();
  const comparison = $("#comparisonNotes").value.trim();
  return [treatment, concern, clinical, comparison, "dentistry", "systematic review OR clinical study"].filter(Boolean).join(" ");
}

function renderPapers() {
  const list = $("#paperList");
  list.replaceChildren();
  if (!state.papers.length) {
    list.textContent = "沒有找到文獻，請調整關鍵字。";
    return;
  }
  state.papers.forEach(paper => {
    const article = document.createElement("article");
    article.className = "paper-item";
    const authors = paper.authors?.length ? paper.authors.join(", ") : "Unknown authors";
    article.innerHTML = `
      <strong>${escapeHtml(paper.title || "Untitled")}</strong>
      <div class="paper-meta">${escapeHtml(authors)} · ${escapeHtml(paper.journal || "PubMed")} · ${escapeHtml(paper.year || "")}</div>
      <div class="paper-meta">PMID ${escapeHtml(paper.pmid || "")}${paper.doi ? ` · DOI ${escapeHtml(paper.doi)}` : ""}</div>
    `;
    list.append(article);
  });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;",
  }[char]));
}

function getFilename(disposition) {
  if (!disposition) return "";
  const match = disposition.match(/filename="([^"]+)"/);
  return match ? match[1] : "";
}

init();
