'use strict';
// Mechanisms, not run traces. Values explicitly marked as examples are illustrative.
window.workflowDiagram = (step, node) => {
 const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const box = (x,y,w,h,cls='d-data') => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${cls==='d-code'?2:6}" class="${cls}"/>`;
 const label = (x,y,t,cls='d-label',anchor='start') => `<text x="${x}" y="${y}" class="${cls}" text-anchor="${anchor}">${escape(t)}</text>`;
 const path = (d,cls='d-link',head=false) => `<path d="${d}" class="${cls}"${head?' marker-end="url(#diagram-arrow)"':''}/>`;
 const flow = (x,y,a,b) => path(`M${x} ${y}L${a} ${b}`,'d-link',true);
 const bars = (x,y,w,count=3) => Array.from({length:count},(_,i)=>box(x,y+i*13,w-(i%3)*18,3,'d-bar')).join('');
 const table = (x,y,w,title,rows,accent=-1,pitch=32) => box(x,y,w,48+rows.length*pitch)+label(x+14,y+28,title)+path(`M${x+12} ${y+40}H${x+w-12}`)+rows.map((s,i)=>(i===accent?box(x+7,y+45+i*pitch,w-14,pitch-3,'d-focus'):'')+label(x+14,y+65+i*pitch,s,'d-mono')).join('');
 const chip = (x,y,w,t,cls='d-data') => box(x,y,w,36,cls)+label(x+w/2,y+24,t,'d-mono','middle');
 const stage = (x,y,w,title,sub,focus=false) => box(x,y,w,64,focus?'d-focus':'d-code')+label(x+14,y+26,title)+label(x+14,y+55,sub,'d-note');
 const chain = (labels,accent=1) => labels.map((t,i)=>box(318,36+i*69,214,46,i===accent?'d-focus':'d-code')+label(332,65+i*69,t)+(i<labels.length-1?flow(425,84+i*69,425,101+i*69):'')).join('');
 const submit = (title,fields,checks,out) => table(28,36,222,title,fields,-1,32)+flow(255,59,307,59)+chain(checks)+flow(425,86+(checks.length-1)*69,425,243)+chip(318,250,214,out);
 const repair = (tool,field,out) => {
  return label(28,43,tool,'d-mono')+box(28,82,156,114)+label(42,110,'Rejected draft')+label(42,147,field,'d-mono')+bars(42,163,115,1)+flow(190,139,216,139)+box(224,82,150,114,'d-focus')+label(238,110,'Only edits')+label(238,147,'path','d-mono')+label(238,179,'value / remove','d-mono')+flow(380,139,406,139)+box(414,82,118,114,'d-code')+label(428,118,'Rerun')+label(428,147,'same checks','d-note')+label(428,179,out,'d-mono')+path('M472 204V244H106V204','d-loop',true)+label(284,270,'If rejected again','d-note','middle');
 };
 let body='', caption='';
 switch(`${node.id}/${step.id}`){
 case 'ingestion/settings':
  body=table(28,52,194,'corpus',['documents','classifier','splitter','dir'])+flow(228,150,248,150)+box(252,128,64,44,'d-code')+label(284,156,'check','d-note','middle')+flow(320,150,338,150)+box(344,52,188,176,'d-focus')+label(356,83,'CorpusSettings','d-mono')+label(360,125,'Typed documents','d-note')+label(360,163,'Classifier','d-note')+label(360,201,'Splitters','d-note');
  caption='Validate configuration before reading the PDFs';break;
 case 'ingestion/classify':
  body=table(28,40,228,'Text sample',['File name','Metadata title','Page counts','3 text pages'])+flow(262,148,294,148)+box(302,40,230,220,'d-model')+label(318,69,'Model classification')+chip(314,86,206,'regulatory_text','d-focus')+chip(314,130,206,'zoning_map')+chip(314,174,206,'oap')+label(318,244,'+ a short title','d-note');
  caption='Text only; configured kind and title overrides are preserved';break;
 case 'ingestion/persist':
  body=['Regulation','Zoning plan','OAP'].map((t,i)=>box(28,42+i*72,176,54)+label(42,75+i*72,t)+flow(211,69+i*72,270,150)).join('')+box(278,106,112,88,'d-code')+label(334,140,'Assemble','d-label','middle')+label(334,169,'Corpus','d-mono','middle')+flow(396,150,424,150)+box(432,76,100,148,'d-focus')+bars(446,104,68,5)+label(480,254,'corpus.json','d-mono','middle');
  caption='Save once, after every configured PDF has been processed';break;
 case 'ingestion/georef-settings':
  body=table(28,36,220,'Georef config',['document / page','insee / crs','mask / fit','output'])+flow(254,146,306,146)+box(314,48,218,204,'d-focus')+label(330,82,'Validate settings')+path('M330 98H516')+label(330,130,'Resolve plan PDF','d-note')+label(330,169,'Unknown ID fails','d-note')+label(330,208,'Create IGN client','d-note');
  caption='Settings locate the plan and configure the boundary client';break;
 case 'ingestion/georef-image':
  body=box(28,88,128,126)+label(44,118,'Plan page')+bars(44,144,90)+flow(163,150,206,150)+box(214,114,104,72,'d-model')+label(266,143,'Covering','d-note','middle')+label(266,168,'scan?','d-note','middle')+path('M324 146H344V77H363','d-link',true)+path('M324 158H344V223H363','d-link',true)+stage(371,46,161,'Decode scan','Original pixels',true)+stage(371,192,161,'Render page','Configured DPI')+label(339,68,'yes','d-note')+label(339,248,'no','d-note');
  caption='Use a covering embedded scan; otherwise render the page';break;
 case 'ingestion/georef-mask':
  body=['Reduce','Threshold','Close + fill','Clean'].map((t,i)=>{
   const x=28+i*136; let shape='';
   if(i===0)shape='<path d="M44 98h70v70H44Z M44 120h70m-70 23h70m-47-45v70m24-70v70" class="d-link"/>';
   else if(i===1)shape=box(x+20,102,26,32,'d-bar')+box(x+50,124,28,39,'d-bar')+box(x+34,152,27,19,'d-bar');
   else shape=path(`M${x+19} 118l25-25 38 20-8 49-38 15-21-28Z`,i===3?'d-mask':'d-outline');
   return box(x,60,100,160,i===3?'d-focus':'d-data')+label(x+50,87,t,'d-note','middle')+shape+(i<3?flow(x+105,142,x+129,142):'');
  })+label(280,258,'Largest connected interior; holes filled, thin spurs removed','d-note','middle');
  caption='A commune mask for registration, without interpreting zoning labels';break;
 case 'ingestion/georef-boundary':
  body=box(28,82,224,138)+label(44,115,'IGN API Carto')+label(44,153,'code_insee=91272','d-mono')+label(44,190,'Cached request','d-note')+flow(260,150,304,150)+path('M330 118l42-56 67 12 63 60-20 79-68 23-67-25Z','d-mask')+label(418,260,'Largest polygon part','d-note','middle')+label(418,286,'EPSG:2154','d-mono','middle');
  caption='Project the official commune outline from WGS84 to Lambert-93';break;
 case 'ingestion/georef-save':
  body=stage(28,34,228,'outline_errors','Mean / max metres')+flow(142,103,142,115)+stage(28,120,228,'scaled','Back to full pixels')+flow(142,189,142,201)+stage(28,206,228,'save_georeference','Atomic JSON')+flow(263,238,292,238)+table(302,28,230,'Georeference',['matrix','iou','mean_error_m','max_error_m'],0,30)+label(302,238,'Then diagnostic PNGs','d-note')+label(302,267,'mask + boundary','d-mono');
  caption='Score, scale and save; fit metrics have no acceptance threshold';break;
 case 'orchestrator/playbook':
  body=chip(28,124,190,'load_playbook')+label(123,190,'name="study"','d-mono','middle')+flow(224,142,272,142)+box(280,28,252,244,'d-focus')+label(298,58,'Study playbook')+['Frame the request','Site and zone','Read documents','Decide','Envelope if eligible','Submit and reply'].map((t,i)=>label(298,95+i*31,String(i+1),'d-note')+label(325,95+i*31,t,'d-note')).join('');
  caption='The model follows a loaded recipe; it is not a coded scheduler';break;
 case 'orchestrator/clarify':
  body=box(28,64,182,166)+label(44,96,'Question batch')+[0,1,2].map(i=>`<circle cx="51" cy="${126+i*33}" r="6" class="${i===1?'d-mask':'d-outline'}"/>`+bars(70,123+i*33,112,1)).join('')+flow(218,145,245,145)+box(252,122,48,48,'d-code')+path('M270 134v24m12-24v24')+label(276,201,'Pause','d-note','middle')+flow(306,145,335,145)+table(342,64,190,'Resolution',['user: answered','agent: fallback'])+label(28,270,'Playbook: at most two calls','d-note');
  caption='Pause for the user; on resume, the agent settles unanswered questions';break;
 case 'orchestrator/artifacts':
  body=table(28,42,214,'artifacts',['site','zone','notes.<label>','envelope'],1)+flow(250,145,298,145)+box(306,42,226,58)+label(322,78,'Task reply: summary','d-note')+box(306,122,226,140,'d-focus')+label(322,154,'Full stored JSON')+label(322,184,'read_artifact','d-mono')+bars(322,206,176,3);
  caption='Read the full artifact before making dependent decisions';break;
 case 'orchestrator/decide':
  body=box(28,100,128,104)+label(44,135,'zone','d-mono')+label(44,166,'notes.*','d-mono')+flow(164,152,190,152)+box(198,28,334,244,'d-model')+label(216,58,'Model reasoning')+['Regime','Admissibility','Parking + conditions','Open points','Gaps'].map((t,i)=>(i===3?box(208,186,314,33,'d-focus'):'')+label(216,94+i*35,t,'d-note')).join('')+label(369,211,'→ ambiguities','d-mono')+label(369,246,'→ reread','d-note');
  caption='Apply the checklist, retain questions, request missing evidence';break;
 case 'surveyor/geocode':
  body=chip(28,122,196,'geocode(query)')+label(126,188,'4 rue Joliot Curie','d-note','middle')+flow(231,140,268,140)+table(276,48,256,'Address candidates',['housenumber','street','locality'],0)+label(292,242,'Match number + street','d-note')+label(292,270,'+ town','d-note');
  caption='Prefer a matching housenumber; stop if no reliable candidate';break;
 case 'surveyor/submit':
  body=submit('Parcel choice',['address','parcel_ids','rationale','assumptions','public_parcels'],['Validate schema','Build metric site','Public parcels'],'site accepted');
  caption='The model supplies identifiers and reasons; code builds the geometry';break;
 case 'surveyor/build':
  body=label(28,39,'Re-geocode label → fetch + project IDs','d-note')+box(42,82,62,95)+box(104,82,62,95)+label(73,137,'A','d-label','middle')+label(135,137,'B','d-label','middle')+flow(173,128,219,128)+box(227,82,104,95,'d-focus')+flow(339,128,377,128)+box(385,82,147,95)+path('M385 82H532V177H385Z M385 177H532')+path('M385 177H532','d-loop')+label(104,217,'Fetch IDs','d-note','middle')+label(279,217,'Connected union','d-note','middle')+label(458,217,'Tag edges','d-note','middle')+label(280,265,'Neighbours → parcel / public land sides, area and citations','d-note','middle');
  caption='One connected site; declared public parcels are checked afterwards';break;
 case 'surveyor/repair':body=repair('revise_parcel','address','site');caption='Patch the retained draft, then rerun validation and site construction';break;
 case 'zoning/catalogue':
  body=table(28,44,290,'Document catalogue',['regulatory_text','zoning_map','oap'],1)+flow(324,148,356,148)+box(364,76,168,150)+label(380,109,'Plan metadata')+label(380,147,'ID + page count','d-note')+label(380,187,'Image-only?','d-note');
  caption='Identify the plan before opening its page image';break;
 case 'zoning/overlays':
  body=box(28,44,234,212)+path('M44 82L124 60 240 107V230H44Z','d-outline')+path('M60 233Q80 40 236 67','d-loop')+path('M120 127l56-12 17 63-59 13Z','d-mask')+flow(270,149,308,149)+box(316,44,216,212,'d-model')+label(332,77,'Each legend item')+label(332,119,'Inside / touching?','d-note')+label(332,160,'Follow perimeters','d-note')+label(332,201,'Record uncertainty','d-note')+label(332,238,'Keep every item','d-note');
  caption='Visual interpretation against the site outline, item by item';break;
 case 'zoning/submit':
  body=submit('Zone findings',['zone','overlays','rationale','region','ambiguities'],['Validate schema','Region on page'],'zone accepted');
  caption='Code checks structure and image bounds, not the model’s zone reading';break;
 case 'zoning/repair':body=repair('revise_zone','region','zone');caption='Patch the rejected zone draft; the same checks run again';break;
 case 'documents/catalogue':
  body=label(28,43,'Choose sources for each task')+label(240,88,'rules','d-mono','middle')+label(360,88,'oap','d-mono','middle')+label(474,88,'uses','d-note','middle')+['Regulation','Zoning plan','OAP'].map((t,i)=>label(28,138+i*56,t,'d-note')+path(`M28 ${156+i*56}H532`)).join('')+[[240,132],[474,132],[360,188],[360,244]].map(([x,y],i)=>`<circle cx="${x}" cy="${y}" r="7" class="${i===2?'d-mask':'d-dot'}"/>`).join('')+label(280,291,'PLU: conformity · OAP: compatibility','d-note','middle');
  caption='The OAP task also reads the plan to establish applicability';break;
 case 'documents/sections':
  body=table(28,46,210,'Document outline',['Titre I','Titre II','Titre III'],1,44)+flow(246,157,306,157)+label(276,139,'parent','d-mono','middle')+table(314,46,218,'Child headings',['Article 9','Article 10','Article 11','Article 12'],-1,36);
  caption='One level per call; pass a heading as parent to descend';break;
 case 'documents/search':
  body=chip(28,66,178,'search')+label(28,140,'stationnement','d-mono')+label(28,172,'Example query','d-note')+flow(212,121,250,121)+[0,1,2].map(i=>box(258,36+i*74,274,64)+(i===0?label(272,62,'Ranked section + pages','d-note'):'')+bars(272,76+i*74,232,i===0?1:2)+(i===0?box(336,76,52,4,'d-focus'):'')).join('')+label(258,282,'BM25 · ≤ 8 hits · snippets','d-note');
  caption='Keyword retrieval; read the full section before citing it';break;
 case 'documents/notes':
  body=submit('Scoped notes',['label / topics','notes','citations / views','open_points'],['Declared topics','Quotes + figures','Views on page'],'notes.<label>');
  caption='Verify text citations and crop bounds; raster text checks are skipped';break;
 case 'architect/read':
  body=label(28,35,'read_artifact','d-mono')+[['site','Edges + area'],['notes.rules','Cited limits'],['notes.destinations','Height bands'],['notes.oap','If OAP applies']].map(([a,b],i)=>chip(28,59+i*55,232,a,i===1?'d-focus':i===3?'d-model':'d-data')+flow(267,77+i*55,308,77+i*55)+label(324,83+i*55,b,'d-note')).join('');
  caption='Read saved findings and named extras; no source-document tools';break;
 case 'architect/rules':
  body=box(28,50,190,194)+label(44,82,'Cited note')+bars(44,105,156,2)+box(40,145,166,42)+label(54,172,'H/2, min 4 m','d-note')+label(44,223,'Prompt example','d-note')+flow(224,163,242,163)+box(250,129,70,68,'d-model')+label(285,168,'Model','d-note','middle')+flow(326,163,344,163)+box(352,50,180,210,'d-focus')+label(366,82,'Typed rule')+label(366,117,'min_m: 4','d-mono')+label(366,149,'height_ratio','d-mono')+label(366,178,'0.5','d-mono')+label(366,212,'citations','d-mono')+label(366,244,'copied','d-note');
  caption='Encode max(min_m, height_ratio × H), retaining the source citations';break;
 case 'architect/submit':
  body=submit('Envelope input',['rules','layout','open_points'],['Validate schema','Layout fits rules','Compute envelope'],'envelope accepted');
  caption='If rejected, correct and resubmit the full payload';break;
 case 'validation/schema':
  body=table(28,22,238,'Study payload',['address / program','regime','admissibility','parking','conditions','ambiguities','summary'],-1,29)+flow(272,147,312,147)+box(320,104,212,88,'d-focus')+label(336,135,'Study','d-mono')+label(336,170,'model_validate','d-mono')+label(328,238,'Invalid → retained draft','d-note');
  caption='Validate the Study schema before reading dependent artifacts';break;
 case 'validation/findings':
  body=label(28,35,'Graph-state artifact','d-note')+label(326,35,'Producer','d-note')+[['site','surveyor'],['zone','zoning_analyst'],['notes.rules','doc_analyst'],['notes.oap','doc_analyst'],['notes.destinations','doc_analyst'],['envelope','architect']].map(([a,b],i)=>chip(28,50+i*34,246,a,i===5?'d-focus':'d-data')+path(`M280 ${68+i*34}H312`)+label(326,74+i*34,b,'d-mono')).join('')+label(28,286,'Envelope required only if a proposed use remains eligible','d-note');
  caption='Missing deliveries name the producer; labels and note topics also checked';break;
 case 'validation/points':
  body=label(28,36,'Delivered questions')+label(334,36,'Study ambiguities')+['Notes','Envelope, if any','Zoning'].map((t,i)=>box(28,60+i*65,198,47)+label(42,90+i*65,t,'d-note')+path(`M234 ${83+i*65}H318`,i===1?'d-loop':'d-match')+box(326,60+i*65,206,47,i===1?'d-model':'d-data')+(i===1?label(340,90+i*65,'Missing → reject','d-note'):bars(340,81+i*65,170,1))).join('')+label(280,282,'Same question text; case and spacing ignored','d-note','middle');
  caption='Retain every open question; this check does not judge the answer';break;
 case 'validation/consistency':
  body=[['zone + overlays','study.regime'],['rule citations','notes.*'],['layout citations','notes.oap'],['layout buildings','rules buildings'],['rules buildings','admissibility']].map(([a,b],i)=>box(28,24+i*49,214,40,i===0?'d-focus':'d-data')+label(42,50+i*49,a,'d-note')+path(`M250 ${44+i*49}H304`)+box(312,24+i*49,220,40)+label(326,50+i*49,b,'d-mono')).join('');
  caption='Keep zoning findings, citation provenance, building labels and heights aligned';break;
 case 'validation/citations':
  body=table(28,48,170,'Citation',['doc','page','quote'])+path('M204 144H230')+box(238,104,94,86,'d-focus')+label(285,138,'≥ 0.9','d-label','middle')+label(285,171,'numbers','d-note','middle')+path('M340 144H368')+box(376,48,156,166)+label(390,79,'Cited page')+bars(390,101,128,3)+box(388,150,132,30)+label(280,258,'Raster: no text verification','d-note','middle');
  caption='Match the same page and quoted-number counts; not a legal-meaning check';break;
 case 'validation/recompute':
  body=label(28,35,'Eligible use → site + rules + layout','d-note')+['Edges','Bounds','Split','Slice + cap'].map((t,i)=>{
   const x=28+i*136;let icon='';
   if(i===0)icon=path(`M${x+17} 124h66v48h-66Z`)+path(`M${x+17} 172h66`,'d-loop');
   if(i===1)icon=path(`M${x+12} 121h76v54h-76Z M${x+23} 132h54v32h-54Z`)+label(x+50,199,'2 bounds','d-note','middle');
   if(i===2)icon=path(`M${x+16} 121h68v54h-68Z M${x+50} 121v54`)+label(x+50,199,'Proposal','d-note','middle');
   if(i===3)icon=[0,1,2].map(j=>box(x+23+j*5,119+j*19,54-j*8,11)).join('')+path(`M${x+13} 150h75`,'d-loop');
   return box(x,65,100,145)+label(x+50,94,t,'d-note','middle')+icon+(i<3?flow(x+105,144,x+129,144):'');
  })+chip(324,232,208,'EnvelopeStudy','d-focus')+label(28,246,'All prohibited?','d-note')+label(28,275,'Edges only; no envelope','d-note');
  caption='Recompute geometry; caps trim polygons, not just reported areas';break;
 case 'validation/repair':body=repair('revise_study','ambiguities.0','study');caption='Patch and recheck; empty edits rerun after a producer repairs its artifact';break;
 default:
  // Unreachable for current non-image operations: fail visibly if a new step needs art.
  body=label(28,146,step.operation,'d-mono')+label(28,186,'See the exact mechanism below','d-note');
  caption='A diagram for this new operation is pending';
 }
 return `<svg viewBox="0 0 560 310" class="mechanism-diagram" role="img" aria-label="${escape(step.operation)}: ${escape(caption)}"><title>${escape(step.operation)}</title><desc>${escape(caption)}</desc><defs><marker id="diagram-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 10 5 0 10Z"/></marker></defs><g class="reveal">${body}</g></svg><p class="scene-caption">${escape(caption)}</p>`;
};
