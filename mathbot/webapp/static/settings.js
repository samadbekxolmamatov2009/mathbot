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

function showMessage(msg) {
  if (tg) tg.showAlert(msg);
  else alert(msg);
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

function makeDayPicker(container) {
  let selected = 0;
  function select(day) {
    selected = day;
    [...container.children].forEach((btn) => {
      btn.classList.toggle("selected", Number(btn.dataset.day) === day);
    });
  }
  container.addEventListener("click", (e) => {
    const btn = e.target.closest(".day-btn");
    if (!btn) return;
    select(Number(btn.dataset.day));
  });
  select(0);
  return {
    select,
    get value() {
      return selected;
    },
  };
}

// ---------------- Haftalik hisobot: mavjud vaqtlar ro'yxati ----------------

const scheduleListEl = document.getElementById("scheduleList");
const scheduleListEmptyEl = document.getElementById("scheduleListEmpty");

function initData() {
  return tg ? tg.initData : "";
}

async function loadSchedules() {
  try {
    const res = await fetch(`/api/report_schedule?init_data=${encodeURIComponent(initData())}`);
    const data = await res.json();
    if (!res.ok) {
      showMessage("Ro'yxatni yuklab bo'lmadi.");
      return;
    }
    renderSchedules(data.schedules || []);
  } catch (e) {
    showMessage("Server bilan bog'lanishda xatolik.");
  }
}

function renderSchedules(schedules) {
  scheduleListEl.innerHTML = "";
  scheduleListEmptyEl.style.display = schedules.length === 0 ? "block" : "none";

  for (const item of schedules) {
    const row = document.createElement("div");
    row.className = "result-row schedule-item" + (item.enabled ? "" : " disabled");

    const timeSpan = document.createElement("span");
    timeSpan.className = "schedule-item-time";
    timeSpan.textContent = `${WEEKDAY_NAMES[item.day_of_week]}, soat ${item.time_of_day}`;
    row.appendChild(timeSpan);

    const actions = document.createElement("div");
    actions.className = "schedule-item-actions";

    const label = document.createElement("label");
    label.className = "switch";
    const toggle = document.createElement("input");
    toggle.type = "checkbox";
    toggle.checked = item.enabled;
    toggle.addEventListener("change", async () => {
      toggle.disabled = true;
      const ok = await updateSchedule(item.id, item.day_of_week, item.time_of_day, toggle.checked);
      toggle.disabled = false;
      if (ok) {
        row.classList.toggle("disabled", !toggle.checked);
      } else {
        toggle.checked = !toggle.checked;
        showMessage("Xatolik yuz berdi. Qaytadan urinib ko'ring.");
      }
    });
    const slider = document.createElement("span");
    slider.className = "switch-slider";
    label.appendChild(toggle);
    label.appendChild(slider);
    actions.appendChild(label);

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "schedule-del-btn";
    delBtn.textContent = "🗑";
    delBtn.addEventListener("click", () => deleteSchedule(item.id, row));
    actions.appendChild(delBtn);

    row.appendChild(actions);
    scheduleListEl.appendChild(row);
  }
}

async function updateSchedule(id, dayOfWeek, timeOfDay, enabled) {
  try {
    const res = await fetch(`/api/report_schedule/${id}/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        init_data: initData(),
        day_of_week: dayOfWeek,
        time_of_day: timeOfDay,
        enabled,
      }),
    });
    return res.ok;
  } catch (e) {
    return false;
  }
}

function confirmDelete(message) {
  return new Promise((resolve) => {
    if (tg && tg.showConfirm) {
      tg.showConfirm(message, (ok) => resolve(ok));
    } else {
      resolve(confirm(message));
    }
  });
}

async function deleteSchedule(id, row) {
  const ok = await confirmDelete("Bu vaqtni o'chirmoqchimisiz?");
  if (!ok) return;
  try {
    const res = await fetch(`/api/report_schedule/${id}/delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ init_data: initData() }),
    });
    if (res.ok) {
      row.remove();
      if (!scheduleListEl.children.length) scheduleListEmptyEl.style.display = "block";
    } else {
      showMessage("O'chirishda xatolik yuz berdi.");
    }
  } catch (e) {
    showMessage("Server bilan bog'lanishda xatolik.");
  }
}

// ---------------- Yangi vaqt qo'shish ----------------

const newDayPickerEl = document.getElementById("newDayPicker");
const newHourSelect = document.getElementById("newHourSelect");
const newMinuteSelect = document.getElementById("newMinuteSelect");
const addBtn = document.getElementById("addBtn");

fillTimeSelects(newHourSelect, newMinuteSelect);
newHourSelect.value = "09";
newMinuteSelect.value = "00";
const newDayPicker = makeDayPicker(newDayPickerEl);

async function addSchedule() {
  addBtn.disabled = true;
  addBtn.textContent = "⏳ Qo'shilmoqda...";
  try {
    const res = await fetch("/api/report_schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        init_data: initData(),
        day_of_week: newDayPicker.value,
        time_of_day: `${newHourSelect.value}:${newMinuteSelect.value}`,
        enabled: true,
      }),
    });
    if (res.ok) {
      await loadSchedules();
    } else {
      showMessage("Xatolik yuz berdi. Qaytadan urinib ko'ring.");
    }
  } catch (e) {
    showMessage("Server bilan bog'lanishda xatolik.");
  } finally {
    addBtn.disabled = false;
    addBtn.textContent = "➕ Qo'shish";
  }
}

addBtn.addEventListener("click", addSchedule);

loadSchedules();
