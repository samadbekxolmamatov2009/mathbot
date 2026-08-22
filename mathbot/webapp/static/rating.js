const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const myId = tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : null;

const loadingEl = document.getElementById("loadingState");
const listEl = document.getElementById("ratingList");
const emptyEl = document.getElementById("emptyState");

function medalFor(rank) {
  if (rank === 1) return "🥇";
  if (rank === 2) return "🥈";
  if (rank === 3) return "🥉";
  return String(rank);
}

function renderLeaderboard(rows) {
  const frag = document.createDocumentFragment();

  rows.forEach((row) => {
    const el = document.createElement("div");
    el.className = "rating-row" + (row.telegram_id === myId ? " me" : "");

    const rankEl = document.createElement("div");
    rankEl.className = "rating-rank";
    rankEl.textContent = medalFor(row.rank);

    const nameEl = document.createElement("div");
    nameEl.className = "rating-name";
    nameEl.textContent = row.full_name;

    const coinsEl = document.createElement("div");
    coinsEl.className = "rating-coins";
    coinsEl.textContent = `🪙 ${row.coins}`;

    el.appendChild(rankEl);
    el.appendChild(nameEl);
    el.appendChild(coinsEl);
    frag.appendChild(el);
  });

  listEl.appendChild(frag);
  listEl.hidden = false;
}

async function init() {
  try {
    const res = await fetch(`/api/rating?init_data=${encodeURIComponent(tg.initData)}`);
    const data = await res.json();
    loadingEl.hidden = true;

    if (!res.ok) {
      emptyEl.textContent = "Reytingni yuklab bo'lmadi.";
      emptyEl.hidden = false;
      return;
    }

    if (!data.leaderboard || data.leaderboard.length === 0) {
      emptyEl.hidden = false;
      return;
    }

    renderLeaderboard(data.leaderboard);
  } catch (e) {
    loadingEl.hidden = true;
    emptyEl.textContent = "Server bilan bog'lanishda xatolik.";
    emptyEl.hidden = false;
  }
}

init();
