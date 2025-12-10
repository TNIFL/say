// static/js/admin_analytics.js
(async function () {
  const $ = (id) => document.getElementById(id);

  // 방문자 KPI 카드
  const kpiToday = $("kpi_today");
  const kpiWeek  = $("kpi_week");
  const kpiMonth = $("kpi_month");
  const seriesBox = $("series_box");

  // 사용량 KPI 카드
  const kpiUsageToday = $("kpi_usage_today");
  const kpiUsageWeek = $("kpi_usage_week");
  const kpiUsageMonth = $("kpi_usage_month");
  const usageChartBox = $("usage_chart_box");

  // 필터 UI
  const fromInput = $("f_from");
  const toInput   = $("f_to");
  const pathSel   = $("f_path");
  const userInput = $("f_user");
  const btnApply  = $("btn_apply");
  const btnReset  = $("btn_reset");

  const BASE_VISITS = "/admin/analytics/data/visits";
  const BASE_USAGE = "/admin/analytics/data/usage";

  const fmt = (n) => Number(n || 0).toLocaleString();

  function ymd(d) {
    const Y = d.getFullYear();
    const M = String(d.getMonth() + 1).padStart(2, "0");
    const D = String(d.getDate()).padStart(2, "0");
    return `${Y}-${M}-${D}`;
  }
  function addDays(dateObj, delta) { const d = new Date(dateObj); d.setDate(d.getDate() + delta); return d; }
  function firstDayOfMonth(dateObj) { return new Date(dateObj.getFullYear(), dateObj.getMonth(), 1); }

  function extractSeries(json) {
    return Array.isArray(json?.series) ? json.series : [];
  }

  function renderSeriesTable(series, container, title, unit) {
    if (!series || series.length === 0) {
      container.innerHTML = `<div class="empty">표시할 데이터가 없습니다.</div>`;
      return;
    }
    const rows = series.map(({ date, count }) => `
      <tr>
        <td style="padding:6px 8px; border-bottom:1px solid var(--border)">${date}</td>
        <td style="padding:6px 8px; border-bottom:1px solid var(--border); text-align:right">${fmt(count)}</td>
      </tr>`).join("");

    container.innerHTML = `
      <div class="muted" style="margin-bottom:8px">${title}</div>
      <table style="width:100%; border-collapse:collapse">
        <thead>
          <tr>
            <th style="text-align:left; padding:6px 8px; border-bottom:1px solid var(--border)">날짜</th>
            <th style="text-align:right; padding:6px 8px; border-bottom:1px solid var(--border)">${unit}</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  function renderBarChart(series, container) {
    if (!series || series.length === 0) {
      container.innerHTML = `<div class="empty">표시할 데이터가 없습니다.</div>`;
      return;
    }
    const maxCount = Math.max(1, ...series.map(s => s.count));
    const bars = series.map(({ date, count }) => {
      const height = (count / maxCount) * 100;
      return `
        <div class="bar-wrap" title="${date}: ${fmt(count)}">
          <div class="bar" style="height: ${height}%"></div>
        </div>
      `;
    }).join("");

    container.innerHTML = `
      <style>
        .chart-container { display: flex; align-items: flex-end; gap: 2px; width: 100%; height: 180px; border-bottom: 1px solid var(--border); padding: 0 4px; }
        .bar-wrap { flex: 1; display: flex; align-items: flex-end; height: 100%; }
        .bar { width: 100%; background-color: var(--accent); border-radius: 2px 2px 0 0; transition: background-color .2s; }
        .bar-wrap:hover .bar { background-color: #91f2c3; }
      </style>
      <div class="chart-container">${bars}</div>
    `;
  }

  async function loadVisitsStats() {
    try {
      const res = await fetch(`${BASE_VISITS}?t=${Date.now()}`, { credentials: "same-origin", cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      const series = extractSeries(json);
      
      const today = series.find(s => s.date === ymd(new Date()))?.count || 0;
      const weekStart = addDays(new Date(), -6);
      const weekSum = series.filter(s => new Date(s.date) >= weekStart).reduce((sum, s) => sum + s.count, 0);
      const monthSum = series.filter(s => s.date.startsWith(ymd(new Date()).substring(0, 7))).reduce((sum, s) => sum + s.count, 0);

      if (kpiToday) kpiToday.textContent = fmt(today);
      if (kpiWeek) kpiWeek.textContent = fmt(weekSum);
      if (kpiMonth) kpiMonth.textContent = fmt(monthSum);
      
      renderSeriesTable(series, seriesBox, `최근 ${series.length}일 방문자`, '방문 수');
    } catch (e) {
      console.error("[admin] visits load error:", e);
      if (seriesBox) seriesBox.innerHTML = `<div class="empty">방문자 데이터 로드 실패: ${String(e)}</div>`;
    }
  }

  async function loadUsageStats() {
    try {
      const res = await fetch(`${BASE_USAGE}?t=${Date.now()}`, { credentials: "same-origin", cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      
      if (kpiUsageToday) kpiUsageToday.textContent = fmt(json.today);
      if (kpiUsageWeek) kpiUsageWeek.textContent = fmt(json.week);
      if (kpiUsageMonth) kpiUsageMonth.textContent = fmt(json.month);

      const series = extractSeries(json);
      renderBarChart(series, usageChartBox);
    } catch (e) {
      console.error("[admin] usage load error:", e);
      if (usageChartBox) usageChartBox.innerHTML = `<div class="empty">사용량 데이터 로드 실패: ${String(e)}</div>`;
    }
  }

  async function applyVisitFilters() {
    const p = new URLSearchParams();
    if (fromInput?.value) p.set("from", fromInput.value);
    if (toInput?.value) p.set("to", toInput.value);
    if (pathSel?.value) p.set("path", pathSel.value);
    if (userInput?.value) p.set("user", userInput.value);
    p.set("t", Date.now());

    try {
      const res = await fetch(`${BASE_VISITS}?${p.toString()}`, { credentials: "same-origin", cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      const series = extractSeries(json);
      renderSeriesTable(series, seriesBox, '필터된 기간의 방문자', '방문 수');
    } catch (e) {
      console.error("[admin] filter error:", e);
      seriesBox.innerHTML = `<div class="empty">필터 로드 실패: ${String(e)}</div>`;
    }
  }

  btnApply?.addEventListener("click", applyVisitFilters);
  btnReset?.addEventListener("click", () => {
    if (fromInput) fromInput.value = "";
    if (toInput) toInput.value = "";
    if (pathSel) pathSel.value = "";
    if (userInput) userInput.value = "";
    applyVisitFilters();
  });

  // 초기 로드
  loadVisitsStats();
  loadUsageStats();
})();
