/* MC repository theme preference; preserves existing game controls. */
(function () {
  'use strict';
  const root = document.documentElement;
  const media = matchMedia('(prefers-color-scheme: dark)');
  let selected = 'system';
  try { selected = localStorage.getItem('ore-theme') || 'system'; } catch (_) {}
  function apply() {
    const resolved = selected === 'system' ? (media.matches ? 'dark' : 'light') : selected;
    root.setAttribute('data-ore-theme', resolved);
    root.style.colorScheme = resolved;
  }
  apply();
  media.addEventListener('change', apply);
  function addControl() {
    const body = document.querySelector('.ore-dialog[open] .ore-dialog-body');
    if (!body || body.querySelector('[data-ore-theme-control]') || !body.querySelector('.ore-setting-row')) return;
    const row = document.createElement('label');
    row.className = 'ore-setting-row';
    row.setAttribute('data-ore-theme-control', '');
    const label = document.createElement('span'); label.textContent = '界面主题';
    const control = document.createElement('select'); control.setAttribute('aria-label', '界面主题');
    for (const [value, text] of [['system','跟随系统'],['dark','深色'],['light','浅色']]) {
      const option = document.createElement('option'); option.value = value; option.textContent = text; control.append(option);
    }
    control.value = selected;
    control.addEventListener('change', () => {
      selected = control.value;
      try { localStorage.setItem('ore-theme', selected); } catch (_) {}
      apply();
    });
    row.append(label, control); body.append(row);
  }
  const observer = new MutationObserver(addControl);
  function mount() { observer.observe(document.body, {childList:true,subtree:true,attributes:true,attributeFilter:['open']}); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once:true}); else mount();
})();
