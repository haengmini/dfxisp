"""Figures for the beginner-friendly README (run from anywhere):
  python make_readme_figures.py <repo_root>
Writes <repo_root>/docs/assets/overview_flow.png and summary_accuracy.png.
Numbers are read from docs/experiments/2026-10-v2-board/results/final_live_comparison/comparison.csv (no retyped values).
"""
import csv,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
from matplotlib import font_manager
# Optional Korean font: set DFXISP_FONT to a .ttf path (e.g. Noto Sans KR); otherwise installed fonts are used.
import os
if os.environ.get('DFXISP_FONT') and Path(os.environ['DFXISP_FONT']).exists():font_manager.fontManager.addfont(os.environ['DFXISP_FONT'])
plt.rcParams.update({'font.family':['Noto Sans KR','NanumGothic','DejaVu Sans'],'axes.unicode_minus':False,'svg.fonttype':'none'})
R=Path(sys.argv[1]);A=R/'docs/assets';A.mkdir(parents=True,exist_ok=True)
BLUE,ORANGE,GREEN,GRAY,DARK='#4c72b0','#dd8452','#55a868','#8795a4','#222222'

# ---------- Figure 1: how the system works ----------
fig,ax=plt.subplots(figsize=(15,5.6));ax.set_xlim(0,15);ax.set_ylim(-0.2,5.4);ax.axis('off')
def box(x,y,w,h,txt,fc,tc='white',fs=13,ec=None):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.02,rounding_size=0.15',fc=fc,ec=ec or fc,lw=1.6))
    ax.text(x+w/2,y+h/2,txt,ha='center',va='center',color=tc,fontsize=fs,fontweight='bold',linespacing=1.35)
def arrow(x1,y1,x2,y2,c=DARK):ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle='-|>',mutation_scale=20,lw=2,color=c))
def num(x,y,t):ax.text(x,y,t,fontsize=16,ha='center',va='center',color=DARK,fontweight='bold')
ax.add_patch(FancyBboxPatch((3.35,0.2),8.2,4.55,boxstyle='round,pad=0.02,rounding_size=0.2',fc='#f4f6f8',ec=GRAY,lw=1.4,ls='--'))
ax.text(7.45,4.5,'FPGA 칩 (ZCU104 보드)',ha='center',fontsize=12,color='#555')
box(0.15,2.2,2.6,1.3,'카메라\n원본 데이터\n(RAW)',GRAY)
box(3.7,2.2,2.5,1.3,'밝기 판단기\n(checker)',GREEN)
ax.add_patch(FancyBboxPatch((6.75,0.5),4.5,3.6,boxstyle='round,pad=0.02,rounding_size=0.18',fc='white',ec=DARK,lw=2))
ax.text(9.0,3.8,'교체되는 자리 (ISP)',ha='center',fontsize=12.5,fontweight='bold')
box(7.0,2.5,4.0,0.85,'NormalISP  (밝은 장면용)',BLUE,fs=12)
box(7.0,1.3,4.0,0.85,'LowlightISP  (어두운 장면용)',ORANGE,fs=12)
ax.text(9.0,0.78,'둘 중 하나만 올라가 있음',ha='center',fontsize=10.5,color='#444')
box(12.2,2.2,2.6,1.3,'물체 찾는 AI\n(DPU)',GRAY)
arrow(2.78,2.85,3.67,2.85);arrow(6.23,2.85,6.72,2.85);arrow(11.28,2.85,12.17,2.85)
arrow(4.95,2.17,6.7,1.72,GREEN)
ax.text(4.0,1.55,'"어두워졌다!"\n→ 자리의 회로를 교체',fontsize=10.5,color='#2f6b3f',va='top',ha='left')
num(1.45,1.8,'①');num(4.95,3.85,'②');num(9.0,4.38,'③');num(13.5,3.85,'④')
ax.text(0.2,-0.05,'①  카메라가 찍은 원본 데이터가 들어옵니다.   ②  판단기가 장면의 밝기를 보고, 필요하면 ISP 회로를 바꿉니다.',fontsize=10.5,color='#333',va='center')
ax.text(0.2,-0.5,'③  선택된 ISP가 원본 데이터를 사람이 보는 컬러 영상으로 바꿉니다.   ④  AI가 영상에서 사람, 자동차, 자전거의 위치를 찾습니다.',fontsize=10.5,color='#333',va='center')
ax.set_ylim(-0.8,5.1)
fig.suptitle('DFXISP가 하는 일: 밝기에 따라 영상 처리 회로(ISP)를 바꿔 끼웁니다',fontsize=16,fontweight='bold',y=0.99)
fig.savefig(A/'overview_flow.png',dpi=200,bbox_inches='tight',facecolor='white');plt.close(fig)

# ---------- Figure 2: simple result summary (DFX live, board) ----------
rows=list(csv.DictReader((R/'docs/experiments/2026-10-v2-board/results/final_live_comparison/comparison.csv').open()))
fig,axs=plt.subplots(1,2,figsize=(14,5.6),sharey=True)
for ax,model,name in zip(axs,('YOLOv8n','SSD-MobileNet'),('YOLOv8n','SSD-MobileNet')):
    xs=range(3);labels=[('day','낮'),('night','밤'),('mixed','낮과 밤 섞음')]
    for i,(s,_) in enumerate(labels):
        r=next(x for x in rows if x['model']==model and x['subset']==s and x['mode']=='dfx_live')
        b,m=float(r['baseline']),float(r['mean'])
        ax.bar(i-0.2,b,0.38,color=GRAY,zorder=3,label='이전 모델' if i==0 else None);ax.bar(i+0.2,m,0.38,color=BLUE,zorder=3,label='새 모델 (낮과 밤 함께 학습)' if i==0 else None)
        ax.text(i-0.2,b+0.012,f'{b:.2f}',ha='center',fontsize=12);ax.text(i+0.2,m+0.012,f'{m:.2f}',ha='center',fontsize=12,fontweight='bold')
    ax.set_xticks(list(xs),[l for _,l in labels],fontsize=12);ax.set_ylim(0,0.8);ax.set_title(name,fontsize=15,pad=10);ax.grid(axis='y',color='#e2e2e2',zorder=0);ax.spines[['top','right']].set_visible(False)
axs[0].set_ylabel('물체 찾기 정확도 (mAP50-95, 높을수록 좋음)',fontsize=12);axs[0].legend(loc='upper right',frameon=False,fontsize=11)
fig.suptitle('실제 보드에서 잰 정확도: 밤에는 크게 좋아졌고, 낮에는 조금 낮아졌습니다',fontsize=16,fontweight='bold',y=1.0)
fig.text(0.5,-0.02,'새 모델은 학습 3회(시드 3개)의 평균입니다. 이전 모델은 YOLO는 기존 배포 모델, SSD는 같은 가중치를 같은 방식으로 다시 변환하고 오류를 고친 모델입니다.',ha='center',fontsize=10.5,color='#444')
fig.tight_layout();fig.savefig(A/'summary_accuracy.png',dpi=200,bbox_inches='tight',facecolor='white');plt.close(fig)
print('ok',A)
