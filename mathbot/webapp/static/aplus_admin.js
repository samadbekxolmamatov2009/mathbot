const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const params = new URLSearchParams(location.search);
const editId = params.get("edit");

const answers = {};
let questionCount = 1;
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
const showWrongToggleEl = document.getElementById("showWrongToggle");
const headerTitleEl = document.querySelector(".header h1");
const resultTitleEl = document.getElementById("resultTitle");
const resultHintEl = document.getElementById("resultHint");

let stage = "answers";
const mathKeyboard = createMathKeyboard(document.body);

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

function fieldKeysFor(count) {
  const keys = [];
  for (let n = 1; n <= count; n++) {
    keys.push(`${n}a`, `${n}b`);
  }
  return keys;
}

function updateProgress() {
  const total = questionCount * 2;
  const count = Object.values(answers).filter((v) => v && v.trim()).length;
  progressEl.textContent = `${count} / ${total} belgilandi`;

  if (stage !== "answers") return;

  if (count === total) {
    tg.MainButton.setText("Davom etish");
    tg.MainButton.enable();
    tg.MainButton.show();
  } else {
    tg.MainButton.hide();
  }
}

function updateQuestionCountLabel() {
  questionCountLabelEl.textContent = `${questionCount} ta savol`;
  minusBtn.disabled = questionCount <= 1;
}

function buildFieldRow(key, prefillValue) {
  const row = document.createElement("div");
  row.className = "aplus-row";
  row.dataset.key = key;

  const badge = document.createElement("div");
  badge.className = "aplus-badge";
  badge.textContent = key;
  row.appendChild(badge);

  const input = document.createElement("input");
  input.type = "text";
  input.readOnly = true;
  input.inputMode = "none";
  input.className = "aplus-input";
  input.placeholder = "Javob";
  input.value = prefillValue || "";
  input.addEventListener("input", () => {
    answers[key] = input.value;
    row.classList.toggle("answered", !!input.value.trim());
    updateProgress();
  });
  row.appendChild(input);

  const kbdBtn = document.createElement("button");
  kbdBtn.type = "button";
  kbdBtn.className = "aplus-kbd-btn";
  kbdBtn.textContent = "⌨";
  kbdBtn.addEventListener("click", () => mathKeyboard.toggle(input, kbdBtn));
  row.appendChild(kbdBtn);

  input.addEventListener("focus", () => mathKeyboard.show(input, kbdBtn));

  if (prefillValue) {
    answers[key] = prefillValue;
    row.classList.add("answered");
  }

  return row;
}

function buildQuestions(prefillAnswers) {
  listEl.innerHTML = "";
  fieldKeysFor(questionCount).forEach((key) => {
    listEl.appendChild(buildFieldRow(key, prefillAnswers && prefillAnswers[key]));
  });
}

function addQuestion() {
  questionCount += 1;
  listEl.appendChild(buildFieldRow(`${questionCount}a`, null));
  listEl.appendChild(buildFieldRow(`${questionCount}b`, null));
  updateQuestionCountLabel();
  updateProgress();
}

function removeQuestion() {
  if (questionCount <= 1) return;
  delete answers[`${questionCount}a`];
  delete answers[`${questionCount}b`];
  listEl.removeChild(listEl.lastElementChild);
  listEl.removeChild(listEl.lastElementChild);
  questionCount -= 1;
  updateQuestionCountLabel();
  updateProgress();
}

plusBtn.addEventListener("click", addQuestion);
minusBtn.addEventListener("click", removeQuestion);

function goToTimeStage() {
  stage = "time";
  mathKeyboard.hide();
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

async function submitTest() {
  tg.MainButton.showProgress();
  const url = editId ? `/api/aplus/test_by_id/${editId}/update` : "/api/aplus/create_test";
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        init_data: tg.initData,
        name: testNameEl.value.trim(),
        answers,
        question_count: questionCount,
        start_time: getStartValue(),
        end_time: getEndValue(),
        show_wrong_answers: showWrongToggleEl.checked,
      }),
    });
    const data = await res.json();

    if (!res.ok) {
      tg.MainButton.hideProgress();
      if (data.error === "not_admin") {
        tg.showAlert("Sizda ruxsat yo'q.");
      } else if (data.error === "incomplete_answers") {
        tg.showAlert(`${data.field} javobi to'ldirilmagan.`);
      } else if (data.error === "missing_name") {
        tg.showAlert("Testga nom bering.");
      } else if (data.error === "missing_time") {
        tg.showAlert("Boshlanish va tugash vaqtini kiriting.");
      } else if (data.error === "invalid_time_range") {
        tg.showAlert("Tugash vaqti boshlanish vaqtidan keyin bo'lishi kerak.");
      } else if (data.error === "not_found") {
        tg.showAlert("Test topilmadi (bekor qilingan bo'lishi mumkin).");
      } else {
        tg.showAlert("Xatolik yuz berdi. Qaytadan urinib ko'ring.");
      }
      return;
    }

    document.getElementById("timeState").style.display = "none";
    if (resultTitleEl) {
      resultTitleEl.textContent = editId ? "✅ A+ test muvaffaqiyatli yangilandi" : "✅ A+ test muvaffaqiyatli yaratildi";
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
          type: editId ? "aplus_test_updated" : "aplus_test_created",
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
    if (headerTitleEl) headerTitleEl.textContent = "A+ testni tahrirlash";
    try {
      const res = await fetch(
        `/api/aplus/test_by_id/${editId}?init_data=${encodeURIComponent(tg.initData)}`
      );
      const data = await res.json();
      if (!res.ok) {
        buildQuestions(null);
        updateQuestionCountLabel();
        tg.showAlert("Testni yuklab bo'lmadi (topilmagan bo'lishi mumkin).");
        updateProgress();
        return;
      }
      questionCount = data.question_count || 1;
      buildQuestions(data.answers);
      updateQuestionCountLabel();
      testNameEl.value = data.name || "";
      showWrongToggleEl.checked = data.show_wrong_answers !== false;
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
