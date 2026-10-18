'use strict';
(() => {
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let data, nodeIndex=0, stepIndex=0, playing=false, timer=null, retryStage=0, loading=false;
const phone=window.matchMedia('(max-width:650px)');
const kindLabels={tool:'Agent tool',code:'Code function',model:'Model decision',decision:'Agent reasoning'};
const callable=step=>step.kind==='tool'||step.kind==='code';
const imageKinds={page:'Page scan',plan:'Zoning plan',aerial:'Aerial',crop:'Crop',ui:'Interface',mask:'Mask'};
const expandIcon='<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M9.5 2.5h4v4M6.5 13.5h-4v-4M13.5 2.5 9 7M2.5 13.5 7 9"/></svg>';
const captionHtml=img=>`<span>${esc(img.caption||img.alt||'')}</span>${imageKinds[img.kind]?`<span class="tag">${imageKinds[img.kind]}</span>`:''}${img.illustrative?'<span class="tag">Illustrative</span>':''}`;
function imageScene(img,step){
 const w=Number(img.width)||1600,h=Number(img.height)||1000;
 const srcset=img.srcSmall&&w>800?` srcset="${esc(img.srcSmall)} 800w, ${esc(img.src)} ${w}w" sizes="(max-width:650px) 92vw, (max-width:950px) 60vw, 900px"`:'';
 return `<figure class="shot reveal${h>w?' portrait':''}" style="--w:${w};--h:${h}"><button type="button" class="shot-open" data-lightbox aria-label="Enlarge image: ${esc(img.alt||step.operation)}"><img src="${esc(img.src)}"${srcset} width="${w}" height="${h}" alt="${esc(img.alt||'')}" decoding="async" fetchpriority="high"><span class="expand">${expandIcon}</span></button><figcaption>${captionHtml(img)}</figcaption></figure>`;
}
const prefetched=new Set();
function prefetch(step){const img=step?.image;if(!img||prefetched.has(img.src))return;prefetched.add(img.src);const i=new Image();i.decoding='async';i.loading='lazy';i.src=img.srcSmall||img.src;}
const sceneFor = (step, node) => window.workflowDiagram(step, node);
function pause(){playing=false;clearTimeout(timer);timer=null;if(data) $('play').textContent='Play steps';}
function schedule(){clearTimeout(timer);timer=setTimeout(()=>{if(!playing)return;const n=data.nodes[nodeIndex];if(stepIndex<n.steps.length-1){stepIndex++;render();if(stepIndex===n.steps.length-1)pause();else schedule();}else pause();},5500);}
function choose(n,s=0,focus){pause();nodeIndex=n;stepIndex=s;retryStage=0;render();if(focus){const target=focus==='node'?$('tabs').querySelector('[aria-current]'):focus==='operation'?$('operations').querySelector('[aria-current]'):$(focus);target?.focus({preventScroll:true});}}
function containment(node,step){
 if(node.id==='surveyor'&&step.id==='build')return ['Inside submit_parcel / revise_parcel','Inside submit_parcel'];
 if(node.id==='zoning'&&step.id==='project-site')return ['Inside plan_site','Inside plan_site'];
 if(node.id==='architect'&&step.id==='compute')return ['Inside preview_envelope / submit_envelope','Inside preview / submit'];
 return null;
}
function sequenceHint(node,step){return containment(node,step)?.[1]||(/^revise_/.test(step.operation)?'If rejected':'');}
function render(){
 const node=data.nodes[nodeIndex],step=node.steps[stepIndex];
 const bar=$('tabs'),sl=bar.scrollLeft;$('tabs').innerHTML=data.nodes.map((n,i)=>`<button data-node="${i}" aria-label="${esc(n.title)}, ${n.steps.length} operations" ${i===nodeIndex?'aria-current="page"':''}>${esc(n.title)}<span class="n" aria-hidden="true">${n.steps.length}</span></button>`).join('');
 bar.scrollLeft=sl;bar.querySelector('[aria-current]')?.scrollIntoView({block:'nearest',inline:'center'});$('node-title').textContent=node.title;$('order-note').textContent=node.orderNote||node.summary;
 $('operations').innerHTML=node.steps.map((s,i)=>`<li class="${containment(node,s)?'nested':''}"><button data-step="${i}" ${i===stepIndex?'aria-current="step"':''}><span class="number">${i+1}</span><span>${callable(s)?`<code>${esc(s.operation)}</code>`:`<span class="opname">${esc(s.operation)}</span>`}${sequenceHint(node,s)?`<small class="sequence-hint">${esc(sequenceHint(node,s))}</small>`:''}</span></button></li>`).join('');
 $('step-select').innerHTML=node.steps.map((s,i)=>`<option value="${i}" ${i===stepIndex?'selected':''}>${i+1} / ${node.steps.length} · ${esc(s.operation)}${!phone.matches&&sequenceHint(node,s)?` — ${esc(sequenceHint(node,s))}`:''}</option>`).join('');
 $('kind').textContent=kindLabels[step.kind]||'Operation';$('operation-title').textContent=step.operation;$('operation-title').classList.toggle('plain',!callable(step));$('purpose').textContent=step.purpose;
 const within=containment(node,step);$('condition').hidden=!step.condition&&!within;$('condition').textContent=[within?.[0],step.condition?`Conditional · ${step.condition}`:''].filter(Boolean).join(' · ');
 $('scene').classList.toggle('has-image',!!step.image);$('scene').innerHTML=step.image?imageScene(step.image,step):sceneFor(step,node);prefetch(node.steps[stepIndex+1]);$('previous').disabled=stepIndex===0;$('next').disabled=stepIndex===node.steps.length-1;
 $('count').textContent=`${stepIndex+1} / ${node.steps.length}`;$('play').textContent=playing?'Pause':'Play steps';
 $('next-node').hidden=stepIndex!==node.steps.length-1||nodeIndex===data.nodes.length-1;
 $('mechanism-detail').open=false;
 const fields=[['Inputs',step.arguments],['Result',step.result],['Checks',step.checks],['Source',step.source||node.source,'path'],['Image source',step.image?.provenance,'path']];
 $('detail-content').innerHTML=`<p>${esc(step.detail)}</p><dl>${fields.filter(([,v])=>v).map(([k,v,c])=>`<dt>${k}</dt><dd${c?` class="${c}"`:''}>${esc(typeof v==='object'?JSON.stringify(v,null,2):v)}</dd>`).join('')}</dl>`;
 const repair=node.id==='validation'&&(step.visual==='repair'||/repair|revise/i.test(step.operation));
 $('retry-lab').hidden=!repair;if(repair)renderRetry();
 const hash=`#${encodeURIComponent(node.id)}/${encodeURIComponent(step.id)}`;if(location.hash!==hash)history.replaceState(null,'',hash);
}
function renderRetry(focusAction){
 const question='Which destination applies to Building A?';
 const patch={edits:[{path:'ambiguities.0',value:{question,options:['Interpretation A','Interpretation B'],chosen:'Interpretation A',rationale:'Illustrative choice supported by the example notes.',resolved_by:'agent'}}]};
 const states=['A notes question is missing from the draft.','Rejected: notes.destinations has an unanswered question.','revise_study adds only the missing ambiguity.','The same validation pipeline runs again.','study accepted — in this illustrative example.'];
 const actions=['Submit incomplete','Apply focused patch','Recheck','Checking…','Try again'];
 const diff=retryStage<2?'ambiguities: []':'+ ambiguities.0: same question, choice and rationale';
 $('retry-lab').innerHTML=`<div class="retry-heading"><strong>Try the repair loop</strong><p>Illustrative · only if a gate rejects</p></div><div class="retry-track" aria-hidden="true">${states.map((_,i)=>`<span class="${i<=retryStage?'done':''}"></span>`).join('')}</div><p class="retry-state" role="status">${states[retryStage]}</p><code class="repair-diff">${esc(diff)}</code><button data-retry="advance">${actions[retryStage]}</button>${retryStage>0?'<button data-retry="reset" class="retry-reset">Reset example</button>':''}<p class="retry-note">Other prerequisites assumed valid; acceptance is not planning approval.</p>`;
 if(!$('repair-payload'))$('detail-content').insertAdjacentHTML('beforeend',`<div id="repair-payload"><p>Illustrative question: ${esc(question)}</p><pre>${esc(JSON.stringify(patch,null,2))}</pre></div>`);
 if(focusAction)$('retry-lab').querySelector(`[data-retry="${focusAction}"]`)?.focus({preventScroll:true});
}
function fromHash(){if(!data)return;let parts;try{parts=location.hash.slice(1).split('/').map(decodeURIComponent);}catch{return;}const n=data.nodes.findIndex(n=>n.id===parts[0]);if(n<0)return;const s=data.nodes[n].steps.findIndex(s=>s.id===parts[1]);choose(n,Math.max(0,s));}
async function load(){if(loading)return;loading=true;$('load-state').hidden=false;$('explorer').hidden=true;$('load-state').innerHTML='<p>Loading the operation sequence…</p>';try{
 const response=await fetch(`workflow-data.json?v=drawings-20261018-8`,{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);const loaded=await response.json();
 if(!Array.isArray(loaded.nodes)||!loaded.nodes.length||loaded.nodes.some(n=>!n.id||!Array.isArray(n.steps)||!n.steps.length||n.steps.some(s=>!s.id||!s.operation||!s.visual)))throw new Error('The operation data is incomplete');
 data=loaded;nodeIndex=0;stepIndex=0;$('load-state').hidden=true;$('explorer').hidden=false;fromHash();render();
 }catch(error){$('load-state').innerHTML=`<p>The operation sequence could not be loaded.</p><p class="load-error">${esc(error.message)}</p><button id="retry-load">Retry loading</button>`;$('retry-load').onclick=load;}finally{loading=false;}}
$('tabs').addEventListener('click',e=>{const b=e.target.closest('[data-node]');if(b)choose(Number(b.dataset.node),0,'node');});
$('operations').addEventListener('click',e=>{const b=e.target.closest('[data-step]');if(b)choose(nodeIndex,Number(b.dataset.step),'operation');});
$('step-select').addEventListener('change',e=>choose(nodeIndex,Number(e.target.value)));
$('previous').onclick=()=>{if(stepIndex>0)choose(nodeIndex,stepIndex-1);};$('next').onclick=()=>{if(stepIndex<data.nodes[nodeIndex].steps.length-1)choose(nodeIndex,stepIndex+1);};$('next-node').onclick=()=>{if(nodeIndex<data.nodes.length-1)choose(nodeIndex+1);};
$('play').onclick=()=>{if(playing){pause();return;}if(stepIndex===data.nodes[nodeIndex].steps.length-1){stepIndex=0;retryStage=0;}playing=true;render();schedule();};
$('retry-lab').addEventListener('click',e=>{const b=e.target.closest('[data-retry]');if(!b)return;pause();retryStage=b.dataset.retry==='reset'?0:(retryStage+1)%5;renderRetry(retryStage===3?'reset':'advance');if(retryStage===3){const currentNode=nodeIndex,currentStep=stepIndex;$('retry-lab').querySelector('button').disabled=true;setTimeout(()=>{if(nodeIndex===currentNode&&stepIndex===currentStep&&retryStage===3){const hadFocus=$('retry-lab').contains(document.activeElement);retryStage=4;renderRetry(hadFocus?'advance':null);}},650);}});
const lightbox=$('lightbox');
$('scene').addEventListener('click',e=>{const b=e.target.closest('[data-lightbox]');if(!b||!lightbox.showModal)return;const img=data.nodes[nodeIndex].steps[stepIndex].image;if(!img)return;pause();$('lightbox-figure').innerHTML=`<img src="${esc(img.src)}" alt="${esc(img.alt||'')}" decoding="async"><figcaption>${captionHtml(img)}</figcaption>`;lightbox.showModal();});
lightbox.addEventListener('click',e=>{if(e.target===lightbox)lightbox.close();});
$('lightbox-close').onclick=()=>lightbox.close();
lightbox.addEventListener('close',()=>{$('lightbox-figure').innerHTML='';});
$('mechanism-detail').addEventListener('toggle',()=>{if($('mechanism-detail').open)pause();});
// Pointer and keyboard exploration pause guided playback, including scene inspection.
$('workspace').addEventListener('pointerdown',e=>{if(!e.target.closest('#play'))pause();});
$('workspace').addEventListener('keydown',e=>{if(['ArrowRight','ArrowLeft'].includes(e.key)&&!e.target.closest('select,summary,details')){e.preventDefault();const offset=e.key==='ArrowRight'?1:-1;const s=stepIndex+offset;if(s>=0&&s<data.nodes[nodeIndex].steps.length)choose(nodeIndex,s,window.matchMedia('(max-width:650px)').matches?'workspace':'operation');}});
$('tabs').addEventListener('keydown',e=>{if(!['ArrowRight','ArrowLeft','Home','End'].includes(e.key))return;e.preventDefault();let n=e.key==='Home'?0:e.key==='End'?data.nodes.length-1:(nodeIndex+(e.key==='ArrowRight'?1:-1)+data.nodes.length)%data.nodes.length;choose(n);const b=$('tabs').querySelector('[aria-current]');b.focus();b.scrollIntoView({block:'nearest',inline:'nearest'});});
phone.addEventListener('change',()=>{if(data)render();});window.addEventListener('hashchange',fromHash);document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});load();
})();
