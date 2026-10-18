// A+ yozma javoblar uchun matematik kiritish: MathLive (math-field + virtual klaviatura).
//
// MathLive javobni LaTeX ko'rinishida beradi (\frac{3}{4}, \sqrt{2}, x^{2}). Backend
// (answer_check.py) esa oddiy matnni tushunadi ("3/4", "√2", "x^2"), shuning uchun
// har bir javob SAQLANISHDAN OLDIN shu fayldagi latexToPlain() bilan oddiy matnga
// aylantiriladi - serverga ketadigan va bazada saqlanadigan format o'zgarmaydi.
//
//   mathLiveReady()            -> Promise<boolean> (kutubxona yuklandimi)
//   createAnswerField(opts)    -> { el, getPlain() }   opts: {prefill, placeholder, onChange}
//   hideMathKeyboard()         -> virtual klaviaturani yopadi
//   latexToPlain / plainToLatex (sinash uchun ham eksport qilinadi)
//
// Kutubxona yuklanmasa (internet/CDN muammosi) - oddiy matn maydoniga o'tiladi.

(function (root) {
  "use strict";

  var MATHLIVE_VERSION = "0.110.0";
  var MATHLIVE_BASE = "https://cdn.jsdelivr.net/npm/mathlive@" + MATHLIVE_VERSION;

  // ---------- LaTeX -> oddiy matn ----------

  var GREEK = {
    alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε", varepsilon: "ε", zeta: "ζ", eta: "η",
    theta: "θ", vartheta: "θ", lambda: "λ", mu: "μ", nu: "ν", xi: "ξ", pi: "π", rho: "ρ", sigma: "σ",
    tau: "τ", phi: "φ", varphi: "φ", chi: "χ", psi: "ψ", omega: "ω",
    Gamma: "Γ", Delta: "Δ", Theta: "Θ", Lambda: "Λ", Xi: "Ξ", Pi: "Π", Sigma: "Σ", Phi: "Φ", Psi: "Ψ", Omega: "Ω",
  };
  var SYMBOLS = {
    times: "*", cdot: "*", div: "/", pm: "±", mp: "∓", infty: "∞", neq: "≠", ne: "≠", leq: "≤", le: "≤",
    geq: "≥", ge: "≥", approx: "≈", lt: "<", gt: ">", degree: "°", circ: "°", in: "∈", notin: "∉",
    cup: "∪", cap: "∩", subset: "⊂", emptyset: "∅", varnothing: "∅", to: "→", rightarrow: "→",
    lbrace: "{", rbrace: "}", lbrack: "[", rbrack: "]", vert: "|", lvert: "|", rvert: "|", ldots: "...", dots: "...",
    exponentialE: "e", imaginaryI: "i", differentialD: "d", forall: "∀", exists: "∃", Rightarrow: "⇒", Leftrightarrow: "⇔", leftrightarrow: "↔",
    colon: ":", mid: "|", prime: "'", ast: "*", leqslant: "≤", geqslant: "≥", setminus: "\\",
    "%": "%", "&": "&", "$": "$", "#": "#", "_": "_", "{": "{", "}": "}", "|": "|", "\\": "",
  };
  var SKIP = {
    ",": 1, ";": 1, ":": 1, "!": 1, " ": 1, quad: 1, qquad: 1, displaystyle: 1, textstyle: 1,
    mleft: 1, mright: 1, nobreak: 1, hfill: 1, limits: 1, nolimits: 1,
  };
  var TEXT_CMDS = { text: 1, mathrm: 1, operatorname: 1, mathit: 1, mathbf: 1, textbf: 1, textit: 1, mathnormal: 1, mbox: 1 };
  var SIMPLE_RE = /^[A-Za-z0-9.]+$/;

  function tokenize(src) {
    var toks = [], i = 0, n = src.length;
    while (i < n) {
      var c = src[i];
      if (c === "\\") {
        i++;
        if (i >= n) break;
        if (/[A-Za-z]/.test(src[i])) {
          var j = i;
          while (j < n && /[A-Za-z]/.test(src[j])) j++;
          toks.push({ cmd: src.slice(i, j) });
          i = j;
          while (i < n && src[i] === " ") i++;       // buyruqdan keyingi bo'shliq LaTeX'da e'tiborga olinmaydi
        } else {
          toks.push({ cmd: src[i] });
          i++;
        }
      } else {
        toks.push({ ch: c });
        i++;
      }
    }
    return toks;
  }

  function wrapIfNeeded(s, simpleRe) {
    return simpleRe.test(s) ? s : "(" + s + ")";
  }

  function latexToPlain(latex) {
    var toks = tokenize(String(latex == null ? "" : latex));
    var pos = 0;

    function peek() { return toks[pos]; }
    function isCh(t, c) { return t && t.ch === c; }

    // "{...}" guruhi yoki bitta birlik (argument)
    function parseArg() {
      var t = peek();
      if (!t) return "";
      if (isCh(t, "{")) { pos++; return parseSeq(true); }
      return parseAtom();
    }

    function parseSeq(stopAtBrace) {
      var out = "";
      while (pos < toks.length) {
        var t = peek();
        if (isCh(t, "}")) {
          pos++;
          if (stopAtBrace) return out;
          continue;
        }
        out += parseAtom();
      }
      return out;
    }

    function parseAtom() {
      var t = toks[pos++];
      if (!t) return "";
      if (t.ch !== undefined) {
        var c = t.ch;
        if (c === "{") return parseSeq(true);
        if (c === "}") return "";
        if (c === "^" || c === "_") {
          var arg = parseArg();
          if (c === "^" && (arg === "°" || arg === "∘")) return "°";
          return c + wrapIfNeeded(arg, SIMPLE_RE);
        }
        if (/\s/.test(c)) return "";
        return c;
      }

      var name = t.cmd;
      if (name === "frac" || name === "dfrac" || name === "tfrac" || name === "cfrac") {
        var a = parseArg(), b = parseArg();
        return wrapIfNeeded(a, SIMPLE_RE) + "/" + wrapIfNeeded(b, SIMPLE_RE);
      }
      if (name === "sqrt") {
        var index = "";
        if (isCh(peek(), "[")) {
          pos++;
          while (pos < toks.length && !isCh(peek(), "]")) {
            var it = toks[pos++];
            index += it.ch !== undefined ? it.ch : "";
          }
          pos++;
        }
        var body = parseArg();
        if (index) return "(" + body + ")^(1/" + index + ")";
        return "√" + (/^[0-9.]+$/.test(body) ? body : "(" + body + ")");
      }
      if (name === "left" || name === "right") {
        var d = toks[pos++];
        if (!d) return "";
        if (d.ch !== undefined) return d.ch === "." ? "" : d.ch;
        return SYMBOLS[d.cmd] !== undefined ? SYMBOLS[d.cmd] : "";
      }
      if (name === "placeholder") { parseArg(); return ""; }
      if (TEXT_CMDS[name]) return parseArg();
      if (name === "begin" || name === "end") { parseArg(); return ""; }
      if (SKIP[name]) return "";
      if (GREEK[name]) return GREEK[name];
      if (SYMBOLS[name] !== undefined) return SYMBOLS[name];
      return name;            // sin, cos, log, ln, lim ... - nomi shundayligicha
    }

    return parseSeq(false)
      .replace(/\s+/g, "")
      .replace(/[\u2212\u2013\u2014\u2012]/g, "-");      // uzun minus/tire -> oddiy "-"
  }

  // ---------- oddiy matn -> LaTeX (tahrirlashda avvalgi javobni ko'rsatish uchun) ----------

  var REVERSE = {
    "×": "\\times ", "÷": "\\div ", "*": "\\cdot ", "±": "\\pm ", "∞": "\\infty ", "≠": "\\ne ", "≤": "\\le ",
    "≥": "\\ge ", "≈": "\\approx ", "%": "\\%", "°": "^{\\circ}", "{": "\\{", "}": "\\}", "#": "\\#", "&": "\\&",
    "$": "\\$", "\\": "", "∈": "\\in ", "∉": "\\notin ", "→": "\\to ",
  };
  Object.keys(GREEK).forEach(function (k) { if (!REVERSE[GREEK[k]]) REVERSE[GREEK[k]] = "\\" + k + " "; });

  function matchParen(s, open) {
    var depth = 0;
    for (var i = open; i < s.length; i++) {
      if (s[i] === "(") depth++;
      else if (s[i] === ")" && --depth === 0) return i;
    }
    return -1;
  }

  function plainToLatex(plain) {
    var s = String(plain == null ? "" : plain);
    var out = "", i = 0, m;
    while (i < s.length) {
      var c = s[i];
      if (c === "√") {
        i++;
        if (s[i] === "(") {
          var j = matchParen(s, i);
          if (j < 0) j = s.length;
          out += "\\sqrt{" + plainToLatex(s.slice(i + 1, j)) + "}";
          i = j + 1;
        } else if ((m = /^[0-9.,]+|^[A-Za-zπ]/.exec(s.slice(i)))) {
          out += "\\sqrt{" + plainToLatex(m[0]) + "}";
          i += m[0].length;
        } else {
          out += "\\sqrt{}";
        }
        continue;
      }
      if (c === "^" || c === "_") {
        i++;
        if (s[i] === "(") {
          var k = matchParen(s, i);
          if (k < 0) k = s.length;
          out += c + "{" + plainToLatex(s.slice(i + 1, k)) + "}";
          i = k + 1;
        } else if ((m = /^-?[0-9.]+|^[A-Za-z]/.exec(s.slice(i)))) {
          out += c + "{" + m[0] + "}";
          i += m[0].length;
        } else {
          out += c;
        }
        continue;
      }
      out += REVERSE[c] !== undefined ? REVERSE[c] : c;
      i++;
    }
    return out;
  }

  // ---------- MathLive yuklash ----------

  var readyPromise = null;

  function configureMathLive() {
    var M = root.MathfieldElement;
    if (M) {
      try { M.fontsDirectory = MATHLIVE_BASE + "/fonts"; } catch (e) {}
      try { M.soundsDirectory = null; M.plonkSound = null; M.keypressSound = null; } catch (e) {}
    }
  }

  function mathLiveReady() {
    if (readyPromise) return readyPromise;
    readyPromise = new Promise(function (resolve) {
      if (!root.customElements) return resolve(false);
      if (root.customElements.get("math-field")) { configureMathLive(); return resolve(true); }
      var done = false;
      var finish = function (ok) { if (!done) { done = true; clearTimeout(timer); resolve(ok); } };
      var timer = setTimeout(function () { finish(false); }, 10000);
      var s = document.createElement("script");
      s.src = MATHLIVE_BASE + "/mathlive.min.js";
      s.async = true;
      s.onload = function () {
        configureMathLive();
        finish(!!root.customElements.get("math-field"));
      };
      s.onerror = function () { finish(false); };
      document.head.appendChild(s);
    });
    return readyPromise;
  }

  // ---------- javob maydoni ----------

  function createAnswerField(opts) {
    opts = opts || {};
    var onChange = opts.onChange || function () {};
    var placeholder = opts.placeholder || "";

    if (root.customElements && root.customElements.get("math-field")) {
      var mf = document.createElement("math-field");
      mf.className = "aplus-input aplus-mathfield";
      mf.setAttribute("placeholder", placeholder);
      try { mf.smartMode = false; } catch (e) {}
      try { mf.menuItems = []; } catch (e) {}
      if (opts.prefill) {
        try { mf.value = plainToLatex(opts.prefill); } catch (e) {}
      }
      var getPlain = function () { return latexToPlain(mf.value); };
      mf.addEventListener("input", function () { onChange(getPlain()); });

      // Klaviaturani O'ZIMIZ boshqaramiz (policy="manual"): MathLive'ning avtomatik ochilishi/yopilishi
      // ba'zi telefonlarda ikonka bosilganda adashar edi. Qoidalar:
      //   - telefonda maydonga bosish: yopiq bo'lsa ochadi; shu maydon faol va klaviatura ochiq bo'lsa - yopadi;
      //   - maydon ichidagi klaviatura ikonkasi: shu maydon faol va klaviatura ochiq bo'lsa - yopadi, aks holda ochadi
      //     (boshqa maydonning ikonkasi bosilsa - klaviatura ochiq qoladi va o'sha maydonga o'tadi).
      mf.setAttribute("math-virtual-keyboard-policy", "manual");
      var kbVisible = function () { return !!(root.mathVirtualKeyboard && root.mathVirtualKeyboard.visible); };
      var isFocused = function () { return document.activeElement === mf || mf.matches(":focus-within"); };
      var openKb = function () {
        try { mf.focus(); } catch (e) {}
        try { root.mathVirtualKeyboard && root.mathVirtualKeyboard.show(); } catch (e) {}
      };
      var closeKb = function () {
        hideMathKeyboard();
        try { mf.blur(); } catch (e) {}
      };
      var isToggleEvent = function (e) {
        var path = e.composedPath ? e.composedPath() : [];
        for (var i = 0; i < path.length; i++) {
          var el = path[i];
          if (el && el.getAttribute && /virtual-keyboard-toggle/.test(el.getAttribute("part") || "")) return true;
        }
        return false;
      };
      // Telefonlarda bitta bosishdan bir nechta hodisa (pointerup, sintetik click) kelishi mumkin -
      // shuning uchun harakat pointerup'da BIR marta bajariladi va qisqa muddat ichida takrorlanmaydi.
      var pressedWhileOpen = false, downX = 0, downY = 0, lastAct = 0;
      var act = function (fn) {
        var now = Date.now();
        if (now - lastAct < 350) return;
        lastAct = now;
        fn();
      };
      mf.addEventListener("pointerdown", function (e) {
        pressedWhileOpen = kbVisible() && isFocused();
        downX = e.clientX; downY = e.clientY;
        if (isToggleEvent(e)) e.stopImmediatePropagation();
      }, true);
      mf.addEventListener("pointerup", function (e) {
        if (isToggleEvent(e)) {
          e.stopImmediatePropagation();
          act(function () { if (pressedWhileOpen) closeKb(); else openKb(); });
          return;
        }
        var touch = e.pointerType === "touch" || e.pointerType === "pen";
        var moved = Math.abs(e.clientX - downX) > 10 || Math.abs(e.clientY - downY) > 10;
        if (touch && !moved) act(function () { if (pressedWhileOpen) closeKb(); else openKb(); });
      }, true);
      ["mousedown", "mouseup", "touchstart", "touchend", "click"].forEach(function (type) {
        mf.addEventListener(type, function (e) {
          if (isToggleEvent(e)) { e.stopImmediatePropagation(); if (type === "click") e.preventDefault(); return; }
          // Telefon bosishdan keyin "mousedown/mouseup/click" ham keladi - MathLive ularni klaviaturani qayta
          // ochish uchun ishlatadi. Bizning harakatdan keyingi qisqa vaqtda ularni to'xtatamiz.
          if (type !== "touchstart" && type !== "touchend" && Date.now() - lastAct < 700) {
            e.stopImmediatePropagation();
            e.preventDefault();
          }
        }, true);
      });
      return { el: mf, getPlain: getPlain, isMath: true };
    }

    // Zaxira: kutubxona yuklanmadi - oddiy matn maydoni ("3/4", "sqrt(2)" kabi yoziladi)
    var input = document.createElement("input");
    input.type = "text";
    input.className = "aplus-input aplus-input-plain";
    input.placeholder = placeholder;
    input.autocomplete = "off";
    input.setAttribute("autocapitalize", "off");
    input.value = opts.prefill || "";
    input.addEventListener("input", function () { onChange(input.value); });
    return { el: input, getPlain: function () { return input.value; }, isMath: false };
  }

  function hideMathKeyboard() {
    try { if (root.mathVirtualKeyboard) root.mathVirtualKeyboard.hide(); } catch (e) {}
  }

  var api = {
    mathLiveReady: mathLiveReady,
    createAnswerField: createAnswerField,
    hideMathKeyboard: hideMathKeyboard,
    latexToPlain: latexToPlain,
    plainToLatex: plainToLatex,
  };
  Object.keys(api).forEach(function (k) { root[k] = api[k]; });
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
