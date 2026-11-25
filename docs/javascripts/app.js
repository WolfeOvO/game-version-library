/* Standalone Ore navigation, search, outline and utilities. */
(function(){'use strict';
const doc=document, media=matchMedia('(prefers-reduced-motion: reduce)');let initialized=false,userReduced=false,indexPromise=null,toastTimer;
const BASE=new URL(document.querySelector('meta[name="ore-base"]')?.content||'./',location.href).href.replace(/\/?$/,'/');
try{userReduced=localStorage.getItem('ore-reduce-motion')==='1';}catch(_){}
const reduced=()=>media.matches||userReduced;
const glyphs={menu:'<path d="M4 5h16M4 12h16M4 19h16"/>',search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',settings:'<path d="m9 3-.7 2.3-2 .9L4 5.5 2 9l1.7 1.6v2.8L2 15l2 3.5 2.3-.7 2 .9L9 21h6l.7-2.3 2-.9 2.3.7 2-3.5-1.7-1.6v-2.8L22 9l-2-3.5-2.3.7-2-.9L15 3Z"/><circle cx="12" cy="12" r="3"/>',close:'<path d="m6 6 12 12M18 6 6 18"/>',top:'<circle cx="12" cy="12" r="10"/><path d="m16 12-4-4-4 4M12 16V8"/>'};
function icon(name){return '<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square" stroke-linejoin="miter">'+glyphs[name]+'</svg>';}
function controlIcons(){
 doc.querySelectorAll('.ore-appbar [data-ore-action],.ore-dialog-head button[data-ore-action]').forEach(b=>{const key=({menu:'menu',search:'search',settings:'settings',close:'close','close-outline':'close'})[b.dataset.oreAction];if(key){b.classList.add('ore-icon-button');b.innerHTML=icon(key);b.title=b.getAttribute('aria-label')||'';}});
 const trigger=doc.querySelector('.ore-outline-trigger');if(trigger){trigger.innerHTML=icon('menu')+'<span>页面大纲</span>';trigger.setAttribute('aria-expanded','false');}
 const top=doc.querySelector('.ore-top');if(top){top.innerHTML=icon('top')+'<span>回到页面顶部</span>';top.setAttribute('aria-label','回到页面顶部');}
 const panel=doc.querySelector('.ore-outline-panel'),filter=panel&&panel.querySelector('.ore-outline-filter');if(filter&&!panel.querySelector('.ore-outline-controls')){const box=doc.createElement('div'),count=doc.createElement('small');box.className='ore-outline-controls';count.className='ore-outline-count';count.setAttribute('role','status');filter.before(box);box.append(filter,count);}
}
function motionPreference(){doc.body.classList.toggle('ux-motion-disabled',reduced());doc.body.classList.toggle('ore-motion-on',!reduced());}
function surfaceMotion(surface,opening){
 if(!surface)return;const old=surface.__motion;const current=surface.open?getComputedStyle(surface).transform:'none';if(old){old.cancel();surface.__motion=null;}
 if(opening&&!surface.open)surface.showModal();if(!surface.open)return;
 if(reduced()||!surface.animate){if(!opening)surface.close();return;}
 const drawer=surface.classList.contains('ore-drawer'),away=drawer?(surface.classList.contains('ore-outline-dialog')?'translateX(100%)':'translateX(-100%)'):'translateY(20px)';
 const animation=surface.animate(opening?[{transform:current==='none'?away:current,opacity:drawer?1:0},{transform:'none',opacity:1}]:[{transform:current,opacity:1},{transform:away,opacity:drawer?1:0}],{duration:drawer?600:opening?300:260,easing:'ease',fill:'both'});surface.__motion=animation;
 animation.finished.then(()=>{if(surface.__motion!==animation)return;surface.__motion=null;if(!opening)surface.close();animation.cancel();}).catch(()=>{});
}
function open(surface,trigger){if(!surface||surface.open&&!surface.__motion)return;surface.__trigger=trigger||doc.activeElement;surfaceMotion(surface,true);}
function close(surface){if(surface&&surface.open)surfaceMotion(surface,false);}
function toast(text){const box=doc.querySelector('.ore-toast');if(!box)return;clearTimeout(toastTimer);box.textContent=text;box.hidden=false;toastTimer=setTimeout(()=>box.hidden=true,2200);}
function revealTarget(id){let decoded=id;try{decoded=decodeURIComponent(id);}catch(_){}const e=doc.getElementById(decoded);if(!e)return;if(e.tagName==='DETAILS')e.open=true;let child=e,parent=e.parentElement;const chain=[];while(parent){chain.unshift([parent,child]);child=parent;parent=parent.parentElement;}chain.forEach(([p,c])=>{if(p.tagName==='DETAILS')p.open=true;if(c.classList.contains('tabbed-block')){const set=p.parentElement,blocks=[...p.children],input=set.querySelectorAll(':scope > input')[blocks.indexOf(c)];if(input){input.checked=true;input.dispatchEvent(new Event('change',{bubbles:true}));}}});e.scrollIntoView({behavior:reduced()?'instant':'smooth',block:'start'});}
function getIndex(){if(!indexPromise)indexPromise=fetch(new URL('search/ore-index.json',BASE)).then(r=>{if(!r.ok)throw Error(r.status);return r.json();}).catch(e=>{indexPromise=null;throw e;});return indexPromise;}
function dialogBody(title){const dialog=doc.querySelector('.ore-dialog');dialog.replaceChildren();const head=doc.createElement('div');head.className='ore-dialog-head';const strong=doc.createElement('strong');strong.textContent=title;const b=doc.createElement('button');b.type='button';b.className='ore-icon-button';b.innerHTML=icon('close');b.setAttribute('aria-label','关闭');b.onclick=()=>close(dialog);head.append(strong,b);const body=doc.createElement('div');body.className='ore-dialog-body';dialog.append(head,body);return {dialog,body};}
function search(trigger){const {dialog,body}=dialogBody('搜索游戏版本');const input=doc.createElement('input');input.type='search';input.placeholder='游戏名、版本号、平台…';input.setAttribute('aria-label','搜索版本库');const status=doc.createElement('p');status.className='ore-search-status';status.setAttribute('role','status');status.textContent='正在读取版本索引…';const list=doc.createElement('ul');list.className='ore-search-results';body.append(input,status,list);open(dialog,trigger);input.focus();
function load(){getIndex().then(entries=>{function run(){const terms=input.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);list.replaceChildren();const found=terms.length?entries.filter(e=>terms.every(t=>(e.title+' '+e.location).toLocaleLowerCase().includes(t))):[];status.textContent=terms.length?'找到 '+found.length+' 个页面，显示前 40 项。':'输入名称或版本号；索引含 '+entries.length+' 个页面。';found.slice(0,40).forEach(e=>{const li=doc.createElement('li'),a=doc.createElement('a'),small=doc.createElement('small');a.href=new URL(e.location,BASE).href;a.textContent=e.title;small.textContent=e.location;li.append(a,small);list.append(li);});}input.oninput=run;run();}).catch(()=>{status.textContent='版本索引读取失败，请重试。';const retry=doc.createElement('button');retry.className='ore-button ore-retry';retry.textContent='重新读取';retry.onclick=()=>{retry.remove();status.textContent='正在读取版本索引…';load();};body.append(retry);});}load();}
function settings(trigger){const {dialog,body}=dialogBody('显示设置');const p=doc.createElement('p');p.textContent='非 Minecraft 游戏版本库 · 开源数据与主题';const row=doc.createElement('label');row.className='ore-setting-row';const text=doc.createElement('span');text.textContent='减少动态效果';const input=doc.createElement('input');input.type='checkbox';input.checked=userReduced;input.onchange=()=>{userReduced=input.checked;try{localStorage.setItem('ore-reduce-motion',userReduced?'1':'0');}catch(_){}motionPreference();};row.append(text,input);body.append(p,row);open(dialog,trigger);}
function mount(){if(initialized)return;initialized=true;doc.documentElement.dataset.oreBoot='ready';controlIcons();motionPreference();media.addEventListener('change',motionPreference);
const drawer=doc.querySelector('dialog[aria-label="版本库导航"]'),outline=doc.querySelector('.ore-outline-dialog'),panel=doc.querySelector('.ore-outline-panel'),aside=doc.querySelector('.ore-outline-aside'),wide=matchMedia('(min-width:1200px)');
doc.querySelectorAll('dialog').forEach(d=>{d.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();e.stopImmediatePropagation();close(d);}},true);d.addEventListener('cancel',e=>{e.preventDefault();close(d);});d.addEventListener('close',()=>{if(d.__trigger){d.__trigger.setAttribute('aria-expanded','false');if(d.__trigger.isConnected)d.__trigger.focus();}});d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)close(d);}});});
function relocate(){if(!panel||!aside)return;if(wide.matches){close(outline);aside.append(panel);}else outline.append(panel);}relocate();wide.addEventListener('change',relocate);
doc.addEventListener('click',async e=>{const b=e.target.closest('[data-ore-action]');if(b){const action=b.dataset.oreAction;if(action==='menu'){b.setAttribute('aria-expanded','true');open(drawer,b);}else if(action==='close')close(b.closest('dialog'));else if(action==='search')search(b);else if(action==='settings')settings(b);else if(action==='outline'){if(panel){b.setAttribute('aria-expanded','true');open(outline,b);}}else if(action==='close-outline')close(outline);}
const a=e.target.closest('.ore-outline-list a[data-heading-id]');if(a){e.preventDefault();history.replaceState(null,'','#'+encodeURIComponent(a.dataset.headingId));revealTarget(a.dataset.headingId);close(outline);requestAnimationFrame(scroll);}
const copy=e.target.closest('.ore-copy');if(copy){const code=copy.parentElement.querySelector('code');if(code){try{await navigator.clipboard.writeText(code.textContent);copy.textContent='已复制';toast('已复制代码');}catch(_){copy.textContent='复制失败';toast('复制失败，请手动选择代码');}setTimeout(()=>copy.textContent='复制',2200);}}
});
const filter=doc.querySelector('.ore-outline-filter');function filterOutline(){const terms=filter?filter.value.toLocaleLowerCase().split(/\s+/).filter(Boolean):[];const items=[...doc.querySelectorAll('.ore-outline-list li')];items.forEach(li=>li.hidden=!terms.every(t=>li.textContent.toLocaleLowerCase().includes(t)));const count=doc.querySelector('.ore-outline-count');if(count)count.textContent=items.filter(li=>!li.hidden).length+' / '+items.length+' 个章节';}if(filter)filter.addEventListener('input',filterOutline);filterOutline();
const top=doc.querySelector('.ore-top');let lastY=scrollY;
const outlineHeadings=[...doc.querySelectorAll('article h2[id],article h3[id],article h4[id],article h5[id],article h6[id],article details[data-ore-outline][id]')];let outlineOffsets=[];
function measureOutlineOffsets(){const padding=parseFloat(getComputedStyle(doc.documentElement).scrollPaddingTop)||0;outlineOffsets=outlineHeadings.map(h=>({heading:h,offset:Math.max(90,padding+(parseFloat(getComputedStyle(h).scrollMarginTop)||0)+2)}));}
function scroll(){if(top)top.hidden=scrollY<350||scrollY>=lastY;lastY=scrollY;let active=null,activeTop=-Infinity,activeMatchesHash=false;let fragment=location.hash.slice(1);try{fragment=decodeURIComponent(fragment);}catch(_){}outlineOffsets.forEach(({heading:h,offset})=>{if(!h.getClientRects().length)return;const y=h.getBoundingClientRect().top;if(y>offset)return;const matchesHash=h.id===fragment;if(active===null||y>activeTop+1||(Math.abs(y-activeTop)<=1&&(!activeMatchesHash||matchesHash))){active=h.id;activeTop=y;activeMatchesHash=matchesHash;}});doc.querySelectorAll('.ore-outline-list a').forEach(a=>{if(a.dataset.headingId===active)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');});}
measureOutlineOffsets();scroll();window.addEventListener('scroll',scroll,{passive:true});let outlineResizeFrame=0;window.addEventListener('resize',()=>{cancelAnimationFrame(outlineResizeFrame);outlineResizeFrame=requestAnimationFrame(()=>{measureOutlineOffsets();scroll();});});if(top)top.onclick=()=>window.scrollTo({top:0,behavior:reduced()?'instant':'smooth'});
doc.addEventListener('keydown',e=>{const editable=e.target.closest('input,textarea,[contenteditable=true]');if(((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k')||(e.key==='/'&&!editable)){e.preventDefault();search(doc.querySelector('[data-ore-action=search]'));}});
window.addEventListener('hashchange',()=>{if(location.hash)revealTarget(location.hash.slice(1));requestAnimationFrame(scroll);});
doc.addEventListener('click',e=>{const a=e.target.closest('article a[href]');if(!a||a.closest('.tabbed-labels'))return;const u=new URL(a.href,location.href);if(u.origin===location.origin&&u.pathname===location.pathname&&u.hash){e.preventDefault();history.pushState(null,'',u.hash);revealTarget(u.hash.slice(1));requestAnimationFrame(scroll);}});
/* Restore history against a stable content anchor, not stale page pixels. */
const viewKey='__oreView';let restoreFrame=0;
function rememberView(){
 const candidates=[...doc.querySelectorAll('article :is(h1,h2,h3,h4,h5,h6,details)[id]')].filter(e=>e.getClientRects().length);
 let anchor=null,distance=Infinity;
 candidates.forEach(e=>{const top=e.getBoundingClientRect().top,d=Math.abs(top-145);if(d<distance){anchor=e;distance=d;}});
 const state=history.state&&typeof history.state==='object'?history.state:{};
 const view={url:location.pathname+location.search+location.hash,y:scrollY,anchor:anchor?anchor.id:null,top:anchor?anchor.getBoundingClientRect().top:0,tabs:[...doc.querySelectorAll('.tabbed-set > input:checked')].map(input=>input.id)};
 try{history.replaceState({...state,[viewKey]:view},'');}catch(_){}
}
function restoreView(){
 if(window.OreTabs&&window.OreTabs.refresh)window.OreTabs.refresh();
 const view=history.state&&history.state[viewKey];
 if(!view||view.url!==location.pathname+location.search+location.hash)return;
 cancelAnimationFrame(restoreFrame);restoreFrame=requestAnimationFrame(()=>{restoreFrame=requestAnimationFrame(()=>{
  const anchor=view.anchor&&doc.getElementById(view.anchor);
  const y=anchor&&anchor.getClientRects().length?scrollY+anchor.getBoundingClientRect().top-view.top:view.y;
  window.scrollTo({top:Math.max(0,y),behavior:'instant'});measureOutlineOffsets();scroll();
 });});
}
window.addEventListener('pagehide',rememberView);
window.addEventListener('pageshow',restoreView);
if(location.hash)setTimeout(()=>{revealTarget(location.hash.slice(1));requestAnimationFrame(scroll);},0);
setTimeout(restoreView,0);
}
window.OreUI={mount,revealTarget,open,close};if(doc.readyState==='loading')doc.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();
