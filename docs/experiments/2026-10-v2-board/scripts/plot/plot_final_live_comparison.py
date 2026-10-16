"""Final measured fixed-RM replay and real DFX live comparison; no offline Adaptive.
Baseline: YOLO deployed; SSD existing weights re-calibrated on v2 train, SE fixed.
Source JSONs, exact values, CSV and Markdown accompany charts. No fabricated CI.
"""
import json,csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
R=Path(__file__).resolve().parent
O=R/'final_live_comparison';O.mkdir(exist_ok=True)
font_manager.fontManager.addfont('/opt/data/home/.local/share/fonts/NotoSansKR.ttf')
plt.rcParams.update({'font.family':'Noto Sans KR','axes.unicode_minus':False,'font.size':12,'svg.fonttype':'none'})
SOURCES={'YOLOv8n':R/'dfx_live/v2_quant/dfx_live/dfx_live_analysis.json','SSD-MobileNet':R/'ssd/dfx_live/v2_quant/ssd_dfx_live/ssd_dfx_live_analysis.json'}
SUB=[('day','주간'),('night','야간'),('mixed','혼합')]
ARMS=[('normal','Normal 고정'),('lowlight','Lowlight 고정'),('dfx_live','DFX live')]
rows=[];fig,axs=plt.subplots(2,3,figsize=(17,9),sharey=True)
for ri,(model,path) in enumerate(SOURCES.items()):
 d=json.loads(path.read_text());base='old' if ri==0 else 'oldfx'
 for ci,(sub,title) in enumerate(SUB):
  ax=axs[ri,ci]
  for ai,(arm,label) in enumerate(ARMS):
   old=d[f'{sub}_{base}'][arm];ss=[d[f'{sub}_s{i}'][arm] for i in range(3)];mean=float(np.mean(ss));sd=float(np.std(ss,ddof=1))
   ax.bar(ai-.19,old,.36,color='#8795a4',edgecolor='black',linewidth=.7,hatch='//',zorder=3)
   ax.bar(ai+.19,mean,.36,color='#3986c1',edgecolor='black',linewidth=.7,zorder=3)
   ax.scatter([ai+.19]*3,ss,color='#163955',s=14,zorder=4)
   ax.text(ai-.19,old+.013,f'{old:.3f}',ha='center',fontsize=11)
   ax.text(ai+.19,max(ss)+.013,f'{mean:.3f}',ha='center',fontsize=11)
   rows.append({'model':model,'subset':sub,'mode':arm,'baseline_tag':base,'baseline':old,'s0':ss[0],'s1':ss[1],'s2':ss[2],'mean':mean,'sd':sd,'delta_mean':mean-old})
  ax.set_title(f'{model} — {title}',pad=14);ax.set_xticks(range(3),[x[1] for x in ARMS]);ax.set_ylim(0,.76);ax.grid(axis='y',alpha=.2,zorder=0);ax.spines[['top','right']].set_visible(False)
  if ci==0:ax.set_ylabel('보드 mAP50-95')
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
fig.legend(handles=[Patch(facecolor='#8795a4',edgecolor='black',hatch='//',label='기준 모델'),Patch(facecolor='#3986c1',edgecolor='black',label='균형학습 모델: 3시드 평균'),Line2D([],[],marker='o',linestyle='',color='#163955',label='개별 시드')],loc='lower center',bbox_to_anchor=(.5,.045),ncol=3,frameon=False)
fig.suptitle('YOLO 및 SSD 보드 실측: 고정 ISP와 실제 DFX 자동 전환',fontsize=18,y=.985)
fig.text(.5,.015,'YOLO 기준: 기존 배포 모델 / SSD 기준: 기존 가중치 재보정 + SE 수정. 막대 위 수치는 평균, 점은 시드별 값.',ha='center',fontsize=11)
fig.tight_layout(rect=(0,.10,1,.95))
for ext in ('png','pdf','svg'):fig.savefig(O/f'final_board_live.{ext}',dpi=300)
plt.close(fig)
with (O/'comparison.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
lines=['# YOLO 및 SSD 최종 보드 실측 비교','', '고정 ISP 열은 보드 DPU 재생, DFX live 열은 RAW→체커→실제 RM 선택→ISP→DPU 측정이다. 오프라인 Adaptive는 포함하지 않는다.','', '| 모델 | 구간 | 방식 | 기준 | 시드0 | 시드1 | 시드2 | 평균 ± 표준편차 |','|---|---|---|---:|---:|---:|---:|---:|']
for r in rows:
 lines.append('| '+ ' | '.join([r['model'],dict(SUB)[r['subset']],dict(ARMS)[r['mode']],*[f'{r[k]:.4f}' for k in ('baseline','s0','s1','s2')],f"{r['mean']:.4f} ± {r['sd']:.4f}"])+' |')
lines+=['','## 비교 계약과 한계','- YOLO 기준은 기존 배포 xmodel이다. SSD 기준은 기존 가중치를 v2 학습 자료로 재보정하고 SE 고정소수점 위치를 수정한 xmodel이다. 새 SSD도 같은 SE 수정 경로다. 두 모델의 기준선을 같은 종류라고 간주하지 않는다.','- 기존 배포 SSD의 결함 수정 효과와 새 모델의 학습 효과는 별도다. 이 표는 학습 효과 비교용이며 원래 배포 SSD 값은 넣지 않았다.','- 두 검출기는 동일 기존 시험 프레임군을 사용하지만 입력 크기와 전후처리가 다르다. 모델 간 차이를 ISP 효과로 해석하지 않는다.','- 3시드 표준편차는 독립 데이터셋 반복이 아니며 프레임 부트스트랩 신뢰구간과 다르다. 혼합은 주간과 야간 프레임의 합이며 새 독립 표본이 아니다.','- 고정값과 live는 서로 다른 실행에서 얻었다. 동일 프레임의 live ISP RGB는 기준과 해시가 일치했으며 수치는 각 실행의 저장 결과를 그대로 사용한다.','- 야간 모델 개선은 확인됐으나 주간 성능 유지 또는 비열등 통과는 입증하지 못했다. 차이 CI에 0이 포함된다는 이유로 동등이라 하지 않는다.','- 추가 부트스트랩에서 더 좋은 고정 RM 대비 DFX 정확도 우위는 확인되지 않았다. YOLO 혼합에서 Normal 고정 대비 이점과 최선 고정 방식 대비 우위를 구분한다.','- SSD 호스트/보드 검출 잔여 불일치가 있으며 독립 Sony 장면 holdout은 미완료다.','- 순차 하네스 측정이며 처리량이나 프레임 드롭을 평가한 결과가 아니다.','','## 원자료']
lines += [f'- {m}: `{p.relative_to(R)}`' for m,p in SOURCES.items()]
lines += ['- 추가 통계: `dfx_extra_bootstrap.json`','- 수치 CSV: `comparison.csv` (반올림 전 값 보존)','- PNG/PDF/SVG는 동일 입력에서 생성한 실험 결과 그래프이며 논문 채택본으로 지정하지 않는다.']
(O/'comparison.md').write_text('\n'.join(lines)+'\n')
assert len(rows)==18 and all(np.isfinite(r['mean']) for r in rows)
print('PASS: 18 rows, 2 detectors x 3 subsets x 3 modes; saved PNG/PDF/SVG, CSV, Markdown')
print(O)
