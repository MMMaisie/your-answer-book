"""Export saved text only. No model calls and no remotely loaded resources."""
import io,json
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,KeepTogether
from i18n import EN
pdfmetrics.registerFont(TTFont('BookText',str(Path(__file__).parent/'fonts'/'NotoSansSC.ttf')))

def reading_pdf(row,lang,paid):
 out=io.BytesIO();doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=42,leftMargin=42,topMargin=42,bottomMargin=42,title='Your Answer Book',author='Your Answer Book')
 base=ParagraphStyle('body',fontName='BookText',fontSize=11,leading=18,wordWrap='CJK',spaceAfter=10)
 title=ParagraphStyle('title',parent=base,fontSize=22,leading=29,textColor=colors.HexColor('#254a45'),spaceAfter=18)
 small=ParagraphStyle('small',parent=base,fontSize=9,leading=14,textColor=colors.HexColor('#555555'))
 sub=ParagraphStyle('sub',parent=base,fontSize=14,leading=21,spaceBefore=12)
 def tr(value):
  if lang=='zh':return str(value)
  value=str(value)
  if value in EN:return EN[value]
  if value and all(c in '甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥' for c in value):return ' '.join(EN[c] for c in value)
  return value
 def p(text,style=base):return Paragraph(escape(str(text)).replace('\n','<br/>'),style)
 cast=json.loads(row['cast_json']);zh=lang=='zh'
 flow=[p('你的答案之书' if zh else 'Your Answer Book',title),p(row['question']),p(cast.get('calendar',{}).get('beijing_time','')+(' · 北京时间' if zh else ' - Beijing time'),small),p(cast['main']['name']+(' → '+cast['changed']['name'] if cast.get('moving') else '（静卦）') if zh else cast['main'].get('name_en',cast['main']['name'])+(' -> '+cast['changed'].get('name_en',cast['changed']['name']) if cast.get('moving') else ' (Static)'),sub)]
 table=[[p('爻位 / 世应' if zh else 'Line / Role',small),p('六亲 / 纳甲' if zh else 'Relationship / Branch',small),p('动变' if zh else 'Change',small)]]
 for r in reversed(cast['rows']):
  a=f"{r['position']} {tr(r.get('label',''))}";b=' '.join(tr(r[k]) for k in ('kin','stem','branch','element'));changed=r.get('changed')
  end=(' '.join(tr(changed[k]) for k in ('kin','branch','element'))) if changed else ('静' if zh else 'Static')
  table.append([p(a,small),p(b,small),p(end,small)])
 grid=Table(table,colWidths=[100,220,150],repeatRows=1,hAlign='LEFT');grid.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eef2ec')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),0.3,colors.HexColor('#dddddd')),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),3)]));flow.extend([grid,Spacer(1,14)])
 for tier,heading in [('free','初判' if zh else 'Initial reading'),('paid','完整解读' if zh else 'Full reading')]:
  if tier=='paid' and not paid:continue
  text=row.get(tier+'_'+lang,'')
  if text:flow.extend([p(heading,sub),p(text)])
 flow.append(p('请自行保存。线上解读仅临时保存10天；传统文化与反思用途，不保证预测结果。' if zh else 'Keep this file. Online readings are stored temporarily for 10 days. For cultural reflection; predictions are not guaranteed.',small))
 def footer(canvas,document):
  canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#666666'));canvas.drawRightString(A4[0]-42,24,f'Your Answer Book | {document.page}')
 doc.build(flow,onFirstPage=footer,onLaterPages=footer)
 return out.getvalue()
