document.addEventListener('DOMContentLoaded', function() {
  const btn = document.getElementById('themeToggle');
  if (!btn) return;

  // body에 light 클래스를 붙여서 전환 (당신의 CSS 구조 유지)
  const body = document.body;
  const saved = localStorage.getItem('theme') || 'dark';

  if (saved === 'light') body.classList.add('light');

  btn.addEventListener('click', () => {
    body.classList.toggle('light');
    const isLight = body.classList.contains('light');
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
  });
});


document.addEventListener("DOMContentLoaded", () => {
  const sel = document.getElementById("lang-select-web");
  if (!sel) return;

  sel.addEventListener("change", () => {
    const url = sel.value;
    if (url) window.location.href = url;
  });
});

