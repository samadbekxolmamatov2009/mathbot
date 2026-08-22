// Oddiy matematik klaviatura komponenti (A+ yozma javobli testlar uchun).
// createMathKeyboard(mountEl) -> { toggle(inputEl, toggleBtnEl), hide(), isOpen }

function createMathKeyboard(mountEl) {
  const TABS = {
    "123": ["7", "8", "9", "4", "5", "6", "1", "2", "3", "0", ".", "/"],
    belgi: ["+", "-", "×", "÷", "(", ")", "√", "^", "±", "∞", "≠", "%"],
    harf: ["x", "y", "z", "a", "b", "c", "n", "m"],
    yun: ["π", "α", "β", "γ", "θ", "Δ"],
  };
  const TAB_LABELS = { "123": "123", belgi: "√ ± ( )", harf: "abc", yun: "αβγ" };

  let activeTab = "123";
  let activeInput = null;

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

  function dispatchInput(el) {
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function insertAtCursor(text) {
    if (!activeInput) return;
    const el = activeInput;
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? el.value.length;
    el.value = el.value.slice(0, start) + text + el.value.slice(end);
    const pos = start + text.length;
    el.focus();
    el.setSelectionRange(pos, pos);
    dispatchInput(el);
  }

  function backspace() {
    if (!activeInput) return;
    const el = activeInput;
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? el.value.length;
    if (start === end && start > 0) {
      el.value = el.value.slice(0, start - 1) + el.value.slice(end);
      el.focus();
      el.setSelectionRange(start - 1, start - 1);
    } else {
      el.value = el.value.slice(0, start) + el.value.slice(end);
      el.focus();
      el.setSelectionRange(start, start);
    }
    dispatchInput(el);
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

  function show(inputEl, toggleBtn) {
    if (activeInput && activeInput._kbdBtn) {
      activeInput._kbdBtn.classList.remove("active");
    }
    activeInput = inputEl;
    activeInput._kbdBtn = toggleBtn || null;
    if (toggleBtn) toggleBtn.classList.add("active");
    root.hidden = false;
  }

  function hide() {
    if (activeInput && activeInput._kbdBtn) activeInput._kbdBtn.classList.remove("active");
    activeInput = null;
    root.hidden = true;
  }

  function toggle(inputEl, toggleBtn) {
    if (!root.hidden && activeInput === inputEl) {
      hide();
    } else {
      show(inputEl, toggleBtn);
    }
  }

  return {
    toggle,
    hide,
    get isOpen() {
      return !root.hidden;
    },
  };
}
