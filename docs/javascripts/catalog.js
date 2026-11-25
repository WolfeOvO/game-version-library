/* Two presentations, one resource DOM; failures never hide links. */
(function () {
  'use strict';
  function mount() {
    const catalogs = [...document.querySelectorAll('[data-ore-catalog]')];
    if (!catalogs.length) return;
    let view = 'cards';
    try { if (localStorage.getItem('ore-catalog-view') === 'list') view = 'list'; } catch (_) {}
    function apply(next) {
      for (const catalog of catalogs) {
        catalog.dataset.catalogView = next;
        for (const button of catalog.querySelectorAll('button[data-catalog-view]')) {
          button.setAttribute('aria-pressed', String(button.dataset.catalogView === next));
        }
      }
    }
    for (const catalog of catalogs) {
      if (catalog.dataset.catalogReady) continue;
      catalog.dataset.catalogReady = 'true';
      const toolbar = catalog.querySelector('[data-catalog-toolbar], .ore-catalog-toolbar');
      if (!toolbar) continue;
      toolbar.addEventListener('click', function (event) {
        const button = event.target.closest('button[data-catalog-view]');
        if (!button || !toolbar.contains(button)) return;
        const next = button.dataset.catalogView;
        if (next !== 'cards' && next !== 'list') return;
        apply(next);
        try { localStorage.setItem('ore-catalog-view', next); } catch (_) {}
      });
      toolbar.hidden = false;
    }
    apply(view);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once:true});
  else mount();
})();
