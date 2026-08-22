const tg = window.Telegram && window.Telegram.WebApp;
const isTelegram = !!(tg && tg.platform && tg.platform !== "unknown");

if (tg) {
  tg.ready();
  tg.expand();
  applyThemeColors();
  tg.onEvent("themeChanged", applyThemeColors);
  if (isTelegram) tg.enableClosingConfirmation();
}

function applyThemeColors() {
  const bg = (tg.themeParams && tg.themeParams.bg_color) || "#eef3f9";
  if (tg.setHeaderColor) tg.setHeaderColor(bg);
  if (tg.setBackgroundColor) tg.setBackgroundColor(bg);
}

const params = new URLSearchParams(window.location.search);
const code = params.get("code");

const answers = {};
let fields = [];

const els = {
  loadingState: document.getElementById("loadingState"),
  loadingText: document.getElementById("loadingText"),
  infoState: document.getElementById("infoState"),
  infoIcon: document.getElementById("infoIcon"),
  infoText: document.getElementById("infoText"),
  testNameLabel: document.getElementById("testNameLabel"),
  questionList: document.getElementById("questionList"),
  progressTrack: document.getElementById("progressTrack"),
  progressFill: document.getElementById("progressFill"),
  progressLabel: document.getElementById("progressLabel"),
  submitBar: document.getElementById("submitBar"),
  submitBtn: document.getElementById("submitBtn"),
  resultState: document.getElementById("resultState"),
  scoreRing: document.getElementById("scoreRing"),
  scoreValue: document.getElementById("scoreValue"),
  scoreTotal: document.getElementById("scoreTotal"),
  resultList: document.getElementById("resultList"),
};

let loadingHintTimer = null;
const mathKeyboard = createMathKeyboard(document.body);

function startLoadingHint() {
  loadingHintTimer = setTimeout(() => {
    els.loadingText.textContent = "Internet aloqasi sekin, biroz kuting...";
  }, 4000);
}

function clearLoadingHint() {
  if (loadingHintTimer) {
    clearTimeout(loadingHintTimer);
    loadingHintTimer = null;
  }
}

function showTestName(name) {
  if (name) {
    els.testNameLabel.textContent = name;
    els.testNameLabel.hidden = false;
  }
}

function showInfo(icon, text) {
  els.loadingState.hidden = true;
  els.infoIcon.textContent = icon;
  els.infoText.textContent = text;
  els.infoState.hidden = false;
}

function haptic() {
  if (isTelegram && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
}

function updateProgress() {
  const count = Object.values(answers).filter((v) => v && v.trim()).length;
  const pct = fields.length ? Math.round((count / fields.length) * 100) : 0;
  els.progressFill.style.width = `${pct}%`;
  els.progressLabel.textContent = `${count} / ${fields.length} javob berildi`;
}

function renderQuestions() {
  const frag = document.createDocumentFragment();

  fields.forEach((key) => {
    const row = document.createElement("div");
    row.className = "aplus-row";

    const badge = document.createElement("div");
    badge.className = "aplus-badge";
    badge.textContent = key;
    row.appendChild(badge);

    const input = document.createElement("input");
    input.type = "text";
    input.className = "aplus-input";
    input.placeholder = "Javobingiz";
    input.addEventListener("input", () => {
      answers[key] = input.value;
      row.classList.toggle("answered", !!input.value.trim());
      haptic();
      updateProgress();
    });
    row.appendChild(input);

    const kbdBtn = document.createElement("button");
    kbdBtn.type = "button";
    kbdBtn.className = "aplus-kbd-btn";
    kbdBtn.textContent = "⌨";
    kbdBtn.addEventListener("click", () => mathKeyboard.toggle(input, kbdBtn));
    row.appendChild(kbdBtn);

    frag.appendChild(row);
  });

  els.questionList.appendChild(frag);
  els.loadingState.hidden = true;
  els.questionList.hidden = false;
  els.progressTrack.hidden = false;
  els.progressLabel.hidden = false;
  updateProgress();

  if (isTelegram) {
    tg.MainButton.setParams({
      text: "Yakunlash",
      color: tg.themeParams.button_color || "#3d6ea5",
      text_color: tg.themeParams.button_text_color || "#ffffff",
    });
    tg.MainButton.show();
    tg.MainButton.onClick(submitTest);
  } else {
    els.submitBar.hidden = false;
    els.submitBtn.addEventListener("click", submitTest);
  }
}

function formatDateTime(value) {
  if (!value) return "";
  const [datePart, timePart] = value.split("T");
  const [year, month, day] = datePart.split("-");
  return `${day}.${month}.${year} ${timePart}`;
}

function renderResult(score, total, details) {
  mathKeyboard.hide();
  els.progressTrack.hidden = true;
  els.progressLabel.hidden = true;
  els.questionList.hidden = true;
  els.submitBar.hidden = true;
  if (isTelegram) tg.MainButton.hide();

  const pct = total ? Math.round((score / total) * 100) : 0;
  els.scoreRing.style.setProperty("--pct", pct);
  els.scoreValue.textContent = score;
  els.scoreTotal.textContent = `/ ${total}`;

  els.resultList.innerHTML = "";
  details.forEach((d) => {
    const row = document.createElement("div");
    row.className = `result-row ${d.is_correct ? "correct" : "wrong"}`;

    const left = document.createElement("span");
    left.textContent = `${d.key}-javob`;

    const right = document.createElement("span");
    right.className = `result-status ${d.is_correct ? "correct" : "wrong"}`;
    right.textContent = d.is_correct
      ? `✔ To'g'ri (${d.your_answer ?? "—"})`
      : `✘ Noto'g'ri (siz: ${d.your_answer ?? "—"}, to'g'ri: ${d.correct_answer ?? "—"})`;

    row.appendChild(left);
    row.appendChild(right);
    els.resultList.appendChild(row);
  });

  els.resultState.hidden = false;
}

async function submitTest() {
  if (isTelegram) tg.MainButton.showProgress();
  els.submitBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/aplus/test/${encodeURIComponent(code)}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ init_data: tg ? tg.initData : "", answers }),
    });
    const result = await res.json();

    if (!res.ok) {
      if (isTelegram) tg.MainButton.hideProgress();
      els.submitBtn.disabled = false;
      const message =
        result.error === "not_started"
          ? "Test hali boshlanmagan."
          : result.error === "ended"
          ? "Test vaqti tugagan."
          : "Xatolik yuz berdi. Qaytadan urinib ko'ring.";
      if (isTelegram) tg.showAlert(message);
      else alert(message);
      return;
    }

    renderResult(result.score, result.total, result.details);
  } catch (e) {
    if (isTelegram) tg.MainButton.hideProgress();
    els.submitBtn.disabled = false;
    const message = "Server bilan bog'lanishda xatolik.";
    if (isTelegram) tg.showAlert(message);
    else alert(message);
  }
}

async function init() {
  if (typeof API_BASE !== "string" || API_BASE.includes("api.mathbot.uz")) {
    showInfo("⚙️", "Backend manzili sozlanmagan. netlify-site/config.js ichidagi API_BASE ni to'g'irlang.");
    return;
  }

  if (!code) {
    showInfo("❓", "Test kodi topilmadi.");
    return;
  }

  startLoadingHint();
  try {
    const res = await fetch(
      `${API_BASE}/api/aplus/test/${encodeURIComponent(code)}/status?init_data=${encodeURIComponent(tg ? tg.initData : "")}`
    );
    const data = await res.json();
    clearLoadingHint();

    if (!res.ok || !data.exists) {
      showInfo("❌", "Bunday test topilmadi.");
      return;
    }

    showTestName(data.name);

    if (data.already_submitted) {
      els.loadingState.hidden = true;
      renderResult(
        data.already_submitted.score,
        data.already_submitted.total,
        data.already_submitted.details
      );
      return;
    }

    if (data.window_status === "not_started") {
      showInfo("⏳", `Test hali boshlanmagan. Boshlanish vaqti: ${formatDateTime(data.start_time)}`);
      return;
    }

    if (data.window_status === "ended") {
      showInfo("🔒", "Test vaqti tugagan.");
      return;
    }

    fields = data.fields || [];
    renderQuestions();
  } catch (e) {
    clearLoadingHint();
    showInfo("⚠️", "Server bilan bog'lanishda xatolik.");
  }
}

init();
