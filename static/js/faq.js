// static/js/faq.js
document.addEventListener("DOMContentLoaded", () => {
  const items = document.querySelectorAll(".faq-item");

  items.forEach((item, idx) => {
    const header = item.querySelector(".faq-q");
    const btn = header?.querySelector("button");
    const answer = item.querySelector(".faq-a");

    if (!btn || !answer) return;

    // 접근성: aria 속성 셋업
    const answerId = answer.id || `faq-a-${idx}`;
    answer.id = answerId;
    btn.setAttribute("aria-controls", answerId);
    btn.setAttribute("aria-expanded", "false");
    answer.setAttribute("role", "region");
    answer.setAttribute("aria-labelledby", btn.id || `faq-btn-${idx}`);
    if (!btn.id) btn.id = `faq-btn-${idx}`;

    // 처음엔 닫힘 상태를 명시
    answer.hidden = true;

    const toggle = () => {
      const isOpen = item.classList.toggle("open");
      btn.setAttribute("aria-expanded", String(isOpen));
      answer.hidden = !isOpen;
    };

    // 버튼 클릭으로 토글
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      toggle();
    });

    // 질문줄 전체(.faq-q) 클릭도 허용 (버튼 외 영역 클릭 대비)
    header.addEventListener("click", (e) => {
      // 버튼 클릭과 중복 방지
      if (e.target === btn || btn.contains(e.target)) return;
      toggle();
    });

    // 키보드 접근: Enter/Space 지원 (헤더 포커스 시)
    header.tabIndex = 0;
    header.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggle();
      }
    });
  });
});
