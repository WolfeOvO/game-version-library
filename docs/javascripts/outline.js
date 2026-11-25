/* Build the page outline before the standalone navigation mounts. */
(function () {
  'use strict';
  function mount() {
    const article = document.querySelector('article#content');
    const list = document.querySelector('.ore-outline-list');
    if (!article || !list || list.childElementCount) return;
    for (const heading of article.querySelectorAll('h2[id],h3[id],h4[id],h5[id],h6[id]')) {
      const li = document.createElement('li');
      li.className = `ore-outline-level-${heading.tagName.slice(1)}`;
      const link = document.createElement('a');
      link.href = `#${encodeURIComponent(heading.id)}`;
      link.dataset.headingId = heading.id;
      link.textContent = heading.textContent.replace(/¶/g, '').trim();
      li.append(link);
      list.append(li);
    }
    if (list.childElementCount <= 1) {
      document.querySelector('.ore-outline-aside')?.setAttribute('hidden', '');
      document.querySelector('.ore-outline-trigger')?.setAttribute('hidden', '');
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once: true});
  else mount();
})();
