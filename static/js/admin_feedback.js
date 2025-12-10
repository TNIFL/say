
(() => {
  // ===== DOM =====
  const els = {
    box: document.getElementById("list_box"),
    pageLabel: document.getElementById("page_label"),
    countLabel: document.getElementById("count_label"),
    prevBtn: document.getElementById("prev_btn"),
    nextBtn: document.getElementById("next_btn"),
    fCat: document.getElementById("f_category"),
    fRes: document.getElementById("f_resolved"),
    fQ: document.getElementById("f_q"),
    btnApply: document.getElementById("btn_apply"),
    btnReset: document.getElementById("btn_reset"),
  };
  const CSRF = document.querySelector('meta[name="csrf-token"]')?.content || "";

  // ===== STATE =====
  let page = 1;
  let perPage = 20;
  let total = 0;

  // ===== UTILS =====
  const esc = (s) => String(s ?? "")
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;")
    .replace(/'/g,"&#39;");

  const setLoading = (msg = "불러오는 중…") => {
    els.box.innerHTML = `<div class="empty">${msg}</div>`;
  };

  const pageCount = () => Math.max(1, Math.ceil(total / perPage));

  // ===== RENDER =====
  function render(data) {
    total = data.total || 0;
    const items = Array.isArray(data.items) ? data.items : [];

    els.countLabel.textContent = `총 ${total}건`;
    els.pageLabel.textContent = `페이지 ${data.page} / ${pageCount()}`;

    if (!items.length) {
      setLoading("데이터가 없습니다");
      return;
    }

    const rows = items.map(r => `
      <tr class="row-link" data-row-id="${r.id}" data-href="/admin/feedback/${r.id}">
        <td class="muted" style="white-space:nowrap">${esc(r.created_at) || "-"}</td>
        <td style="white-space:nowrap">${esc(r.email || r.user_id) || "—"}</td>
        <td>${esc(r.category) || "—"}</td>
        <td style="word-break:break-word;">${esc(r.message) || ""}</td>
        <td style="white-space:nowrap">
          <span class="pill ${r.resolved ? "pill-ok" : "pill-no"}" data-pill>
            ${r.resolved ? "해결" : "미해결"}
          </span>
        </td>
        <td class="actions">
          <button class="btn sm" data-act="toggle" data-id="${r.id}">
            ${r.resolved ? "되돌리기" : "해결"}
          </button>
          <button class="btn sm" data-act="del" data-id="${r.id}">삭제</button>
        </td>
      </tr>
    `).join("");

    els.box.innerHTML = `
      <table class="table">
        <thead>
          <tr>
            <th>시각</th>
            <th>보낸이</th>
            <th>분류</th>
            <th>내용</th>
            <th>상태</th>
            <th>액션</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  // 행 클릭 → 상세로 이동 (버튼 클릭은 제외)
  els.box.addEventListener("click", (e) => {
    const actionBtn = e.target.closest("button[data-act]");
    if (actionBtn) return; // 액션 버튼은 행 네비 무시

    const tr = e.target.closest("tr.row-link[data-href]");
    if (tr) {
      const url = tr.getAttribute("data-href");
      if (url) window.location.href = url;
    }
  });

  // 액션: 해결/삭제 (버튼 클릭 시 행 네비 전파 방지)
  els.box.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;

    e.stopPropagation(); // 행 클릭 네비게이션 막기

    const id = btn.dataset.id;
    const act = btn.dataset.act;
    if (btn.disabled) return;
    btn.disabled = true;

    try {
      if (act === "toggle") {
        const res = await fetch(`/admin/feedback/${id}/resolve`, {
          method: "POST",
          credentials: "include",
          headers: { "X-CSRFToken": CSRF }
        });
        if (!res.ok) throw new Error(res.status);
        const data = await res.json();
        updateRowResolved(id, !!data.resolved);
      } else if (act === "del") {
        if (!confirm("정말 삭제할까요?")) return;
        const res = await fetch(`/admin/feedback/${id}`, {
          method: "DELETE",
          credentials: "include",
          headers: { "X-CSRFToken": CSRF }
        });
        if (!res.ok) throw new Error(res.status);

        const tr = document.querySelector(`tr[data-row-id="${id}"]`);
        if (tr) tr.remove();
        total = Math.max(0, total - 1);
        els.countLabel.textContent = `총 ${total}건`;
        els.pageLabel.textContent = `페이지 ${page} / ${pageCount()}`;
        if (!document.querySelector('#list_box tbody tr')) {
          if (page > 1) page -= 1;
          load();
        }
      }
    } catch (err) {
      alert("실패: " + err);
    } finally {
      btn.disabled = false;
    }
});

  // 행 상태만 즉시 반영(토글 후 깔끔한 하이라이트)
  function updateRowResolved(id, resolved){
    const tr   = document.querySelector(`tr[data-row-id="${id}"]`);
    if (!tr) return;
    const pill = tr.querySelector('[data-pill]');
    const btn  = tr.querySelector('button[data-act="toggle"]');
    if (pill){
      pill.textContent = resolved ? "해결" : "미해결";
      pill.classList.toggle("pill-ok", resolved);
      pill.classList.toggle("pill-no", !resolved);
    }
    if (btn){
      btn.textContent = resolved ? "되돌리기" : "해결";
    }
    tr.classList.remove("flash-ok", "flash-no");
    void tr.offsetWidth; // reflow
    tr.classList.add(resolved ? "flash-ok" : "flash-no");
    setTimeout(() => tr.classList.remove("flash-ok", "flash-no"), 500);
  }

  // ===== LOAD =====
  async function load() {
    setLoading();
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (els.fCat.value) params.set("category", els.fCat.value);
    if (els.fRes.value) params.set("resolved", els.fRes.value);
    if (els.fQ.value.trim()) params.set("q", els.fQ.value.trim());

    try {
      const res = await fetch(`/admin/feedback/data?${params.toString()}`, {
        credentials: "include",
        cache: "no-store"
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      render(data);
    } catch (e) {
      console.error(e);
      setLoading("로드 실패");
    }
  }

  // ===== EVENTS =====
  // 액션: 해결/삭제
  els.box.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const id = btn.dataset.id;
    const act = btn.dataset.act;

    if (btn.disabled) return;
    btn.disabled = true;

    try {
      if (act === "toggle") {
        const res = await fetch(`/admin/feedback/${id}/resolve`, {
          method: "POST",
          credentials: "include",
          headers: { "X-CSRFToken": CSRF }
        });
        if (!res.ok) throw new Error(res.status);
        const data = await res.json(); // { ok:true, resolved: bool }
        updateRowResolved(id, !!data.resolved);

      } else if (act === "del") {
        if (!confirm("정말 삭제할까요?")) return;
        const res = await fetch(`/admin/feedback/${id}`, {
          method: "DELETE",
          credentials: "include",
          headers: { "X-CSRFToken": CSRF }
        });
        if (!res.ok) throw new Error(res.status);

        // 행 제거 및 카운팅 보정
        const tr = document.querySelector(`tr[data-row-id="${id}"]`);
        if (tr) tr.remove();
        total = Math.max(0, total - 1);
        els.countLabel.textContent = `총 ${total}건`;
        els.pageLabel.textContent = `페이지 ${page} / ${pageCount()}`;

        // 현재 페이지가 비면 재로딩(마지막 한 건 삭제 등)
        if (!document.querySelector('#list_box tbody tr')) {
          // 페이지가 1보다 크고 현재 페이지가 비었으면 한 페이지 당겨서 로드
          if (page > 1) page -= 1;
          load();
        }
      }
    } catch (err) {
      alert("실패: " + err);
    } finally {
      btn.disabled = false;
    }
  });

  // 페이지네이션
  els.prevBtn.addEventListener("click", () => {
    if (page > 1) { page -= 1; load(); }
  });
  els.nextBtn.addEventListener("click", () => {
    if (page < pageCount()) { page += 1; load(); }
  });

  // 필터
  els.btnApply.addEventListener("click", () => { page = 1; load(); });
  els.btnReset.addEventListener("click", () => {
    els.fCat.value = "";
    els.fRes.value = "";
    els.fQ.value = "";
    page = 1;
    load();
  });

  // ===== FIRST LOAD =====
  load();
})();

