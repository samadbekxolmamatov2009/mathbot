const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const loadingEl = document.getElementById("loadingState");
const totalCardEl = document.getElementById("totalCard");
const totalValueEl = document.getElementById("totalValue");

const testSectionEl = document.getElementById("testSection");
const statsRowEl = document.getElementById("statsRow");
const statTotalEl = document.getElementById("statTotal");
const statAvgEl = document.getElementById("statAvg");
const statDeltaEl = document.getElementById("statDelta");
const scrollEl = document.getElementById("chartScroll");
const barsEl = document.getElementById("bars");
const chartHintEl = document.getElementById("chartHint");
const testEmptyEl = document.getElementById("testEmpty");

const streakSectionEl = document.getElementById("streakSection");
const streakValueEl = document.getElementById("streakValue");

const attendanceSectionEl = document.getElementById("attendanceSection");
const attendanceCountEl = document.getElementById("attendanceCount");
const attendanceValueEl = document.getElementById("attendanceValue");

const emptyEl = document.getElementById("emptyState");

function formatDate(value) {
  if (!value) return "";
  return value.split(" ")[0].split("T")[0];
}

function renderStats(results) {
  const pcts = results.map((r) => (r.total_questions ? (r.score / r.total_questions) * 100 : 0));
  const avg = Math.round(pcts.reduce((a, b) => a + b, 0) / pcts.length);

  statTotalEl.textContent = String(results.length);
  statAvgEl.textContent = `${avg}%`;

  if (pcts.length >= 2) {
    const delta = Math.round(pcts[pcts.length - 1] - pcts[pcts.length - 2]);
    const sign = delta > 0 ? "+" : "";
    statDeltaEl.textContent = `${sign}${delta}%`;
    statDeltaEl.classList.toggle("up", delta > 0);
    statDeltaEl.classList.toggle("down", delta < 0);
  } else {
    statDeltaEl.textContent = "—";
  }

  statsRowEl.hidden = false;
}

function renderChart(results) {
  const frag = document.createDocumentFragment();

  results.forEach((r, i) => {
    const pct = r.total_questions ? Math.max(2, Math.round((r.score / r.total_questions) * 100)) : 0;
    const shortName = r.name.length > 10 ? `${r.name.slice(0, 9)}…` : r.name;
    const isLatest = i === results.length - 1;

    const col = document.createElement("div");
    col.className = "bar-col" + (isLatest ? " latest" : "");
    col.addEventListener("click", () => {
      const msg = `${r.name}\n${r.score} / ${r.total_questions} to'g'ri (${pct}%)\n${formatDate(r.submitted_at)}`;
      if (tg.showAlert) tg.showAlert(msg);
      else alert(msg);
    });

    const valueEl = document.createElement("div");
    valueEl.className = "bar-value";
    valueEl.textContent = `${r.score}/${r.total_questions}`;

    const trackEl = document.createElement("div");
    trackEl.className = "bar-track";
    const barEl = document.createElement("div");
    barEl.className = "bar";
    barEl.style.height = `${pct}%`;
    trackEl.appendChild(barEl);

    const nameEl = document.createElement("div");
    nameEl.className = "bar-name";
    nameEl.textContent = shortName;

    col.appendChild(valueEl);
    col.appendChild(trackEl);
    col.appendChild(nameEl);
    frag.appendChild(col);
  });

  barsEl.appendChild(frag);
  scrollEl.hidden = false;
  chartHintEl.hidden = false;
  scrollEl.scrollLeft = scrollEl.scrollWidth;
}

async function init() {
  try {
    const res = await fetch(`/api/my_results?init_data=${encodeURIComponent(tg.initData)}`);
    const data = await res.json();
    loadingEl.hidden = true;

    if (!res.ok) {
      emptyEl.textContent = "Natijalarni yuklab bo'lmadi.";
      emptyEl.hidden = false;
      return;
    }

    const results = data.results || [];
    const coins = data.coins || { attendance_count: 0, attendance_coins: 0, test_streak_coins: 0, total: 0 };

    if (results.length === 0 && coins.total === 0) {
      emptyEl.hidden = false;
      return;
    }

    totalValueEl.textContent = String(coins.total);
    totalCardEl.hidden = false;

    testSectionEl.hidden = false;
    if (results.length > 0) {
      renderStats(results);
      renderChart(results);
    } else {
      statsRowEl.hidden = true;
      testEmptyEl.hidden = false;
    }

    streakValueEl.textContent = String(coins.test_streak_coins);
    streakSectionEl.hidden = false;

    attendanceCountEl.textContent = `${coins.attendance_count} marta ishtirok`;
    attendanceValueEl.textContent = `${coins.attendance_coins} ball`;
    attendanceSectionEl.hidden = false;
  } catch (e) {
    loadingEl.hidden = true;
    emptyEl.textContent = "Server bilan bog'lanishda xatolik.";
    emptyEl.hidden = false;
  }
}

init();
