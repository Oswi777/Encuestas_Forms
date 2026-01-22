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
})();
