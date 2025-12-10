// static/js/admin_usage.js
(async function () {
  const $ = (id) => document.getElementById(id);

  // --- DOM Elements ---
  const kpiUsageToday = $("kpi_usage_today");
  const kpiUsageWeek = $("kpi_usage_week");
  const kpiUsageMonth = $("kpi_usage_month");
  const usageChartBox = $("usage_chart_box");
  const periodSwitcher = $("period-switcher");

  const BASE_USAGE_API = "/admin/analytics/data/usage";

  // --- Utils ---
  const fmt = (n) => Number(n || 0).toLocaleString();

  // --- Custom Tooltip ---
  let tooltip;
  function createTooltip() {
    if ($("custom-tooltip")) return;
    const style = document.createElement('style');
    style.textContent = `
      .custom-tooltip {
        position: absolute;
        display: none;
        background: #111;
        color: #fff;
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 5px 10px;
        font-size: 12px;
        z-index: 1000;
        pointer-events: none;
        white-space: nowrap;
      }
    `;
    document.head.appendChild(style);
    tooltip = document.createElement('div');
    tooltip.id = 'custom-tooltip';
    tooltip.className = 'custom-tooltip';
    document.body.appendChild(tooltip);
  }

  // --- Rendering ---
  function renderBarChart(series) {
    if (!series || series.length === 0) {
      usageChartBox.innerHTML = `<div class="empty">표시할 데이터가 없습니다.</div>`;
      return;
    }
    const maxCount = Math.max(1, ...series.map(s => s.count));
    const bars = series.map(({ label, count }) => {
      const height = (count / maxCount) * 100;
      return `
        <div class="bar-wrap" data-label="${label}" data-count="${fmt(count)}">
          <div class="bar" style="height: ${height}%"></div>
          <div class="bar-label">${label}</div>
        </div>
      `;
    }).join("");

    usageChartBox.innerHTML = `
      <style>
        .chart-container { display: flex; align-items: flex-end; gap: 4px; width: 100%; height: 200px; border-bottom: 1px solid var(--border); padding: 0 4px; }
        .bar-wrap { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; text-align: center; cursor: pointer; }
        .bar { width: 75%; background-color: var(--accent); border-radius: 3px 3px 0 0; transition: background-color .2s; min-height:1px; }
        .bar-wrap:hover .bar { background-color: #91f2c3; }
        .bar-label { font-size: 10px; color: var(--muted); margin-top: 4px; white-space: nowrap; }
      </style>
      <div class="chart-container">${bars}</div>
    `;
  }

  // --- Data Loading ---
  async function loadUsageData(period = "month") {
    if(usageChartBox) usageChartBox.innerHTML = `<div class="empty">불러오는 중…</div>`;
    
    periodSwitcher.querySelectorAll('.btn').forEach(b => {
        b.classList.toggle('active', b.dataset.period === period);
    });

    try {
      const res = await fetch(`${BASE_USAGE_API}?period=${period}&t=${Date.now()}`, { 
        credentials: "same-origin", 
        cache: "no-store" 
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      
      if (kpiUsageToday) kpiUsageToday.textContent = fmt(data.kpi.today);
      if (kpiUsageWeek) kpiUsageWeek.textContent = fmt(data.kpi.week);
      if (kpiUsageMonth) kpiUsageMonth.textContent = fmt(data.kpi.month);

      renderBarChart(data.series);

    } catch (e) {
      console.error("[admin] usage load error:", e);
      if (usageChartBox) usageChartBox.innerHTML = `<div class="empty">사용량 데이터 로드 실패: ${String(e)}</div>`;
    }
  }

  // --- Event Listeners ---
  periodSwitcher?.addEventListener("click", (e) => {
    const btn = e.target.closest('button[data-period]');
    if (btn) {
      loadUsageData(btn.dataset.period);
    }
  });

  usageChartBox?.addEventListener('mouseover', (e) => {
    const barWrap = e.target.closest('.bar-wrap');
    if (!barWrap || !tooltip) return;
    tooltip.style.display = 'block';
    tooltip.innerHTML = `${barWrap.dataset.label}: <strong>${barWrap.dataset.count}</strong>`;
  });

  usageChartBox?.addEventListener('mouseout', (e) => {
    const barWrap = e.target.closest('.bar-wrap');
    if (!barWrap || !tooltip) return;
    tooltip.style.display = 'none';
  });

  usageChartBox?.addEventListener('mousemove', (e) => {
    if (!tooltip) return;
    tooltip.style.left = `${e.pageX + 15}px`;
    tooltip.style.top = `${e.pageY}px`;
  });

  // --- Initial Load ---
  createTooltip();
  loadUsageData("month");
})();
