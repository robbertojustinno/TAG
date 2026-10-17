(() => {
  const key = 'tagcheck.theme';
  let theme = 'dark';
  try { if (localStorage.getItem(key) === 'light') theme = 'light'; } catch (_) {}
  function apply(value) {
    theme = value === 'light' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    const button = document.getElementById('themeToggle');
    if (button) {
      const en = document.documentElement.lang.startsWith('en');
      button.textContent = theme === 'light' ? (en ? 'Dark theme' : 'Tema escuro') : (en ? 'Light theme' : 'Tema claro');
      button.setAttribute('aria-label', en ? 'Switch color theme' : 'Alternar tema claro e escuro');
      button.setAttribute('aria-pressed', String(theme === 'light'));
    }
  }
  apply(theme);
  document.addEventListener('DOMContentLoaded', () => {
    apply(theme);
    document.getElementById('themeToggle')?.addEventListener('click', () => {
      apply(theme === 'dark' ? 'light' : 'dark');
      try { localStorage.setItem(key, theme); } catch (_) {}
    });
    new MutationObserver(() => apply(theme)).observe(document.documentElement, {attributes:true, attributeFilter:['lang']});
  });
  window.addEventListener('storage', event => { if (event.key === key) apply(event.newValue); });
})();
