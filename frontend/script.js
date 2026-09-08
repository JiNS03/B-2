// ---------------------------------------------------------
// 상태
// ---------------------------------------------------------
let currentConversationId = null;
let allDataRecords = [];       // 현재 로드된 전체 시청 기록 (필터링/시각화용 원본)
let activePlatformFilter = "all";
let trendChart = null;
let platformChart = null;
let formtypeChart = null;

// 플랫폼 코드 -> 화면에 표시할 한글 이름
const PLATFORM_LABELS = {
  youtube: "유튜브",
  youtube_music: "유튜브 뮤직",
  netflix: "넷플릭스",
  disney_plus: "디즈니+",
  watcha: "왓챠",
  instagram_reels: "인스타 릴스",
  tiktok: "틱톡",
  youtube_shorts: "유튜브 쇼츠",
  coupang_play: "쿠팡플레이",
};

// 플랫폼별로 의미 있는 콘텐츠 형태만 남기기 위한 매핑.
// 값이 하나뿐이면 그 값으로 자동 고정하고 선택 UI는 숨긴다.
const PLATFORM_CONTENT_TYPES = {
  youtube: ["long_form", "short_form"],
  youtube_shorts: ["short_form"],
  instagram_reels: ["short_form"],
  tiktok: ["short_form"],
  youtube_music: ["long_form"], // "재생"만 있으므로 롱폼으로 고정 취급
  netflix: ["long_form"],
  disney_plus: ["long_form"],
  watcha: ["long_form"],
  coupang_play: ["long_form"],
};

const CONTENT_TYPE_LABELS = {
  long_form: "롱폼 (OTT/일반영상)",
  short_form: "숏폼 (쇼츠/릴스)",
};

// 차트에 쓸 고정 색상 팔레트
const CHART_COLORS = ["#E8B34C", "#3E8E8A", "#C1584A", "#7D8CE0", "#9098A3", "#5AB584"];

function platformLabel(code) {
  return PLATFORM_LABELS[code] || code;
}

// ---------------------------------------------------------
// 초기화
// ---------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  setupTheme();
  setupTabs();
  setupContentTypeSync();
  setupImportForm();

  loadSummary();
  loadDataList();
  loadHistoryList();
  loadBatchList();

  document.getElementById("chat-form").addEventListener("submit", handleChatSubmit);
  document.getElementById("data-form").addEventListener("submit", handleDataSubmit);
});

// ---------------------------------------------------------
// 다크/라이트 테마 토글
// ---------------------------------------------------------
function setupTheme() {
  const saved = localStorage.getItem("watchlog-theme");
  const initial = saved || "dark";
  document.documentElement.setAttribute("data-theme", initial);

  document.getElementById("theme-toggle").addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("watchlog-theme", next);

    // Chart.js는 색상을 그릴 때 고정값을 쓰므로, 테마가 바뀌면 다시 그려줘야 축/범례 글자색이 맞음
    loadSummary();
    if (allDataRecords.length) renderInsightsFromRecords(allDataRecords);
  });
}

// ---------------------------------------------------------
// 탭 전환
// ---------------------------------------------------------
function setupTabs() {
  const buttons = document.querySelectorAll(".tab-btn");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");

      document.querySelectorAll(".tab-pane").forEach((pane) => pane.classList.remove("active"));
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });
}

// ---------------------------------------------------------
// 데이터 관리 폼: 플랫폼에 따라 콘텐츠 형태 옵션을 다시 그림
// ---------------------------------------------------------
function setupContentTypeSync() {
  const platformSelect = document.getElementById("input-platform");
  const contentTypeRow = document.getElementById("content-type-row");
  const contentTypeSelect = document.getElementById("input-content-type");

  function sync() {
    const platform = platformSelect.value;
    const allowed = PLATFORM_CONTENT_TYPES[platform] || ["long_form", "short_form"];

    if (allowed.length === 1) {
      // 선택지가 하나뿐이면 그 값으로 고정하고 필드 자체를 숨김
      contentTypeSelect.innerHTML = `<option value="${allowed[0]}">${CONTENT_TYPE_LABELS[allowed[0]]}</option>`;
      contentTypeRow.style.display = "none";
    } else {
      contentTypeSelect.innerHTML = allowed
        .map((v) => `<option value="${v}">${CONTENT_TYPE_LABELS[v]}</option>`)
        .join("");
      contentTypeRow.style.display = "";
    }
  }

  platformSelect.addEventListener("change", sync);
  sync(); // 초기 상태 반영
}

// ---------------------------------------------------------
// 요약 정보 (상단 히어로 통계 + 인사이트 차트)
// ---------------------------------------------------------
async function loadSummary() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/data/summary`);
    if (!res.ok) throw new Error("summary fetch failed");
    const summary = await res.json();

    document.getElementById("stat-total").textContent = summary.metrics.total_minutes;
    document.getElementById("stat-avg").textContent = summary.metrics.average_minutes_per_day;
    document.getElementById("stat-period").textContent = summary.period;
    document.getElementById("stat-trend").textContent = summary.trend;

    renderPlatformChart(summary.platform_breakdown || {});
    renderFormtypeChart(summary.metrics);
  } catch (err) {
    console.error(err);
    document.getElementById("stat-period").textContent = "불러오기 실패";
  }
}

function chartTextColor() {
  return getComputedStyle(document.documentElement).getPropertyValue("--text-muted").trim() || "#9098A3";
}

function chartGridColor() {
  return getComputedStyle(document.documentElement).getPropertyValue("--border").trim() || "#2E333D";
}

function renderPlatformChart(breakdown) {
  const canvas = document.getElementById("platform-chart");
  const entries = Object.entries(breakdown);

  if (platformChart) platformChart.destroy();
  if (entries.length === 0) return;

  const labels = entries.map(([platform]) => platformLabel(platform));
  const data = entries.map(([, stats]) => stats.total_minutes);

  platformChart = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data, backgroundColor: CHART_COLORS, borderWidth: 0 }],
    },
    options: {
      plugins: {
        legend: { position: "bottom", labels: { color: chartTextColor(), font: { family: "Inter" }, boxWidth: 12, padding: 12 } },
      },
    },
  });
}

function renderFormtypeChart(metrics) {
  const canvas = document.getElementById("formtype-chart");
  if (formtypeChart) formtypeChart.destroy();

  formtypeChart = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels: ["롱폼", "숏폼"],
      datasets: [
        {
          data: [metrics.longform_ratio, metrics.shortform_ratio],
          backgroundColor: [CHART_COLORS[1], CHART_COLORS[0]],
          borderWidth: 0,
        },
      ],
    },
    options: {
      plugins: {
        legend: { position: "bottom", labels: { color: chartTextColor(), font: { family: "Inter" }, boxWidth: 12, padding: 12 } },
      },
    },
  });
}

// ---------------------------------------------------------
// 인사이트: 캘린더 히트맵 + 추이 라인차트
// ---------------------------------------------------------
function renderInsightsFromRecords(records) {
  const dailyTotals = {};
  records.forEach((r) => {
    dailyTotals[r.date] = (dailyTotals[r.date] || 0) + r.value;
  });

  renderHeatmap(dailyTotals);
  renderTrendChart(dailyTotals);
}

function renderHeatmap(dailyTotals) {
  const grid = document.getElementById("heatmap-grid");
  const caption = document.getElementById("heatmap-caption");
  const dates = Object.keys(dailyTotals).sort();

  if (dates.length === 0) {
    grid.innerHTML = "";
    caption.textContent = "아직 데이터가 없어요.";
    return;
  }

  const startDate = new Date(dates[0]);
  const endDate = new Date(dates[dates.length - 1]);

  const gridStart = new Date(startDate);
  gridStart.setDate(gridStart.getDate() - gridStart.getDay());

  const maxValue = Math.max(...Object.values(dailyTotals), 1);

  const cells = [];
  const cursor = new Date(gridStart);
  while (cursor <= endDate) {
    const iso = cursor.toISOString().slice(0, 10);
    const value = dailyTotals[iso] || 0;
    const level = value === 0 ? 0 : Math.min(4, Math.ceil((value / maxValue) * 4));
    cells.push(`<div class="heatmap-cell level-${level}" title="${iso} · ${value}분"></div>`);
    cursor.setDate(cursor.getDate() + 1);
  }

  grid.innerHTML = cells.join("");
  caption.textContent = `${dates[0]} ~ ${dates[dates.length - 1]} · 칸에 마우스를 올리면 날짜별 시청 시간이 보여요.`;
}

function renderTrendChart(dailyTotals) {
  const canvas = document.getElementById("trend-chart");
  const dates = Object.keys(dailyTotals).sort();

  if (trendChart) trendChart.destroy();
  if (dates.length === 0) return;

  const values = dates.map((d) => dailyTotals[d]);

  trendChart = new Chart(canvas, {
    type: "line",
    data: {
      labels: dates,
      datasets: [
        {
          label: "일별 시청 시간(분)",
          data: values,
          borderColor: "#E8B34C",
          backgroundColor: "rgba(232, 179, 76, 0.15)",
          fill: true,
          tension: 0.25,
          pointRadius: 0,
        },
      ],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: chartTextColor(), maxTicksLimit: 8 }, grid: { color: chartGridColor() } },
        y: { ticks: { color: chartTextColor() }, grid: { color: chartGridColor() } },
      },
    },
  });
}

// ---------------------------------------------------------
// 채팅
// ---------------------------------------------------------
async function handleChatSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const message = input.value.trim();
  if (!message) return;

  appendChatMessage("user", message);
  input.value = "";
  setChatLoading(true);

  try {
    const res = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        conversation_id: currentConversationId,
      }),
    });

    if (!res.ok) throw new Error("chat request failed");
    const data = await res.json();

    currentConversationId = data.conversation_id;
    appendChatMessage("assistant", data.reply);

    loadHistoryList();
  } catch (err) {
    console.error(err);
    appendChatMessage(
      "assistant",
      "죄송해요, 답변을 가져오는 중 문제가 생겼어요. 서버가 콜드스타트 중일 수 있으니 잠시 후 다시 시도해주세요."
    );
  } finally {
    setChatLoading(false);
  }
}

function appendChatMessage(role, text) {
  const chatWindow = document.getElementById("chat-window");
  const msg = document.createElement("div");
  msg.className = `chat-msg ${role}`;
  const p = document.createElement("p");
  p.textContent = text;
  msg.appendChild(p);
  chatWindow.appendChild(msg);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function setChatLoading(isLoading) {
  document.getElementById("chat-loading").hidden = !isLoading;
}

function resetChatWindow() {
  const chatWindow = document.getElementById("chat-window");
  chatWindow.innerHTML = "";
}

// ---------------------------------------------------------
// 데이터 관리 (CRUD)
// ---------------------------------------------------------
async function handleDataSubmit(e) {
  e.preventDefault();

  const payload = {
    date: document.getElementById("input-date").value,
    value: Number(document.getElementById("input-value").value),
    memo: document.getElementById("input-memo").value,
    platform: document.getElementById("input-platform").value,
    content_type: document.getElementById("input-content-type").value,
  };

  try {
    const res = await fetch(`${API_BASE_URL}/api/data`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("data create failed");

    e.target.reset();
    document.getElementById("input-platform").dispatchEvent(new Event("change"));
    loadDataList();
    loadSummary();
  } catch (err) {
    console.error(err);
    alert("데이터 추가에 실패했어요. 입력값을 확인해주세요.");
  }
}

async function loadDataList() {
  const tbody = document.getElementById("data-table-body");
  try {
    const res = await fetch(`${API_BASE_URL}/api/data`);
    if (!res.ok) throw new Error("data list fetch failed");
    const records = await res.json();

    allDataRecords = records;
    renderPlatformFilterButtons(records);
    renderDataTable();
    renderInsightsFromRecords(records);
  } catch (err) {
    console.error(err);
    tbody.innerHTML = `<tr><td colspan="6" class="empty-row">목록을 불러오지 못했어요.</td></tr>`;
  }
}

function renderPlatformFilterButtons(records) {
  const container = document.getElementById("platform-filter");
  const platforms = [...new Set(records.map((r) => r.platform))].sort();

  const buttonsHtml = platforms
    .map(
      (p) =>
        `<button class="filter-btn${p === activePlatformFilter ? " active" : ""}" data-platform="${p}">${platformLabel(p)}</button>`
    )
    .join("");

  container.innerHTML = `<button class="filter-btn${activePlatformFilter === "all" ? " active" : ""}" data-platform="all">전체</button>${buttonsHtml}`;

  container.querySelectorAll(".filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      activePlatformFilter = btn.dataset.platform;
      container.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      renderDataTable();
    });
  });
}

function renderDataTable() {
  const tbody = document.getElementById("data-table-body");

  const filtered =
    activePlatformFilter === "all"
      ? allDataRecords
      : allDataRecords.filter((r) => r.platform === activePlatformFilter);

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-row">해당 항목의 기록이 없어요.</td></tr>`;
    return;
  }

  const sorted = [...filtered].sort((a, b) => (a.date < b.date ? 1 : -1));

  tbody.innerHTML = sorted
    .map(
      (r) => `
    <tr>
      <td>${r.date}</td>
      <td>${r.value}분</td>
      <td>${platformLabel(r.platform)}</td>
      <td>${r.content_type === "short_form" ? "숏폼" : "롱폼"}</td>
      <td>${escapeHtml(r.memo || "")}</td>
      <td><button class="btn-delete" data-id="${r.id}">삭제</button></td>
    </tr>`
    )
    .join("");

  tbody.querySelectorAll(".btn-delete").forEach((btn) => {
    btn.addEventListener("click", () => deleteRecord(btn.dataset.id));
  });
}

async function deleteRecord(id) {
  if (!confirm("이 기록을 삭제할까요?")) return;
  try {
    const res = await fetch(`${API_BASE_URL}/api/data/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("delete failed");
    loadDataList();
    loadSummary();
  } catch (err) {
    console.error(err);
    alert("삭제에 실패했어요.");
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---------------------------------------------------------
// 가져오기: Takeout HTML 업로드
// ---------------------------------------------------------
let selectedImportFile = null;

function setupImportForm() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("import-file-input");
  const dropzoneText = document.getElementById("dropzone-text");

  fileInput.addEventListener("change", () => {
    if (fileInput.files[0]) setSelectedFile(fileInput.files[0]);
  });

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    const file = e.dataTransfer.files[0];
    if (file) setSelectedFile(file);
  });

  function setSelectedFile(file) {
    selectedImportFile = file;
    dropzoneText.textContent = `선택됨: ${file.name} (${(file.size / 1024 / 1024).toFixed(1)}MB)`;
  }

  document.getElementById("import-form").addEventListener("submit", handleImportSubmit);
}

async function handleImportSubmit(e) {
  e.preventDefault();

  if (!selectedImportFile) {
    alert("먼저 HTML 파일을 선택해주세요.");
    return;
  }

  const formData = new FormData();
  formData.append("file", selectedImportFile);
  formData.append("filter_start_date", document.getElementById("import-start-date").value || "");
  formData.append("avg_long_minutes", document.getElementById("import-avg-long").value || "3");
  formData.append("avg_short_minutes", document.getElementById("import-avg-short").value || "1");
  formData.append("avg_music_minutes", document.getElementById("import-avg-music").value || "4");

  const submitBtn = document.getElementById("import-submit-btn");
  const loading = document.getElementById("import-loading");
  const loadingText = document.getElementById("import-loading-text");
  const resultBox = document.getElementById("import-result");

  submitBtn.disabled = true;
  loading.hidden = false;
  resultBox.hidden = true;

  // 큰 파일일수록 대략적인 안내 문구를 바꿔줌 (실제 진행률은 아니고 심리적 안내용)
  const sizeMB = selectedImportFile.size / 1024 / 1024;
  loadingText.textContent =
    sizeMB > 10
      ? "파일이 커서 시간이 조금 더 걸려요 (최대 2분). 창을 닫지 말고 기다려주세요..."
      : "파일을 분석하고 있어요. 잠시만 기다려주세요...";

  try {
    const res = await fetch(`${API_BASE_URL}/api/imports/youtube-html`, {
      method: "POST",
      body: formData,
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "업로드에 실패했어요.");
    }

    resultBox.className = "import-result";
    resultBox.innerHTML = `
      <strong>${data.filename}</strong> 분석 완료<br>
      총 ${data.parsed_count}개 시청 기록 파싱 (게시물 확인 등 ${data.skipped_non_watch}건 제외)<br>
      기간: ${data.period}<br>
      ${data.saved_row_count}개 행으로 집계되어 저장됐어요. 이 배치가 자동으로 화면에 적용됩니다.
    `;
    resultBox.hidden = false;

    // 새로 만든 배치가 활성화된 상태이므로 화면 전체를 새로고침
    loadSummary();
    loadDataList();
    loadBatchList();
  } catch (err) {
    console.error(err);
    resultBox.className = "import-result error";
    resultBox.textContent = `업로드 실패: ${err.message}`;
    resultBox.hidden = false;
  } finally {
    submitBtn.disabled = false;
    loading.hidden = true;
  }
}

// ---------------------------------------------------------
// 가져오기 기록 (배치 목록/전환/삭제)
// ---------------------------------------------------------
async function loadBatchList() {
  const list = document.getElementById("batch-list");
  try {
    const res = await fetch(`${API_BASE_URL}/api/imports`);
    if (!res.ok) throw new Error("batch list fetch failed");
    const batches = await res.json();

    if (batches.length === 0) {
      list.innerHTML = `<li class="empty-row">아직 업로드한 기록이 없어요.</li>`;
      return;
    }

    list.innerHTML = batches
      .map(
        (b) => `
      <li class="batch-item${b.is_active ? " active" : ""}" data-id="${b.id}">
        <div class="batch-info">
          <div class="batch-filename">${escapeHtml(b.filename)}${b.is_active ? '<span class="batch-active-badge">적용됨</span>' : ""}</div>
          <div class="batch-meta">${formatDate(b.uploaded_at)} · ${b.record_count}행 · ${escapeHtml(b.period)}</div>
        </div>
        <div class="batch-actions">
          <button class="btn-secondary btn-activate" data-id="${b.id}" ${b.is_active ? "disabled" : ""}>이 데이터 보기</button>
          <button class="btn-delete btn-delete-batch" data-id="${b.id}">삭제</button>
        </div>
      </li>`
      )
      .join("");

    list.querySelectorAll(".btn-activate").forEach((btn) => {
      btn.addEventListener("click", () => activateBatch(btn.dataset.id));
    });
    list.querySelectorAll(".btn-delete-batch").forEach((btn) => {
      btn.addEventListener("click", () => deleteBatch(btn.dataset.id));
    });
  } catch (err) {
    console.error(err);
    list.innerHTML = `<li class="empty-row">가져오기 기록을 불러오지 못했어요.</li>`;
  }
}

async function activateBatch(batchId) {
  try {
    const res = await fetch(`${API_BASE_URL}/api/imports/${batchId}/activate`, { method: "POST" });
    if (!res.ok) throw new Error("activate failed");
    loadBatchList();
    loadSummary();
    loadDataList();
  } catch (err) {
    console.error(err);
    alert("데이터 전환에 실패했어요.");
  }
}

async function deleteBatch(batchId) {
  if (!confirm("이 배치와 관련 시청 기록을 전부 삭제할까요? 되돌릴 수 없어요.")) return;
  try {
    const res = await fetch(`${API_BASE_URL}/api/imports/${batchId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("delete failed");
    loadBatchList();
    loadSummary();
    loadDataList();
  } catch (err) {
    console.error(err);
    alert("삭제에 실패했어요.");
  }
}

// ---------------------------------------------------------
// 대화 기록 (불러오기)
// ---------------------------------------------------------
async function loadHistoryList() {
  const list = document.getElementById("history-list");
  try {
    const res = await fetch(`${API_BASE_URL}/api/conversations`);
    if (!res.ok) throw new Error("history fetch failed");
    const conversations = await res.json();

    if (conversations.length === 0) {
      list.innerHTML = `<li class="empty-row">아직 대화 기록이 없어요.</li>`;
      return;
    }

    list.innerHTML = conversations
      .map(
        (c) => `
      <li class="history-item" data-id="${c.id}">
        <div>
          <div class="history-title">${escapeHtml(c.title)}</div>
          <div class="history-meta">${formatDate(c.created_at)} · 메시지 ${c.message_count}개</div>
        </div>
        <button class="history-delete" data-id="${c.id}">삭제</button>
      </li>`
      )
      .join("");

    list.querySelectorAll(".history-item").forEach((item) => {
      item.addEventListener("click", (e) => {
        if (e.target.classList.contains("history-delete")) return;
        loadConversation(item.dataset.id);
      });
    });

    list.querySelectorAll(".history-delete").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        deleteConversation(btn.dataset.id);
      });
    });
  } catch (err) {
    console.error(err);
    list.innerHTML = `<li class="empty-row">대화 기록을 불러오지 못했어요.</li>`;
  }
}

async function loadConversation(id) {
  try {
    const res = await fetch(`${API_BASE_URL}/api/conversations/${id}`);
    if (!res.ok) throw new Error("conversation fetch failed");
    const conv = await res.json();

    currentConversationId = conv.id;
    resetChatWindow();
    conv.messages.forEach((m) => appendChatMessage(m.role, m.content));

    document.querySelector('.tab-btn[data-tab="chat"]').click();
  } catch (err) {
    console.error(err);
    alert("대화를 불러오지 못했어요.");
  }
}

async function deleteConversation(id) {
  if (!confirm("이 대화를 삭제할까요?")) return;
  try {
    const res = await fetch(`${API_BASE_URL}/api/conversations/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("delete failed");
    if (currentConversationId === id) {
      currentConversationId = null;
      resetChatWindow();
    }
    loadHistoryList();
  } catch (err) {
    console.error(err);
    alert("삭제에 실패했어요.");
  }
}

function formatDate(isoString) {
  if (!isoString) return "";
  const d = new Date(isoString);
  return d.toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}
