/* ============================================================
 *  Lexinoa mainpage.js — SINGLE SUBMIT HANDLER (no duplicates)
 *  기능:
 *    - 카테고리/말투 칩 + hidden input 동기화
 *    - 서버 상태 복원(data-*)
 *    - 결과 렌더(복사 버튼 포함)
 *    - 폼 제출(fetch /api/polish) + 429/empty_input 처리
 *    - 사용량 표시 갱신(/api/usage)
 *    - 템플릿 라이브러리(목록/추가/삭제/즉시적용)
 * ============================================================ */

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

  // 템플릿 셀렉트도 초기화 (있으면)
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
    head.textContent = `결과 ${i + 1}`;

    // 복사 버튼 (Pro + 다중결과일 때)
    if (isPro && outputs.length > 1) {
      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "btn small ghost copy-single-btn";
      copyBtn.textContent = "복사";
      copyBtn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(txt);
          copyBtn.textContent = "복사됨!";
          setTimeout(() => (copyBtn.textContent = "복사"), 1000);
        } catch {
          alert("복사 실패");
        }
      });
      head.appendChild(copyBtn);
    }

    const body = document.createElement("div");
    body.className = "output";
    body.textContent = txt || ""; // XSS-safe

    card.appendChild(head);
    card.appendChild(body);
    wrap.appendChild(card);
  });

  // 전체 복사 (다중결과)
  if (outputs.length > 1) {
    const allCopyBtn = document.createElement("button");
    allCopyBtn.type = "button";
    allCopyBtn.className = "btn secondary";
    allCopyBtn.textContent = "전체 복사";
    allCopyBtn.style.marginTop = "8px";

    allCopyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(outputs.join("\n\n"));
        allCopyBtn.textContent = "복사됨!";
        setTimeout(() => (allCopyBtn.textContent = "전체 복사"), 1000);
      } catch {
        alert("복사 실패");
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
      btn.textContent = "복사됨!";
      btn.disabled = true;
      setTimeout(() => {
        btn.textContent = labelOrig;
        btn.disabled = false;
      }, 1200);
    } catch {
      btn.textContent = "복사 실패";
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

    const label = data.tier === "guest" ? "비로그인"
      : data.tier === "free" ? "회원"
      : "구독";

    el.textContent = `총 ${data.limit}회 / ${data.limit - data.used}회 남음 (${label})`;
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

  // Pro UI 없으면 종료
  if (!sel) return;

  async function loadTemplates() {
    try {
      const res  = await fetch("/api/user_templates", {
        method: "GET",
        credentials: "include",
        cache: "no-store",
      });
      const data = await safeJson(res);

      // 401/403이면 조용히 종료 (원래 동작 유지)
      if (res.status === 401 || res.status === 403) return;
      if (!res.ok) return;

      const list = Array.isArray(data?.items) ? data.items
        : Array.isArray(data) ? data
        : [];

      sel.innerHTML = '<option value=""> 템플릿 선택…</option>';
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

  // 외부에서 호출할 수 있게 유지
  window.loadTemplates = loadTemplates;

  // 선택 즉시 적용
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

    // 초기화
    cChips.innerHTML = ""; tChips.innerHTML = "";
    cHidden.innerHTML = ""; tHidden.innerHTML = "";

    // 카테고리 1개 적용(현재 구조 기준)
    if (opt.dataset.category) {
      const match = Array.from(cSel.options).find(o => o.value === opt.dataset.category);
      const made  = createChip(match?.text || opt.dataset.category, opt.dataset.category, "category", "selected_categories");
      if (made) { cChips.appendChild(made.chip); cHidden.appendChild(made.hid); }
    }

    // 톤 1개 적용
    if (opt.dataset.tone) {
      const match = Array.from(tSel.options).find(o => o.value === opt.dataset.tone);
      const made  = createChip(match?.text || opt.dataset.tone, opt.dataset.tone, "tone", "selected_tones");
      if (made) { tChips.appendChild(made.chip); tHidden.appendChild(made.hid); }
    }

    // 체크박스
    document.getElementById("honorific").checked = opt.dataset.honorific === "true";
    document.getElementById("opener").checked    = opt.dataset.opener    === "true";
    document.getElementById("emoji").checked     = opt.dataset.emoji     === "true";
  });

  // 다이얼로그 열기
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

  // 저장
  btnSave?.addEventListener("click", async () => {
    const title     = document.getElementById("tplTitle").value.trim();
    const category  = document.getElementById("tplCategory").value || "";
    const tone      = document.getElementById("tplTone").value || "";
    const honorific = document.getElementById("tplHonorific").checked;
    const opener    = document.getElementById("tplOpener").checked;
    const emoji     = document.getElementById("tplEmoji").checked;

    if (!title) { alert("제목을 입력하세요."); return; }

    try {
      const res  = await fetch("/api/user_templates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        cache: "no-store",
        body: JSON.stringify({ title, category, tone, honorific, opener, emoji })
      });
      const data = await safeJson(res);

      if (res.status === 401) return alert("로그인이 필요합니다.");
      if (res.status === 403) return alert("Pro 구독이 필요합니다.");
      if (!res.ok || data.ok === false) return alert(data.message || "저장 중 오류가 발생했습니다.");

      await loadTemplates();
      closeDlg();
      alert("템플릿이 저장되었습니다.");
    } catch (err) {
      console.error("템플릿 저장 오류:", err);
      alert("네트워크 오류가 발생했습니다.");
    }
  });

  // 삭제
  delBtn?.addEventListener("click", async (e) => {
    e.preventDefault();
    const tplId = sel?.value;
    if (!tplId) return alert("삭제할 템플릿을 먼저 선택해주세요.");
    if (!confirm("정말 이 템플릿을 삭제하시겠습니까?")) return;

    try {
      const res  = await fetch(`/api/user_templates/${tplId}`, {
        method: "DELETE",
        credentials: "include",
        cache: "no-store",
      });
      const data = await safeJson(res);

      if (res.status === 401 || res.status === 403) return; // 조용히 종료(기존 유지)
      if (res.status === 404) return alert("이미 삭제된 템플릿입니다.");
      if (!res.ok || data.ok === false) return alert(data.message || "템플릿 삭제 실패");

      await loadTemplates();
      sel.value = "";
      alert("🗑️ 템플릿을 삭제했습니다.");
    } catch (err) {
      console.error("템플릿 삭제 오류:", err);
      alert("네트워크 오류가 발생했습니다. 다시 시도해주세요.");
    }
  });

  // 초기화 버튼
  resetBtn?.addEventListener("click", () => {
    clearAll();
  });

  // 첫 로드
  loadTemplates();
}

/* ------------------ 메인 초기화 + 단일 submit 핸들러 ------------------ */
document.addEventListener("DOMContentLoaded", () => {
  // 칩 바인딩
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

  // 서버 상태 복원
  restoreFromServer();

  // 복사 버튼
  bindCopyOutputButton();

  // 사용량 최초 로드
  updateUsageInfo();

  // 템플릿
  initTemplates();

  // submit 핸들러(단 하나)
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

      // 입력이 없으면: 스피너/disabled 절대 하지 않음
      if (!inputText) {
        alert("사용자 입력이 없습니다.");
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

      // 스피너 ON
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
          alert(`무료 사용 한도(${data.limit ?? "?"}회)를 모두 사용했습니다.\n\n로그인 또는 구독으로 한도를 늘려보세요.`);
          return;
        }

        if (!res.ok) {
          if (data?.error === "empty_input") {
            alert("사용자 입력이 없습니다.");
            return;
          }
          alert(data?.message || `요청 처리 중 오류가 발생했습니다. (${res.status})`);
          return;
        }

        // 성공 렌더
        const out = document.getElementById("output_text");
        if (!out) return;

        if (Array.isArray(data.outputs) && data.outputs.length) {
          renderOutputsInto(out, data.outputs);
        } else {
          out.textContent = data.output_text || "";
        }
      } catch (err) {
        alert("네트워크 오류가 발생했습니다. 다시 시도해주세요.");
      } finally {
        await updateUsageInfo();
        btn.classList.remove("loading");
        btn.removeAttribute("aria-busy");
        btn.disabled = false;
      }
    });
  }
});
