"""Self-contained bilingual UI preview. No AI requests or payment transactions."""
import base64,json,re,sys
from pathlib import Path
from app import app
from hexagrams import HEXAGRAMS
ROOT=Path(__file__).resolve().parent
main=lambda html:re.search(r'<main>(.*?)</main>',html,re.S).group(1)
bodies={};shell=''
for lang in ('zh','en'):
 client=app.test_client();pages={n:client.get(route+'?lang='+lang).data.decode() for n,route in [('home','/'),('deck','/deck'),('demo','/demo')]}
 page=pages['home'];notice='交互预览：按真实六次结果展示卦象与动爻；教学示例独立呈现。本文件不连接 AI 或付款。' if lang=='zh' else 'Interactive preview: your six results determine the images and changing lines. The teaching example is separate. This file makes no AI requests or payments.'
 contents='<div class="notice">'+notice+'</div>'+''.join('<section id="offline-'+n+'"'+(' hidden' if n!='home' else '')+'>'+main(html)+'</section>' for n,html in pages.items())
 page=re.sub(r'<main>.*?</main>',lambda m:'<main>'+contents+'</main>',page,flags=re.S)
 bodies[lang]=re.search(r'<body[^>]*>(.*?)</body>',page,re.S).group(1)
 if lang=='zh':shell=page
css=(ROOT/'static/site.css').read_text()
for path in (ROOT/'static/art').glob('*.webp'):css=css.replace('art/'+path.name,'data:image/webp;base64,'+base64.b64encode(path.read_bytes()).decode())
shell=re.sub(r'<link rel="stylesheet"[^>]+>',lambda m:'<style>'+css+'</style>',shell)
shell=re.sub(r'<script src="[^>]+></script>','',shell)
js=(ROOT/'static/site.js').read_text()
offline='''
function offlinePage(n){for(const name of ['home','deck','demo'])document.getElementById('offline-'+name).hidden=name!==n;window.scrollTo(0,0);}
document.querySelectorAll('a').forEach(a=>{const href=a.getAttribute('href')||'';if(/^\\/deck\\/\\d+$/.test(href))return;const switchLang=href.match(/[?&]lang=(en|zh)/);if(switchLang){a.href='#'+switchLang[1];a.addEventListener('click',e=>{e.preventDefault();try{localStorage.setItem('answer-book-preview-lang',switchLang[1]);}catch{}location.hash=switchLang[1];location.reload();});return;}if(href.startsWith('/')){const n=href==='/deck'?'deck':href==='/demo'||href==='/history'?'demo':'home';a.href='#'+n;a.addEventListener('click',e=>{e.preventDefault();offlinePage(n);});}});
form?.addEventListener('submit',e=>{e.preventDefault();document.getElementById('loading').hidden=true;document.getElementById('read-button').disabled=false;if(!form.checkValidity()){form.reportValidity();return;}preview();const holder=document.getElementById('cast-preview');let note=document.getElementById('offline-reading-note');if(!note){note=document.createElement('p');note.id='offline-reading-note';note.className='notice';holder.after(note);}note.textContent=zh?'以上卦象与动爻来自你刚才的六次结果。此预览不生成个人解读；点击“先看示例”可查看独立教学内容。':'These images and changing lines follow your six results. This preview does not generate personal readings. Explore the separate teaching example for sample interpretation.';holder.scrollIntoView({behavior:'smooth',block:'start'});});
'''
setup='window.offlineDeck='+json.dumps(HEXAGRAMS,ensure_ascii=False)+';window.offlineBodies='+json.dumps(bodies,ensure_ascii=False)+''';let previewLang=location.hash==='#en'?'en':location.hash==='#zh'?'zh':null;try{previewLang=previewLang||localStorage.getItem('answer-book-preview-lang');}catch{}previewLang=previewLang==='en'?'en':'zh';document.body.dataset.lang=previewLang;document.documentElement.lang=previewLang==='en'?'en':'zh-CN';document.body.innerHTML=window.offlineBodies[previewLang];document.title=previewLang==='en'?'Your Answer Book · Preview':'你的答案之书 · 交互预览';'''
shell=re.sub(r'<body[^>]*>.*?</body>',lambda m:'<body data-lang="zh"><script>'+setup.replace('</','<\\/')+'</script><script>'+js+'\n'+offline+'</script></body>',shell,flags=re.S)
output=Path(sys.argv[1] if len(sys.argv)>1 else ROOT.parent/'answer-book-v4-preview.html');output.write_text(shell);print(output)
