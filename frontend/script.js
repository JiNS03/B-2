// ---------------------------------------------------------
// 상태
// ---------------------------------------------------------
let currentConversationId = null;

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
// 요약 정보 (상단 티켓)
// ---------------------------------------------------------
async function loadSummary() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/data/summary`);
    if (!res.ok) throw new Error("summary fetch failed");
    const summary = await res.json();

    document.getElementById("summary-period").textContent = summary.period;
    document.getElementById("summary-avg").textContent = `${summary.metrics.average_minutes_per_day}분`;
    document.getElementById("summary-shortform").textContent = `${Math.round(summary.metrics.shortform_ratio * 100)}%`;
    document.getElementById("summary-trend").textContent = summary.trend;
  } catch (err) {
    console.error(err);
    document.getElementById("summary-period").textContent = "불러오기 실패";
  }
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

    if (records.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty-row">아직 기록이 없어요. 위 폼으로 추가해보세요.</td></tr>`;
      return;
    }

    // 최근 날짜가 위로 오도록 정렬해서 표시
    const sorted = [...records].sort((a, b) => (a.date < b.date ? 1 : -1));

    tbody.innerHTML = sorted
      .map(
        (r) => `
      <tr>
        <td>${r.date}</td>
        <td>${r.value}분</td>
        <td>${r.platform}</td>
        <td>${r.content_type === "short_form" ? "숏폼" : "롱폼"}</td>
        <td>${escapeHtml(r.memo || "")}</td>
        <td><button class="btn-delete" data-id="${r.id}">삭제</button></td>
      </tr>`
      )
      .join("");

    tbody.querySelectorAll(".btn-delete").forEach((btn) => {
      btn.addEventListener("click", () => deleteRecord(btn.dataset.id));
    });
  } catch (err) {
    console.error(err);
    tbody.innerHTML = `<tr><td colspan="6" class="empty-row">목록을 불러오지 못했어요.</td></tr>`;
  }
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
