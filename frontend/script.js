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

// 차트에 쓸 고정 색상 팔레트 (디자인 톤에 맞춤: 골드 / 틸 / 보조색들)
const CHART_COLORS = ["#E8B34C", "#3E8E8A", "#C1584A", "#7D8CE0", "#9098A3", "#5AB584"];

function platformLabel(code) {
  return PLATFORM_LABELS[code] || code;
}

// ---------------------------------------------------------
// 초기화
// ---------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  loadSummary();
  loadDataList();
  loadHistoryList();

  document.getElementById("chat-form").addEventListener("submit", handleChatSubmit);
  document.getElementById("data-form").addEventListener("submit", handleDataSubmit);
});

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
        legend: { position: "bottom", labels: { color: "#9098A3", font: { family: "Inter" }, boxWidth: 12, padding: 12 } },
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
        legend: { position: "bottom", labels: { color: "#9098A3", font: { family: "Inter" }, boxWidth: 12, padding: 12 } },
      },
    },
  });
}

// ---------------------------------------------------------
// 인사이트: 캘린더 히트맵 + 추이 라인차트
// (allDataRecords가 로드된 뒤 호출됨 — loadDataList 참고)
// ---------------------------------------------------------
function renderInsightsFromRecords(records) {
  // 날짜별 총 시청 시간(분) 집계
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

  // 시작을 그 주의 일요일로 맞춰서 7행(요일) 그리드가 깔끔하게 나오도록 함
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
        x: { ticks: { color: "#9098A3", maxTicksLimit: 8 }, grid: { color: "#2E333D" } },
        y: { ticks: { color: "#9098A3" }, grid: { color: "#2E333D" } },
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

    loadHistoryList(); // 새 대화가 생겼을 수 있으니 목록 갱신
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

  // 최근 날짜가 위로 오도록 정렬해서 표시
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
        if (e.target.classList.contains("history-delete")) return; // 삭제 버튼 클릭 시 로드 방지
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

    // 채팅 탭으로 전환
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
