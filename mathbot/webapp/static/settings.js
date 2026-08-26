const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const enabledToggle = document.getElementById("enabledToggle");
const messageText = document.getElementById("messageText");
const dayPicker = document.getElementById("dayPicker");
const hourSelect = document.getElementById("hourSelect");
const minuteSelect = document.getElementById("minuteSelect");
const statusLine = document.getElementById("statusLine");
const formStateEl = document.getElementById("formState");
const successStateEl = document.getElementById("successState");
const fileInput = document.getElementById("fileInput");
const fileNameLabel = document.getElementById("fileNameLabel");
const removeFileBtn = document.getElementById("removeFileBtn");
const hourlyReportToggle = document.getElementById("hourlyReportToggle");

const WEEKDAY_NAMES = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"];

let selectedDay = 0;

function pad(n) {
  return String(n).padStart(2, "0");
}

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

function selectDay(day) {
  selectedDay = day;
  [...dayPicker.children].forEach((btn) => {
    btn.classList.toggle("selected", Number(btn.dataset.day) === day);
  });
}

dayPicker.addEventListener("click", (e) => {
  const btn = e.target.closest(".day-btn");
  if (!btn) return;
  selectDay(Number(btn.dataset.day));
  updateStatus();
});

function updateStatus() {
  const time = `${hourSelect.value}:${minuteSelect.value}`;
  if (!enabledToggle.checked) {
    statusLine.textContent = "🔕 O'chirilgan — xabar avtomatik yuborilmaydi.";
    return;
  }
  statusLine.textContent = `🔔 Har ${WEEKDAY_NAMES[selectedDay]}, soat ${time} da yuboriladi.`;
}

function updateButton() {
  const hasFile = removeFileBtn.style.display !== "none";
  const valid = !!messageText.value.trim() || hasFile;
  tg.MainButton.setText("Saqlash");
  tg.MainButton.show();
  if (valid) {
    tg.MainButton.enable();
  } else {
    tg.MainButton.disable();
  }
}

enabledToggle.addEventListener("change", updateStatus);
messageText.addEventListener("input", updateButton);
hourSelect.addEventListener("change", updateStatus);
minuteSelect.addEventListener("change", updateStatus);

async function loadSchedule() {
  try {
    const res = await fetch(`/api/broadcast_schedule?init_data=${encodeURIComponent(tg.initData)}`);
    const data = await res.json();
    if (!res.ok) {
      if (data.error === "not_admin") {
        tg.showAlert("Sizda ruxsat yo'q.");
      }
      return;
    }

    if (data.schedule) {
      messageText.value = data.schedule.message;
      selectDay(data.schedule.day_of_week);
      const [h, m] = data.schedule.time_of_day.split(":");
      hourSelect.value = h;
      minuteSelect.value = m;
      enabledToggle.checked = data.schedule.enabled;
      setFileName(data.schedule.file_name);
    } else {
      selectDay(0);
      hourSelect.value = "09";
      minuteSelect.value = "00";
      setFileName(null);
    }
    hourlyReportToggle.checked = !!data.hourly_report_enabled;
    updateStatus();
    updateButton();
  } catch (e) {
    statusLine.textContent = "Server bilan bog'lanishda xatolik.";
  }
}

function setFileName(name) {
  if (name) {
    fileNameLabel.textContent = `📎 ${name}`;
    removeFileBtn.style.display = "inline-block";
  } else {
    fileNameLabel.textContent = "Biriktirilmagan";
    removeFileBtn.style.display = "none";
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
      `/api/broadcast_schedule/file?init_data=${encodeURIComponent(tg.initData)}`,
      { method: "POST", body: formData }
    );
    const data = await res.json();
    if (!res.ok) {
      tg.showAlert("Faylni yuklashda xatolik yuz berdi.");
      setFileName(null);
      return;
    }
    setFileName(data.file_name);
  } catch (e) {
    tg.showAlert("Server bilan bog'lanishda xatolik.");
    setFileName(null);
  } finally {
    fileInput.value = "";
  }
  updateButton();
});

removeFileBtn.addEventListener("click", async () => {
  try {
    await fetch("/api/broadcast_schedule/file/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ init_data: tg.initData }),
    });
  } catch (e) {
    // e'tiborsiz - baribir UI'ni tozalaymiz, keyingi ochilishda haqiqiy holat ko'rinadi
  }
  setFileName(null);
  updateButton();
});

hourlyReportToggle.addEventListener("change", async () => {
  try {
    await fetch("/api/broadcast_schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        init_data: tg.initData,
        hourly_report_enabled: hourlyReportToggle.checked,
      }),
    });
  } catch (e) {
    tg.showAlert("Server bilan bog'lanishda xatolik.");
  }
});

async function saveSchedule() {
  tg.MainButton.showProgress();
  try {
    const res = await fetch("/api/broadcast_schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        init_data: tg.initData,
        message: messageText.value.trim(),
        day_of_week: selectedDay,
        time_of_day: `${hourSelect.value}:${minuteSelect.value}`,
        enabled: enabledToggle.checked,
      }),
    });
    const data = await res.json();

    if (!res.ok) {
      tg.MainButton.hideProgress();
      if (data.error === "not_admin") {
        tg.showAlert("Sizda ruxsat yo'q.");
      } else if (data.error === "missing_message") {
        tg.showAlert("Xabar matnini kiriting.");
      } else {
        tg.showAlert("Xatolik yuz berdi. Qaytadan urinib ko'ring.");
      }
      return;
    }

    formStateEl.style.display = "none";
    successStateEl.style.display = "block";
    tg.MainButton.hide();

    const day = WEEKDAY_NAMES[selectedDay];
    const time = `${hourSelect.value}:${minuteSelect.value}`;
    const enabled = enabledToggle.checked;
    setTimeout(() => {
      tg.sendData(JSON.stringify({ type: "schedule_saved", day, time, enabled }));
    }, 800);
  } catch (e) {
    tg.MainButton.hideProgress();
    tg.showAlert("Server bilan bog'lanishda xatolik.");
  }
}

tg.MainButton.setParams({ color: "#3d6ea5" });
tg.MainButton.onClick(saveSchedule);

loadSchedule();
