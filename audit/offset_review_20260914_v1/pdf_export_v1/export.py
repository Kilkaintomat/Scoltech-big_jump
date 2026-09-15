from __future__ import annotations
import datetime,hashlib,html,importlib.metadata,json,os,pathlib,platform,re,subprocess,sys
ROOT=pathlib.Path('/beegfs/home/denis.rakhmankin/onebigjump')
HERE=ROOT/'audit/offset_review_20260914_v1/pdf_export_v1'
REPORT=HERE.parent/'result-8466720'
job=os.environ['SLURM_JOB_ID']; OUT=HERE/('result-'+job);OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
md=REPORT/'REPORT_RU.md'; chart=REPORT/'offsets.png'
source_manifest=json.loads((REPORT/'render-manifest.json').read_text())
for p in (md,chart):
 assert sha(p)==source_manifest['outputs'][str(p)],p
deps=HERE/'deps'
if not (deps/'reportlab').is_dir():
    subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--no-cache-dir','--no-deps',
                   '--target',str(deps),'--report',str(OUT/'dependency-install.json'),'reportlab'],check=True)
else:
    (OUT/'dependency-install.json').write_text(json.dumps({'reused_from':str(deps),'original_install_manifest':str(HERE/'result-8466730/dependency-install.json')}))
sys.path.insert(0,str(deps))
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from matplotlib import font_manager
from PIL import Image as PILImage
fontpath=font_manager.findfont('DejaVu Sans')
boldpath=font_manager.findfont(font_manager.FontProperties(family='DejaVu Sans',weight='bold'))
pdfmetrics.registerFont(TTFont('DejaVu',fontpath))
pdfmetrics.registerFont(TTFont('DejaVuBold',boldpath))
pdfmetrics.registerFontFamily('DejaVu',normal='DejaVu',bold='DejaVuBold',italic='DejaVu',boldItalic='DejaVuBold')
styles={
 'body':ParagraphStyle('body',fontName='DejaVu',fontSize=9.2,leading=13.3,spaceAfter=8),
 'section':ParagraphStyle('section',fontName='DejaVuBold',fontSize=11.2,leading=15,spaceBefore=13,spaceAfter=7,keepWithNext=True),
 'title':ParagraphStyle('title',fontName='DejaVuBold',fontSize=18,leading=23,spaceAfter=14,keepWithNext=True),
 'table':ParagraphStyle('table',fontName='DejaVu',fontSize=7.3,leading=10),
 'th':ParagraphStyle('th',fontName='DejaVuBold',fontSize=7.3,leading=10),
}
def rich(s):
 s=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'\1 (\2)',s)
 s=html.escape(s)
 return re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s)
story=[];table_count=0;para_count=0;image_count=0
for i,c in enumerate(md.read_text().strip().split('\n\n')):
 if not c.strip():continue
 if c.startswith('|'):
  ls=c.splitlines();rows=[[x.strip() for x in l.strip('|').split('|')] for l in [ls[0],*ls[2:]]]
  assert len({len(r) for r in rows})==1
  nc=len(rows[0]); widths=[491/nc]*nc
  if nc>=5:
   widths=[61]+[(491-61)/(nc-1)]*(nc-1)
  values=[[Paragraph(rich(x),styles['th'] if k==0 else styles['table']) for x in r] for k,r in enumerate(rows)]
  tab=Table(values,colWidths=widths,repeatRows=1,hAlign='LEFT')
  tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eaf0f4')),
       ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.35,colors.HexColor('#d6e0e7')),
       ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
       ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
  story.extend([tab,Spacer(1,9)]);table_count+=1
 elif c.startswith('!['):
  with PILImage.open(chart) as im:w,h=im.size
  story.extend([Image(str(chart),width=491,height=491*h/w),Spacer(1,10)]);image_count+=1
 else:
  style=styles['title'] if i==0 else styles['section'] if re.fullmatch(r'\*\*[^*]+\*\*',c) else styles['body']
  story.append(Paragraph(rich(c),style));para_count+=1
pages=[]
def footer(canvas,doc):
 pages.append(doc.page)
 canvas.saveState();canvas.setStrokeColor(colors.HexColor('#ced8df'));canvas.line(52,37,543,37)
 canvas.setFont('DejaVu',7.5);canvas.setFillColor(colors.HexColor('#52606b'))
 canvas.drawString(52,24,'ONE BIG JUMP · отчёт по сохранённым экспериментам')
 canvas.drawRightString(543,24,str(doc.page));canvas.restoreState()
pdf=OUT/'REPORT_RU.pdf'
doc=SimpleDocTemplate(str(pdf),pagesize=A4,rightMargin=52,leftMargin=52,topMargin=42,bottomMargin=50,
 title='ONE BIG JUMP — отчёт по результатам экспериментов',author='ONE BIG JUMP experiment audit')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
receipt={'stage':'pdf-export','job':job,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'git_commit':os.environ.get('ONEBIGJUMP_GIT_COMMIT'),'git_dirty':bool(os.environ.get('ONEBIGJUMP_GIT_STATUS')),
 'config':{'input':'existing report; no numerical or narrative changes','pagesize':'A4','font':'DejaVu Sans'},
 'environment':{'hostname':platform.node(),'platform':platform.platform(),'python':sys.version,
     'reportlab':importlib.metadata.version('reportlab'),'allocated_cpus':os.environ.get('SLURM_CPUS_PER_TASK')},
 'inputs':{str(p):sha(p) for p in (md,chart,REPORT/'render-manifest.json',HERE/'export.py',HERE/'export.sbatch',pathlib.Path(fontpath),pathlib.Path(boldpath))},
 'outputs':{str(p):sha(p) for p in (pdf,OUT/'dependency-install.json')},
 'metrics':{'pages':len(pages),'tables':table_count,'paragraphs':para_count,'figures':image_count,'pdf_bytes':pdf.stat().st_size}}
(OUT/'manifest.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print('PDF_READY',str(pdf),json.dumps(receipt['metrics']),flush=True)
