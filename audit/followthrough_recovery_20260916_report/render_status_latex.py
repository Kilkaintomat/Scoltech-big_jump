# -*- coding: utf-8 -*-
from pathlib import Path
import hashlib, html, json, re, shutil, sys
source=Path(sys.argv[1]).resolve()
out=Path(sys.argv[2]).resolve()
out.mkdir(parents=True,exist_ok=True)
(out/'fonts').mkdir(exist_ok=True)
font_source=Path('/beegfs/home/denis.rakhmankin/onebigjump-inference-audit-20260911/audit/process_report/typesetting-tools/fonts')
font_names=['LiberationSans-Regular.ttf','LiberationSans-Bold.ttf','LiberationSans-Italic.ttf','LiberationSans-BoldItalic.ttf','DejaVuSans.ttf','DejaVuSans-Bold.ttf','DejaVuSans-Oblique.ttf','DejaVuSans-BoldOblique.ttf','DejaVuSansMono.ttf','DejaVuSansMono-Bold.ttf','DejaVuSansMono-Oblique.ttf','DejaVuSansMono-BoldOblique.ttf','Liberation-LICENSE.txt','DejaVu-LICENSE.txt']
for name in font_names:shutil.copy2(font_source/name,out/'fonts'/name)
text=(source/'REPORT_RU.md').read_text(encoding='utf-8')
removed='В текущем оформленном протоколе нет реализованной последовательности P6, P7 и далее. Более широкие идеи обсуждаются отдельно и не считаются уже запущенными экспериментами.'
text=text.replace(removed,'')
text=text.replace('Меняется ли хвостовой показатель при переходе небольшой обучаемой модели к обобщению?', 'Меняются ли редкие большие скачки внутри модели, когда она начинает правильно решать новые примеры?')
text=text.replace('P4 использует небольшую модель на модульном сложении: вход — два числа a и b, правильный класс — остаток (a+b) mod 113. Обобщение означает правильные ответы на комбинациях, которые не входили в обучение. Grokking — название наблюдаемого в некоторых задачах позднего перехода к обобщению после длительного обучения; сам переход здесь ещё не наблюдался, потому что новая серия не начала обучение.', 'В P4 небольшая модель учится складывать два числа и брать остаток при делении на 113. Например, для 111 и 5 правильный ответ — 3, потому что 116 = 113 + 3. Модель обучается на части пар чисел, после чего её проверяют на остальных. Правильные ответы на новых парах называются обобщением. Мы хотим проверить, меняется ли характер редких больших скачков внутренних состояний при появлении этой способности. Grokking — название позднего перехода к обобщению после длительного обучения. В новой серии такой переход ещё не наблюдался: обучение на дату отчёта не началось.')
text=text.replace('Сравнение включает пять пар с разными начальными состояниями случайного генератора: обычная задача и контроль со случайно перемешанными целевыми классами. В контроле разрушается систематическое правило между входом и ответом. Это позволяет сопоставить обучение закономерности с обучением на случайном соответствии.', 'Для сравнения такую же модель обучают на тех же входах, но правильные ответы случайно переставляют между примерами. Метка здесь означает целевой ответ, которому модель учат. После перестановки вместо правила сложения получается случайное соответствие. Сравнение обычного обучения с таким контролем помогает проверить, связано ли изменение скачков с освоением закономерности. Предусмотрены пять пар обучений с разными начальными состояниями случайного генератора.')
# Parse the existing report into paragraphs, headings, tables, images and links.
blocks=[]
text=re.sub(r'(?m)^(\d+\.)',r'\n\1',text)
lines=text.splitlines(); i=0
while i<len(lines):
 line=lines[i].strip()
 if not line:i+=1;continue
 if line.startswith('#'):
  match=re.match(r'^(#+)\s+(.*)$',line);blocks.append(('heading',(len(match.group(1)),match.group(2))));i+=1;continue
 if line.startswith('|'):
  rows=[]
  while i<len(lines) and lines[i].strip().startswith('|'):
   cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
   if not all(re.fullmatch(r':?-+:?',x) for x in cells):rows.append(cells)
   i+=1
  if rows[0]==['Обозначение','Проверяемое предсказание','Где проверяем сейчас']:
   rows=[r[:2] for r in rows]
  blocks.append(('table',rows));continue
 if line.startswith('!['):
  match=re.fullmatch(r'!\[(.*?)\]\((.*?)\)',line)
  if not match:raise ValueError(line)
  blocks.append(('image',match.groups()));i+=1;continue
 match=re.fullmatch(r'\[(.*?)\]\((.*?)\)(.*)',line)
 if match:
  blocks.append(('link',match.groups()));i+=1;continue
 paragraph=[line];i+=1
 while i<len(lines) and lines[i].strip() and not lines[i].lstrip().startswith(('#','|','![')):
  paragraph.append(lines[i].strip());i+=1
 blocks.append(('paragraph',' '.join(paragraph)))
assert all('Где проверяем сейчас' not in str(b) for b in blocks)
assert removed not in str(blocks)

# Keep editable Markdown and browser versions synchronized with the LaTeX edition.
md=[];web=[]
for kind,value in blocks:
 if kind=='heading':
  level,title=value;md.append('#'*level+' '+title);web.append('<h{0}>{1}</h{0}>'.format(level,html.escape(title)))
 elif kind=='paragraph':md.append(value);web.append('<p>'+html.escape(value)+'</p>')
 elif kind=='table':
  header=value[0];md.append('| '+' | '.join(header)+' |\n| '+' | '.join(['---']*len(header))+' |\n'+'\n'.join('| '+' | '.join(r)+' |' for r in value[1:]))
  web.append('<div class="table"><table><thead><tr>'+''.join('<th>'+html.escape(x)+'</th>' for x in header)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(x)+'</td>' for x in r)+'</tr>' for r in value[1:])+'</tbody></table></div>')
 elif kind=='image':
  caption,filename=value;md.append('!['+caption+']('+filename+')');web.append('<figure><img src="'+html.escape(filename,quote=True)+'" alt="'+html.escape(caption,quote=True)+'"><figcaption>'+html.escape(caption)+'</figcaption></figure>')
 elif kind=='link':
  label,url,suffix=value;md.append('['+label+']('+url+')'+suffix);web.append('<p><a href="'+html.escape(url,quote=True)+'">'+html.escape(label)+'</a>'+html.escape(suffix)+'</p>')
(out/'REPORT.md').write_text('\n\n'.join(md)+'\n',encoding='utf-8')
style='body{font:17px/1.65 system-ui,sans-serif;color:#1d2935;max-width:1120px;margin:40px auto;padding:0 24px}h1{font-size:2rem;line-height:1.2}h2{margin-top:2.4em;border-top:1px solid #d5dee6;padding-top:1em}p{max-width:95ch}.table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:.9rem;margin:1.2em 0}th,td{text-align:left;vertical-align:top;padding:9px 11px;border:1px solid #d5dee6;overflow-wrap:anywhere}th{background:#ecf3f8}tr:nth-child(even){background:#f9fbfc}img{max-width:100%;height:auto}figure{margin:1em 0}figcaption{font-size:.9rem;color:#516575}a{color:#155b82}@media print{body{font-size:10pt;margin:0;max-width:none}h2{break-after:avoid}.table{overflow:visible}table{font-size:8pt}tr{break-inside:avoid}}'
(out/'REPORT.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>One Big Jump — эксперименты и результаты</title><style>'+style+'</style><body>'+''.join(web)+'</body></html>',encoding='utf-8')

symbols={'γ':r'\(\gamma\)','α':r'\(\alpha\)','τ':r'\(\tau\)','θ':r'\(\theta\)','σ':r'\(\sigma\)','μ':r'\(\mu\)','≤':r'\(\leq\)','≥':r'\(\geq\)','−':r'\( - \)','×':r'\(\times\)','³':r'\(^{3}\)','²':r'\(^{2}\)','⁻':r'\(^{-}\)','⇒':r'\(\Rightarrow\)'}
maths={
 'H_alg':r'\(H_{\mathrm{alg}}\)','H_heur':r'\(H_{\mathrm{heur}}\)',
 'X_(t−1)':r'\(X_{t-1}\)','X_t':r'\(X_t\)','Z_t':r'\(Z_t\)','t*':r'\(t^{*}\)',
 'xi = max(γ, 0)':r'\(\xi=\max(\gamma,0)\)','α = 1/γ':r'\(\alpha=1/\gamma\)',
 'Y = Z − τ':r'\(Y=Z-\tau\)','Z > τ':r'\(Z>\tau\)','γ ≤ −1':r'\(\gamma\leq -1\)',
 'γ=0,25':r'\(\gamma=0{,}25\)','γ=0,1':r'\(\gamma=0{,}1\)','γ=0,5':r'\(\gamma=0{,}5\)',
 'γ = 0,1':r'\(\gamma=0{,}1\)','γ = 0,5':r'\(\gamma=0{,}5\)',
 'τ < c':r'\(\tau<c\)','c−τ':r'\(c-\tau\)','F̄(τ)':r'\(\overline F(\tau)\)',
 'α/(2×9)':r'\(\alpha/(2\times9)\)','α = 0,05':r'\(\alpha=0{,}05\)',
 '(a+b) mod 113':r'\((a+b)\bmod 113\)',
 '4x³ − 7y³':r'\(4x^{3}-7y^{3}\)',
}
escapes={'\\':r'\textbackslash{}','{':r'\{','}':r'\}','%':r'\%','&':r'\&','#':r'\#','$':r'\$','_':r'\_','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
pattern=re.compile('|'.join(re.escape(k) for k in sorted(maths,key=len,reverse=True))+r'|[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+')
def plain(value):return ''.join(symbols.get(c,escapes.get(c,c)) for c in value)
def tex(value):
 result=[];last=0
 for match in pattern.finditer(value):
  result.append(plain(value[last:match.start()]));word=match.group()
  if word in maths:result.append(maths[word])
  else:result.append(r'\texttt{'+r'\_\allowbreak{}'.join(plain(part) for part in word.split('_'))+'}')
  last=match.end()
 result.append(plain(value[last:]));return ''.join(result)

preamble=r'''% !TeX program = xelatex
% Compile twice with XeLaTeX, or use Tectonic. Keep calibration-coverage.png beside this file.
\documentclass[11pt,a4paper]{article}
\usepackage{fontspec}
\setmainfont{LiberationSans}[Path=fonts/,Extension=.ttf,UprightFont=*-Regular,BoldFont=*-Bold,ItalicFont=*-Italic,BoldItalicFont=*-BoldItalic]
\setsansfont{DejaVuSans}[Path=fonts/,Extension=.ttf,UprightFont=*,BoldFont=*-Bold,ItalicFont=*-Oblique,BoldItalicFont=*-BoldOblique]
\setmonofont{DejaVuSansMono}[Path=fonts/,Extension=.ttf,UprightFont=*,BoldFont=*-Bold,ItalicFont=*-Oblique,BoldItalicFont=*-BoldOblique,Scale=0.88]
\usepackage[english,russian]{babel}
\usepackage{amsmath,amssymb}
\usepackage[margin=22mm,headheight=16pt]{geometry}
\usepackage{graphicx,array,longtable,booktabs}
\usepackage[table]{xcolor}
\usepackage{ragged2e}
\usepackage{titlesec}
\usepackage{fancyhdr}
\usepackage[unicode,colorlinks=true,linkcolor=blue!45!black,urlcolor=blue!45!black]{hyperref}
\hypersetup{pdftitle={One Big Jump: эксперименты и промежуточные результаты},pdfauthor={},pdfsubject={Отчёт об исследовании связи внутренних состояний модели с ошибками}}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.6em}
\setlength{\emergencystretch}{2em}
\setlength{\tabcolsep}{5pt}
\renewcommand{\arraystretch}{1.23}
\setlength{\LTpre}{0.65em}
\setlength{\LTpost}{0.75em}
\newcolumntype{P}[1]{>{\RaggedRight\arraybackslash}p{#1}}
\titleformat{\section}{\Large\sffamily\bfseries\color{blue!35!black}}{\thesection.}{0.6em}{}
\titlespacing*{\section}{0pt}{1.5em}{0.6em}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small\sffamily One Big Jump}
\fancyhead[R]{\small\sffamily Промежуточные результаты}
\fancyfoot[C]{\small\thepage}
\renewcommand{\headrulewidth}{0.3pt}
\widowpenalty=10000
\clubpenalty=10000
\begin{document}
\begin{center}
{\LARGE\sffamily\bfseries One Big Jump\par}
\vspace{0.4em}
{\Large\sffamily Эксперименты, данные\par и промежуточные результаты\par}
\end{center}
'''
latex=[preamble]
first_section=True

def latex_table(rows):
 headers=rows[0]; n=len(headers)
 if n==7:
  for cols in [[0,1,2,3],[0,4,5,6]]:latex_table([[r[c] for c in cols] for r in rows])
  return
 if n==6:
  groups=[[0,1,2,3],[0,1,4,5]] if headers[0]=='Сценарий' else [[0,1,2],[0,3,4,5]]
  for cols in groups:latex_table([[r[c] for c in cols] for r in rows])
  return
 if n==2:weights=[.15,.85] if headers[0]=='Обозначение' else [.2,.8]
 elif n==3:weights=[.20,.40,.40]
 elif n==4:weights=[.25,.17,.29,.29]
 elif n==5:weights=[.14,.23,.21,.21,.21]
 else:weights=[1/n]*n
 if headers[0]=='Эксперимент':weights=[.23,.45,.32]
 if headers[0]=='Приоритет':weights=[.12,.42,.46]
 if headers[0]=='Сценарий' and n==4:
  weights=[.22,.37,.28,.13] if headers[1]=='Как устроен' else [.26,.12,.31,.31]
 if headers[0].startswith('Дополнительная диагностика'):weights=[.29,.12,.24,.35]
 if headers[0]=='Модель' and n==4 and headers[1]!='Ответы':weights=[.16,.27,.27,.30]
 # Text width is 166 mm; subtract intercolumn spaces (10pt per column).
 usable=166-n*3.515
 spec='@{}'+''.join('P{%.2fmm}'%(usable*w) for w in weights)+'@{}'
 latex.append(r'\begingroup\fontsize{9.3}{12}\selectfont')
 latex.append(r'\begin{longtable}{'+spec+'}')
 header=' & '.join(r'\textbf{'+tex(h)+'}' for h in headers)+r' \\'
 latex.extend([r'\toprule',header,r'\midrule',r'\endfirsthead',r'\toprule',header,r'\midrule',r'\endhead',r'\bottomrule',r'\endfoot'])
 for row in rows[1:]:latex.append(' & '.join(tex(c) for c in row)+r' \\[3pt]')
 latex.extend([r'\end{longtable}',r'\endgroup'])

for kind,value in blocks:
 if kind=='heading':
  level,title=value
  if level==1:continue
  if first_section:
   first_section=False
  latex.append(r'\section{'+tex(re.sub(r'^\d+\.\s*','',title))+'}')
 elif kind=='paragraph':
  latex.append(tex(value)+'\n')
  if value.startswith('Пусть X_t'):
   latex.append(r'''\[
   \Delta_t=X_t-X_{t-1},\qquad Z_t=\lVert\Delta_t\rVert_2.
   \]
   ''')
 elif kind=='table':latex_table(value)
 elif kind=='image':
  caption,filename=value
  latex.extend([r'\begin{figure}[htbp]',r'\centering',r'\includegraphics[width=\linewidth]{'+filename+'}',r'\caption{'+tex(caption)+'}',r'\end{figure}'])
 elif kind=='link':
  label,url,suffix=value
  latex.append(r'\href{'+url+'}{'+tex(label)+'}'+tex(suffix)+'\n')
latex.append(r'\end{document}')
(out/'REPORT.tex').write_text('\n'.join(latex)+'\n',encoding='utf-8')
for name in ['metrics.json']:
 shutil.copy2(source/name,out/name)
shutil.copy2(Path(__file__),out/'render_latex.py')
# This rendering receipt is extended after PDF compilation by finalize_latex.py.
receipt={'stage':'latex-editorial-render','source_report':str(source/'REPORT_RU.md'),'source_report_sha256':hashlib.sha256((source/'REPORT_RU.md').read_bytes()).hexdigest(),'source_manifest':str(source/'manifest.json'),'source_manifest_sha256':hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest(),'changes':['typeset_dated_status_report_without_changing_scientific_metrics'],'scientific_metrics_unchanged':hashlib.sha256((source/'metrics.json').read_bytes()).hexdigest()==hashlib.sha256((out/'metrics.json').read_bytes()).hexdigest()}
(out/'render-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Rendered LaTeX, Markdown and HTML')
