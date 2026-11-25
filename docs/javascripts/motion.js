/* Semantic Ore motion: no hidden content pending JS/observer initialization. */
(function(){'use strict';let mounted=false;function mount(root=document){if(mounted)return;mounted=true;const reduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches||document.body.classList.contains('ux-motion-disabled');if('IntersectionObserver'in window){const observer=new IntersectionObserver(entries=>{const visible=entries.filter(e=>e.isIntersecting);visible.forEach(e=>{if(!reduced())e.target.classList.add('ux-pop');observer.unobserve(e.target);});},{rootMargin:'0px 0px 20px'});const targets=[...root.querySelectorAll('article h1,article h2,article h3,article p,article details,article .admonition')].filter(e=>!e.closest('.tabbed-labels'));targets.forEach(e=>observer.observe(e));}root.querySelectorAll('article table').forEach(table=>{if(table.parentElement.classList.contains('ore-table-wrap'))return;const wrap=document.createElement('div');wrap.className='ore-table-wrap';table.before(wrap);wrap.append(table);});/* Pointer/keyboard parity for the same visual face; no synthetic clicks. */
const pressSelector='.md-button,.dl-opts__btn,.ore-button,.ore-top,.ore-outline-trigger,.ore-appbar button,.ore-dialog-head button,.ore-copy,.tabbed-button';
let pressed=null,pointerId=null,pressKey=null;
function clearPress(){if(pressed)pressed.classList.remove('ore-pressed');pressed=null;pointerId=null;pressKey=null;}
function pressTarget(target){if(!(target instanceof Element))return null;const e=target.closest(pressSelector);return e&&!e.closest('.dl-opts__menu')&&!e.matches(':disabled,[aria-disabled="true"]')?e:null;}
root.addEventListener('pointerdown',e=>{if(!e.isPrimary||e.button!==0)return;clearPress();const b=pressTarget(e.target);if(b){pressed=b;pointerId=e.pointerId;b.classList.add('ore-pressed');}},{passive:true});
root.addEventListener('pointermove',e=>{if(!pressed||pointerId!==e.pointerId)return;const r=pressed.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)clearPress();},{passive:true});
function releasePointer(e){if(pointerId===e.pointerId)clearPress();}
root.addEventListener('pointerup',releasePointer,true);root.addEventListener('pointercancel',releasePointer,true);
root.addEventListener('keydown',e=>{if(e.repeat||e.altKey||e.ctrlKey||e.metaKey||![' ','Enter'].includes(e.key))return;const b=pressTarget(e.target);if(!b||(b.tagName==='A'&&e.key===' '))return;clearPress();pressed=b;pressKey=e.key;b.classList.add('ore-pressed');});
root.addEventListener('keyup',e=>{if(e.key===pressKey)clearPress();},true);root.addEventListener('focusout',clearPress,true);
window.addEventListener('blur',clearPress);window.addEventListener('pagehide',clearPress);root.addEventListener('visibilitychange',()=>{if(document.hidden)clearPress();});

/* Page-navigation disclosure motion, scoped to native details in the drawer. */
const treeStates=new Map();
function revealExpandedTree(detail){
 const drawer=detail.closest('dialog[aria-label="版本库导航"]');
 if(!drawer||!drawer.open)return;
 const viewport=drawer.getBoundingClientRect(),summary=detail.querySelector(':scope > summary'),list=detail.querySelector(':scope > ul');
 if(!summary||!list)return;
 const top=viewport.top+drawer.clientTop+8,bottom=viewport.top+drawer.clientTop+drawer.clientHeight-8;
 const heading=summary.getBoundingClientRect(),content=list.getBoundingClientRect();
 const delta=content.bottom-heading.top<=bottom-top?Math.max(0,content.bottom-bottom):Math.max(0,heading.top-top);
 if(delta>0)drawer.scrollBy({top:delta,behavior:'instant'});
}
function settleTree(detail,state){
 if(treeStates.get(detail)!==state)return;
 treeStates.delete(detail);
 if(state.animation)state.animation.cancel();
 if(state.frame)cancelAnimationFrame(state.frame);
 detail.open=state.expanded;
 state.summary.setAttribute('aria-expanded',String(state.expanded));
 state.list.style.overflow=state.overflow;state.list.inert=state.inert;
 if(state.expanded)revealExpandedTree(detail);
}
function settleAllTrees(){for(const [detail,state] of treeStates)settleTree(detail,state);}
root.addEventListener('click',e=>{
 const target=e.target instanceof Element?e.target:null;
 const summary=target&&target.closest('.ore-tree summary');
 if(!summary||target.closest('a[href]')||e.defaultPrevented)return;
 const detail=summary.parentElement,list=detail.querySelector(':scope > ul');
 if(!list)return;
 e.preventDefault();
 for(const [ancestor,state] of treeStates){if(ancestor!==detail&&(ancestor.contains(detail)||detail.contains(ancestor)))settleTree(ancestor,state);}
 const previous=treeStates.get(detail),expanded=!(previous?previous.expanded:detail.open);
 const height=detail.open?list.getBoundingClientRect().height:0;
 const opacity=detail.open?Number(getComputedStyle(list).opacity):0;
 const overflow=previous?previous.overflow:list.style.overflow;
 const inert=previous?previous.inert:list.inert;
 if(previous){treeStates.delete(detail);if(previous.animation)previous.animation.cancel();if(previous.frame)cancelAnimationFrame(previous.frame);}
 detail.open=true;summary.setAttribute('aria-expanded',String(expanded));
 const state={list,summary,expanded,overflow,inert,animation:null,frame:0};treeStates.set(detail,state);
 if(reduced()||!list.animate){settleTree(detail,state);return;}
 const fullHeight=list.scrollHeight;
 list.style.overflow='hidden';list.inert=!expanded||inert;
 state.animation=list.animate([{height:height+'px',opacity},{height:(expanded?fullHeight:0)+'px',opacity:expanded?1:0}],{duration:expanded?200:160,easing:'cubic-bezier(.2,.7,.25,1)',fill:'both'});
 state.animation.onfinish=()=>settleTree(detail,state);
 if(expanded){const follow=()=>{if(treeStates.get(detail)!==state)return;revealExpandedTree(detail);state.frame=requestAnimationFrame(follow);};state.frame=requestAnimationFrame(follow);}
});
root.addEventListener('close',e=>{if(e.target.matches('dialog'))settleAllTrees();},true);
window.addEventListener('resize',settleAllTrees,{passive:true});
window.addEventListener('pagehide',settleAllTrees);
const treeMedia=matchMedia('(prefers-reduced-motion: reduce)');
treeMedia.addEventListener('change',()=>{if(reduced())settleAllTrees();});
new MutationObserver(()=>{if(reduced())settleAllTrees();}).observe(document.body,{attributes:true,attributeFilter:['class']});
}window.OreMotion={mount};if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>mount());else mount();})();

/* Inline-link underline replay. Delegated, so dynamic article links work too. */
(function () {
  'use strict';
  if (window.__uxLinkUnderline) return;
  window.__uxLinkUnderline = 1;
  var doc = document;
  var media = window.matchMedia('(prefers-reduced-motion: reduce)');
  var active = new Map();
  var excluded = [
    '.md-button,.gh-mirror,.headerlink,.md-tag,.md-nav__link,.entry-btn',
    '.dl-opts,.tabbed-labels,.md-nav,.md-tags,.md-footer',
    '.grid.cards,.catalog-list,.catalog-entry,.proxy-card,.entry-actions,.related-links',
    '.ore-outline,.ore-drawer,.ore-appbar,.sv-outline-pages,dialog',
    '[role="button"],[role="tab"],button'
  ].join(',');
  function reduced() {
    return media.matches || (doc.body && doc.body.classList.contains('ux-motion-disabled'));
  }
  function linkFor(target) {
    var a = target && target.closest ? target.closest('a[href]') : null;
    if (!a || !a.closest('.md-content__inner') || a.closest(excluded)) return null;
    if (!a.textContent.trim() || a.getAttribute('aria-disabled') === 'true') return null;
    return a;
  }
  function stop(a) {
    var state = active.get(a);
    if (!state) return;
    if (state.timer) clearTimeout(state.timer);
    active.delete(a);
    if (state.animation) state.animation.cancel();
    a.classList.remove('ux-link-drawing');
  }
  function replay(a) {
    if (!a) return;
    stop(a);
    a.classList.add('ux-link-drawing');
    var state = { animation: null, timer: 0 };
    active.set(a, state);
    if (reduced() || typeof a.animate !== 'function') return;
    state.animation = a.animate([
      { backgroundSize: '0% 1px' },
      { backgroundSize: '100% 1px' }
    ], { duration: 280, easing: 'cubic-bezier(.22,.72,.28,1)', fill: 'none' });
    state.animation.onfinish = function () {
      if (active.get(a) !== state) return;
      state.animation = null;
      // Touch/programmatic activations must not leave a perpetual custom line.
      state.timer = setTimeout(function () {
        if (doc.activeElement !== a && !a.matches(':hover')) stop(a);
      }, 450);
    };
  }
  doc.addEventListener('pointerover', function (event) {
    if (event.pointerType === 'touch') return;
    var a = linkFor(event.target);
    if (a && (!event.relatedTarget || !a.contains(event.relatedTarget))) replay(a);
  }, true);
  doc.addEventListener('pointerout', function (event) {
    var a = linkFor(event.target);
    if (a && (!event.relatedTarget || !a.contains(event.relatedTarget)) && doc.activeElement !== a) stop(a);
  }, true);
  doc.addEventListener('pointerdown', function (event) {
    if (event.button === 0 || event.button === 1) replay(linkFor(event.target));
  }, true);
  doc.addEventListener('focusin', function (event) { replay(linkFor(event.target)); }, true);
  doc.addEventListener('focusout', function (event) {
    var a = linkFor(event.target);
    if (a && !a.matches(':hover')) stop(a);
  }, true);
  doc.addEventListener('keydown', function (event) {
    if (event.key === 'Enter' && !event.repeat) replay(linkFor(event.target));
  }, true);
  doc.addEventListener('click', function (event) {
    // Keyboard and programmatic .click(), never prevent/stop the native action.
    if (event.detail === 0) replay(linkFor(event.target));
  }, true);
  function clear() { Array.from(active.keys()).forEach(stop); }
  if (media.addEventListener) media.addEventListener('change', clear);
  else if (media.addListener) media.addListener(clear);
  window.addEventListener('pagehide', clear);
  doc.addEventListener('visibilitychange', function () { if (doc.hidden) clear(); });
  if (window.document$ && typeof window.document$.subscribe === 'function') window.document$.subscribe(clear);
  function watchPreference() {
    if (doc.body && typeof MutationObserver === 'function') {
      new MutationObserver(function () { if (reduced()) clear(); }).observe(doc.body, { attributes: true, attributeFilter: ['class'] });
    }
  }
  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', watchPreference, { once: true });
  else watchPreference();
})();