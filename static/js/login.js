// 비밀번호 보기 토글
(function pwdToggle(){
  const btn = document.getElementById('pwdToggle');
  const input = document.getElementById('password');
  if (!btn || !input) return; // Add a check if elements exist
  btn.addEventListener('click', ()=>{
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    btn.textContent = show ? '숨기기' : '보기';
    btn.setAttribute('aria-pressed', String(show));
  });
})();