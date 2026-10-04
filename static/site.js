'use strict';
const lang=document.body.dataset.lang||'zh';
const zh=lang==='zh';
const words=['老阳','少阴','少阳','老阴'];
const wordEn=['Changing yang','Yin','Yang','Changing yin'];
const announce=document.getElementById('throw-announcement');
let deck=[];
const deckReady=(window.offlineDeck?Promise.resolve(window.offlineDeck):fetch(document.body.dataset.deck||'/static/deck.json').then(r=>{if(!r.ok)throw Error('deck');return r.json();})).then(data=>{deck=data.map(h=>zh?h:{...h,...Object.fromEntries(['name','theme','meaning','motif','classical_image','art_note'].map(k=>[k,h[k+'_en']])),upper:({乾:'Qian / Heaven',坤:'Kun / Earth',震:'Zhen / Thunder',巽:'Xun / Wind',坎:'Kan / Water',离:'Li / Fire',艮:'Gen / Mountain',兑:'Dui / Lake'})[h.upper],lower:({乾:'Qian / Heaven',坤:'Kun / Earth',震:'Zhen / Thunder',巽:'Xun / Wind',坎:'Kan / Water',离:'Li / Fire',艮:'Gen / Mountain',兑:'Dui / Lake'})[h.lower]});preview();return deck;}).catch(()=>[]);
const form=document.getElementById('cast-form');
function showLine(select){
 const tile=select.closest('.throw-tile'),el=tile.querySelector('.tile-line'),state=tile.querySelector('.tile-state');
 const v=select.value;
 el.replaceChildren();
 if(v===''){const s=document.createElement('span');s.textContent=zh?'待落':'Waiting';el.append(s);state.textContent='—';tile.classList.remove('set','moving');return;}
 const value=9-Number(v),line=document.createElement('span');
 line.className='yao-line '+(value%2?'yang':'yin');line.append(document.createElement('i'),document.createElement('i'));
 el.append(line);state.textContent=(zh?words:wordEn)[Number(v)]+(value===9?' ○':value===6?' ×':'');
 tile.classList.add('set');tile.classList.toggle('moving',value===6||value===9);
 tile.classList.remove('latest');void tile.offsetWidth;tile.classList.add('latest');
}
function makeCard(h,label){
 const el=document.createElement('article');el.className='oracle-card reveal-card';
 const head=document.createElement('div');head.className='card-head';
 const caption=document.createElement('span');caption.textContent=label;
 const num=document.createElement('span');num.textContent=String(h.number).padStart(2,'0')+' / 64';head.append(caption,num);
 const art=document.createElement('div');art.className=`painting atlas-${h.atlas} cell-${h.cell} art-${h.number}`;art.setAttribute('role','img');art.setAttribute('aria-label',h.motif);
 const body=document.createElement('div');body.className='card-body';
 const symbol=document.createElement('span');symbol.className='card-symbol';symbol.textContent=h.symbol;symbol.setAttribute('aria-hidden','true');
 const name=document.createElement('h2');name.textContent=h.name;
 const theme=document.createElement('p');theme.textContent=h.theme;body.append(symbol,name,theme);el.append(head,art,body);return el;
}
function preview(){
 if(!form)return;
 const values=[...form.querySelectorAll('select[name^="word"]')].map(s=>s.value);
 const holder=document.getElementById('cast-preview');
 if(values.some(v=>v==='')||!deck.length){holder.hidden=true;holder.replaceChildren();return;}
 const bits=values.map(v=>(9-Number(v))%2).join('');
 const changed=values.map(v=>{const value=9-Number(v);return value===6||value===9?1-value%2:value%2;}).join('');
 const main=deck.find(h=>h.bits===bits),next=deck.find(h=>h.bits===changed);
 holder.replaceChildren(makeCard(main,zh?'本卦':'Primary'));
 if(bits!==changed)holder.append(makeCard(next,zh?'变卦':'Transformation'));
 holder.append(makeChanges(values));holder.hidden=false;
}
if(form){
 const selects=[...form.querySelectorAll('select[name^="word"]')];
 const time=document.getElementById('cast-time'),timezone=document.getElementById('timezone');
 const now=new Date();
 if(!time.value){const local=new Date(now.getTime()-now.getTimezoneOffset()*60000);time.value=local.toISOString().slice(0,16);}
 const browserZone=Intl.DateTimeFormat().resolvedOptions().timeZone||'Asia/Shanghai';
 const chosen=timezone.dataset.selected||browserZone;
 if(![...timezone.options].some(o=>o.value===chosen)){const o=document.createElement('option');o.value=chosen;o.textContent=chosen;timezone.append(o);}
 timezone.value=chosen;
 function formattedParts(date,zone){return Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(date).map(x=>[x.type,x.value]));}
 function displayTime(date,zone){const p=formattedParts(date,zone);return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}`;}
 function zoneOffset(date,zone){return new Intl.DateTimeFormat('en',{timeZone:zone,timeZoneName:'longOffset'}).formatToParts(date).find(p=>p.type==='timeZoneName').value.replace('GMT','UTC');}
 function convertTime(){
  const el=document.getElementById('time-conversion');if(!el||!time.value)return;
  try{const target=Date.parse(time.value+'Z');let instant=target;for(let i=0;i<4;i++){const p=formattedParts(new Date(instant),timezone.value);const observed=Date.parse(`${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}Z`);const diff=target-observed;if(!diff)break;instant+=diff;}
   const date=new Date(instant);if(displayTime(date,timezone.value)!==time.value.replace('T',' ')){el.textContent=zh?'该时间可能处于夏令时跳时区间，请重新选择。':'This local time may fall in a daylight-saving gap. Choose another time.';return;}
   const city=timezone.selectedOptions[0].textContent;el.textContent=zh?`${city}（${zoneOffset(date,timezone.value)}）当地 ${time.value.replace('T',' ')} → 北京 ${displayTime(date,'Asia/Shanghai')}（UTC+08:00）`:`${city} (${zoneOffset(date,timezone.value)}) ${time.value.replace('T',' ')} → Beijing ${displayTime(date,'Asia/Shanghai')} (UTC+08:00)`;
  }catch{el.textContent=zh?'请检查当地时间与城市；排盘时会再次校验夏令时。':'Check local time and location; daylight saving is validated on submission.';}
 }
 if(!time.dataset.edited&&!time.defaultValue){const p=formattedParts(now,timezone.value);time.value=`${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;}
 timezone.addEventListener('change',()=>{if(time.dataset.edited!=='1'&&!time.defaultValue){const p=formattedParts(new Date(),timezone.value);time.value=`${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;}convertTime();});
 time.addEventListener('input',()=>{time.dataset.edited='1';convertTime();});convertTime();
 selects.forEach(s=>{showLine(s);s.addEventListener('change',()=>{showLine(s);preview();});});
 const manual=document.getElementById('manual-mode'),auto=document.getElementById('auto-mode'),stage=document.getElementById('coin-stage'),throwButton=document.getElementById('throw-button');
 let autoMode=false,tossing=false;
 function setMode(isAuto){
  if(tossing)return;
  autoMode=isAuto;manual.classList.toggle('active',!isAuto);auto.classList.toggle('active',isAuto);
  manual.setAttribute('aria-pressed',String(!isAuto));auto.setAttribute('aria-pressed',String(isAuto));
  stage.hidden=!isAuto;
  selects.forEach(s=>{s.hidden=isAuto;s.required=!isAuto;});
  document.getElementById('casting-help').textContent=isAuto?(zh?'每点击一次，系统独立掷三枚硬币。六次完成后显示卦牌。':'Each click casts three independent coins. Six throws reveal the card.'):(zh?'准备三枚相同硬币，一起掷出。每次选择有几枚数字面朝上，重复六次即可。':'Toss three identical coins together. Select how many land with the number side up. Repeat six times.');
  if(isAuto){selects.forEach(s=>{s.value='';showLine(s);});preview();throwButton.disabled=false;throwButton.textContent=zh?'摇第一爻':'Cast line 1';announce.textContent=zh?'轻点一次，摇出一爻。':'One click, one line.';}
 }
 manual.addEventListener('click',()=>setMode(false));auto.addEventListener('click',()=>setMode(true));
 throwButton.addEventListener('click',()=>{
  if(tossing||!autoMode)return;
  const index=selects.findIndex(s=>s.value==='');if(index<0)return;
  tossing=true;throwButton.disabled=true;const coins=document.querySelector('.three-coins');coins.classList.add('shaking');
  // Three independent fair bits: front-count probabilities = 1:3:3:1, not uniform 0..3.
  const random=new Uint8Array(3);crypto.getRandomValues(random);const faces=[...random].map(b=>b&1);const count=faces.reduce((a,b)=>a+b,0);
  window.setTimeout(()=>{
   [...coins.children].forEach((c,i)=>c.textContent=faces[i]?(zh?'正':'F'):(zh?'背':'B'));
   coins.classList.remove('shaking');selects[index].value=String(count);showLine(selects[index]);preview();
   announce.textContent=zh?`第${index+1}次：${count}个数字面，${words[count]}${count===0||count===3?' · 动爻':''}`:`Throw ${index+1}: ${count} front faces, ${wordEn[count]}`;
   tossing=false;throwButton.disabled=index===5;throwButton.textContent=index===5?(zh?'六爻已成':'Six lines complete'):(zh?`摇第${index+2}爻`:`Cast line ${index+2}`);
  },520);
 });
 form.addEventListener('submit',e=>{
  if(selects.some(s=>s.value==='')){e.preventDefault();alert(zh?'请先完成六次结果。':'Complete all six throws first.');return;}
  if(!form.checkValidity()){e.preventDefault();form.reportValidity();return;}
  document.getElementById('loading').hidden=false;document.getElementById('read-button').disabled=true;
 });
 window.addEventListener('pageshow',()=>{document.getElementById('loading').hidden=true;document.getElementById('read-button').disabled=false;});
}
const search=document.getElementById('deck-search');
if(search){search.addEventListener('input',()=>{const q=search.value.trim().toLowerCase();let n=0;document.querySelectorAll('.deck-item').forEach(el=>{const match=el.dataset.search.toLowerCase().includes(q);el.hidden=!match;if(match)n++;});document.getElementById('deck-count').textContent=n+(zh?' 卦':' cards');document.getElementById('deck-empty').hidden=n>0;});}
document.querySelectorAll('[data-copy]').forEach(button=>button.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(location.href);button.textContent=zh?'链接已复制':'Link copied';}catch{window.prompt(zh?'复制此链接：':'Copy this link:',location.href);}}));
document.querySelectorAll('[data-format-reading]').forEach(el=>{
 const text=el.textContent.trim();const lines=text.split(/\n+/);el.replaceChildren();
 for(const line of lines){if(!line.trim())continue;const heading=line.match(/^【(.+?)】(.*)$/);if(heading){const h=document.createElement('h2');h.textContent=heading[1];el.append(h);if(heading[2]){const p=document.createElement('p');p.textContent=heading[2];el.append(p);}}else{const p=document.createElement('p');p.textContent=line;el.append(p);}}
 el.style.whiteSpace='normal';
});
document.querySelectorAll('.generation-form').forEach(f=>f.addEventListener('submit',()=>{const b=f.querySelector('button');b.disabled=true;b.textContent=zh?'正在生成，请稍候…':'Generating reading…';}));

function makeChanges(values){
 const wrap=document.createElement('section');wrap.className='change-diagram';
 const title=document.createElement('h2');title.textContent=zh?'六爻如何变':'How the lines change';wrap.append(title);
 const moving=values.flatMap((v,i)=>Number(v)===0||Number(v)===3?[i+1]:[]);
 const note=document.createElement('p');note.textContent=moving.length?(zh?`第 ${moving.join('、')} 爻发动 · 老阳变阴，老阴变阳`:`Changing lines: ${moving.join(', ')} · Yang becomes yin; yin becomes yang`):(zh?'六爻皆静 · 本次没有动爻，也不另立变卦':'All lines are still · No separate transformed hexagram');wrap.append(note);
 const header=document.createElement('div');header.className='change-header';(zh?['爻位','本卦','变化',moving.length?'变卦':'仍为本卦']:['Line','Primary','Change',moving.length?'Transformed':'Unchanged']).forEach(t=>{const s=document.createElement('span');s.textContent=t;header.append(s);});wrap.append(header);
 for(let i=5;i>=0;i--){const value=9-Number(values[i]),isMoving=value===9||value===6,yang=Boolean(value%2);const row=document.createElement('div');row.className='change-row'+(isMoving?' is-moving':'');const pos=document.createElement('span');pos.textContent=zh?`${i+1}爻`:`Line ${i+1}`;row.append(pos);const line=y=>{const s=document.createElement('span');s.className='yao-line '+(y?'yang':'yin');s.append(document.createElement('i'),document.createElement('i'));return s;};row.append(line(yang));const change=document.createElement('span');change.textContent=isMoving?(yang?(zh?'阳 → 阴':'Yang → Yin'):(zh?'阴 → 阳':'Yin → Yang')):(zh?'静':'Still');row.append(change,line(isMoving?!yang:yang));wrap.append(row);}
 const small=document.createElement('p');small.className='fineprint';small.textContent=zh?'初爻在底，上爻在顶。亮色行是动爻。':'Line 1 is at the bottom; line 6 is at the top. Highlighted rows change.';wrap.append(small);return wrap;
}
const cardDialog=document.getElementById('card-dialog');
function openCard(h){
 if(!h||!cardDialog)return;
 const container=document.getElementById('card-dialog-content');container.replaceChildren();
 const art=makeCard(h,zh?'六十四卦 · 画中之象':'64 hexagrams · Painted symbolism');const section=document.createElement('section');section.className='dialog-copy';
 const title=document.createElement('h2');title.id='dialog-title';title.textContent=h.name;section.append(title);
 const sections=zh?[['卦义',h.meaning+'。'],['原典取象','《象传》：'+h.classical_image+'。'],['画中取象',h.motif+'。'+h.art_note],['上下卦',`上卦 ${h.upper} · 下卦 ${h.lower}。画面为卦义的艺术转译。读一卦还须结合所问与动爻。`]]:[['Meaning',h.meaning],['Classical image','Image Commentary: '+h.classical_image+'.'],['Painted symbolism',h.motif+' '+h.art_note],['Trigrams',`Upper: ${h.upper}. Lower: ${h.lower}. The artwork illustrates symbolism; a reading also considers your question and the changing lines.`]];
 for(const [heading,text] of sections){const t=document.createElement('h3');t.textContent=heading;const copy=document.createElement('p');copy.textContent=text;section.append(t,copy);}
 const pager=document.createElement('div');pager.className='card-pager';for(const [delta,label] of [[-1,zh?'前一卦':'Previous card'],[1,zh?'后一卦':'Next card']]){const b=document.createElement('button');b.type='button';b.textContent=label;b.disabled=h.number+delta<1||h.number+delta>64;b.addEventListener('click',()=>openCard(deck[h.number+delta-1]));pager.append(b);}section.append(pager);container.append(art,section);
 if(!cardDialog.open)cardDialog.showModal();cardDialog.scrollTop=0;
}
cardDialog?.querySelector('.dialog-close').addEventListener('click',()=>cardDialog.close());
cardDialog?.addEventListener('click',e=>{if(e.target===cardDialog){const r=cardDialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)cardDialog.close();}});
document.addEventListener('click',async e=>{const a=e.target.closest('a[href]');if(!a)return;const match=a.getAttribute('href').match(/^\/deck\/(\d+)(?:\?.*)?$/);if(!match||e.ctrlKey||e.metaKey||e.shiftKey)return;e.preventDefault();if(!deck.length){await deckReady;}const h=deck.find(h=>h.number===Number(match[1]));if(h){openCard(h);}else{location.href=a.href;}});

document.querySelectorAll('[data-plate-toggle]').forEach(b=>b.addEventListener('click',()=>{const plate=b.closest('.unified-plate');const expanded=plate.classList.toggle('show-technical');b.setAttribute('aria-expanded',String(expanded));b.textContent=expanded?(zh?'收起排盘详情':'Hide chart details'):(zh?'展开排盘详情':'Show chart details');}));
