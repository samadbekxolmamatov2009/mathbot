const tg = window.Telegram && window.Telegram.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

window.onerror = function (message, source, lineno, colno, error) {
  fetch("/api/debug_log", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      page: "settings.js",
      message: String(message),
      source,
      lineno,
      colno,
      stack: error && error.stack,
    }),
  }).catch(() => {});
};

const WEEKDAY_NAMES = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"];

function pad(n) {
  return String(n).padStart(2, "0");
}

function fillTimeSelects(hourSelect, minuteSelect) {
  for (let h = 0; h < 24; h++) {
    const opt = document.createElement("option");
    opt.value = pad(h);
    opt.textContent = pad(h);
    hourSelect.appendChild(opt);
  }
  for (let m = 0; m < 60; m++) {
    const opt = document.createElement("option");
    opt.value = pad(m);
    opt.textContent = pad(m);
    minuteSelect.appendChild(opt);
  }
}

function makeDayPicker(container, onChange) {
  let selected = 0;
  function select(day) {
    selected = day;
    [...container.children].forEach((btn) => {
      btn.classList.toggle("selected", Number(btn.dataset.day) === day);
    });
    onChange();
  }
  container.addEventListener("click", (e) => {
    const btn = e.target.closest(".day-btn");
    if (!btn) return;
    select(Number(btn.dataset.day));
  });
  return {
    select,
    get value() {
      return selected;
    },
  };
}

// ---------------- Haftalik hisobot ----------------

const reportEnabledToggle = document.getElementById("reportEnabledToggle");
const reportDayPickerEl = document.getElementById("reportDayPicker");
const reportHourSelect = document.getElementById("reportHourSelect");
const reportMinuteSelect = document.getElementById("reportMinuteSelect");
const reportStatusLine = document.getElementById("reportStatusLine");

fillTimeSelects(reportHourSelect, reportMinuteSelect);
const reportDayPicker = makeDayPicker(reportDayPickerEl, updateReportStatus);

function updateReportStatus() {
  const time = `${reportHourSelect.value}:${reportMinuteSelect.value}`;
  if (!reportEnabledToggle.checked) {
    reportStatusLine.textContent = "🔕 O'chirilgan — hisobot avtomatik yuborilmaydi.";
    return;
  }
  reportStatusLine.textContent = `🔔 Har ${WEEKDAY_NAMES[reportDayPicker.value]}, soat ${time} da yuboriladi.`;
}

reportEnabledToggle.addEventListener("change", updateReportStatus);
reportHourSelect.addEventListener("change", updateReportStatus);
reportMinuteSelect.addEventListener("change", updateReportStatus);

async function loadReportSchedule() {
  try {
    const res = await fetch(`/api/report_schedule?init_data=${encodeURIComponent(tg ? tg.initData : "")}`);
    const data = await res.json();
    if (!res.ok) return;

    if (data.schedule) {
      reportDayPicker.select(data.schedule.day_of_week);
      const [h, m] = data.schedule.time_of_day.split(":");
      reportHourSelect.value = h;
      reportMinuteSelect.value = m;
      reportEnabledToggle.checked = data.schedule.enabled;
    } else {
      reportDayPicker.select(0);
      reportHourSelect.value = "09";
      reportMinuteSelect.value = "00";
    }
    updateReportStatus();
  } catch (e) {
    reportStatusLine.textContent = "Server bilan bog'lanishda xatolik.";
  }
}

async function saveReportSchedule() {
  const res = await fetch("/api/report_schedule", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      init_data: tg ? tg.initData : "",
      day_of_week: reportDayPicker.value,
      time_of_day: `${reportHourSelect.value}:${reportMinuteSelect.value}`,
      enabled: reportEnabledToggle.checked,
    }),
  });
  return res.ok;
}

// ---------------- Saqlash ----------------

const saveBtn = document.getElementById("saveBtn");
const formStateEl = document.getElementById("formState");
const successStateEl = document.getElementById("successState");

async function saveAll() {
  saveBtn.disabled = true;
  saveBtn.textContent = "⏳ Saqlanmoqda...";
  try {
    const reportOk = await saveReportSchedule();

    if (!reportOk) {
      saveBtn.disabled = false;
      saveBtn.textContent = "💾 Saqlash";
      const msg = "Xatolik yuz berdi. Qaytadan urinib ko'ring.";
      if (tg) tg.showAlert(msg);
      else alert(msg);
      return;
    }

    formStateEl.style.display = "none";
    successStateEl.style.display = "block";
    if (tg) {
      setTimeout(() => tg.close(), 900);
    }
  } catch (e) {
    saveBtn.disabled = false;
    saveBtn.textContent = "💾 Saqlash";
    const msg = "Server bilan bog'lanishda xatolik.";
    if (tg) tg.showAlert(msg);
    else alert(msg);
  }
}

saveBtn.addEventListener("click", saveAll);

loadReportSchedule();
