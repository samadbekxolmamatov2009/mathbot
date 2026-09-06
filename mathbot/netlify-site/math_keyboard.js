// Oddiy matematik klaviatura komponenti (A+ yozma javobli testlar uchun).
// createMathKeyboard(mountEl) -> { toggle(fieldEl, toggleBtnEl), show(fieldEl, toggleBtnEl), hide(), isOpen }
//
// MUHIM: fieldEl HAQIQIY <input> EMAS, oddiy <div>/<span> (matn ko'rsatuvchi,
// "value" o'rniga fieldEl.dataset.value ishlatiladi). Bu ataylab shunday -
// haqiqiy <input>'ga fokus berilsa, ba'zi telefonlarda (ayniqsa iOS'da)
// "readonly" bo'lishiga qaramay tabiiy klaviatura baribir ochilib qolar edi.
// <div> hech qachon klaviatura chiqarmaydi, chunki u umuman tahrirlanadigan
// matn kiritish elementi emas.

function createMathKeyboard(mountEl) {
  const TABS = {
    "123": ["7", "8", "9", "4", "5", "6", "1", "2", "3", "0", ".", "/"],
    belgi: ["+", "-", "×", "÷", "(", ")", "√", "^", "±", "∞", "≠", "%"],
    harf: ["x", "y", "z", "a", "b", "c", "n", "m"],
    yun: ["π", "α", "β", "γ", "θ", "Δ"],
  };
  const TAB_LABELS = { "123": "123", belgi: "√ ± ( )", harf: "abc", yun: "αβγ" };

  let activeTab = "123";
  let activeField = null;

  const root = document.createElement("div");
  root.className = "math-keyboard";
  root.hidden = true;

  const tabsEl = document.createElement("div");
  tabsEl.className = "math-keyboard-tabs";
  Object.keys(TABS).forEach((key) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "math-keyboard-tab" + (key === activeTab ? " active" : "");
    btn.textContent = TAB_LABELS[key];
    btn.dataset.tab = key;
    btn.addEventListener("click", () => {
      activeTab = key;
      [...tabsEl.children].forEach((b) => b.classList.toggle("active", b.dataset.tab === key));
      renderGrid();
    });
    tabsEl.appendChild(btn);
  });

  const gridEl = document.createElement("div");
  gridEl.className = "math-keyboard-grid";

  function getValue(el) {
    return el.dataset.value || "";
  }

  function setValue(el, value) {
    el.dataset.value = value;
    el.textContent = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function insertAtCursor(text) {
    if (!activeField) return;
    setValue(activeField, getValue(activeField) + text);
  }

  function backspace() {
    if (!activeField) return;
    setValue(activeField, getValue(activeField).slice(0, -1));
  }

  function renderGrid() {
    gridEl.innerHTML = "";
    TABS[activeTab].forEach((sym) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "math-keyboard-key";
      btn.textContent = sym;
      btn.addEventListener("click", () => insertAtCursor(sym));
      gridEl.appendChild(btn);
    });
    const back = document.createElement("button");
    back.type = "button";
    back.className = "math-keyboard-key danger wide";
    back.textContent = "⌫";
    back.addEventListener("click", backspace);
    gridEl.appendChild(back);
  }

  renderGrid();

  const footerEl = document.createElement("div");
  footerEl.className = "math-keyboard-footer";
  const doneBtn = document.createElement("button");
  doneBtn.type = "button";
  doneBtn.className = "math-keyboard-done";
  doneBtn.textContent = "✓ Tayyor";
  doneBtn.addEventListener("click", () => hide());
  footerEl.appendChild(doneBtn);

  root.appendChild(tabsEl);
  root.appendChild(gridEl);
  root.appendChild(footerEl);
  mountEl.appendChild(root);

  function show(fieldEl, toggleBtn) {
    if (activeField) activeField.classList.remove("aplus-input-focused");
    if (activeField && activeField._kbdBtn) {
      activeField._kbdBtn.classList.remove("active");
    }
    activeField = fieldEl;
    activeField.classList.add("aplus-input-focused");
    activeField._kbdBtn = toggleBtn || null;
    if (toggleBtn) toggleBtn.classList.add("active");
    root.hidden = false;
  }

  function hide() {
    if (activeField) {
      activeField.classList.remove("aplus-input-focused");
      if (activeField._kbdBtn) activeField._kbdBtn.classList.remove("active");
    }
    activeField = null;
    root.hidden = true;
  }

  function toggle(fieldEl, toggleBtn) {
    if (!root.hidden && activeField === fieldEl) {
      hide();
    } else {
      show(fieldEl, toggleBtn);
    }
  }

  return {
    show,
    toggle,
    hide,
    get isOpen() {
      return !root.hidden;
    },
  };
}
