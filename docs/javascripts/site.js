(function () {
  'use strict';
  function mount() {
    document.body.dataset.renderer = 'standalone-ore';
    document.documentElement.dataset.oreSite = 'non-minecraft';
    document.querySelectorAll('.ore-tree a[aria-current="page"]').forEach(link => {
      let parent = link.parentElement;
      while (parent) {
        if (parent.tagName === 'DETAILS') parent.open = true;
        parent = parent.parentElement;
      }
    });
    const links = document.querySelectorAll('a[href^="http"]');
    for (const link of links) {
      if (link.origin !== location.origin) {
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
      }
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once: true});
  else mount();
})();
