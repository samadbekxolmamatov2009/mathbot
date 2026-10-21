/* ===== Admin panel (Mini App) ===== */
(function () {
  "use strict";

  var tg = window.Telegram && window.Telegram.WebApp;
  var PAGE = 20;

  // ---------- Telegram: tayyorlash, to'liq ekran, mavzu ----------

  function applyTheme() {
    var dark = tg && tg.colorScheme
      ? tg.colorScheme === "dark"
      : window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    if (tg) {
      var bg = dark ? "#0b1020" : "#f3f5fb";
      try { tg.setHeaderColor(bg); tg.setBackgroundColor(bg); tg.setBottomBarColor && tg.setBottomBarColor(bg); } catch (e) {}
    }
  }

  function supports(version) {
    try { return !!tg && tg.isVersionAtLeast && tg.isVersionAtLeast(version); } catch (e) { return false; }
  }

  var fsBtn = document.getElementById("fullscreenBtn");

  function syncFullscreenBtn() {
    if (!tg || !fsBtn) return;
    fsBtn.hidden = !(supports("8.0") && tg.requestFullscreen);
  }

  function enterFullscreen() {
    try {
      if (supports("8.0") && tg.requestFullscreen && !tg.isFullscreen) tg.requestFullscreen();
    } catch (e) {}
  }

  function toggleFullscreen() {
    if (!tg) return;
    try { tg.isFullscreen ? tg.exitFullscreen() : tg.requestFullscreen(); } catch (e) {}
  }

  if (tg) {
    tg.ready();
    tg.expand();                                   // butun balandlikka yoyadi
    applyTheme();
    try { supports("7.7") && tg.disableVerticalSwipes(); } catch (e) {}   // aylantirganda tasodifan yopilmasin
    // Ilova ochilishi bilan TO'LIQ EKRAN (Telegram 8.0+; barcha qurilmalarda). Eski versiyada expand() yetarli.
    enterFullscreen();
    // Ba'zi mijozlar birinchi chaqiruvni rad etadi - qisqa pauzadan keyin va birinchi tegishda qayta uriniladi.
    setTimeout(enterFullscreen, 400);
    ["pointerdown", "keydown"].forEach(function (ev) {
      window.addEventListener(ev, enterFullscreen, { once: true, passive: true });
    });
    tg.onEvent("fullscreenChanged", syncFullscreenBtn);
    syncFullscreenBtn();
    tg.onEvent("themeChanged", applyTheme);
    tg.onEvent("viewportChanged", function () { /* CSS o'zgaruvchilar avtomatik yangilanadi */ });
  } else {
    applyTheme();
  }
  if (fsBtn) fsBtn.addEventListener("click", toggleFullscreen);

  // ---------- Yordamchilar ----------
  var $ = function (id) { return document.getElementById(id); };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function haptic(kind) {
    try {
      if (!tg || !tg.HapticFeedback) return;
      if (kind === "ok") tg.HapticFeedback.notificationOccurred("success");
      else if (kind === "err") tg.HapticFeedback.notificationOccurred("error");
      else tg.HapticFeedback.selectionChanged();
    } catch (e) {}
  }

  var toastTimer = null;
  function toast(msg) {
    var t = $("toast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; }, 2200);
  }

  function initials(name) {
    var parts = String(name || "").trim().split(/\s+/).filter(Boolean).slice(0, 2);
    if (!parts.length) return "?";
    return parts.map(function (p) { return p.charAt(0); }).join("").toUpperCase();
  }

  // Bazadagi vaqt UTC; Toshkent vaqti (UTC+5) bilan ko'rsatamiz.
  function fmtDate(s) {
    if (!s) return "—";
    var m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
    if (!m) return esc(s);
    var d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]) + 5 * 3600 * 1000);
    var p = function (n) { return String(n).padStart(2, "0"); };
    return p(d.getUTCDate()) + "." + p(d.getUTCMonth() + 1) + "." + d.getUTCFullYear() +
      " · " + p(d.getUTCHours()) + ":" + p(d.getUTCMinutes());
  }

  function phoneHref(phone) {
    var digits = String(phone || "").replace(/\D/g, "");
    if (!digits) return "";
    if (digits.length === 9) digits = "998" + digits;
    return "+" + digits;
  }

  // +998901234567 / 901234567 -> +998 90 123 45 67
  function fmtPhone(phone) {
    var d = String(phone || "").replace(/\D/g, "");
    if (d.length === 9) d = "998" + d;
    if (d.length === 12 && d.indexOf("998") === 0) {
      return "+998 " + d.slice(3, 5) + " " + d.slice(5, 8) + " " + d.slice(8, 10) + " " + d.slice(10);
    }
    return phone || "";
  }

  // Rol: botda ro'yxatdan o'tishda tanlangan ("teacher" - o'qituvchi, qolgani / bo'sh - o'quvchi)
  function roleInfo(s) {
    return s.role === "teacher"
      ? { label: "O'qituvchi", cls: "role-teacher" }
      : { label: "O'quvchi", cls: "role-student" };
  }

  // Xavf darajasi: ro'yxatdan o'tganidan beri berilgan vazifalarning qancha qismi qilinmagan
  function risk(s) {
    if (!s.tests_total) return "new";
    var r = s.tests_missed / s.tests_total;
    if (r >= 0.7) return "high";
    if (r >= 0.35) return "mid";
    return "ok";
  }
  var RISK_LABEL = { high: "Xavfli", mid: "Diqqat", ok: "Yaxshi", new: "Yangi" };
  var RISK_AVATAR = {
    high: ["var(--danger)", "var(--danger-soft)"],
    mid: ["var(--warn)", "var(--warn-soft)"],
    ok: ["var(--ok)", "var(--ok-soft)"],
    new: ["var(--muted)", "var(--surface-2)"],
  };

  function barLevel(done, total) {
    if (!total) return "";
    var r = done / total;
    return r >= 0.65 ? "ok" : r >= 0.3 ? "mid" : "high";
  }

  function meter(label, done, total) {
    var pct = total ? Math.round((done / total) * 100) : 0;
    var zero = total > 0 && done === 0;
    return '<div class="meter">' +
      '<div class="meter-head"><span>' + label + '</span><b class="' + (zero ? "zero" : "") + '">' +
      (total ? done + " / " + total : "—") + "</b></div>" +
      '<div class="bar"><i class="' + barLevel(done, total) + '" style="width:' + pct + '%"></i></div></div>';
  }

  // ---------- API ----------
  function api(path, opts) {
    opts = opts || {};
    var headers = { "X-Init-Data": tg ? tg.initData : "" };
    if (opts.body) headers["Content-Type"] = "application/json";
    return fetch(path, {
      method: opts.method || "GET",
      headers: headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok) {
          var err = new Error(data.error || "http_" + res.status);
          err.status = res.status;
          throw err;
        }
        return data;
      });
    });
  }

  function errorInfo(e) {
    if (!tg || !tg.initData) return ["Telegram ichida oching", "Bu panel faqat Telegram bot orqali ochiladi."];
    if (e.status === 401) return ["Kirish tasdiqlanmadi", "Panelni bot menyusidagi «🖥 Admin panel» tugmasi orqali qayta oching."];
    if (e.status === 403) return ["Ruxsat yo'q", "Bu panel faqat Admin va Boss uchun."];
    return ["Ulanishda xatolik", "Ma'lumotni yuklab bo'lmadi. Internetni tekshirib, qayta urinib ko'ring."];
  }

  // ---------- Holat ----------
  var state = { worst: true, absent: false, uncalled: false, search: "", offset: 0, total: 0, req: 0, loading: false };

  var listEl = $("list");
  var moreBtn = $("moreBtn");

  function showError(e) {
    var info = errorInfo(e);
    $("errorTitle").textContent = info[0];
    $("errorText").textContent = info[1];
    $("errorState").hidden = false;
    $("emptyState").hidden = true;
    moreBtn.hidden = true;
  }

  // ---------- Umumiy ko'rsatkichlar ----------
  function loadSummary() {
    return api("/api/panel/summary").then(function (s) {
      $("statStudents").textContent = s.students;
      $("statStudentsNote").textContent = s.sessions_count + " ta dars · " + s.tests_count + " ta test";
      $("statNoHw").textContent = s.no_homework;
      $("statAbsent").textContent = s.absent_last_session;
      $("statWithHw").textContent = s.with_homework;
      $("statTestsNote").textContent = "kamida bittasini topshirgan";
    }).catch(function () { /* ro'yxat xatosi alohida ko'rsatiladi */ });
  }

  // ---------- Ro'yxat ----------
  function skeletons() {
    var html = "";
    for (var i = 0; i < 5; i++) {
      html += '<div class="card skeleton"><div class="card-top">' +
        '<div class="sk" style="width:44px;height:44px;border-radius:14px"></div>' +
        '<div class="card-id"><div class="sk" style="height:14px;width:60%"></div>' +
        '<div class="sk" style="height:11px;width:40%;margin-top:8px"></div></div></div>' +
        '<div class="sk" style="height:30px"></div></div>';
    }
    listEl.innerHTML = html;
  }

  function cardHtml(s, index) {
    var lvl = risk(s);
    var av = RISK_AVATAR[lvl];
    var tel = phoneHref(s.phone);
    var place = [s.region, s.district].filter(Boolean).join(", ");
    var meta = place || s.course || "";
    var role = roleInfo(s);
    return '<div class="card risk-' + lvl + '" data-id="' + esc(s.telegram_id) + '" tabindex="0" role="button" style="animation-delay:' + Math.min(index, 8) * 25 + 'ms">' +
      '<div class="card-top">' +
        '<div class="avatar" style="--av-ink:' + av[0] + ";--av-bg:" + av[1] + '">' + esc(initials(s.full_name)) + "</div>" +
        '<div class="card-id"><div class="card-name">' + esc(s.full_name || "Ismsiz") + "</div>" +
        '<div class="card-meta"><span class="role ' + role.cls + '">' + role.label + "</span>" + (meta ? " " + esc(meta) : "") + "</div></div>" +
        '<span class="badge ' + lvl + '">' + RISK_LABEL[lvl] + "</span>" +
      "</div>" +
      '<div class="meters">' + meter("Vazifa", s.tests_done, s.tests_total) + meter("Davomat", s.attendance_attended, s.attendance_total) + "</div>" +
      (s.called_at ? '<div class="called">📞 Qo\'ng\'iroq qilingan · ' + esc(s.called_by || "") + " · " + fmtDate(s.called_at) +
        (s.call_count > 1 ? " · " + s.call_count + " marta" : "") + "</div>" : "") +
      '<div class="card-foot"><span class="days">' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>' +
        daysText(s.days_registered) + "</span>" +
        (tel ? '<a class="call" href="tel:' + esc(tel) + '" data-call="1"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/></svg>Qo\'ng\'iroq</a>' : "") +
      "</div></div>";
  }

  function daysText(d) {
    if (d == null) return "—";
    if (d <= 0) return "bugun qo'shilgan";
    return d + " kun oldin qo'shilgan";
  }

  function loadStudents(reset) {
    if (state.loading && !reset) return;
    var req = ++state.req;
    state.loading = true;
    $("errorState").hidden = true;
    if (reset) {
      state.offset = 0;
      $("emptyState").hidden = true;
      moreBtn.hidden = true;
      skeletons();
    } else {
      moreBtn.disabled = true;
    }

    var q = new URLSearchParams({
      limit: PAGE,
      offset: state.offset,
      sort: state.worst ? "worst" : "newest",
    });
    if (state.search) q.set("search", state.search);
    if (state.absent) q.set("absent_last", "1");
    if (state.uncalled) q.set("uncalled", "1");

    return api("/api/panel/students?" + q.toString()).then(function (data) {
      if (req !== state.req) return;      // eskirgan javob
      var items = data.items || [];
      state.total = data.total || 0;
      if (reset) listEl.innerHTML = "";
      listEl.insertAdjacentHTML("beforeend", items.map(function (s, i) { return cardHtml(s, i); }).join(""));
      state.offset += items.length;

      $("emptyState").hidden = state.total !== 0;
      if (data.no_session) {
        $("emptyState").querySelector("h3").textContent = "Hali davomat bo'lmagan";
        $("emptyState").querySelector("p").textContent = "Birorta ham davomat sessiyasi yaratilmagan.";
      } else {
        $("emptyState").querySelector("h3").textContent = "Hech kim topilmadi";
        $("emptyState").querySelector("p").textContent = "Qidiruv yoki filtrni o'zgartirib ko'ring.";
      }
      $("resultCount").textContent = state.total ? state.offset + " / " + state.total + " ta o'quvchi" : "";
      moreBtn.hidden = state.offset >= state.total;
    }).catch(function (e) {
      if (req !== state.req) return;
      if (reset) listEl.innerHTML = "";
      showError(e);
    }).then(function () {
      if (req === state.req) { state.loading = false; moreBtn.disabled = false; }
    });
  }

  function refreshAll() {
    var btn = $("refreshBtn");
    btn.classList.add("spin");
    Promise.all([loadSummary(), loadStudents(true)]).then(function () {
      setTimeout(function () { btn.classList.remove("spin"); }, 300);
    });
  }

  // ---------- Filtrlar ----------
  function syncChips() {
    $("worstChip").classList.toggle("is-on", state.worst);
    $("worstChip").setAttribute("aria-pressed", String(state.worst));
    $("absentChip").classList.toggle("is-on", state.absent);
    $("absentChip").setAttribute("aria-pressed", String(state.absent));
    $("uncalledChip").classList.toggle("is-on", state.uncalled);
    $("uncalledChip").setAttribute("aria-pressed", String(state.uncalled));
    $("statAbsentBtn").classList.toggle("is-on", state.absent);
    $("rankHint").hidden = !state.worst;
  }

  $("worstChip").addEventListener("click", function () {
    state.worst = !state.worst; haptic(); syncChips(); loadStudents(true);
  });
  function toggleAbsent() {
    state.absent = !state.absent; haptic(); syncChips(); loadStudents(true);
  }
  $("absentChip").addEventListener("click", toggleAbsent);
  $("uncalledChip").addEventListener("click", function () {
    state.uncalled = !state.uncalled; haptic(); syncChips(); loadStudents(true);
  });
  $("statAbsentBtn").addEventListener("click", toggleAbsent);

  var searchTimer = null;
  var searchInput = $("searchInput");
  searchInput.addEventListener("input", function () {
    $("searchClear").hidden = !searchInput.value;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(function () {
      var v = searchInput.value.trim();
      if (v === state.search) return;
      state.search = v;
      loadStudents(true);
    }, 350);
  });
  searchInput.addEventListener("keydown", function (e) { if (e.key === "Enter") searchInput.blur(); });
  $("searchClear").addEventListener("click", function () {
    searchInput.value = ""; $("searchClear").hidden = true; state.search = ""; loadStudents(true); searchInput.focus();
  });

  moreBtn.addEventListener("click", function () { loadStudents(false); });
  $("retryBtn").addEventListener("click", refreshAll);
  $("refreshBtn").addEventListener("click", function () {
    haptic();
    if (!$("reportsView").hidden) { loadReports(true); return; }
    if (!$("rankingView").hidden) { loadRanking(true); return; }
    refreshAll();
  });

  // ---------- Hisobotlar bo'limi (testlar / A+ / davomat: faqat umumiy sonlar) ----------
  var rep = { kind: "tests", offset: 0, total: 0, loading: false, req: 0, loaded: false };

  function fmtShort(v) {
    var m = String(v || "").match(/^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})/);
    if (!m) return "";
    var d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]) + 5 * 3600 * 1000);   // UTC -> Toshkent
    var p = function (n) { return (n < 10 ? "0" : "") + n; };
    return p(d.getUTCDate()) + "." + p(d.getUTCMonth() + 1) + " " + p(d.getUTCHours()) + ":" + p(d.getUTCMinutes());
  }

  function repCard(it) {
    var att = rep.kind === "attendance";
    var title = att ? "Davomat" : (it.name || "Test");
    title += " · kod " + it.code;
    var pct = it.total ? Math.round(it.done * 100 / it.total) : 0;
    var note = (att ? "qatnashdi" : "ishladi") + " · " + pct + "%";
    if (!att && it.avg != null) note += " · o'rtacha ball " + it.avg;
    if (!it.finished) note += " · davom etmoqda";
    return '<div class="rep-card is-click" data-rid="' + it.id + '" data-title="' + esc(title) + '" role="button" tabindex="0"><div class="rep-top"><span class="rep-title">' + esc(title) +
      '</span><span class="rep-date">' + esc(fmtShort(it.created_at)) + '</span></div>' +
      '<div class="rep-nums"><span class="rep-count">' + it.done + '<small> / ' + it.total + '</small></span>' +
      '<span class="rep-note">' + esc(note) + '</span></div>' +
      '<div class="rep-bar"><i style="width:' + pct + '%"></i></div>' +
      '<div class="rep-more">Kimlar ' + (att ? "qatnashgani" : "ishlagani") + ' ›</div></div>';
  }

  function loadReports(reset) {
    if (rep.loading && !reset) return;
    if (reset) { rep.offset = 0; rep.req++; }
    var req = rep.req, list = $("reportsList"), more = $("reportsMore");
    rep.loading = true; more.disabled = true;
    if (reset) { list.innerHTML = ""; $("reportsEmpty").hidden = true; }
    return api("/api/panel/reports?kind=" + rep.kind + "&limit=" + PAGE + "&offset=" + rep.offset).then(function (data) {
      if (req !== rep.req) return;
      list.insertAdjacentHTML("beforeend", data.items.map(repCard).join(""));
      rep.offset += data.items.length; rep.total = data.total;
      $("reportsEmpty").hidden = rep.total > 0;
      more.hidden = rep.offset >= rep.total;
    }).catch(function (e) {
      if (req !== rep.req) return;
      haptic("err"); toast("Hisobotni yuklab bo'lmadi");
    }).then(function () {
      if (req === rep.req) { rep.loading = false; more.disabled = false; }
    });
  }


  // ---------- Hisobot tafsiloti: shu testni ishlagan o'quvchilar (+ natijani o'chirish) ----------
  var RESET_ERRORS = {
    not_allowed: "Sizda natijani o'chirish uchun ruxsat yo'q.",
    not_found: "Natija topilmadi (allaqachon o'chirilgan bo'lishi mumkin).",
    telegram_unreachable: "Server bilan bog'lanib bo'lmadi. Qayta urinib ko'ring.",
  };

  function fmtScore(v) { return v == null ? "" : String(v); }


  function answerRow(d) {
    var cls = d.is_correct ? "ok" : "wrong";
    var right = d.is_correct
      ? esc(d.your_answer == null ? "" : d.your_answer)
      : "siz: " + esc(d.your_answer == null || d.your_answer === "" ? "\u2014" : d.your_answer) +
        "  \u2192  to'g'ri: " + esc(d.correct_answer == null ? "\u2014" : d.correct_answer);
    return '<div class="ans-row ' + cls + '"><span class="ans-key">' + (d.is_correct ? "\u2705" : "\u274c") + " " + esc(d.key) +
      '</span><span class="ans-val">' + right + "</span></div>";
  }

  function toggleAnswers(kind, rid, btn) {
    var box = btn.nextElementSibling;
    if (!box.hidden) { box.hidden = true; btn.textContent = "📋 Javoblarni ko'rish"; return; }
    haptic();
    box.hidden = false;
    btn.textContent = "📋 Javoblarni yashirish";
    if (box.dataset.loaded) return;
    box.innerHTML = '<div class="sk" style="height:60px;border-radius:10px"></div>';
    var uid = btn.getAttribute("data-uid");
    api("/api/panel/report/" + kind + "/" + rid + "/answers/" + encodeURIComponent(uid)).then(function (data) {
      box.dataset.loaded = "1";
      box.innerHTML = data.details.map(answerRow).join("");
    }).catch(function () {
      box.innerHTML = '<p class="hint">Yuklab bo\'lmadi, qayta urinib ko\'ring.</p>';
    });
  }

  function openReportSheet(kind, rid, title) {
    haptic();
    $("sheetTitle").textContent = "Natijalar";
    current = null;
    sheetBody.innerHTML =
      '<div class="rep-sheet-head"><h3>' + esc(title) + '</h3></div>' +
      '<div class="sk" style="height:56px;margin-top:12px;border-radius:14px"></div>' +
      '<div class="sk" style="height:56px;margin-top:10px;border-radius:14px"></div>' +
      '<div class="sk" style="height:56px;margin-top:10px;border-radius:14px"></div>';
    sheet.hidden = false; backdrop.hidden = false;
    document.body.classList.add("sheet-open");
    $("sheetScroll").scrollTop = 0;
    if (tg && tg.BackButton) { try { tg.BackButton.show(); } catch (e) {} }

    api("/api/panel/report/" + kind + "/" + rid).then(function (data) {
      renderReportSheet(kind, rid, title, data);
    }).catch(function (e) {
      var info = errorInfo(e);
      sheetBody.innerHTML = '<div class="state"><div class="state-icon">⚠️</div><h3>' + esc(info[0]) + "</h3><p>" + esc(info[1]) + "</p></div>";
    });
  }

  function renderReportSheet(kind, rid, title, data) {
    var att = kind === "attendance";
    var rows = data.participants.map(function (p) {
      var badge = p.late ? ' <span class="rep-late">kech</span>' : "";
      var score = att ? "" : '<span class="rep-score">' + esc(fmtScore(p.score)) + ' ball</span>';
      var btn = data.can_reset
        ? '<button class="rep-reset" type="button" data-uid="' + p.telegram_id + '" data-name="' + esc(p.full_name || "O'quvchi") + '" data-score="' + esc(fmtScore(p.score)) + '">♻️ Qayta ishlashga ruxsat</button>'
        : "";
      var toggle = kind === "aplus"
        ? '<button class="rep-toggle" type="button" data-uid="' + p.telegram_id + '">📋 Javoblarni ko\'rish</button><div class="rep-answers" hidden></div>'
        : "";
      return '<div class="rep-person" data-uid="' + p.telegram_id + '">' +
        '<div class="rep-person-top"><span class="rep-person-name">' + esc(p.full_name || "Ismsiz") + badge + '</span>' + score + '</div>' +
        '<div class="rep-person-sub">' + esc(fmtShort(p.submitted_at)) + '</div>' + toggle + btn + '</div>';
    }).join("");
    sheetBody.innerHTML =
      '<div class="rep-sheet-head"><h3>' + esc(title) + '</h3>' +
      '<p><b id="repCount">' + data.participants.length + '</b> ta o\'quvchi ' + (att ? "qatnashgan" : "ishlagan") + '</p></div>' +
      (rows || '<div class="state"><div class="state-icon">📭</div><h3>Hali hech kim</h3></div>') +
      (data.can_reset ? '<p class="hint" style="margin-top:14px">♻️ tugmasi o\'quvchining shu test natijasini bazadan o\'chiradi: ball ham ayriladi va u testni qayta ishlay oladi.</p>' : "");

    sheetBody.querySelectorAll(".rep-toggle").forEach(function (b) {
      b.addEventListener("click", function () { toggleAnswers(kind, rid, b); });
    });
    sheetBody.querySelectorAll(".rep-reset").forEach(function (b) {
      b.addEventListener("click", function () {
        var name = b.getAttribute("data-name"), uid = b.getAttribute("data-uid"), sc = b.getAttribute("data-score");
        var q = name + " ning «" + title + "» natijasi (" + sc + " ball) o'chiriladi va u testni qayta ishlay oladi. Ballari ham shunga mos kamayadi. Davom etasizmi?";
        var go = function () {
          b.disabled = true; b.textContent = "O'chirilmoqda...";
          api("/api/panel/report/" + kind + "/" + rid + "/reset/" + encodeURIComponent(uid),
              { method: "POST", body: { confirm: true } })
            .then(function () {
              haptic("ok"); toast("Natija o'chirildi — qayta ishlashi mumkin");
              var row = b.closest(".rep-person"); if (row) row.remove();
              var c = $("repCount"); if (c) c.textContent = Math.max(0, (parseInt(c.textContent, 10) || 1) - 1);
              rep.loaded = true; loadReports(true);       // orqadagi ro'yxatdagi sonlarni yangilaymiz
            })
            .catch(function (e) {
              haptic("err"); toast(RESET_ERRORS[e.message] || "O'chirib bo'lmadi, qayta urinib ko'ring");
              b.disabled = false; b.textContent = "♻️ Qayta ishlashga ruxsat";
            });
        };
        if (tg && tg.showConfirm) tg.showConfirm(q, function (ok) { if (ok) go(); });
        else if (window.confirm(q)) go();
      });
    });
  }

  $("reportsList").addEventListener("click", function (e) {
    var card = e.target.closest(".rep-card[data-rid]");
    if (card) openReportSheet(rep.kind, card.getAttribute("data-rid"), card.getAttribute("data-title"));
  });
  $("reportsList").addEventListener("keydown", function (e) {
    if (e.key !== "Enter" && e.key !== " ") return;
    var card = e.target.closest(".rep-card[data-rid]");
    if (card) { e.preventDefault(); openReportSheet(rep.kind, card.getAttribute("data-rid"), card.getAttribute("data-title")); }
  });

  // ---------- Reyting bo'limi ----------
  var rk = { offset: 0, total: 0, loading: false, req: 0, loaded: false, search: "", timer: null };

  function chip(label, value, cls) {
    return '<span class="rk-chip' + (cls ? " " + cls : "") + '"><i>' + esc(label) + '</i> ' + esc(value) + '</span>';
  }

  function rankCard(it) {
    var medal = it.rank === 1 ? "🥇" : it.rank === 2 ? "🥈" : it.rank === 3 ? "🥉" : "";
    var bonus = (it.tests_streak || 0) + (it.aplus_streak || 0);
    var chips = chip("A+", it.aplus) + chip("Test", it.tests) + chip("Davomat", it.attendance) +
      chip("🔥", it.streak_now + (bonus ? " · +" + bonus : ""), it.streak_now > 0 ? "hot" : "");
    if (it.adjustments) chips += chip("±", (it.adjustments > 0 ? "+" : "") + it.adjustments);
    return '<div class="rk-card" data-id="' + it.telegram_id + '" role="button" tabindex="0">' +
      '<div class="rk-rank">' + (medal || it.rank) + '</div>' +
      '<div class="rk-main"><div class="rk-top"><span class="rk-name">' + esc(it.full_name || "Ismsiz") + '</span>' +
      '<span class="rk-total">' + it.total + '</span></div><div class="rk-chips">' + chips + '</div></div></div>';
  }

  function loadRanking(reset) {
    if (rk.loading && !reset) return;
    if (reset) { rk.offset = 0; rk.req++; }
    var req = rk.req, list = $("rankList"), more = $("rankMore");
    rk.loading = true; more.disabled = true;
    if (reset) { list.innerHTML = ""; $("rankEmpty").hidden = true; }
    var url = "/api/panel/ranking?limit=" + PAGE + "&offset=" + rk.offset + (rk.search ? "&search=" + encodeURIComponent(rk.search) : "");
    return api(url).then(function (data) {
      if (req !== rk.req) return;
      list.insertAdjacentHTML("beforeend", data.items.map(rankCard).join(""));
      rk.offset += data.items.length; rk.total = data.total;
      $("rankEmpty").hidden = rk.total > 0;
      $("rankCount").textContent = rk.total ? rk.offset + " / " + rk.total + " ta o'quvchi" : "";
      more.hidden = rk.offset >= rk.total;
    }).catch(function () {
      if (req !== rk.req) return;
      haptic("err"); toast("Reytingni yuklab bo'lmadi");
    }).then(function () {
      if (req === rk.req) { rk.loading = false; more.disabled = false; }
    });
  }

  $("rankMore").addEventListener("click", function () { loadRanking(false); });
  $("rankSearch").addEventListener("input", function () {
    clearTimeout(rk.timer);
    rk.timer = setTimeout(function () {
      var v = $("rankSearch").value.trim();
      if (v === rk.search) return;
      rk.search = v; loadRanking(true);
    }, 350);
  });
  $("rankList").addEventListener("click", function (e) {
    var card = e.target.closest(".rk-card[data-id]");
    if (card) openSheet(card.getAttribute("data-id"));
  });
  $("rankList").addEventListener("keydown", function (e) {
    if (e.key !== "Enter" && e.key !== " ") return;
    var card = e.target.closest(".rk-card[data-id]");
    if (card) { e.preventDefault(); openSheet(card.getAttribute("data-id")); }
  });

  function showView(view) {
    var names = ["students", "reports", "ranking"];
    names.forEach(function (n) {
      var cap = n.charAt(0).toUpperCase() + n.slice(1);
      $(n + "View").hidden = n !== view;
      var tab = $("tab" + cap);
      tab.classList.toggle("is-on", n === view);
      tab.setAttribute("aria-selected", String(n === view));
    });
    if (view === "reports" && !rep.loaded) { rep.loaded = true; loadReports(true); }
    if (view === "ranking" && !rk.loaded) { rk.loaded = true; loadRanking(true); }
  }
  $("tabStudents").addEventListener("click", function () { haptic(); showView("students"); });
  $("tabReports").addEventListener("click", function () { haptic(); showView("reports"); });
  $("tabRanking").addEventListener("click", function () { haptic(); showView("ranking"); });
  $("reportsMore").addEventListener("click", function () { loadReports(false); });
  document.querySelectorAll("[data-rkind]").forEach(function (b) {
    b.addEventListener("click", function () {
      rep.kind = b.getAttribute("data-rkind"); haptic();
      document.querySelectorAll("[data-rkind]").forEach(function (x) { x.classList.toggle("is-on", x === b); });
      loadReports(true);
    });
  });


  // Ro'yxatdagi kartani bosish -> profil
  listEl.addEventListener("click", function (e) {
    if (e.target.closest("[data-call]")) { haptic(); return; }     // qo'ng'iroq havolasi o'zi ishlaydi
    var card = e.target.closest(".card[data-id]");
    if (card) openSheet(card.getAttribute("data-id"));
  });
  listEl.addEventListener("keydown", function (e) {
    if (e.key !== "Enter") return;
    var card = e.target.closest(".card[data-id]");
    if (card) openSheet(card.getAttribute("data-id"));
  });

  // Yuqori panel chizig'i (aylantirilganda)
  window.addEventListener("scroll", function () {
    $("app").querySelector(".topbar").classList.toggle("is-stuck", window.scrollY > 4);
  }, { passive: true });

  // ---------- Profil (pastdan chiqadigan oyna) ----------
  var sheet = $("sheet"), backdrop = $("sheetBackdrop"), sheetBody = $("sheetBody");
  var current = null;     // { id, tab, sections: {tests:{items,total}, ...} }

  function closeSheet() {
    if (sheet.hidden) return;
    sheet.classList.add("closing");
    setTimeout(function () {
      sheet.hidden = true; backdrop.hidden = true; sheet.classList.remove("closing");
      document.body.classList.remove("sheet-open");
      current = null;
    }, 200);
    if (tg && tg.BackButton) { try { tg.BackButton.hide(); } catch (e) {} }
  }

  $("sheetClose").addEventListener("click", closeSheet);
  backdrop.addEventListener("click", closeSheet);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeSheet(); });
  if (tg && tg.BackButton) { try { tg.BackButton.onClick(closeSheet); } catch (e) {} }

  function openSheet(id) {
    haptic();
    $("sheetTitle").textContent = "Profil";
    current = { id: id, tab: "tests", sections: {} };
    sheetBody.innerHTML =
      '<div class="profile-head"><div class="sk" style="width:58px;height:58px;border-radius:18px"></div>' +
      '<div style="flex:1"><div class="sk" style="height:18px;width:70%"></div><div class="sk" style="height:12px;width:45%;margin-top:9px"></div></div></div>' +
      '<div class="sk" style="height:64px;margin-top:16px;border-radius:14px"></div>' +
      '<div class="sk" style="height:180px;margin-top:12px;border-radius:14px"></div>';
    sheet.hidden = false; backdrop.hidden = false;
    document.body.classList.add("sheet-open");
    $("sheetScroll").scrollTop = 0;
    if (tg && tg.BackButton) { try { tg.BackButton.show(); } catch (e) {} }

    var myId = id;
    api("/api/panel/student/" + encodeURIComponent(id)).then(function (data) {
      if (!current || current.id !== myId) return;
      current.data = data;
      ["tests", "aplus", "attendance"].forEach(function (k) { current.sections[k] = data[k]; });
      renderProfile();
    }).catch(function (e) {
      if (!current || current.id !== myId) return;
      var info = errorInfo(e);
      sheetBody.innerHTML = '<div class="state"><div class="state-icon">⚠️</div><h3>' + esc(info[0]) + "</h3><p>" + esc(info[1]) + "</p></div>";
    });
  }

  var ICON = {
    call: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/></svg>',
    tg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg>',
    msg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
  };

  function renderProfile() {
    var s = current.data.student;
    var lvl = risk(s);
    var av = RISK_AVATAR[lvl];
    var tel = phoneHref(s.phone);
    var place = [s.region, s.district].filter(Boolean).join(", ");

    sheetBody.innerHTML =
      '<div class="profile-head">' +
        '<div class="avatar lg" style="--av-ink:' + av[0] + ";--av-bg:" + av[1] + '">' + esc(initials(s.full_name)) + "</div>" +
        '<div style="min-width:0"><div class="profile-name">' + esc(s.full_name || "Ismsiz") + "</div>" +
        '<div class="profile-sub"><span class="badge ' + lvl + '">' + RISK_LABEL[lvl] + "</span> &nbsp;" + esc(daysText(s.days_registered)) + "</div></div>" +
      "</div>" +

      '<div class="actions">' +
        (tel ? '<a class="act act-call" href="tel:' + esc(tel) + '">' + ICON.call + "Qo'ng'iroq</a>"
             : '<span class="act disabled">' + ICON.call + "Raqam yo'q</span>") +
        '<button class="act" type="button" id="actTg">' + ICON.tg + "Telegram</button>" +
        '<button class="act" type="button" id="actCopy"' + (tel ? "" : " disabled") + ">" + ICON.copy + "Nusxalash</button>" +
        (current.data.can_message
          ? '<button class="act act-wide act-msg" type="button" id="actMsg">' + ICON.msg + "Botdan xabar yuborish</button>"
          : "") +
      "</div>" +
      (current.data.can_message ? '<div class="composer" id="composer" hidden>' +
        '<div class="composer-title">💬 Xabar: <b>' + esc(s.full_name || "O'quvchi") + "</b></div>" +
        '<p class="composer-hint">Xabar faqat shu o\'quvchiga, bot nomidan boradi. Raqami Telegram\'niki bo\'lmasa ham yetib boradi.</p>' +
        '<textarea id="msgText" maxlength="3500" placeholder="Masalan: Assalomu alaykum, nega darsga kelmayapsiz?"></textarea>' +
        '<p class="note-error" id="msgError" hidden></p>' +
        '<div class="composer-row"><button class="btn btn-soft" id="msgCancel" type="button">Bekor qilish</button>' +
        '<button class="btn btn-primary" id="msgSend" type="button">Yuborish</button></div>' +
      "</div>" : "") +

      '<div id="callMark"></div>' +
      '<div class="kpis">' +
        '<div class="kpi' + (s.tests_total && !s.tests_done ? " is-bad" : "") + '"><span>Vazifa</span><b>' + s.tests_done + " <small>/ " + s.tests_total + "</small></b></div>" +
        '<div class="kpi' + (s.attendance_total && !s.attendance_attended ? " is-bad" : "") + '"><span>Davomat</span><b>' + s.attendance_attended + " <small>/ " + s.attendance_total + "</small></b></div>" +
        '<div class="kpi"><span>Qilinmagan</span><b>' + s.tests_missed + " <small>ta</small></b></div>" +
      "</div>" +

      '<div class="kv">' +
        kv("Rol", '<span class="role ' + roleInfo(s).cls + '">' + roleInfo(s).label + "</span>", true) +
        kv("Telefon", fmtPhone(s.phone)) + kv("Kurs", s.course) + kv("Hudud", place) +
        kv("Ro'yxatdan o'tgan", fmtDate(s.registered_at), true) + kv("Telegram ID", s.telegram_id) +
      "</div>" +

      '<div class="tabs" role="tablist" id="tabs">' + tabBtn("tests", "Testlar") + tabBtn("aplus", "A+") + tabBtn("attendance", "Davomat") + "</div>" +
      '<div id="tabPanel"></div>' +

      '<h3 class="section-title">📝 Izohlar</h3>' +
      '<div class="rows" id="notes"></div>' +
      '<div class="note-form"><textarea id="noteText" maxlength="1000" placeholder="Qo\'ng\'iroq natijasi yoki izoh yozing..."></textarea>' +
        '<p class="note-error" id="noteError" hidden></p>' +
        '<button class="btn btn-primary" id="noteBtn" type="button">Izoh qo\'shish</button></div>' +
      (current.data.can_remove
        ? '<div class="danger-zone"><h3 class="section-title">⚠️ Xavfli amal</h3>' +
          '<p class="composer-hint">O\'quvchi o\'qimasa: <b>botdan ham, guruhdan ham</b> o\'chiriladi. Qaytarib bo\'lmaydi (o\'quvchi qayta ro\'yxatdan o\'tishi kerak bo\'ladi).</p>' +
          '<input class="reason" id="removeReason" maxlength="200" placeholder="Sabab (ixtiyoriy), masalan: o\'qimayman" />' +
          '<p class="note-error" id="removeError" hidden></p>' +
          '<button class="btn btn-danger" id="removeBtn" type="button">🚪 O\'qimayman — botdan va guruhdan o\'chirish</button>' +
          '<button class="btn btn-ghost" id="removeBotOnlyBtn" type="button" hidden>Faqat botdan o\'chirish (guruhga tegmasdan)</button></div>'
        : "");

    // Mini App ichida tg:// havolalari ko'p mijozlarda ochilmaydi - t.me havolasi
    // openTelegramLink orqali ishonchli ochiladi. Avval telefon raqami bo'yicha
    // (o'quvchi botga raqamini Telegram kontakti orqali yuborgan), bo'lmasa ID bo'yicha.
    $("actTg").addEventListener("click", function () {
      haptic();
      var url = tel ? "https://t.me/" + tel : "tg://user?id=" + s.telegram_id;
      try {
        if (tg && tg.openTelegramLink && tel) { tg.openTelegramLink(url); return; }
        window.location.href = url;
      } catch (e) { toast("Telegram ochilmadi — raqamni nusxalab qidiring"); }
    });
    if (current.data.can_message) {
      $("actMsg").addEventListener("click", function () {
        haptic();
        var box = $("composer");
        box.hidden = !box.hidden;
        if (!box.hidden) { box.scrollIntoView({ behavior: "smooth", block: "center" }); $("msgText").focus(); }
      });
      $("msgCancel").addEventListener("click", function () { $("composer").hidden = true; $("msgError").hidden = true; });
      $("msgSend").addEventListener("click", function () { sendMessage(s); });
      $("msgText").addEventListener("input", function () { $("msgError").hidden = true; });
    }
    $("actCopy").addEventListener("click", function () {
      copyText(tel);
    });
    $("tabs").addEventListener("click", function (e) {
      var b = e.target.closest(".tab");
      if (!b) return;
      current.tab = b.getAttribute("data-tab");
      haptic();
      renderTabs();
    });
    $("noteBtn").addEventListener("click", addNote);
    renderCallMark();
    if (current.data.can_remove) {
      $("removeBtn").addEventListener("click", function () { removeStudent(s, false); });
      $("removeBotOnlyBtn").addEventListener("click", function () { removeStudent(s, true); });
    }
    renderTabs();
    renderNotes(current.data.notes);
  }

  function kv(k, v, raw) {
    if (v === null || v === undefined || v === "") return "";
    return '<div><span class="k">' + k + '</span><span class="v">' + (raw ? v : esc(v)) + "</span></div>";
  }

  function tabBtn(key, label) {
    return '<button class="tab" role="tab" type="button" data-tab="' + key + '">' + label + "<em>" +
      (current.sections[key] ? current.sections[key].total : 0) + "</em></button>";
  }

  function pillLevel(score, total) {
    if (!total) return "mid";
    var r = score / total;
    return r >= 0.7 ? "ok" : r >= 0.4 ? "mid" : "high";
  }

  function rowHtml(kind, r) {
    if (kind === "attendance") {
      return '<div class="row"><div class="row-main"><div class="row-title">Dars · ' + esc(r.name) + '</div><div class="row-sub">' + fmtDate(r.at) + "</div></div>" +
        '<span class="pill ' + (r.attended ? "ok" : "high") + '">' + (r.attended ? "Qatnashdi" : "Qatnashmadi") + "</span></div>";
    }
    return '<div class="row"><div class="row-main"><div class="row-title">' + esc(r.name || "Test") + '</div><div class="row-sub">' + fmtDate(r.at) + "</div></div>" +
      '<span class="pill ' + pillLevel(r.score, r.total) + '">' + r.score + " / " + (r.total || "?") + "</span></div>";
  }

  function renderTabs() {
    Array.prototype.forEach.call(document.querySelectorAll("#tabs .tab"), function (b) {
      b.classList.toggle("is-on", b.getAttribute("data-tab") === current.tab);
      b.setAttribute("aria-selected", String(b.getAttribute("data-tab") === current.tab));
    });
    var kind = current.tab, sec = current.sections[kind];
    var empty = { tests: "Hali oddiy test topshirmagan.", aplus: "Hali A+ test topshirmagan.", attendance: "Ro'yxatdan o'tgandan beri dars bo'lmagan." }[kind];
    var html = '<div class="rows">' + (sec.items.length ? sec.items.map(function (r) { return rowHtml(kind, r); }).join("") : '<div class="rows-empty">' + empty + "</div>") + "</div>";
    if (sec.items.length < sec.total) {
      html += '<button class="rows-more" type="button" id="rowsMore">Yana ko\'rish (' + (sec.total - sec.items.length) + ")</button>";
    }
    $("tabPanel").innerHTML = html;
    var more = $("rowsMore");
    if (more) more.addEventListener("click", function () { loadMoreSection(kind, more); });
  }

  function loadMoreSection(kind, btn) {
    var id = current.id, sec = current.sections[kind];
    btn.disabled = true; btn.textContent = "Yuklanmoqda...";
    api("/api/panel/student/" + encodeURIComponent(id) + "/" + kind + "?limit=10&offset=" + sec.items.length).then(function (data) {
      if (!current || current.id !== id) return;
      sec.items = sec.items.concat(data.items || []);
      sec.total = data.total;
      renderTabs();
    }).catch(function () { btn.disabled = false; btn.textContent = "Yuklab bo'lmadi — qayta urinish"; });
  }

  function renderNotes(notes) {
    var box = $("notes");
    if (!box) return;
    if (!notes || !notes.length) { box.innerHTML = '<div class="rows-empty">Hozircha izoh yo\'q.</div>'; return; }
    box.innerHTML = notes.map(function (n) {
      return '<div class="note">' + esc(n.note) + "<small>" + esc(n.author_name) + " · " + fmtDate(n.created_at) + "</small></div>";
    }).join("");
  }

  function addNote() {
    var ta = $("noteText"), btn = $("noteBtn"), err = $("noteError");
    var text = ta.value.trim();
    err.hidden = true;
    if (!text) { err.textContent = "Izoh bo'sh bo'lmasin."; err.hidden = false; haptic("err"); return; }
    var id = current.id;
    btn.disabled = true;
    api("/api/panel/student/" + encodeURIComponent(id) + "/notes", { method: "POST", body: { note: text } }).then(function (data) {
      if (!current || current.id !== id) return;
      ta.value = "";
      current.data.notes = data.notes;
      renderNotes(data.notes);
      haptic("ok"); toast("Izoh saqlandi");
    }).catch(function () {
      err.textContent = "Saqlab bo'lmadi. Qayta urinib ko'ring."; err.hidden = false; haptic("err");
    }).then(function () { btn.disabled = false; });
  }

  // ---------- "Qo'ng'iroq qilingan" belgisi ----------
  function renderCallMark() {
    var box = $("callMark");
    if (!box || !current) return;
    var s = current.data.student;
    if (!s.called_at) {
      box.innerHTML = '<button class="callmark-btn" id="markCalled" type="button">✅ Qo\'ng\'iroq qildim — belgilash</button>';
      $("markCalled").addEventListener("click", function () { setCallMark(true); });
      return;
    }
    box.innerHTML = '<div class="callmark"><div class="callmark-info">📞 <b>Qo\'ng\'iroq qilingan</b>' +
      "<span>" + esc(s.called_by || "") + " · " + fmtDate(s.called_at) + (s.call_count > 1 ? " · " + s.call_count + " marta" : "") + "</span></div>" +
      '<div class="callmark-actions"><button type="button" id="markAgain">+ Yana qo\'ng\'iroq qildim</button>' +
      '<button type="button" id="markClear">Belgini olib tashlash</button></div></div>';
    $("markAgain").addEventListener("click", function () { setCallMark(true); });
    $("markClear").addEventListener("click", function () { setCallMark(false); });
  }

  function setCallMark(called) {
    var s = current.data.student, id = s.telegram_id;
    api("/api/panel/student/" + encodeURIComponent(id) + "/call-mark", { method: "POST", body: { called: called } })
      .then(function (data) {
        if (!current || String(current.id) !== String(id)) return;
        var m = data.call_mark;
        s.called_at = m ? m.at : null; s.called_by = m ? m.by : null; s.call_count = m ? m.count : 0;
        renderCallMark();
        haptic("ok"); toast(called ? "Belgi qo'yildi ✓" : "Belgi olib tashlandi");
        // ro'yxatdagi kartani yangilaymiz (yoki "qo'ng'iroq qilinmaganlar" filtrida bo'lsa - olib tashlaymiz)
        var card = document.querySelector('.card[data-id="' + id + '"]');
        if (card) {
          if (state.uncalled && called) { card.remove(); state.total = Math.max(0, state.total - 1); state.offset = Math.max(0, state.offset - 1); }
          else card.outerHTML = cardHtml(s, 0);
        }
      })
      .catch(function () { haptic("err"); toast("Saqlab bo'lmadi, qayta urinib ko'ring"); });
  }

  // ---------- O'quvchini botdan va guruhdan o'chirish ----------
  var REMOVE_ERRORS = {
    no_rights: "Bot guruhda admin emas yoki a'zolarni chiqarish huquqi yo'q.",
    target_admin: "Bu odam guruhda admin yoki egasi — chiqarib bo'lmaydi.",
    chat_not_found: "Guruh topilmadi (kurs uchun belgilangan kanal/guruh noto'g'ri).",
    group_failed: "Guruhdan chiqarib bo'lmadi.",
    extra_no_rights: "Guruhdan chiqarildi, lekin yopiq kanalda bot admin emas yoki \"Ban users\" huquqi yo'q. Hech narsa o'chmadi.",
    extra_target_admin: "Bu odam yopiq kanalda admin yoki egasi — chiqarib bo'lmaydi.",
    extra_chat_not_found: "Yopiq kanal topilmadi (ID noto'g'ri yoki bot kanalda yo'q). Hech narsa o'chmadi.",
    extra_group_failed: "Yopiq kanaldan chiqarib bo'lmadi. Hech narsa o'chmadi.",
    extra_telegram_unreachable: "Yopiq kanal uchun Telegram bilan bog'lanib bo'lmadi. Qayta urinib ko'ring.",
    protected: "Admin yoki Boss'ni o'chirib bo'lmaydi.",
    not_allowed: "Sizda bu amal uchun ruxsat yo'q.",
    telegram_unreachable: "Telegram bilan bog'lanib bo'lmadi. Qayta urinib ko'ring.",
  };

  function removeStudent(s, skipGroup) {
    var err = $("removeError"), reason = $("removeReason").value.trim();
    err.hidden = true;
    var question = (s.full_name || "O'quvchi") + (skipGroup
      ? " faqat BOTdan o'chiriladi (guruhda qoladi). Davom etasizmi?"
      : " BOTdan ham, GURUH (va yopiq kanal)dan ham o'chiriladi. Bu amalni qaytarib bo'lmaydi. Davom etasizmi?");
    var go = function () {
      var id = s.telegram_id, btn = $("removeBtn");
      btn.disabled = true; btn.textContent = "O'chirilmoqda...";
      api("/api/panel/student/" + encodeURIComponent(id) + "/remove",
          { method: "POST", body: { confirm: true, reason: reason, skip_group: !!skipGroup } })
        .then(function (data) {
          haptic("ok");
          var g = data.group === "removed" ? "guruhdan ✓" : (data.group === "skipped" ? "guruhga tegilmadi" : "guruh sozlanmagan");
          toast("O'chirildi: botdan ✓, " + g + (data.channel === "removed" ? ", kanaldan ✓" : ""));
          var card = document.querySelector('.card[data-id="' + id + '"]');
          if (card) { card.remove(); state.total = Math.max(0, state.total - 1); state.offset = Math.max(0, state.offset - 1); }
          current = null; sheet.hidden = true; backdrop.hidden = true; document.body.classList.remove("sheet-open");
          if (tg && tg.BackButton) { try { tg.BackButton.hide(); } catch (e) {} }
          $("resultCount").textContent = state.total ? state.offset + " / " + state.total + " ta o'quvchi" : "";
          loadSummary();
        })
        .catch(function (e) {
          haptic("err");
          err.textContent = REMOVE_ERRORS[e.message] || "O'chirib bo'lmadi. Qayta urinib ko'ring.";
          err.hidden = false;
          // guruh bilan muammo bo'lsa - faqat botdan o'chirish imkoniyatini taklif qilamiz
          if (!skipGroup && ["no_rights", "chat_not_found", "group_failed", "telegram_unreachable", "extra_no_rights", "extra_chat_not_found", "extra_group_failed", "extra_telegram_unreachable"].indexOf(e.message) >= 0) {
            $("removeBotOnlyBtn").hidden = false;
          }
          btn.disabled = false; btn.textContent = "🚪 O'qimayman — botdan va guruhdan o'chirish";
        });
    };
    if (tg && tg.showConfirm) tg.showConfirm(question, function (ok) { if (ok) go(); });
    else if (window.confirm(question)) go();
  }

  var MSG_ERRORS = {
    blocked: "O'quvchi botni bloklagan yoki akkaunti o'chirilgan — xabar yetmaydi.",
    chat_not_found: "Bu o'quvchi botda chat ochmagan — xabar yetmaydi.",
    boss_only: "Sizda xabar yuborish ruxsati yo'q.",
    too_many: "Juda ko'p xabar yuborildi. Bir daqiqadan keyin urinib ko'ring.",
    empty_message: "Xabar matnini yozing.",
    message_too_long: "Xabar juda uzun.",
    telegram_unreachable: "Telegram bilan bog'lanib bo'lmadi. Qayta urinib ko'ring.",
  };

  function sendMessage(s) {
    var ta = $("msgText"), btn = $("msgSend"), err = $("msgError");
    var text = ta.value.trim();
    err.hidden = true;
    if (!text) { err.textContent = MSG_ERRORS.empty_message; err.hidden = false; haptic("err"); return; }

    var go = function () {
      var id = s.telegram_id;
      btn.disabled = true; btn.textContent = "Yuborilmoqda...";
      api("/api/panel/student/" + encodeURIComponent(id) + "/message", { method: "POST", body: { text: text } })
        .then(function (data) {
          if (!current || String(current.id) !== String(id)) return;
          ta.value = "";
          $("composer").hidden = true;
          current.data.notes = data.notes;
          renderNotes(data.notes);
          haptic("ok"); toast("Xabar yuborildi ✓");
        })
        .catch(function (e) {
          err.textContent = MSG_ERRORS[e.message] || "Yuborib bo'lmadi. Qayta urinib ko'ring.";
          err.hidden = false; haptic("err");
        })
        .then(function () { btn.disabled = false; btn.textContent = "Yuborish"; });
    };

    // Adashib yuborib yubormaslik uchun tasdiq so'raymiz
    var question = (s.full_name || "O'quvchi") + "ga xabar yuborilsinmi?";
    if (tg && tg.showConfirm) tg.showConfirm(question, function (ok) { if (ok) go(); });
    else if (window.confirm(question)) go();
  }

  function copyText(text, message) {
    if (!text) return;
    var done = function () { haptic("ok"); toast(message || ("Nusxalandi: " + text)); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else { fallback(); }
    function fallback() {
      var t = document.createElement("textarea");
      t.value = text; t.style.position = "fixed"; t.style.opacity = "0";
      document.body.appendChild(t); t.select();
      try { document.execCommand("copy"); done(); } catch (e) { toast(text); }
      document.body.removeChild(t);
    }
  }

  // ---------- iPhone: qo'ng'iroq ----------
  // iPhone'dagi Telegram Mini App ichidan `tel:` havolasi ochilmaydi (Android'da ochadi).
  // Shuning uchun iPhone'da tugma kichik "qo'ng'iroq sahifasi"ni (call.html) TASHQI brauzerda
  // (Safari) ochadi - u yerda `tel:` ishonchli ishlaydi va telefon ilovasi chiqadi.
  var IS_IOS = (tg && tg.platform === "ios") || /iPhone|iPad|iPod/i.test(navigator.userAgent || "");

  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest('a[href^="tel:"]');
    if (!a || !IS_IOS) return;                       // Android/kompyuter: havola o'zi ishlaydi
    e.preventDefault();
    e.stopPropagation();
    var tel = a.getAttribute("href").replace(/^tel:/, "");
    var page = location.origin + "/call.html#" + encodeURIComponent(tel);
    try {
      if (tg && tg.openLink) { tg.openLink(page, { try_browser: "safari" }); return; }
    } catch (x) {}
    window.location.href = "tel:" + tel;             // zaxira
  }, true);

  // ---------- Boshlash ----------
  syncChips();
  if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
    var u = tg.initDataUnsafe.user;
    $("whoami").textContent = [u.first_name, u.last_name].filter(Boolean).join(" ") || "O'quvchilar nazorati";
  }
  refreshAll();
})();
