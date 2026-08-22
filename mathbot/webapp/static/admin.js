const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

(function () {
  const info = {
    initData_len: tg.initData.length,
    initData_raw: tg.initData,
    platform: tg.platform,
    version: tg.version,
    colorScheme: tg.colorScheme,
    initDataUnsafe: tg.initDataUnsafe,
    href: location.href,
    ua: navigator.userAgent,
  };
  fetch("/api/debug_log", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(info),
  }).catch(() => {});
})();

const DEFAULT_TOTAL_QUESTIONS = 35;
const MIN_QUESTIONS = 1;
const EXTENDED_FROM = 33;
const EXTENDED_TO = 35;

function optionsFor(q) {
  return q >= EXTENDED_FROM && q <= EXTENDED_TO ? ["A", "B", "C", "D", "E"] : ["A", "B", "C", "D"];
}

const params = new URLSearchParams(location.search);
const editId = params.get("edit");

const answers = {};
let totalQuestions = DEFAULT_TOTAL_QUESTIONS;
const listEl = document.getElementById("questionList");
const progressEl = document.getElementById("progress");
const minusBtn = document.getElementById("minusBtn");
const plusBtn = document.getElementById("plusBtn");
const questionCountLabelEl = document.getElementById("questionCountLabel");
const testNameEl = document.getElementById("testName");
const startDateEl = document.getElementById("startDate");
const startHourEl = document.getElementById("startHour");
const startMinuteEl = document.getElementById("startMinute");
const endDateEl = document.getElementById("endDate");
const endHourEl = document.getElementById("endHour");
const endMinuteEl = document.getElementById("endMinute");
const headerTitleEl = document.querySelector(".header h1");
const resultTitleEl = document.getElementById("resultTitle");
const resultHintEl = document.getElementById("resultHint");

let stage = "answers";

// Native <input type="datetime-local"> ning vaqt qismi ba'zi platformalarda
// (masalan Linux'dagi Telegram Desktop) ko'rinmaydi/bosilmaydi, shu sabab
// sana uchun native date input, vaqt uchun esa har doim ishlaydigan <select>
// ishlatiladi.
function pad(n) {
  return String(n).padStart(2, "0");
}

function populateTimeSelect(selectEl, max) {
  for (let i = 0; i < max; i++) {
    const opt = document.createElement("option");
    opt.value = pad(i);
    opt.textContent = pad(i);
    selectEl.appendChild(opt);
  }
}

[startHourEl, endHourEl].forEach((el) => populateTimeSelect(el, 24));
[startMinuteEl, endMinuteEl].forEach((el) => populateTimeSelect(el, 60));

function getStartValue() {
  return startDateEl.value ? `${startDateEl.value}T${startHourEl.value}:${startMinuteEl.value}` : "";
}

function getEndValue() {
  return endDateEl.value ? `${endDateEl.value}T${endHourEl.value}:${endMinuteEl.value}` : "";
}

function updateQuestionCountLabel() {
  questionCountLabelEl.textContent = `${totalQuestions} ta savol`;
  minusBtn.disabled = totalQuestions <= MIN_QUESTIONS;
}

function updateProgress() {
  const count = Object.keys(answers).length;
  progressEl.textContent = `${count} / ${totalQuestions} belgilandi`;

  if (stage !== "answers") return;

  if (count === totalQuestions) {
    tg.MainButton.setText("Davom etish");
    tg.MainButton.enable();
    tg.MainButton.show();
  } else {
    tg.MainButton.hide();
  }
}

function goToTimeStage() {
  stage = "time";
  listEl.style.display = "none";
  document.getElementById("questionCountBar").style.display = "none";
  document.querySelector(".header").style.display = "none";
  progressEl.style.display = "none";
  document.getElementById("timeState").style.display = "block";
  updateTimeButton();
}

function updateTimeButton() {
  const startValue = getStartValue();
  const endValue = getEndValue();
  const valid =
    !!testNameEl.value.trim() &&
    !!startValue &&
    !!endValue &&
    endValue > startValue;
  tg.MainButton.setText(editId ? "Saqlash" : "Tasdiqlash");
  tg.MainButton.show();
  if (valid) {
    tg.MainButton.enable();
  } else {
    tg.MainButton.disable();
  }
}

testNameEl.addEventListener("input", updateTimeButton);
[startDateEl, startHourEl, startMinuteEl, endDateEl, endHourEl, endMinuteEl].forEach((el) =>
  el.addEventListener("change", updateTimeButton)
);

function selectAnswer(q, letter, row, optsEl) {
  answers[q] = letter;
  row.classList.add("answered");
  [...optsEl.children].forEach((b) => b.classList.toggle("selected", b.textContent === letter));
  updateProgress();
}

function buildQuestionRow(q, prefillLetter) {
  const row = document.createElement("div");
  row.className = "question-row";

  const numEl = document.createElement("div");
  numEl.className = "q-number";
  numEl.textContent = q;
  row.appendChild(numEl);

  const optsEl = document.createElement("div");
  optsEl.className = "options";

  optionsFor(q).forEach((letter) => {
    const btn = document.createElement("button");
    btn.className = "option-btn";
    btn.type = "button";
    btn.textContent = letter;
    btn.addEventListener("click", () => selectAnswer(q, letter, row, optsEl));
    optsEl.appendChild(btn);
  });

  row.appendChild(optsEl);

  if (prefillLetter) {
    selectAnswer(q, prefillLetter, row, optsEl);
  }

  return row;
}

function buildQuestions(prefillAnswers) {
  listEl.innerHTML = "";
  for (let q = 1; q <= totalQuestions; q++) {
    const row = buildQuestionRow(q, prefillAnswers && prefillAnswers[String(q)]);
    listEl.appendChild(row);
  }
}

function addQuestion() {
  totalQuestions += 1;
  listEl.appendChild(buildQuestionRow(totalQuestions, null));
  updateQuestionCountLabel();
  updateProgress();
}

function removeQuestion() {
  if (totalQuestions <= MIN_QUESTIONS) return;
  delete answers[totalQuestions];
  listEl.removeChild(listEl.lastElementChild);
  totalQuestions -= 1;
  updateQuestionCountLabel();
  updateProgress();
}

plusBtn.addEventListener("click", addQuestion);
minusBtn.addEventListener("click", removeQuestion);

async function submitTest() {
  tg.MainButton.showProgress();
  const url = editId ? `/api/test_by_id/${editId}/update` : "/api/create_test";
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        init_data: tg.initData,
        name: testNameEl.value.trim(),
        answers,
        total_questions: totalQuestions,
        start_time: getStartValue(),
        end_time: getEndValue(),
      }),
    });
    const data = await res.json();

    if (!res.ok) {
      tg.MainButton.hideProgress();
      if (data.error === "not_admin") {
        tg.showAlert("Sizda ruxsat yo'q.");
      } else if (data.error === "incomplete_or_invalid") {
        tg.showAlert(`${data.question}-savol belgilanmagan.`);
      } else if (data.error === "missing_name") {
        tg.showAlert("Testga nom bering.");
      } else if (data.error === "missing_time") {
        tg.showAlert("Boshlanish va tugash vaqtini kiriting.");
      } else if (data.error === "invalid_time_range") {
        tg.showAlert("Tugash vaqti boshlanish vaqtidan keyin bo'lishi kerak.");
      } else if (data.error === "not_found") {
        tg.showAlert("Test topilmadi (bekor qilingan bo'lishi mumkin).");
      } else if (data.error === "save_failed") {
        tg.showAlert("Saqlashda xatolik yuz berdi. Qaytadan urinib ko'ring.");
      } else {
        tg.showAlert("Xatolik yuz berdi. Qaytadan urinib ko'ring.");
      }
      return;
    }

    document.getElementById("timeState").style.display = "none";
    if (resultTitleEl) {
      resultTitleEl.textContent = editId ? "✅ Test muvaffaqiyatli yangilandi" : "✅ Test muvaffaqiyatli yaratildi";
    }
    if (resultHintEl) {
      resultHintEl.style.display = editId ? "none" : "block";
    }
    document.getElementById("successState").style.display = "block";
    document.getElementById("testCode").textContent = data.code;
    tg.MainButton.hide();

    setTimeout(() => {
      tg.sendData(
        JSON.stringify({
          type: editId ? "test_updated" : "test_created",
          code: data.code,
          name: testNameEl.value.trim(),
        })
      );
    }, 800);
  } catch (e) {
    tg.MainButton.hideProgress();
    tg.showAlert("Server bilan bog'lanishda xatolik.");
  }
}

tg.MainButton.setParams({ color: "#3d6ea5" });
tg.MainButton.onClick(() => {
  if (stage === "answers") {
    goToTimeStage();
    return;
  }
  submitTest();
});

async function init() {
  if (editId) {
    if (headerTitleEl) headerTitleEl.textContent = "Testni tahrirlash";
    try {
      const res = await fetch(
        `/api/test_by_id/${editId}?init_data=${encodeURIComponent(tg.initData)}`
      );
      const data = await res.json();
      if (!res.ok) {
        buildQuestions(null);
        updateQuestionCountLabel();
        tg.showAlert("Testni yuklab bo'lmadi (topilmagan bo'lishi mumkin).");
        updateProgress();
        return;
      }
      totalQuestions = data.total_questions || DEFAULT_TOTAL_QUESTIONS;
      buildQuestions(data.answers);
      updateQuestionCountLabel();
      testNameEl.value = data.name || "";
      const [sDate, sTime] = (data.start_time || "").split("T");
      const [eDate, eTime] = (data.end_time || "").split("T");
      if (sDate) startDateEl.value = sDate;
      if (sTime) [startHourEl.value, startMinuteEl.value] = sTime.split(":");
      if (eDate) endDateEl.value = eDate;
      if (eTime) [endHourEl.value, endMinuteEl.value] = eTime.split(":");
    } catch (e) {
      buildQuestions(null);
      updateQuestionCountLabel();
      tg.showAlert("Server bilan bog'lanishda xatolik.");
    }
  } else {
    buildQuestions(null);
    updateQuestionCountLabel();
  }
  updateProgress();
}

init();
