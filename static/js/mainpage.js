/* ============================================================
 *  Lexinoa mainpage.js — 2025.11 안정 버전
 *  기능:
 *    - 테마 토글 (다크/라이트)
 *    - 카테고리 / 말투 칩 관리 + hidden input 자동 동기화
 *    - 서버 상태 복원
 *    - 체크박스 초기화
 *    - 출력 복사 / 제출 스피너
 * ============================================================ */

// ----- 테마 토글 -----
(function themeToggle() {
  const btn = document.getElementById("themeToggle");
  if (!btn) return;
  const saved = localStorage.getItem("theme") || "dark";
  if (saved === "light") document.body.classList.add("light");
  btn.addEventListener("click", () => {
    document.body.classList.toggle("light");
    localStorage.setItem(
      "theme",
      document.body.classList.contains("light") ? "light" : "dark"
    );
  });
})();

// ----- 칩 유틸리티 -----
function createChip(text, value, group, hiddenContainer, inputName) {
  if (document.querySelector(`.${group}-chip[data-value="${CSS.escape(value)}"]`))
    return;
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
  hid.name = inputName; // ✅ Flask 스키마에 맞춤 (selected_categories / selected_tones)
  hid.value = value;
  hid.dataset.value = value;

  return { chip, hid };
}

function addItem(selectEl, chipsBoxEl, hiddenBoxEl, group, inputName) {
  const opt = selectEl.options[selectEl.selectedIndex];
  if (!opt || !opt.value) return;
  const made = createChip(opt.text, opt.value, group, hiddenBoxEl, inputName) || {};
  if (!made.chip || !made.hid) return;
  chipsBoxEl.appendChild(made.chip);
  hiddenBoxEl.appendChild(made.hid);
  selectEl.selectedIndex = 0;
}

function removeItem(value, group, chipsBoxEl, hiddenBoxEl) {
  const chip = chipsBoxEl.querySelector(
    `.${group}-chip[data-value="${CSS.escape(value)}"]`
  );
  const hid = hiddenBoxEl.querySelector(
    `input[data-value="${CSS.escape(value)}"]`
  );
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
}
//결과 렌더 헬퍼 (복사버튼 포함)
function renderOutputsInto(container, outputs) {
  if (!container) return;
  container.innerHTML = "";

  const isPro = document.getElementById("bootstrap")?.dataset.isPro === "true";
  const wrap = document.createElement("div");
  wrap.className = "outputs-wrap";

  outputs.forEach((txt, i) => {
    const card = document.createElement("div");
    card.className = "output-card";

    // 헤더
    const head = document.createElement("div");
    head.className = "output-card-head small hint";
    head.textContent = `결과 ${i + 1}`;

    // 복사 버튼 (Pro만 표시)
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

    // 본문
    const body = document.createElement("div");
    body.className = "output";
    body.textContent = txt || ""; // XSS 안전

    card.appendChild(head);
    card.appendChild(body);
    wrap.appendChild(card);
  });

  // 전체 복사 버튼 (1개 이상일 때)
  if (outputs.length > 1) {
    const allCopyBtn = document.createElement("button");
    allCopyBtn.type = "button";
    allCopyBtn.className = "btn secondary";
    allCopyBtn.textContent = "전체 복사";
    allCopyBtn.style.marginTop = "8px";

    allCopyBtn.addEventListener("click", async () => {
      const combined = outputs.join("\n\n");
      try {
        await navigator.clipboard.writeText(combined);
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



// ----- 초기 바인딩 -----
(function bind() {
  const cSel = document.getElementById("categorySelect");
  const tSel = document.getElementById("toneSelect");
  const cChips = document.getElementById("categoryChips");
  const tChips = document.getElementById("toneChips");
  const cHidden = document.getElementById("categoryHidden");
  const tHidden = document.getElementById("toneHidden");
  if (!cSel || !tSel || !cChips || !tChips || !cHidden || !tHidden) return;

  // ✅ Flask 스키마에 맞게 필드명 변경
  cSel.addEventListener("change", () => {
    addItem(cSel, cChips, cHidden, "category", "selected_categories");
  });
  tSel.addEventListener("change", () => {
    addItem(tSel, tChips, tHidden, "tone", "selected_tones");
  });

  // 칩 클릭 제거 (이벤트 위임)
  cChips.addEventListener("click", (e) => {
    const btn = e.target.closest(".category-chip");
    if (!btn) return;
    removeItem(btn.dataset.value, "category", cChips, cHidden);
  });
  tChips.addEventListener("click", (e) => {
    const btn = e.target.closest(".tone-chip");
    if (!btn) return;
    removeItem(btn.dataset.value, "tone", tChips, tHidden);
  });

  const clearBtn = document.getElementById("clearAll");
  if (clearBtn) clearBtn.addEventListener("click", clearAll);
})();

// ----- 서버 상태 복원 (data-*에서 읽기) -----
(function restoreFromServer() {
  const boot = document.getElementById("bootstrap");
  if (!boot) return;

  let preCats = [];
  let preTones = [];
  try {
    preCats = JSON.parse(boot.dataset.selectedCategories || "[]");
  } catch {}
  try {
    preTones = JSON.parse(boot.dataset.selectedTones || "[]");
  } catch {}

  const honorificChecked = boot.dataset.honorific === "true";
  const openerChecked = boot.dataset.opener === "true";
  const emojiChecked = boot.dataset.emoji === "true";

  const cSel = document.getElementById("categorySelect");
  const tSel = document.getElementById("toneSelect");
  const cChips = document.getElementById("categoryChips");
  const tChips = document.getElementById("toneChips");
  const cHidden = document.getElementById("categoryHidden");
  const tHidden = document.getElementById("toneHidden");

  // 체크박스 복원
  const honor = document.getElementById("honorific");
  const openr = document.getElementById("opener");
  const emoji = document.getElementById("emoji");
  if (honor) honor.checked = honorificChecked;
  if (openr) openr.checked = openerChecked;
  if (emoji) emoji.checked = emojiChecked;

  // ✅ 카테고리 칩 복원
  if (Array.isArray(preCats)) {
    preCats.forEach((val) => {
      const opt = Array.from(cSel.options || []).find((o) => o.value === val);
      if (!opt) return;
      const made = createChip(opt.text, val, "category", cHidden, "selected_categories");
      if (made) {
        cChips.appendChild(made.chip);
        cHidden.appendChild(made.hid);
      }
    });
  }

  // ✅ 말투 칩 복원
  if (Array.isArray(preTones)) {
    preTones.forEach((val) => {
      const opt = Array.from(tSel.options || []).find((o) => o.value === val);
      if (!opt) return;
      const made = createChip(opt.text, val, "tone", tHidden, "selected_tones");
      if (made) {
        tChips.appendChild(made.chip);
        tHidden.appendChild(made.hid);
      }
    });
  }
})();

// ----- 출력 복사 버튼 -----
(function copyOutputButton() {
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
      setTimeout(() => {
        btn.textContent = labelOrig;
      }, 1200);
    }
  });
})();

// ----- 제출 스피너 -----
(function attachSubmitSpinner() {
  const form = document.getElementById("polishForm");
  const btn = document.getElementById("submitBtn");
  if (!form || !btn) return;
  form.addEventListener("submit", () => {
    setTimeout(() => {
      btn.classList.add("loading");
      btn.setAttribute("aria-busy", "true");
      btn.disabled = true;
    }, 80);
  });
})();

//429
// ===== 교체용: 제출 핸들러 전체 =====
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("polishForm");
  const btn  = document.getElementById("submitBtn");
  if (!form || !btn) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    e.stopPropagation();

    // 로딩 스피너 ON
    btn.classList.add("loading");
    btn.setAttribute("aria-busy", "true");
    btn.disabled = true;

    // 폼 값 수집
    const input = document.getElementById("input_text");
    const providerSel = form.querySelector("[name='provider']");
    const categories = [...document.querySelectorAll("#categoryHidden input[name='selected_categories']")].map(el => el.value);
    const tones      = [...document.querySelectorAll("#toneHidden input[name='selected_tones']")].map(el => el.value);
    const honorific  = document.getElementById("honorific")?.checked ?? false;
    const opener     = document.getElementById("opener")?.checked ?? false;
    const emoji      = document.getElementById("emoji")?.checked ?? false;

    const payload = {
      input_text: (input?.value || "").trim(),
      selected_categories: categories,
      selected_tones: tones,
      honorific_checked: honorific,
      opener_checked: opener,
      emoji_checked: emoji,
      provider: (providerSel?.value || "claude")
    };

    try {
      const res = await fetch("/api/polish", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",   // 세션/쿠키 포함
        body: JSON.stringify(payload),
        provider: "claude"
      });

      if (res.status === 429) {
        const data = await res.json().catch(() => ({}));
        alert(`무료 사용 한도(${data.limit ?? "?"}회)를 모두 사용했습니다.\n\n로그인 또는 구독으로 한도를 늘려보세요.`);
        return;
      }
      if (!res.ok) {
        alert(`요청 처리 중 오류가 발생했습니다. ${res.status} 오류`);
        return;
      }

      const data = await res.json();
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
      // 성공/실패 상관없이 최신 사용량 갱신
      await updateUsageInfo();

      // 로딩 스피너 OFF
      btn.classList.remove("loading");
      btn.removeAttribute("aria-busy");
      btn.disabled = false;
    }
  });
});


async function updateUsageInfo() {
  const el = document.getElementById("usageInfo");
  if (!el) return;
  try {
    const res = await fetch(`/api/usage?t=${Date.now()}`, {
      method: "GET",
      credentials: "include",   // ✅ 쿠키 포함
      cache: "no-store"         // ✅ 캐시 무효화
    });
    if (!res.ok) throw new Error();
    const data = await res.json();
    const label = data.tier === "guest" ? "비로그인"
                : data.tier === "free"  ? "회원"
                : "구독";
    el.textContent = `총 ${data.limit}회 / ${data.limit - data.used}회 남음 (${label})`;
  } catch {
    /* 실패 시 표시 유지 */
  }
}
document.addEventListener("DOMContentLoaded", updateUsageInfo);
/* ============================================================
 * 템플릿 라이브러리 (즉시 적용형) — FINAL FIX
 *  - 목록/추가/삭제 일관 JSON 파싱
 *  - loadTemplates 스코프 노출 문제 해결
 * ============================================================ */

// 공통: 안전 JSON 파서 (빈 본문/304 대비)
async function safeJson(res) {
  try {
    const txt = await res.text();
    return txt ? JSON.parse(txt) : {};
  } catch {
    return {};
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const sel       = document.getElementById("templateSelect");
  const addBtn    = document.getElementById("btnTemplateAdd");
  const resetBtn  = document.getElementById("resetTemplateBtn");
  const delBtn    = document.getElementById("btnTemplateDelete");

  // 다이얼로그 요소
  const dlg       = document.getElementById("tplDialog");
  const btnClose  = document.getElementById("tplClose");
  const btnCancel = document.getElementById("tplCancel");
  const btnSave   = document.getElementById("tplSave");

  if (!sel) return; // Pro UI가 없으면 종료

  // 1) 목록 불러오기 (둘 다 지원: {items:[...]} 또는 [...] )
  async function loadTemplates() {
    try {
      const res  = await fetch("/api/user_templates", {
        method: "GET",
        credentials: "include",
        cache: "no-store",
      });
      const data = await safeJson(res);

      if (res.status === 401 || res.status === 403) {
        //아무것도 안함
        return;
      }
      //if (res.status === 401) return alert("로그인이 필요합니다.");
      //if (res.status === 403) return alert("Pro 구독이 필요합니다.");
      if (!res.ok) {
        console.warn("템플릿 목록 실패:", data);
        return;
      }
      const list = Array.isArray(data?.items) ? data.items
                 : Array.isArray(data)       ? data
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

  // ✨ 전역에서 호출할 수 있게 노출 (삭제 후 새로고침 등에서 사용)
  window.loadTemplates = loadTemplates;

  // 2) 선택 즉시 적용
  sel.addEventListener("change", (e) => {
    const opt = e.target.selectedOptions[0];
    if (!opt) return;

    // 초기화
    document.getElementById("categoryChips").innerHTML  = "";
    document.getElementById("toneChips").innerHTML      = "";
    document.getElementById("categoryHidden").innerHTML = "";
    document.getElementById("toneHidden").innerHTML     = "";

    // 카테고리
    if (opt.dataset.category) {
      const cSel  = document.getElementById("categorySelect");
      const match = Array.from(cSel.options).find(o => o.value === opt.dataset.category);
      const made  = createChip(match?.text || opt.dataset.category, opt.dataset.category,
                               "category", document.getElementById("categoryHidden"), "selected_categories");
      if (made) {
        document.getElementById("categoryChips").appendChild(made.chip);
        document.getElementById("categoryHidden").appendChild(made.hid);
      }
    }
    // 톤
    if (opt.dataset.tone) {
      const tSel  = document.getElementById("toneSelect");
      const match = Array.from(tSel.options).find(o => o.value === opt.dataset.tone);
      const made  = createChip(match?.text || opt.dataset.tone, opt.dataset.tone,
                               "tone", document.getElementById("toneHidden"), "selected_tones");
      if (made) {
        document.getElementById("toneChips").appendChild(made.chip);
        document.getElementById("toneHidden").appendChild(made.hid);
      }
    }
    // 체크박스
    document.getElementById("honorific").checked = opt.dataset.honorific === "true";
    document.getElementById("opener").checked    = opt.dataset.opener    === "true";
    document.getElementById("emoji").checked     = opt.dataset.emoji     === "true";
  });

  // 3) 추가 버튼 → 다이얼로그 열기
  addBtn?.addEventListener("click", () => {
    if (!dlg) return;
    if (typeof dlg.showModal === "function") dlg.showModal();
    else dlg.setAttribute("open", "");
  });

  // 다이얼로그 닫기
  const closeDlg = () => {
    if (!dlg) return;
    if (typeof dlg.close === "function") dlg.close();
    else dlg.removeAttribute("open");
  };
  btnClose?.addEventListener("click", closeDlg);
  btnCancel?.addEventListener("click", closeDlg);

  // 4) 다이얼로그 저장 → 생성 → 목록 갱신
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
      if (!res.ok || (data.ok === false)) {
        console.error("저장 실패:", data);
        return alert(data.message || "저장 중 오류가 발생했습니다.");
      }

      await loadTemplates();
      closeDlg();
      alert("✅ 템플릿이 저장되었습니다.");
    } catch (err) {
      console.error("템플릿 저장 오류:", err);
      alert("네트워크 오류가 발생했습니다.");
    }
  });

  // 5) 삭제 버튼
  // 5) 삭제 버튼
  delBtn?.addEventListener("click", async (e) => {
    e.preventDefault(); // 폼 submit 방지(프린트 창 방지)
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

      // 401 / 403 → 조용히 무시 (알럿 안 띄우겠다고 했으니까)
      if (res.status === 401 || res.status === 403) {
        console.warn("템플릿 삭제 권한 없음:", res.status, data);
        return;
      }

      if (res.status === 404) {
        alert("이미 삭제된 템플릿입니다.");
        return;
      }

      if (!res.ok || data.ok === false) {
        console.error("삭제 실패:", data);
        alert(data.message || "템플릿 삭제 실패");
        return;
      }

      await loadTemplates();
      sel.value = "";
      alert("🗑️ 템플릿을 삭제했습니다.");
    } catch (err) {
      console.error("템플릿 삭제 오류:", err);
      alert("네트워크 오류가 발생했습니다. 다시 시도해주세요.");
    }
  });


  // 6) 초기화
  resetBtn?.addEventListener("click", () => {
    document.getElementById("categoryChips").innerHTML  = "";
    document.getElementById("toneChips").innerHTML      = "";
    document.getElementById("categoryHidden").innerHTML = "";
    document.getElementById("toneHidden").innerHTML     = "";
    document.getElementById("honorific").checked = false;
    document.getElementById("opener").checked    = false;
    document.getElementById("emoji").checked     = false;
    sel.value = "";
  });

  // 7) 첫 로드
  loadTemplates();
});
