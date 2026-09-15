"""Render static scientific figures strictly from saved histogram metrics."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter, MaxNLocator

BLUE="#245C91"
ORANGE="#D36B28"
GRAY="#64717D"
INK="#203449"
BG="#FFFFFF"
PURPLE="#6553A3"

def style_axes(ax):
    ax.set_facecolor(BG)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CCD3DA")
    ax.spines["bottom"].set_color("#CCD3DA")
    ax.tick_params(axis="both",colors=INK,length=3)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100,decimals=0))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
    ax.grid(axis="y",color="#E7ECF1",linewidth=.75)
    ax.set_axisbelow(True)

def axes_row(axes,m,metrics,ylimits=None):
    plan=metrics["config"];h=m["histograms"];cap=plan["absolute_individual_steps"]
    left,center,right=axes
    for ax in axes:style_axes(ax)
    x=np.arange(cap+1)
    left.bar(x-.2,h["absolute_error"]["percent"],width=.38,color=BLUE)
    left.bar(x+.2,h["absolute_maximum"]["percent"],width=.38,color=ORANGE)
    left.plot(x,h["absolute_uniform"]["percent"],color=GRAY,linestyle=":",linewidth=1.5,zorder=4)
    steps=[1,5,10,15,20,cap+1]
    left.set_xticks([s-1 for s in steps],["1","5","10","15","20",f"{cap+1}+"])
    left.set_xlim(-.75,cap+.8)
    left.set_xlabel("Номер формального шага")
    left.set_ylabel("Доля попыток")
    nbins=plan["relative_bins"];edges=np.asarray(metrics["bins"]["relative_edges"])
    width=1/nbins;cx=(edges[:-1]+edges[1:])/2
    center.bar(cx-width*.2,h["relative_error"]["percent"],width=width*.39,color=BLUE)
    center.bar(cx+width*.2,h["relative_maximum"]["percent"],width=width*.39,color=ORANGE)
    center.plot(cx,h["relative_uniform"]["percent"],color=GRAY,linestyle=":",linewidth=1.5,zorder=4)
    center.set_xlim(-.012,1.012)
    center.set_xticks([0,.25,.5,.75,1],["0","0,25","0,5","0,75","1"])
    center.set_xlabel("От первого (0) до последнего (1) шага")
    bound=plan["offset_individual_bound"];dx=np.arange(2*bound+3);zero=bound+1
    colors=[ORANGE if k==zero else PURPLE for k in dx]
    right.bar(dx,h["offset"]["percent"],width=.77,color=colors)
    right.plot(dx,h["offset_uniform"]["percent"],color=GRAY,linestyle=":",linewidth=1.5,zorder=4)
    ticks=[0,zero-5,zero,zero+5,2*bound+2]
    ticklabels=[f"≤−{bound+1}","−5","0","+5",f"≥{bound+1}"]
    right.set_xticks(ticks,ticklabels,fontsize=8)
    right.set_xlim(-.8,len(dx)-.2)
    right.set_xlabel("D = шаг максимума − шаг ошибки")
    right.text(.97,.96,f"Совпадение: {m['exact_percent']:.1f}%",ha="right",va="top",
               transform=right.transAxes,color=INK,fontsize=10,fontweight="bold",
               bbox={"facecolor":"white","edgecolor":"none","alpha":.85,"pad":3})
    if ylimits:
        for ax,limit in zip(axes,ylimits):ax.set_ylim(0,limit)

def legend():
    return [Patch(facecolor=BLUE,label="Первая ошибка Lean"),
            Patch(facecolor=ORANGE,label="Максимальный скачок"),
            Line2D([0],[0],color=GRAY,linestyle=":",linewidth=1.8,label="Равномерный выбор шага в каждой трассе")]

def page(metrics,case,fold,only=None):
    plan=metrics["config"];models=list(metrics["views"][case][str(fold)])
    if only is not None:models=[only]
    nrows=len(models)
    fig,axes=plt.subplots(nrows,3,figsize=(16.6,12.0 if nrows==3 else 5.5),squeeze=False,facecolor="white")
    if nrows==3:
        fig.subplots_adjust(left=.065,right=.98,top=.79,bottom=.12,hspace=.73,wspace=.29)
    else:
        fig.subplots_adjust(left=.06,right=.98,top=.61,bottom=.22,wspace=.28)
    cases={"all_errors":"Все попытки с локализованной ошибкой",
           "later_errors":"Исключены ошибки на первом шаге",
           "later_errors_drop_first_increment":"Исключены ошибки на первом шаге и первое приращение"}
    title="Где первая ошибка и где максимальный скачок"
    if only:title=plan["display_names"][only]+" · "+title.lower()
    fig.suptitle(title,x=.065 if not only else .06,y=.975,ha="left",fontsize=20,fontweight="bold",color=INK)
    fig.text(.065 if not only else .06,.934 if nrows==3 else .905,cases[case],ha="left",fontsize=12,color=INK)
    fig.text(.065 if not only else .06,.908 if nrows==3 else .85,
             f"Whitened · начало у формального доказательства · T = {plan['temperature']} · калибровка {fold} · равный вес попыток",
             ha="left",fontsize=9.5,color=GRAY)
    fig.legend(handles=legend(),loc="upper left",bbox_to_anchor=(.06,.888 if nrows==3 else .823),
               ncol=3,frameon=False,fontsize=10,handlelength=1.8,columnspacing=2)
    families=[("absolute_error","absolute_maximum","absolute_uniform"),
              ("relative_error","relative_maximum","relative_uniform"),("offset","offset_uniform")]
    limits=[]
    for keys in families:
        highest=max(max(metrics["views"][case][str(fold)][model]["histograms"][key]["percent"])
                    for model in models for key in keys)
        limits.append(max(5,highest*1.18))
    for row,model in enumerate(models):
        m=metrics["views"][case][str(fold)][model]
        axes_row(axes[row],m,metrics,limits)
        titles=["Позиции по номеру шага","Позиции с учётом длины","Максимум относительно ошибки"]
        for col,title in enumerate(titles):
            axes[row,col].set_title(title,loc="left",pad=9,color=INK,fontsize=11,fontweight="bold")
        label=f"{plan['display_names'][model]}  ·  {m['traces']} попыток / {m['tasks']} задач"
        axes[row,0].text(0,1.31 if nrows==3 else 1.30,label,transform=axes[row,0].transAxes,
                         fontsize=12,fontweight="bold",color=INK,ha="left")
    footer=(
      "Те же трассы для ошибки и максимума. Серый ориентир учитывает длины; он не проверяет связь сверх типичных позиций.\n"
      f"Шаги ≥{plan['absolute_individual_steps']+1} и смещения за ±{plan['offset_individual_bound']} объединены в крайние столбцы. "
      "После первой ошибки шаги имеют статус unreached."
    )
    fig.text(.065 if not only else .06,.045 if nrows==3 else .05,footer,ha="left",va="bottom",
             fontsize=9,color=GRAY,linespacing=1.55)
    return fig

def render(path,folder):
    metrics=json.loads(Path(path).read_text(encoding="utf-8"));folder=Path(folder)
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"pdf.fonttype":42,"svg.fonttype":"none",
                         "axes.unicode_minus":True,"savefig.facecolor":"white"})
    outputs=[]
    pdf=folder/"position_histograms_all.pdf"
    with PdfPages(pdf,metadata={"Title":"Позиции первой ошибки и максимального скачка","Author":"OneBigJump experiment pipeline"}) as pages:
        for fold in metrics["config"]["folds"]:
            for case in metrics["config"]["cases"]:
                fig=page(metrics,case,fold)
                pages.savefig(fig)
                if fold==0:
                    name={"all_errors":"all_models","later_errors":"later_errors",
                          "later_errors_drop_first_increment":"later_errors_drop_first_increment"}[case]
                    for extension in ["png","svg"]:
                        dst=folder/(name+"."+extension)
                        fig.savefig(dst,dpi=180)
                        outputs.append(dst)
                plt.close(fig)
    outputs.append(pdf)
    for model in metrics["config"]["display_names"]:
        fig=page(metrics,"all_errors",0,model)
        for extension in ["png","pdf","svg"]:
            dst=folder/(model+"."+extension)
            fig.savefig(dst,dpi=180)
            outputs.append(dst)
        plt.close(fig)
    renderer_metadata=folder/"rendering.json"
    renderer_metadata.write_text(json.dumps({"matplotlib":matplotlib.__version__,"backend":matplotlib.get_backend(),
        "font":"DejaVu Sans","source_metrics":str(path),"pdf_pages":len(metrics["config"]["folds"])*len(metrics["config"]["cases"])},indent=2)+"\n",encoding="utf-8")
    outputs.append(renderer_metadata)
    return outputs
