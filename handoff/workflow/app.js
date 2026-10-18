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
const rect=(x,y,w,h,cls='paper',r=5)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" class="${cls}"/>`;
const text=(x,y,t,cls='')=>`<text x="${x}" y="${y}" class="${cls}">${esc(t)}</text>`;
const line=(x,y,x2,y2,cls='line')=>`<path d="M${x} ${y}H${x2}" class="${cls}"/>`;
const lines=(x,y,count=5,w=120)=>Array.from({length:count},(_,i)=>rect(x,y+i*17,w-(i%3)*18,3,'muted',1)).join('');
const arrow=(x,y,x2,y2)=>`<path d="M${x} ${y}L${x2} ${y2}" class="line" marker-end="url(#arrow)"/>`;
const page=(x,y,w=145,h=210,top=26)=>rect(x,y,w,h)+lines(x+16,y+top,Math.min(7,Math.max(2,Math.floor((h-top-16)/17))),w-32);
function sceneFor(step,node){
 const v=step.visual; let body='', caption='Schematic mechanism · illustrative content';
 if(node.id==='surveyor'&&['submit','repair'].includes(step.id)){
  body=rect(40,50,215,195)+text(58,88,step.id==='repair'?'Focused patch':'ParcelChoice')+text(58,132,'Address + parcel IDs','small')+text(58,173,'Assumptions','small')+text(58,214,'Public neighbours','small')+arrow(260,145,310,145)+text(328,83,'Same pipeline')+text(328,127,'Validate fields','small')+text(328,171,'Build metric site','small')+text(328,215,'Check public edges','small');
  caption=step.id==='repair'?'Only after rejection: revise changed fields and run the finalizer again':'Submit a choice; code fetches and computes the site';
 }else if(node.id==='documents'&&step.operation==='submit_notes'){
  body=rect(40,50,205,195)+text(58,89,'Cited notes')+text(58,134,'Label + topics','small')+text(58,177,'Open questions','small')+arrow(260,145,310,145)+text(328,83,'Validate notes')+text(328,127,'Declared topics','small')+text(328,171,'Quotes + pages','small')+text(328,215,'Image bounds','small');
  caption='Check the submitted checklist and evidence; store notes only on acceptance';
 }else if(node.id==='orchestrator'&&step.operation==='task'){
  body=rect(40,105,180,90,'active')+text(58,143,'Orchestrator')+text(58,173,'task(...)','mono');
  if(step.id==='documents'){
   body+=['Rules','OAP','Destinations'].map((label,i)=>arrow(228,150,340,56+i*94)+rect(350,25+i*94,173,65)+text(368,64+i*94,label)).join('');
   caption='Three document tasks in parallel, after zoning';
  }else{
   const title=step.id==='architect'?'Architect':'Surveyor / zoning';
   body+=arrow(230,150,312,150)+rect(326,80,210,135)+text(342,118,title)+text(342,158,'Explicit task text','small')+text(342,194,'Specialist tools','small');
   caption=step.id==='architect'?'Delegate the retained program and destinations':'Survey first; zoning waits for the accepted site';
  }
 }else if(node.id==='architect'&&step.id==='rules'){
  body=page(40,40,215,215,58)+text(57,79,'Cited notes')+rect(55,114,180,48,'active')+text(69,144,'Rule + conditions','small')+arrow(267,145,310,145)+rect(330,60,190,185)+text(345,98,'Typed rule')+text(345,139,'min_m','mono')+text(345,174,'height_ratio','mono')+text(345,211,'citation','mono');
  caption='Model translates the provision; code does not interpret its meaning';
 }else if(node.id==='architect'&&step.id==='layout'){
  body=`<path d="M45 60 255 45 270 245 58 258Z" class="paper"/><path d="m72 88 72-6 8 139-70 6Z" class="active"/><path d="m166 80 65-5 10 139-65 6Z" class="paper"/>`+text(98,160,'A')+text(194,160,'B')+`<path d="M155 60v185" class="line" stroke-dasharray="5 5"/>`+text(320,77,'Draft placement')+text(320,120,'Building order','small')+text(320,160,'Cut + shares','small')+text(320,200,'Heights + spacing','small')+text(320,240,'OAP rationale','small');
  caption='Illustrative layout choices · no dimensions or capacity claimed';
 }else if(node.id==='architect'&&step.id==='preview'){
  body=`<path d="M45 60 250 45 265 239 60 251Z" class="paper"/><path d="m73 89 67-5 8 132-65 5Z" class="active"/><path d="m163 81 61-5 10 132-61 5Z" class="paper"/>`+text(320,78,'Disposable preview')+text(320,121,'Inspect plan + fit','small')+text(320,161,'Review warnings','small')+text(320,201,'Adjust layout','small')+`<path d="M310 232c-35 45-195 45-200 0" class="line" marker-end="url(#arrow)"/>`;
  caption='Preview stores no artifact; inspect and repeat before submission';
 }else if((node.id==='architect'&&step.id==='compute')||(node.id==='validation'&&step.operation==='site_envelope')){
  body=text(28,35,node.id==='validation'?'Delivered rules + layout → recompute':'Rules + layout → deterministic geometry','small')+['Bounds','Split','Slices','Caps'].map((label,i)=>rect(25+i*135,66,105,180,i===2?'active':'paper')+text(36+i*135,100,label)).join('');
  body+=`<path d="M42 125h68v94H42Z" class="line"/><path d="M54 140h44v64H54Z" class="accent"/><path d="M176 125h70v94h-70Z" class="line"/><path d="M207 125v94" class="accent"/>`+[0,1,2,3].map(i=>rect(311,137+i*19,68,11,i===2?'active':'paper')).join('')+text(443,150,'Footprint','small')+text(443,185,'Green','small')+text(443,220,'ratios','small');
  caption='Setback bounds → split footprints → height slices → ground caps';
 }else if(node.id==='zoning'&&step.id==='legend'){
  body=rect(40,35,240,225)+text(59,76,'Plan legend')+['Zone codes','Hatching / symbols','Perimeter lines'].map((label,i)=>rect(58,94+i*48,20,20,i===1?'active':'paper')+text(91,111+i*48,label,'small')).join('')+arrow(295,145,330,145)+text(348,91,'Read every entry')+text(348,136,'Exact labels','small')+text(348,180,'Non-zone items','small')+text(348,224,'Keep for checking','small');
  caption='Read the legend before testing which items affect the outlined site';
 }else if(node.id==='zoning'&&['locality','overlays'].includes(step.id)){
  body=rect(35,35,260,230)+`<path d="M52 85 119 52 195 93 273 68v174H52Z" class="paper"/><path d="m130 119 55-12 16 66-58 14Z" class="accent"/><path d="M57 221c30-170 170-200 220-20" class="line" stroke-dasharray="5 5"/>`;
  body+=step.id==='locality'?text(325,81,'Read full code')+text(325,124,'Preserve suffix','small')+text(325,167,'Same bounded area','small')+text(325,210,'Zoom / pan again','small'):text(325,81,'Test every item')+text(325,124,'Inside / touching','small')+text(325,167,'Follow perimeter','small')+text(325,210,'Retain uncertainty','small');
  caption=step.id==='locality'?'Read the outlined plan crop; colour alone does not identify the zone':'Visual assessment of overlays, including uncertainty near boundaries';
 }else if(node.id==='zoning'&&['town','neighbourhood'].includes(step.id)){
  body=parcelMap()+`<path d="M45 190 295 85M100 45l150 205" class="line"/>`+text(330,81,'Optional context')+text(330,126,'Map / aerial','small')+text(330,171,step.id==='town'?'Town scale':'Neighbourhood','small')+text(330,216,'Understand setting','small');
  caption='Geographic context is optional; the saved fit places the plan outline';
 }else if(node.id==='ingestion'&&step.id.startsWith('georef-')){
  const shape='M58 100 103 55 171 64 226 118 206 212 126 245 64 209Z';
  if(step.id==='georef-settings'){
   body=rect(45,45,205,205)+text(65,82,'Plan settings')+text(65,125,'PDF + page','small')+text(65,165,'Commune code','small')+text(65,205,'Mask / fit knobs','small')+arrow(265,145,310,145)+rect(330,75,185,140,'active')+text(348,116,'Validate config')+text(348,163,'Ground CRS','small')+text(348,196,'Output path','small');
  }else if(step.id==='georef-image'){
   body=page(45,40,190,215,58)+text(65,80,'Plan PDF','small')+arrow(250,145,310,145)+rect(330,55,185,195,'active')+text(348,95,'Page pixels')+lines(348,123,4,143)+text(345,225,'Decode or render','small');
  }else if(step.id==='georef-mask'){
   body=rect(35,35,245,230)+`<path d="${shape}" class="active"/><path d="M61 145h160m-87-84v180" class="line"/>`+arrow(295,145,325,145)+text(345,78,'Downscale')+text(345,118,'Colour threshold','small')+text(345,158,'Close gaps','small')+text(345,198,'Keep interior','small');
  }else if(step.id==='georef-boundary'){
   body=rect(40,75,205,140)+text(58,116,'IGN API Carto')+text(58,162,'Commune outline','small')+arrow(260,145,310,145)+`<path d="${shape}" transform="translate(270 0)" class="active"/>`+text(347,278,'EPSG:2154','small');
  }else if(step.id==='georef-fit'){
   const motion=window.matchMedia('(prefers-reduced-motion:reduce)').matches?'':'<animateTransform attributeName="transform" type="translate" from="30 -22" to="0 0" dur="1.1s" fill="freeze"/>';
   body=`<path d="${shape}" class="paper"/><g>${motion}<path d="${shape}" class="accent"/></g>`+text(320,75,'Fit 6 parameters')+text(320,119,'Boundary to mask','small')+text(320,161,'least_squares','mono')+text(320,203,'Robust residuals','small');
  }else{
   body=rect(40,45,205,205)+text(58,84,'Measure fit')+text(58,130,'IoU / distances','small')+text(58,175,'Full-pixel matrix','small')+arrow(260,145,310,145)+rect(330,45,185,205,'active')+text(347,84,'Save JSON')+text(347,127,'Transform','small')+text(347,169,'Mean / max error','small')+text(347,211,'Diagnostics','small');
  }
  caption='Schematic registration · fitting does not interpret zoning labels';
 }else if(node.id==='zoning'&&['plan-site','project-site'].includes(step.id)){
  body=rect(35,35,255,225)+`<path d="M50 75 125 48 204 87 272 61v174H50Z" class="paper"/><path d="M66 185 247 74M94 53l120 172" class="line"/><path d="m133 113 55-14 15 65-59 14Z" class="accent"/>`+arrow(301,145,337,145)+rect(355,45,165,90,'active')+text(370,82,'Close crop')+text(370,112,'Zone + label','small')+rect(355,162,165,90)+text(370,198,'Context crop')+text(370,227,'Perimeters','small');
  caption='Project cadastral rings through the saved affine matrix · retain uncertainty';
 }else if(step.operation==='load_settings'){
  body=rect(45,40,210,220)+text(65,77,'Corpus settings')+text(65,123,'PDF paths','small')+text(65,164,'Classifier','small')+text(65,205,'Heading rules','small')+arrow(267,145,310,145)+rect(330,75,185,140,'active')+text(350,116,'Validate config')+text(350,160,'Prepare PDFs','small')+text(350,190,'processing','small');
 }else if(step.operation==='read_artifact'){
  body=rect(40,40,220,220)+text(60,78,'Saved artifacts')+['Site','Zone','Notes / decisions'].map((t,i)=>rect(58,99+i*43,181,32,i===2?'active':'paper')+text(68,122+i*43,t,'small')).join('')+arrow(275,145,320,145)+text(345,98,'Read typed data')+text(345,146,'Evidence + refs','small')+text(345,190,'Accepted state','small');caption=node.id==='architect'?'Architect reads artifacts; it does not reread source documents':'Read persisted artifacts before dependent decisions';
 }else if(node.id==='surveyor'&&step.id==='shortlist'){
  body=[0,1,2].map(i=>rect(45,50+i*67,210,48,i===1?'active':'paper')+text(64,81+i*67,`Candidate ${i+1}`)).join('')+arrow(270,145,320,145)+rect(340,75,175,145,'active')+text(358,115,'Shortlist')+text(358,159,'Address match','small')+text(358,197,'Site context','small');caption='Model chooses which parcels need closer description';
 }else if(node.id==='surveyor'&&step.id==='build'){
  body=`<path d="M45 65h110v125H45Z" class="paper"/><path d="M155 65h105v125H155Z" class="active"/><path d="M45 65h215v125H45Z" class="accent"/>`+text(76,225,'Connected union','small')+arrow(275,135,314,135)+text(330,80,'Metric site')+text(330,126,'Neutral edges','small')+text(330,169,'Area + neighbours','small')+text(330,214,'Public-edge check','small');caption='Illustrative parcel union · code rejects disjoint geometry';
 }else if(node.id==='validation'&&['citations','consistency'].includes(step.id)){
  body=page(40,40,205,210,58)+page(315,40,205,210,58)+rect(55,112,175,44,'active')+rect(330,112,175,44,'active')+text(58,80,'Cited quote','small')+text(333,80,step.id==='citations'?'Corpus page':'Notes citation','small')+text(69,140,'Text + numbers','small')+text(344,140,'Text + numbers','small')+`<path d="M250 135h60" class="accent"/>`+text(143,272,'Compare page and normalized quote','small');caption=step.id==='citations'?'Text citations are checked; raster meaning is not text-verifiable':'Check citation provenance and building consistency';
 }else if(v==='inspect'&&node.id!=='surveyor'){
  body=page(45,40,205,215)+rect(60,119,174,46,'active')+arrow(265,145,310,145)+rect(330,70,185,150)+text(347,110,'Inspect')+text(347,153,'Text or image','small')+text(347,195,'Keep references','small');caption='Inspection depends on the selected operation; see exact mechanism';
 }else if(v==='extract'&&node.id!=='ingestion'){
  body=page(45,35,205,225)+rect(60,112,174,48,'active')+arrow(265,145,310,145)+rect(330,65,185,160)+text(346,109,'Selected text')+text(346,154,'Page reference','small')+text(346,198,'Quote check','small');caption='Read existing corpus text; this is not PDF ingestion';
 }else if(v==='map'&&node.id==='surveyor'){
  body=parcelMap()+rect(157,113,90,82,'accent')+arrow(313,145,345,145)+rect(365,60,150,165)+text(382,99,'Site view')+text(382,144,'Aerial context','small')+text(382,185,'Street-side','small');caption='Optional visual inspection · illustrative parcel geometry';
 }else if(v==='save'&&node.id!=='ingestion'){
  body=rect(40,45,200,205)+text(60,85,'Submission')+lines(60,110,5,155)+arrow(255,145,310,145)+rect(330,65,185,170,'active')+text(348,108,'Validate + save')+text(348,154,'Evidence refs','small')+text(348,198,node.id==='zoning'?'zone artifact':node.id==='architect'?'envelope':'Typed artifact','small');caption='Submission handling is described in the exact mechanism';
 }else if(v==='sample'){
  body=page(40,40,150,205)+page(205,40,150,205)+page(370,40,150,205)+rect(54,90,122,35,'active')+rect(219,141,122,35,'active')+rect(384,73,122,35,'active')+text(53,30,'PDF pages','small')+text(65,226,'sample lines','small');caption='First 3 nonempty text pages · up to 1,500 characters each';
 }else if(v==='classify'){
  body=page(55,45,180,210)+rect(72,64,146,38,'active')+text(85,90,'Title','small')+arrow(245,140,300,140)+text(325,83,'Classify')+rect(315,104,200,49,'active')+text(333,135,'document kind')+text(327,190,'Title + sample','small')+text(327,216,'inform the label','small');
 }else if(v==='extract'){
  body=page(45,35,205,225)+rect(65,72,160,34,'active')+rect(65,128,125,38,'active')+arrow(265,144,310,144)+text(329,65,'Native PDF')+text(329,110,'page text')+text(329,150,'block bounds')+text(329,190,'line positions')+text(329,235,'No OCR','small');
 }else if(v==='split'){
  body=page(40,35,190,225)+rect(55,48,160,18,'muted')+rect(55,224,160,18,'muted')+text(65,108,'Heading A','small')+text(65,180,'Heading B','small')+arrow(245,140,290,140)+text(312,58,'Heading tree')+`<path d="M315 83v137m0-107h30m-30 55h30m-30 50h30" class="line"/>`+rect(345,93,170,38,'active')+text(357,119,'Section A','small')+rect(345,147,170,38)+text(357,173,'Subsection','small')+rect(345,201,170,38)+text(357,227,'Section B','small');
  caption='Header / footer removal → sections with page references';
 }else if(v==='save'){
  body=[0,1,2].map(i=>rect(50+i*10,55+i*18,175,135)).join('')+text(87,137,'Sections')+arrow(255,145,315,145)+rect(340,53,165,190,'active')+text(364,92,'Corpus')+lines(363,119,6,115)+text(354,226,'persist to disk','small');
 }else if(v==='geocode'){
  body=rect(35,45,245,62)+text(54,71,'Address request','small')+text(54,94,'geocoder','mono')+arrow(155,116,155,155)+[0,1,2].map(i=>rect(35,165+i*31,245,27,i===0?'active':'paper')+text(51,185+i*31,`Candidate ${i+1}`,'small')).join('')+`<path d="M325 70v175m70-175v175m70-175v175M308 112h220M308 198h220" class="line"/><circle cx="399" cy="155" r="10" class="active"/>`+text(325,50,'Point candidates','small');
 }else if(v==='parcels'){
  body=parcelMap()+`<circle cx="183" cy="139" r="7" class="ink"/><circle cx="183" cy="139" r="38" class="accent" stroke-dasharray="4 5"/>`+text(330,76,'Point query')+text(330,120,'Parcel candidates')+[0,1,2].map(i=>rect(330,143+i*34,177,28,i===0?'active':'paper')+text(343,164+i*34,`Parcel ${String.fromCharCode(65+i)}`,'small')).join('');caption='Illustrative parcel geometry · no live cadastral query';
 }else if(v==='inspect'){
  body=parcelMap()+`<path d="M87 220 253 66" stroke="#fff" stroke-width="18"/><path d="M87 220 253 66" class="line" stroke-dasharray="5 5"/>`+rect(335,52,175,185)+text(351,87,'Inspect context')+text(351,132,'boundaries','small')+text(351,168,'public strip','small')+text(351,204,'aerial / street','small');caption='Illustrative geometry · visual inspection informs judgment';
 }else if(v==='map'||v==='zone'){
  body=rect(35,35,285,225)+`<path d="M45 110 150 55 215 135 310 65v160H45Z" class="active"/><path d="m50 230 250-180M90 45l160 200" class="line"/><circle cx="196" cy="151" r="9" class="ink"/>`+rect(170,123,65,61,'accent')+arrow(320,153,355,153)+rect(370,55,150,125)+rect(385,75,28,25,'active')+text(424,96,'Zone','small')+lines(385,119,3,110)+text(369,221,'Plan detail','small')+text(369,249,'Legend zoom','small');caption='Illustrative map / legend · raster meaning needs interpretation';
 }else if(v==='document'||v==='notes'){
  body=rect(30,35,190,225)+text(46,65,'Navigation','small')+`<path d="M51 86v143m0-120h20m-20 43h20m-20 43h20" class="line"/>`+text(79,116,'Section','small')+text(79,159,'Article','small')+text(79,202,'Page','small')+page(275,35,245,225)+rect(290,123,212,37,'active')+text(299,148,'Passage','small')+text(295,237,'Page reference','small');
  caption=node.id==='documents'?'Three analyst scopes may run in parallel, after zoning':'Navigate sections, select text, retain page references';
 }else if(v==='geometry'){
  body=`<path d="M55 62 237 43 276 222 75 251Z" class="paper"/><path d="m84 91 129-14 28 125-145 19Z" class="active"/><path d="m114 110 77-9 18 83-88 11Z" class="accent"/><path d="M58 274 278 251M65 256l-5 25m211-44 5 25" class="line"/>`+text(315,78,step.kind==='model'?'Model proposes':'Code computes')+text(315,124,'setback offsets','small')+text(315,164,'polygon slices','small')+text(315,204,'usable geometry','small');caption=step.kind==='model'?'Illustrative proposal · deterministic code computes the geometry':'Illustrative geometry · no actual dimensions shown';
 }else if(v==='gate'||v==='repair'){
  const checks=step.id==='schema'?['Required fields','Enums','Model constraints']:step.id==='findings'?['Site + zone','Scoped notes','Envelope']:['Schema','Evidence refs','Ambiguities'];
  body=rect(40,45,200,205)+text(60,80,'Submission')+lines(60,105,4,155)+rect(59,181,160,42,'active')+text(71,209,'Fields','small')+arrow(250,145,303,145)+text(324,71,'Code checks')+checks.map((t,i)=>rect(319,91+i*49,193,37,i===2?'active':'paper')+text(333,117+i*49,t,'small')).join('');caption='Acceptance means implemented checks pass';
 }else if(v==='report'){
  body=page(55,35,190,225,58)+text(77,78,'Study artifacts','small')+arrow(260,145,311,145)+page(330,35,185,225,58)+text(349,77,'Report','small')+rect(346,115,150,50,'active')+text(359,145,'Cited findings','small');caption='Compile the saved study artifacts';
 }else if(v==='decision'){
  body=rect(50,60,175,160)+text(68,98,'Evidence')+lines(68,123,4,135)+arrow(240,140,294,140)+rect(315,56,195,65,'active')+text(334,96,'Selected route')+rect(315,159,195,65)+text(334,199,'Other route')+text(98,257,'Evaluate evidence + conditions','small');
 }else{
  body=page(45,40,175,215,58)+page(340,40,175,215,58)+rect(60,115,145,42,'active')+rect(355,115,145,42,'active')+`<path d="M225 135h110m-75-12-12 12 12 12m40-24 12 12-12 12" class="accent"/>`+text(60,85,'Artifact A','small')+text(355,85,'Artifact B','small')+text(180,272,'Compare evidence and citations','small');
 }
 return `<svg viewBox="0 0 560 300" role="img" aria-label="${esc(step.operation)} — ${esc(caption)}"><defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="m0 0 10 5-10 5Z" fill="#b6beb1"/></marker></defs><g class="reveal">${body}</g></svg><p class="scene-caption">${esc(caption)}</p>`;
}
function parcelMap(){return rect(35,35,270,225)+`<path d="M51 61 159 48 175 123 69 143Z" class="paper"/><path d="m175 48 111 15-14 100-91-35Z" class="paper"/><path d="m71 153 107-19 18 104-125 5Z" class="active"/><path d="m188 142 84 31 13 65-80 1Z" class="paper"/>`;}
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
 const response=await fetch(`workflow-data.json?v=internals-20261018-6`,{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);const loaded=await response.json();
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
