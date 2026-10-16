"""Figures for the v2 balanced-model board results. Data only from saved measurement files (no estimates).
Fig1: absolute mAP50-95 on the board, DFX live (checker-driven), fixed Normal / fixed Lowlight(BLC16) replay; existing deployed model vs v2 (mean of 3 training seeds, dots = each seed). Numbers above bars only.
Fig2: v2 minus existing model per seed (fixed-RM replay, paired frame bootstrap 95% CI).
Fig3: Lowlight minus Normal within each model (ISP effect), per seed, 95% CI (test-frame resampling)."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont('/opt/data/home/.local/share/fonts/NotoSansKR.ttf')
plt.rcParams.update({'font.family': 'Noto Sans KR', 'axes.unicode_minus': False, 'font.size': 12})
R = Path('/opt/data/work/blc16_dfx_board_20261014/v2_model_pilot'); OUT = R / 'figures'; OUT.mkdir(exist_ok=True)
dfx = json.loads((R / 'dfx_live/v2_quant/dfx_live/dfx_live_analysis.json').read_text())
a3 = json.loads((R / 'seeds/seeds_board/analysis3.json').read_text())
SUB = [('night', '야간'), ('day', '주간'), ('mixed', '혼합')]
GROUPS = [('normal', 'Normal\n고정'), ('lowlight', 'Lowlight(BLC16)\n고정'), ('dfx_live', 'DFX 자동\n전환')]
C_OLD, C_NEW = '#8495A5', '#479578'

# ---- Fig1
fig, axs = plt.subplots(1, 3, figsize=(16, 5.6), sharey=True)
rows = []
for ax, (s, title) in zip(axs, SUB):
    for gi, (g, _) in enumerate(GROUPS):
        old = dfx[f'{s}_old'][g]; seeds = [dfx[f'{s}_s{i}'][g] for i in range(3)]; mean = float(np.mean(seeds))
        x0, x1 = gi - .19, gi + .19
        ax.bar(x0, old, .36, color=C_OLD, zorder=3, label='기존 배포 모델' if gi == 0 and s == 'night' else None)
        ax.bar(x1, mean, .36, color=C_NEW, zorder=3, label='새 균형학습 모델(3시드 평균)' if gi == 0 and s == 'night' else None)
        ax.scatter([x1] * 3, seeds, s=16, color='#1b3b2f', zorder=4, label='시드별 값' if gi == 0 and s == 'night' else None)
        top = max(seeds + [old, mean])
        ax.text(x0, old + .012, f'{old:.3f}', ha='center', va='bottom', fontsize=11)
        ax.text(x1, top + .012, f'{mean:.3f}', ha='center', va='bottom', fontsize=11)
        rows.append((s, g, old, *seeds, mean))
    ax.set_xticks(range(3), [g[1] for g in GROUPS], fontsize=11); ax.set_title(title, pad=12)
    ax.set_ylim(0, .78); ax.grid(axis='y', alpha=.22, zorder=0); ax.spines[['top', 'right']].set_visible(False)
axs[0].set_ylabel('mAP50-95 (보드 DPU, INT8)')
h, l = axs[0].get_legend_handles_labels(); fig.legend(h, l, loc='lower center', ncol=3, frameon=False, bbox_to_anchor=(.5, -.02))
fig.suptitle('YOLOv8n 보드 실측 — 기존 모델 대비 새 균형학습 모델', fontsize=17)
fig.tight_layout(rect=(0, .05, 1, .94)); p1 = OUT / 'fig1_board_absolute.png'; fig.savefig(p1, dpi=170, bbox_inches='tight'); plt.close(fig)

# ---- Fig2
fig, axs = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
cols = ['#3b7dd8', '#d98a2b', '#479578']
for ax, (s, title) in zip(axs, SUB):
    for ai, arm in enumerate(('normal', 'lowlight')):
        for si, (d, lo, hi) in enumerate(a3[f'{s}_{arm}']['ci']):
            x = ai * 4 + si
            ax.errorbar(x, d, yerr=[[d - lo], [hi - d]], fmt='o', color=cols[si], capsize=4, ms=7, lw=1.8, zorder=3)
            ax.text(x + .12, d, f'{d:+.3f}', ha='left', va='center', fontsize=10)
    ax.axhline(0, color='k', lw=1, zorder=2); ax.set_xlim(-.6, 8.1)
    ax.set_xticks([1, 5], ['Normal 고정', 'Lowlight(BLC16) 고정'], fontsize=11); ax.set_title(title, pad=12)
    ax.grid(axis='y', alpha=.22, zorder=0); ax.spines[['top', 'right']].set_visible(False)
axs[0].set_ylabel('새 모델 − 기존 모델 (mAP50-95)')
for si, c in enumerate(cols): axs[0].plot([], [], 'o', color=c, label=f'시드 {si}')
h2, l2 = axs[0].get_legend_handles_labels(); fig.legend(h2, l2, loc='lower center', ncol=3, frameon=False, bbox_to_anchor=(.5, -.02)); axs[0].set_ylim(-.1, .21)
fig.suptitle('기존 모델 대비 향상량 — 시드별, 프레임 부트스트랩 95% 신뢰구간', fontsize=16)
fig.tight_layout(rect=(0, .05, 1, .94)); p2 = OUT / 'fig2_gain_over_old.png'; fig.savefig(p2, dpi=170, bbox_inches='tight'); plt.close(fig)

# ---- Fig3
fig, axs = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
names = [('old', '기존'), ('s0', '시드0'), ('s1', '시드1'), ('s2', '시드2')]; cc = ['#8495A5'] + cols
for ax, (s, title) in zip(axs, SUB):
    for i, (t, _) in enumerate(names):
        d, lo, hi = a3[f'{s}_lowlight_minus_normal'][t]
        ax.errorbar(i, d, yerr=[[d - lo], [hi - d]], fmt='o', color=cc[i], capsize=4, ms=7, lw=1.8, zorder=3)
        ax.text(i, hi + .004, f'{d:+.3f}', ha='center', va='bottom', fontsize=10.5)
    ax.axhline(0, color='k', lw=1, zorder=2); ax.set_xticks(range(4), [n[1] for n in names]); ax.set_title(title, pad=12)
    ax.grid(axis='y', alpha=.22, zorder=0); ax.spines[['top', 'right']].set_visible(False); ax.set_xlim(-.6, 3.6)
axs[0].set_ylabel('Lowlight − Normal (mAP50-95)'); axs[0].set_ylim(-.07, .07)
fig.suptitle('ISP 효과: 같은 모델에서 Lowlight(BLC16)와 Normal의 차이 (95% 신뢰구간)', fontsize=16)
fig.tight_layout(rect=(0, 0, 1, .94)); p3 = OUT / 'fig3_isp_effect.png'; fig.savefig(p3, dpi=170, bbox_inches='tight'); plt.close(fig)
import csv
with (OUT / 'fig1_data.csv').open('w') as f:
    w = csv.writer(f); w.writerow(['subset', 'isp', 'old', 's0', 's1', 's2', 'v2_mean']); w.writerows(rows)
print(p1, p2, p3)
