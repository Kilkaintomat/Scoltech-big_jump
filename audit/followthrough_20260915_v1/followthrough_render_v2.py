import html,sys
from stage_support import ROOT
sys.path.insert(0,str(ROOT/"audit/offset_review_20260914_v1/pdf_export_v1/deps"))
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from matplotlib import font_manager
def render(folder,blocks,title):
 pdfmetrics.registerFont(TTFont("DV",font_manager.findfont("DejaVu Sans")))
 pdfmetrics.registerFont(TTFont("DVB",font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans",weight="bold"))))
 styles={"p":ParagraphStyle("body",fontName="DV",fontSize=9,leading=13,spaceAfter=7),
  "h":ParagraphStyle("heading",fontName="DVB",fontSize=12,leading=16,spaceBefore=10,spaceAfter=8,keepWithNext=True),
  "cell":ParagraphStyle("cell",fontName="DV",fontSize=7.4,leading=10),"headcell":ParagraphStyle("hc",fontName="DVB",fontSize=7.4,leading=10)}
 def par(t,key="p"):return Paragraph(html.escape(str(t)),styles[key])
 story=[];md=[];ht=[]
 for kind,b in blocks:
  if kind=="h":
   story.append(par(b,"h"));md += ["## "+b,""];ht.append("<h2>"+html.escape(b)+"</h2>")
  elif kind=="p":
   story.append(par(b));md += [b,""];ht.append("<p>"+html.escape(b)+"</p>")
  elif kind=="table":
   heads,rows=b["heads"],b["rows"];widths=b.get("widths") or [491/len(heads)]*len(heads)
   cells=[[par(x,"headcell") for x in heads]]+[[par(x,"cell") for x in row] for row in rows]
   tab=Table(cells,colWidths=widths,repeatRows=1,hAlign="LEFT")
   tab.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e6edf3")),("VALIGN",(0,0),(-1,-1),"TOP"),("LINEBELOW",(0,0),(-1,-1),.25,colors.HexColor("#cad5df")),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
   story.extend([tab,Spacer(1,10)])
   md += ["| "+" | ".join(heads)+" |","| "+" | ".join(["---"]*len(heads))+" |"]+["| "+" | ".join(str(x).replace("|","/") for x in row)+" |" for row in rows]+[""]
   ht.append("<table><thead><tr>"+"".join("<th>"+html.escape(x)+"</th>" for x in heads)+"</tr></thead><tbody>"+"".join("<tr>"+"".join("<td>"+html.escape(str(x))+"</td>" for x in row)+"</tr>" for row in rows)+"</tbody></table>")
  elif kind=="figure":
   im=Image(str(folder/b["file"]));scale=min(491/im.imageWidth,330/im.imageHeight);im.drawWidth=im.imageWidth*scale;im.drawHeight=im.imageHeight*scale
   story.append(KeepTogether([im,par(b["caption"])]));md += ["!["+b["caption"]+"]("+b["file"]+")",""];ht.append('<figure><img src="'+b["file"]+'"><figcaption>'+html.escape(b["caption"])+"</figcaption></figure>")
 pages=[]
 def foot(c,d):
  c.saveState();c.setFillColor(colors.white);c.rect(0,0,A4[0],A4[1],fill=1,stroke=0);c.restoreState()
  pages.append(d.page);c.setFont("DV",8);c.drawString(52,29,"One Big Jump");c.drawRightString(A4[0]-52,29,str(d.page))
 pdf=folder/"REPORT_RU.pdf";doc=SimpleDocTemplate(str(pdf),pagesize=A4,rightMargin=52,leftMargin=52,topMargin=42,bottomMargin=50,title=title)
 doc.build(story,onFirstPage=foot,onLaterPages=foot)
 (folder/"REPORT_RU.md").write_text("\n".join(md),encoding="utf-8")
 (folder/"REPORT_RU.html").write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>'+html.escape(title)+'</title><style>body{max-width:1000px;margin:36px auto;font:17px/1.55 sans-serif;color:#182c3a}table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:8px;border-bottom:1px solid #d2dce5;text-align:left;vertical-align:top}th{background:#e6edf3}img{max-width:100%}p{overflow-wrap:anywhere}</style>'+"".join(ht)+"</html>",encoding="utf-8")
 return max(pages)
