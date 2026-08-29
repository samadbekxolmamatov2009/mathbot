const tg = window.Telegram && window.Telegram.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

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

// ---------------- Rejalashtirilgan xabar ----------------

const enabledToggle = document.getElementById("enabledToggle");
const messageText = document.getElementById("messageText");
const hourSelect = document.getElementById("hourSelect");
const minuteSelect = document.getElementById("minuteSelect");
const statusLine = document.getElementById("statusLine");
const fileInput = document.getElementById("fileInput");
const fileNameLabel = document.getElementById("fileNameLabel");
const removeFileBtn = document.getElementById("removeFileBtn");
const saveBtn = document.getElementById("saveBtn");
const formStateEl = document.getElementById("formState");
const successStateEl = document.getElementById("successState");

fillTimeSelects(hourSelect, minuteSelect);
const dayPicker = makeDayPicker(document.getElementById("dayPicker"), updateStatus);

function updateStatus() {
  const time = `${hourSelect.value}:${minuteSelect.value}`;
  if (!enabledToggle.checked) {
    statusLine.textContent = "🔕 O'chirilgan — xabar avtomatik yuborilmaydi.";
    return;
  }
  statusLine.textContent = `🔔 Har ${WEEKDAY_NAMES[dayPicker.value]}, soat ${time} da yuboriladi.`;
}

enabledToggle.addEventListener("change", updateStatus);
hourSelect.addEventListener("change", updateStatus);
minuteSelect.addEventListener("change", updateStatus);

function setFileName(name) {
  if (name) {
    fileNameLabel.textContent = `📎 ${name}`;
    removeFileBtn.style.display = "inline-block";
  } else {
    fileNameLabel.textContent = "Biriktirilmagan";
    removeFileBtn.style.display = "none";
  }
}

async function loadSchedule() {
  try {
    const res = await fetch(`/api/broadcast_schedule?init_data=${encodeURIComponent(tg ? tg.initData : "")}`);
    const data = await res.json();
    if (!res.ok) {
      if (data.error === "not_admin" && tg) tg.showAlert("Sizda ruxsat yo'q.");
      return;
    }

    if (data.schedule) {
      messageText.value = data.schedule.message;
      dayPicker.select(data.schedule.day_of_week);
      const [h, m] = data.schedule.time_of_day.split(":");
      hourSelect.value = h;
      minuteSelect.value = m;
      enabledToggle.checked = data.schedule.enabled;
      setFileName(data.schedule.file_name);
    } else {
      dayPicker.select(0);
      hourSelect.value = "09";
      minuteSelect.value = "00";
      setFileName(null);
    }
    updateStatus();
  } catch (e) {
    statusLine.textContent = "Server bilan bog'lanishda xatolik.";
  }
}

fileInput.addEventListener("change", async () => {
  const file = fileInput.files[0];
  if (!file) return;
  fileNameLabel.textContent = "⏳ Yuklanmoqda...";
  try {
    const formData = new FormData();
    formData.append("file", file, file.name);
    const res = await fetch(
      `/api/broadcast_schedule/file?init_data=${encodeURIComponent(tg ? tg.initData : "")}`,
      { method: "POST", body: formData }
    );
    const data = await res.json();
    if (!res.ok) {
      if (tg) tg.showAlert("Faylni yuklashda xatolik yuz berdi.");
      setFileName(null);
      return;
    }
    setFileName(data.file_name);
  } catch (e) {
    if (tg) tg.showAlert("Server bilan bog'lanishda xatolik.");
    setFileName(null);
  } finally {
    fileInput.value = "";
  }
});

removeFileBtn.addEventListener("click", async () => {
  try {
    await fetch("/api/broadcast_schedule/file/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ init_data: tg ? tg.initData : "" }),
    });
  } catch (e) {
    // e'tiborsiz
  }
  setFileName(null);
});

async function saveMessageSchedule() {
  const hasFile = removeFileBtn.style.display !== "none";
  if (!messageText.value.trim() && !hasFile) {
    // Bo'sh bo'lsa ham "Rejalashtirilgan xabar" bo'limi ixtiyoriy - saqlashga urinmaymiz.
    return { ok: true, skipped: true };
  }

  const res = await fetch("/api/broadcast_schedule", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      init_data: tg ? tg.initData : "",
      message: messageText.value.trim(),
      day_of_week: dayPicker.value,
      time_of_day: `${hourSelect.value}:${minuteSelect.value}`,
      enabled: enabledToggle.checked,
    }),
  });
  const data = await res.json();
  return { ok: res.ok, data };
}

// ---------------- Saqlash (bitta tugma, ikkala bo'lim uchun) ----------------

async function saveAll() {
  saveBtn.disabled = true;
  saveBtn.textContent = "⏳ Saqlanmoqda...";
  try {
    const reportOk = await saveReportSchedule();
    const msgResult = await saveMessageSchedule();

    if (!reportOk || !msgResult.ok) {
      saveBtn.disabled = false;
      saveBtn.textContent = "💾 Saqlash";
      const msg =
        msgResult.data && msgResult.data.error === "missing_message"
          ? "Xabar matnini kiriting yoki fayl biriktiring."
          : "Xatolik yuz berdi. Qaytadan urinib ko'ring.";
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
loadSchedule();
