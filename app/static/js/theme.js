(function(){
  const key = 'bw_theme';
  const root = document.documentElement;
  function apply(t){
    root.setAttribute('data-theme', t);
  }
  const saved = localStorage.getItem(key);
  if(saved){
    apply(saved);
  }
  const btn = document.getElementById('themeToggle');
  if(btn){
    btn.addEventListener('click', () => {
      const current = root.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      localStorage.setItem(key, next);
      apply(next);
    });
  }


  document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('topMenuToggle');
  const menu = document.getElementById('topMenu');
  if(!btn || !menu) return;

  btn.addEventListener('click', () => {
    const open = menu.classList.toggle('open');
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  // cerrar al tocar fuera
  document.addEventListener('click', (e) => {
    if(!menu.classList.contains('open')) return;
    const target = e.target;
    if(target === btn || btn.contains(target) || menu.contains(target)) return;
    menu.classList.remove('open');
    btn.setAttribute('aria-expanded', 'false');
  });
});


})();
