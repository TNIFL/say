/* ============================================================
 *  Lexinoa mainpage.js — SINGLE SUBMIT HANDLER (no duplicates)
 * ============================================================ */

/* ------------------ i18n helper ------------------ */
function tr(key, vars, fallback) {
  if (typeof window !== "undefined" && typeof window.t === "function") {
    return window.t(key, vars, fallback);
  }
  // fallback for safety
  let s = fallback || key;
  if (vars && typeof vars === "object") {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replaceAll(`%(${k})s`, String(v));
    }
  }
  return s;
}

/* ------------------ 칩 유틸 ------------------ */
function createChip(text, value, group, inputName) {
  if (document.querySelector(`.${group}-chip[data-value="${CSS.escape(value)}"]`)) return null;

  const chip = document.createElement("button");
  chip.type = "button";
  chip.className = `chip ${group}-chip`;
  chip.dataset.value = value;
  chip.textContent = text + " ";

  const x = document.createElement("span");
  x.className = "x";
  x.textContent = "×";
  chip.appendChild(x);

  const hid = document.createElement("input");
  hid.type = "hidden";
  hid.name = inputName;
  hid.value = value;
  hid.dataset.value = value;

  return { chip, hid };
}

function addItem(selectEl, chipsBoxEl, hiddenBoxEl, group, inputName) {
  const opt = selectEl.options[selectEl.selectedIndex];
  if (!opt || !opt.value) return;

  const made = createChip(opt.text, opt.value, group, inputName);
  if (!made) return;

  chipsBoxEl.appendChild(made.chip);
  hiddenBoxEl.appendChild(made.hid);
  selectEl.selectedIndex = 0;
}

function removeItem(value, chipsBoxEl, hiddenBoxEl, group) {
  const chip = chipsBoxEl.querySelector(`.${group}-chip[data-value="${CSS.escape(value)}"]`);
  const hid = hiddenBoxEl.querySelector(`input[data-value="${CSS.escape(value)}"]`);
  if (chip) chip.remove();
  if (hid) hid.remove();
}

function clearAll() {
  ["categoryChips", "toneChips", "categoryHidden", "toneHidden"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = "";
  });

  const cSel = document.getElementById("categorySelect");
  const tSel = document.getElementById("toneSelect");
  if (cSel) cSel.selectedIndex = 0;
  if (tSel) tSel.selectedIndex = 0;

  ["honorific", "opener", "emoji"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.checked = false;
  });

  const sel = document.getElementById("templateSelect");
  if (sel) sel.value = "";
}

/* ------------------ 결과 렌더(복사 포함) ------------------ */
function renderOutputsInto(container, outputs) {
  if (!container) return;
  container.innerHTML = "";

  const isPro = document.getElementById("bootstrap")?.dataset.isPro === "true";
  const wrap = document.createElement("div");
  wrap.className = "outputs-wrap";

  outputs.forEach((txt, i) => {
    const card = document.createElement("div");
    card.className = "output-card";

    const head = document.createElement("div");
    head.className = "output-card-head small hint";
    head.textContent = tr("output.result_n", { n: String(i + 1) }, `Result ${i + 1}`);

    if (isPro && outputs.length > 1) {
      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "btn small ghost copy-single-btn";
      copyBtn.textContent = tr("common.copy", null, "Copy");
      copyBtn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(txt);
          copyBtn.textContent = tr("common.copied", null, "Copied!");
          setTimeout(() => (copyBtn.textContent = tr("common.copy", null, "Copy")), 1000);
        } catch {
          alert(tr("common.copy_failed", null, "Copy failed"));
        }
      });
      head.appendChild(copyBtn);
    }

    const body = document.createElement("div");
    body.className = "output";
    body.textContent = txt || "";

    card.appendChild(head);
    card.appendChild(body);
    wrap.appendChild(card);
  });

  if (outputs.length > 1) {
    const allCopyBtn = document.createElement("button");
    allCopyBtn.type = "button";
    allCopyBtn.className = "btn secondary";
    allCopyBtn.textContent = tr("common.copy_all", null, "Copy all");
    allCopyBtn.style.marginTop = "8px";

    allCopyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(outputs.join("\n\n"));
        allCopyBtn.textContent = tr("common.copied", null, "Copied!");
        setTimeout(() => (allCopyBtn.textContent = tr("common.copy_all", null, "Copy all")), 1000);
      } catch {
        alert(tr("common.copy_failed", null, "Copy failed"));
      }
    });

    wrap.appendChild(allCopyBtn);
  }

  container.appendChild(wrap);
}

/* ------------------ 서버 상태 복원(data-*) ------------------ */
function restoreFromServer() {
  const boot = document.getElementById("bootstrap");
  if (!boot) return;

  const cSel = document.getElementById("categorySelect");
  const tSel = document.getElementById("toneSelect");
  const cChips = document.getElementById("categoryChips");
  const tChips = document.getElementById("toneChips");
  const cHidden = document.getElementById("categoryHidden");
  const tHidden = document.getElementById("toneHidden");
  if (!cSel || !tSel || !cChips || !tChips || !cHidden || !tHidden) return;

  let preCats = [];
  let preTones = [];
  try { preCats = JSON.parse(boot.dataset.selectedCategories || "[]"); } catch {}
  try { preTones = JSON.parse(boot.dataset.selectedTones || "[]"); } catch {}

  const honorificChecked = boot.dataset.honorific === "true";
  const openerChecked = boot.dataset.opener === "true";
  const emojiChecked = boot.dataset.emoji === "true";

  const honor = document.getElementById("honorific");
  const openr = document.getElementById("opener");
  const emoji = document.getElementById("emoji");
  if (honor) honor.checked = honorificChecked;
  if (openr) openr.checked = openerChecked;
  if (emoji) emoji.checked = emojiChecked;

  if (Array.isArray(preCats)) {
    preCats.forEach((val) => {
      const opt = Array.from(cSel.options || []).find((o) => o.value === val);
      if (!opt) return;
      const made = createChip(opt.text, val, "category", "selected_categories");
      if (!made) return;
      cChips.appendChild(made.chip);
      cHidden.appendChild(made.hid);
    });
  }

  if (Array.isArray(preTones)) {
    preTones.forEach((val) => {
      const opt = Array.from(tSel.options || []).find((o) => o.value === val);
      if (!opt) return;
      const made = createChip(opt.text, val, "tone", "selected_tones");
      if (!made) return;
      tChips.appendChild(made.chip);
      tHidden.appendChild(made.hid);
    });
  }
}

/* ------------------ 출력 복사(단일 output_text 대상) ------------------ */
function bindCopyOutputButton() {
  const btn = document.getElementById("copyOutputBtn");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    const target = document.getElementById("output_text");
    if (!target) return;

    const text = target.innerText ?? target.textContent ?? "";
    const labelOrig = btn.textContent;

    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const range = document.createRange();
        range.selectNodeContents(target);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        document.execCommand("copy");
        sel.removeAllRanges();
      }
      btn.textContent = tr("common.copied", null, "Copied!");
      btn.disabled = true;
      setTimeout(() => {
        btn.textContent = labelOrig;
        btn.disabled = false;
      }, 1200);
    } catch {
      btn.textContent = tr("common.copy_failed", null, "Copy failed");
      setTimeout(() => (btn.textContent = labelOrig), 1200);
    }
  });
}

/* ------------------ 사용량 갱신 ------------------ */
async function updateUsageInfo() {
  const el = document.getElementById("usageInfo");
  if (!el) return;

  try {
    const res = await fetch(`/api/usage?t=${Date.now()}`, {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    });
    if (!res.ok) throw new Error();
    const data = await res.json();

    const label =
      data.tier === "guest" ? tr("tier.guest", null, "Guest") :
      data.tier === "free"  ? tr("tier.free", null, "Free") :
                              tr("tier.pro", null, "Pro");

    el.textContent = tr(
      "usage.summary",
      { limit: String(data.limit), remain: String(data.limit - data.used), label },
      `Total ${data.limit} / ${data.limit - data.used} remaining (${label})`
    );
  } catch {
    // 실패 시 기존 표시 유지
  }
}

/* ------------------ 공통: 안전 JSON 파서 ------------------ */
async function safeJson(res) {
  try {
    const txt = await res.text();
    return txt ? JSON.parse(txt) : {};
  } catch {
    return {};
  }
}

/* ------------------ 템플릿 라이브러리 ------------------ */
function initTemplates() {
  const sel       = document.getElementById("templateSelect");
  const addBtn    = document.getElementById("btnTemplateAdd");
  const resetBtn  = document.getElementById("resetTemplateBtn");
  const delBtn    = document.getElementById("btnTemplateDelete");

  const dlg       = document.getElementById("tplDialog");
  const btnClose  = document.getElementById("tplClose");
  const btnCancel = document.getElementById("tplCancel");
  const btnSave   = document.getElementById("tplSave");

  if (!sel) return;

  async function loadTemplates() {
    const isPro = document.getElementById("bootstrap")?.dataset.isPro === "true";

    const placeholder = sel.dataset.i18nPlaceholder || "Select a template…";
    const hint1 = sel.dataset.i18nHint1 || "";
    const hint2 = sel.dataset.i18nHint2 || "";
    const hint3 = sel.dataset.i18nHint3 || "";

    // 1) 비-Pro: 힌트만 보여주고 API 호출은 하지 않음
    if (!isPro) {
      sel.innerHTML =
        `<option value="" selected>${placeholder}</option>` +
        (hint1 ? `<option value="__hint1" disabled>${hint1}</option>` : "") +
        (hint2 ? `<option value="__hint2" disabled>${hint2}</option>` : "") +
        (hint3 ? `<option value="__hint3" disabled>${hint3}</option>` : "");
      return;
    }

    // 2) Pro: 힌트 없이 placeholder만 먼저 깔고, 템플릿 목록만 append
    sel.innerHTML = `<option value="" selected>${placeholder}</option>`;

    try {
      const res  = await fetch("/api/user_templates", {
        method: "GET",
        credentials: "include",
        cache: "no-store",
      });
      const data = await safeJson(res);

      // Pro인데도 권한 문제면(예: 세션 만료) placeholder만 유지하고 종료
      if (res.status === 401 || res.status === 403) return;
      if (!res.ok) return;

      const list = Array.isArray(data?.items) ? data.items
        : Array.isArray(data) ? data
        : [];

      for (const t of list) {
        const opt = document.createElement("option");
        opt.value = String(t.id);
        opt.textContent = t.title;

        opt.dataset.category  = t.category || "";
        opt.dataset.tone      = t.tone || "";
        opt.dataset.honorific = String(!!t.honorific);
        opt.dataset.opener    = String(!!t.opener);
        opt.dataset.emoji     = String(!!t.emoji);

        sel.appendChild(opt);
      }
    } catch (err) {
      console.error("템플릿 로드 오류:", err);
    }
  }


  window.loadTemplates = loadTemplates;

  sel.addEventListener("change", (e) => {
    const opt = e.target.selectedOptions[0];
    if (!opt) return;

    const cSel = document.getElementById("categorySelect");
    const tSel = document.getElementById("toneSelect");
    const cChips = document.getElementById("categoryChips");
    const tChips = document.getElementById("toneChips");
    const cHidden = document.getElementById("categoryHidden");
    const tHidden = document.getElementById("toneHidden");

    if (!cSel || !tSel || !cChips || !tChips || !cHidden || !tHidden) return;

    cChips.innerHTML = ""; tChips.innerHTML = "";
    cHidden.innerHTML = ""; tHidden.innerHTML = "";

    if (opt.dataset.category) {
      const match = Array.from(cSel.options).find(o => o.value === opt.dataset.category);
      const made  = createChip(match?.text || opt.dataset.category, opt.dataset.category, "category", "selected_categories");
      if (made) { cChips.appendChild(made.chip); cHidden.appendChild(made.hid); }
    }

    if (opt.dataset.tone) {
      const match = Array.from(tSel.options).find(o => o.value === opt.dataset.tone);
      const made  = createChip(match?.text || opt.dataset.tone, opt.dataset.tone, "tone", "selected_tones");
      if (made) { tChips.appendChild(made.chip); tHidden.appendChild(made.hid); }
    }

    document.getElementById("honorific").checked = opt.dataset.honorific === "true";
    document.getElementById("opener").checked    = opt.dataset.opener    === "true";
    document.getElementById("emoji").checked     = opt.dataset.emoji     === "true";
  });

  addBtn?.addEventListener("click", () => {
    if (!dlg) return;
    if (typeof dlg.showModal === "function") dlg.showModal();
    else dlg.setAttribute("open", "");
  });

  const closeDlg = () => {
    if (!dlg) return;
    if (typeof dlg.close === "function") dlg.close();
    else dlg.removeAttribute("open");
  };
  btnClose?.addEventListener("click", closeDlg);
  btnCancel?.addEventListener("click", closeDlg);

  btnSave?.addEventListener("click", async () => {
    const title     = document.getElementById("tplTitle").value.trim();
    const category  = document.getElementById("tplCategory").value || "";
    const tone      = document.getElementById("tplTone").value || "";
    const honorific = document.getElementById("tplHonorific").checked;
    const opener    = document.getElementById("tplOpener").checked;
    const emoji     = document.getElementById("tplEmoji").checked;

    if (!title) { alert(tr("tpl.title_required", null, "Please enter a title.")); return; }

    try {
      const res  = await fetch("/api/user_templates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        cache: "no-store",
        body: JSON.stringify({ title, category, tone, honorific, opener, emoji })
      });
      const data = await safeJson(res);

      if (res.status === 401) return alert(tr("tpl.login_required", null, "Login required."));
      if (res.status === 403) return alert(tr("tpl.pro_required", null, "Pro required."));
      if (!res.ok || data.ok === false) return alert(data.message || tr("tpl.save_error", null, "Error while saving."));

      await loadTemplates();
      closeDlg();
      alert(tr("tpl.saved", null, "Template saved."));
    } catch (err) {
      console.error("템플릿 저장 오류:", err);
      alert(tr("common.network_error_retry", null, "Network error. Please try again."));
    }
  });

  delBtn?.addEventListener("click", async (e) => {
    e.preventDefault();
    const tplId = sel?.value;

    if (!tplId) return alert(tr("tpl.delete_select_first", null, "Select a template to delete."));
    if (!confirm(tr("tpl.delete_confirm", null, "Are you sure you want to delete this template?"))) return;

    try {
      const res  = await fetch(`/api/user_templates/${tplId}`, {
        method: "DELETE",
        credentials: "include",
        cache: "no-store",
      });
      const data = await safeJson(res);

      if (res.status === 401 || res.status === 403) return;
      if (res.status === 404) return alert(tr("tpl.already_deleted", null, "Template already deleted."));
      if (!res.ok || data.ok === false) return alert(data.message || tr("tpl.delete_failed", null, "Delete failed."));

      await loadTemplates();
      sel.value = "";
      alert(tr("tpl.deleted", null, "Template deleted."));
    } catch (err) {
      console.error("템플릿 삭제 오류:", err);
      alert(tr("common.network_error_retry", null, "Network error. Please try again."));
    }
  });

  resetBtn?.addEventListener("click", () => {
    clearAll();
  });

  loadTemplates();
}

/* ------------------ 메인 초기화 + 단일 submit 핸들러 ------------------ */
document.addEventListener("DOMContentLoaded", () => {
  const cSel = document.getElementById("categorySelect");
  const tSel = document.getElementById("toneSelect");
  const cChips = document.getElementById("categoryChips");
  const tChips = document.getElementById("toneChips");
  const cHidden = document.getElementById("categoryHidden");
  const tHidden = document.getElementById("toneHidden");

  if (cSel && tSel && cChips && tChips && cHidden && tHidden) {
    cSel.addEventListener("change", () => addItem(cSel, cChips, cHidden, "category", "selected_categories"));
    tSel.addEventListener("change", () => addItem(tSel, tChips, tHidden, "tone", "selected_tones"));

    cChips.addEventListener("click", (e) => {
      const btn = e.target.closest(".category-chip");
      if (!btn) return;
      removeItem(btn.dataset.value, cChips, cHidden, "category");
    });

    tChips.addEventListener("click", (e) => {
      const btn = e.target.closest(".tone-chip");
      if (!btn) return;
      removeItem(btn.dataset.value, tChips, tHidden, "tone");
    });

    const clearBtn = document.getElementById("clearAll");
    if (clearBtn) clearBtn.addEventListener("click", clearAll);
  }

  restoreFromServer();
  bindCopyOutputButton();
  updateUsageInfo();
  initTemplates();

  const form = document.getElementById("polishForm");
  const btn  = document.getElementById("submitBtn");
  if (form && btn) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      e.stopPropagation();

      const input = document.getElementById("input_text");
      const providerSel = form.querySelector("[name='provider']");
      const categories = [...document.querySelectorAll("#categoryHidden input[name='selected_categories']")].map(el => el.value);
      const tones      = [...document.querySelectorAll("#toneHidden input[name='selected_tones']")].map(el => el.value);

      const honorific  = document.getElementById("honorific")?.checked ?? false;
      const opener     = document.getElementById("opener")?.checked ?? false;
      const emoji      = document.getElementById("emoji")?.checked ?? false;

      const inputText = (input?.value || "").trim();

      if (!inputText) {
        alert(tr("input.empty", null, "No input."));
        return;
      }

      const payload = {
        input_text: inputText,
        selected_categories: categories,
        selected_tones: tones,
        honorific_checked: honorific,
        opener_checked: opener,
        emoji_checked: emoji,
        provider: (providerSel?.value || "claude"),
      };

      btn.classList.add("loading");
      btn.setAttribute("aria-busy", "true");
      btn.disabled = true;

      try {
        const res = await fetch("/api/polish", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(payload),
        });

        const data = await res.json().catch(() => ({}));

        if (res.status === 429) {
          alert(tr("limit.reached", { limit: String(data.limit ?? "?") }, "Limit reached."));
          return;
        }

        if (!res.ok) {
          if (data?.error === "empty_input") {
            alert(tr("input.empty", null, "No input."));
            return;
          }
          alert(data?.message || tr("request.error_status", { status: String(res.status) }, `Error (${res.status})`));
          return;
        }

        const out = document.getElementById("output_text");
        if (!out) return;

        if (Array.isArray(data.outputs) && data.outputs.length) {
          renderOutputsInto(out, data.outputs);
        } else {
          out.textContent = data.output_text || "";
        }
      } catch (err) {
        alert(tr("common.network_error_retry", null, "Network error. Please try again."));
      } finally {
        await updateUsageInfo();
        btn.classList.remove("loading");
        btn.removeAttribute("aria-busy");
        btn.disabled = false;
      }
    });
  }
});
