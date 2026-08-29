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
let questions = [];

const els = {
  loadingState: document.getElementById("loadingState"),
  loadingText: document.getElementById("loadingText"),
  infoState: document.getElementById("infoState"),
  infoIcon: document.getElementById("infoIcon"),
  infoText: document.getElementById("infoText"),
  testNameLabel: document.getElementById("testNameLabel"),
  lateWarning: document.getElementById("lateWarning"),
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
  closeAppBtn: document.getElementById("closeAppBtn"),
};

let loadingHintTimer = null;

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

function showLateWarning(endTime) {
  const timeLabel = endTime ? formatDateTime(endTime) : "";
  els.lateWarning.textContent = timeLabel
    ? `⏰ Test vaqti ${timeLabel} da tugagan — javob berishingiz mumkin, ammo natija 75% hisoblanadi.`
    : "⏰ Test vaqti tugagan — javob berishingiz mumkin, ammo natija 75% hisoblanadi.";
  els.lateWarning.hidden = false;
  setTimeout(() => {
    els.lateWarning.hidden = true;
  }, 2000);
}

function showInfo(icon, text) {
  els.loadingState.hidden = true;
  els.infoIcon.textContent = icon;
  els.infoText.textContent = text;
  els.infoState.hidden = false;
}

function haptic(style) {
  if (isTelegram && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
}

function updateProgress() {
  const count = Object.keys(answers).length;
  const pct = questions.length ? Math.round((count / questions.length) * 100) : 0;
  els.progressFill.style.width = `${pct}%`;
  els.progressLabel.textContent = `${count} / ${questions.length} javob berildi`;
}

function renderQuestions() {
  const frag = document.createDocumentFragment();

  questions.forEach((q) => {
    const card = document.createElement("div");
    card.className = "question-card";

    const numEl = document.createElement("div");
    numEl.className = "q-number";
    numEl.textContent = q.number;
    card.appendChild(numEl);

    const optsEl = document.createElement("div");
    optsEl.className = "options";

    q.options.forEach((letter) => {
      const btn = document.createElement("button");
      btn.className = "option-btn";
      btn.type = "button";
      btn.textContent = letter;
      btn.addEventListener("click", () => {
        answers[q.number] = letter;
        card.classList.add("answered");
        [...optsEl.children].forEach((b) => b.classList.toggle("selected", b === btn));
        haptic();
        updateProgress();
      });
      optsEl.appendChild(btn);
    });

    card.appendChild(optsEl);
    frag.appendChild(card);
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

function renderResult(score, total, details, late) {
  els.progressTrack.hidden = true;
  els.progressLabel.hidden = true;
  els.questionList.hidden = true;
  els.submitBar.hidden = true;
  els.lateWarning.hidden = true;
  if (isTelegram) tg.MainButton.hide();

  const pct = total ? Math.round((score / total) * 100) : 0;
  els.scoreRing.style.setProperty("--pct", pct);
  els.scoreValue.textContent = score;
  els.scoreTotal.textContent = `/ ${total}`;

  els.resultList.innerHTML = "";

  if (late) {
    const note = document.createElement("div");
    note.className = "late-warning";
    note.textContent = "⏰ Kech topshirilgani uchun ball 75% ga qisqartirildi.";
    els.resultList.appendChild(note);
  }
  details.forEach((d) => {
    const row = document.createElement("div");
    row.className = `result-row ${d.is_correct ? "correct" : "wrong"}`;

    const left = document.createElement("span");
    left.textContent = `${d.question}-savol`;

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

  if (isTelegram) {
    els.closeAppBtn.hidden = false;
    els.closeAppBtn.onclick = () => tg.close();
  }
}

async function submitTest() {
  if (isTelegram) tg.MainButton.showProgress();
  els.submitBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/test/${encodeURIComponent(code)}/submit`, {
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
          : "Xatolik yuz berdi. Qaytadan urinib ko'ring.";
      if (isTelegram) tg.showAlert(message);
      else alert(message);
      return;
    }

    renderResult(result.score, result.total, result.details, result.late);
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
      `${API_BASE}/api/test/${encodeURIComponent(code)}/status?init_data=${encodeURIComponent(tg ? tg.initData : "")}`
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
      showLateWarning(data.end_time);
    }

    questions = data.questions || [];
    renderQuestions();
  } catch (e) {
    clearLoadingHint();
    showInfo("⚠️", "Server bilan bog'lanishda xatolik.");
  }
}

init();
