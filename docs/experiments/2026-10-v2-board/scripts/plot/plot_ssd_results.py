"""SSD-MobileNet board figures after the SE fix. Data only from saved measurement files.
Fig4: absolute board mAP50-95 per subset: original deployed xmodel / existing weights re-quantized WITH SE fix / new balanced model (3-seed mean, dots=seeds). Arms: Normal fixed, Lowlight(BLC16) fixed, Adaptive (offline: checker decision applied to the replay, NOT a live DFX run).
Fig5: new minus existing (both with SE fix), per seed, paired frame bootstrap 95% CI.
Fig6: Lowlight minus Normal within each model (ISP effect), 95% CI.
Fig7: effect of the SE fix itself on the existing weights (same calibration, same 400 frames): before vs after."""
import json, csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont('/opt/data/home/.local/share/fonts/NotoSansKR.ttf')
plt.rcParams.update({'font.family': 'Noto Sans KR', 'axes.unicode_minus': False, 'font.size': 12})
R = Path('/opt/data/work/blc16_dfx_board_20261014/v2_model_pilot'); OUT = R / 'figures'; OUT.mkdir(exist_ok=True)
fx = json.loads((R / 'ssd/fix/v2_quant/ssd_fixboard/analysis_fix.json').read_text())
orig = json.loads((R / 'ssd/v2_quant/ssd_board/analysis3.json').read_text())
SUB = [('night', '야간'), ('day', '주간'), ('mixed', '혼합')]
ARMS = [('normal', 'Normal\n고정'), ('lowlight', 'Lowlight(BLC16)\n고정'), ('adaptive', 'Adaptive\n(오프라인 재생)')]
C_ORIG, C_OLD, C_NEW = '#B7C0C8', '#8495A5', '#479578'

# ---- Fig4 (3 bars per arm)
fig, axs = plt.subplots(1, 3, figsize=(17, 5.8), sharey=True); rows = []
for ax, (s, title) in zip(axs, SUB):
    for gi, (g, _) in enumerate(ARMS):
        o = orig[f'{s}_{g}']['old']; f = fx[f'{s}_{g}']; old = f['old_fix']; seeds = f['seeds']; mean = f['mean']
        xs = (gi - .27, gi, gi + .27)
        ax.bar(xs[0], o, .25, color=C_ORIG, zorder=3, label='기존 배포 xmodel(수정 전)' if gi == 0 and s == 'night' else None)
        ax.bar(xs[1], old, .25, color=C_OLD, zorder=3, label='기존 가중치(SE 수정)' if gi == 0 and s == 'night' else None)
        ax.bar(xs[2], mean, .25, color=C_NEW, zorder=3, label='새 균형학습 모델(SE 수정, 3시드 평균)' if gi == 0 and s == 'night' else None)
        ax.scatter([xs[2]] * 3, seeds, s=14, color='#1b3b2f', zorder=4, label='시드별 값' if gi == 0 and s == 'night' else None)
        for x, v in zip(xs, (o, old, max(seeds + [mean]))):
            ax.text(x, v + .012, f'{(mean if x == xs[2] else (o if x == xs[0] else old)):.3f}', ha='center', va='bottom', fontsize=10)
        rows.append((s, g, o, old, *seeds, mean))
    ax.set_xticks(range(3), [a[1] for a in ARMS], fontsize=10.5); ax.set_title(title, pad=12)
    ax.set_ylim(0, .72); ax.grid(axis='y', alpha=.22, zorder=0); ax.spines[['top', 'right']].set_visible(False)
axs[0].set_ylabel('mAP50-95 (보드 DPU, INT8)')
h, l = axs[0].get_legend_handles_labels(); fig.legend(h, l, loc='lower center', ncol=4, frameon=False, bbox_to_anchor=(.5, -.03))
fig.suptitle('SSD-MobileNet 보드 실측 — SE 결함 수정 후', fontsize=17)
fig.tight_layout(rect=(0, .06, 1, .94)); p4 = OUT / 'fig4_ssd_board_absolute.png'; fig.savefig(p4, dpi=170, bbox_inches='tight'); plt.close(fig)

# ---- Fig5
cols = ['#3b7dd8', '#d98a2b', '#479578']
fig, axs = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
for ax, (s, title) in zip(axs, SUB):
    for ai, arm in enumerate(('normal', 'lowlight')):
        for si, (d, lo, hi) in enumerate(fx[f'{s}_{arm}']['ci']):
            x = ai * 5.2 + si * 1.3
            ax.errorbar(x, d, yerr=[[d - lo], [hi - d]], fmt='o', color=cols[si], capsize=4, ms=7, lw=1.8, zorder=3)
            ax.text(x, hi + .004, f'{d:+.3f}', ha='center', va='bottom', fontsize=10, bbox=dict(fc='white', ec='none', pad=1.2, alpha=.9), zorder=5)
    ax.axhline(0, color='k', lw=1, zorder=2); ax.set_xlim(-.9, 8.4)
    ax.set_xticks([1.3, 6.5], ['Normal 고정', 'Lowlight(BLC16) 고정'], fontsize=11); ax.set_title(title, pad=12)
    ax.grid(axis='y', alpha=.22, zorder=0); ax.spines[['top', 'right']].set_visible(False)
axs[0].set_ylabel('새 모델 − 기존 가중치 (mAP50-95, 둘 다 SE 수정)')
for si, c in enumerate(cols): axs[0].plot([], [], 'o', color=c, label=f'시드 {si}')
h2, l2 = axs[0].get_legend_handles_labels(); fig.legend(h2, l2, loc='lower center', ncol=3, frameon=False, bbox_to_anchor=(.5, -.02)); axs[0].set_ylim(-.09, .09)
fig.suptitle('SSD 기존 가중치 대비 향상량 — 시드별, 프레임 부트스트랩 95% 신뢰구간', fontsize=16)
fig.tight_layout(rect=(0, .05, 1, .94)); p5 = OUT / 'fig5_ssd_gain_over_old.png'; fig.savefig(p5, dpi=170, bbox_inches='tight'); plt.close(fig)

# ---- Fig6
fig, axs = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
names = [('old8', '기존'), ('s0', '시드0'), ('s1', '시드1'), ('s2', '시드2')]; cc = ['#8495A5'] + cols
for ax, (s, title) in zip(axs, SUB):
    for i, (t, _) in enumerate(names):
        d, lo, hi = fx[f'{s}_lowlight_minus_normal'][t]
        ax.errorbar(i, d, yerr=[[d - lo], [hi - d]], fmt='o', color=cc[i], capsize=4, ms=7, lw=1.8, zorder=3)
        ax.text(i, hi + .004, f'{d:+.3f}', ha='center', va='bottom', fontsize=10.5, bbox=dict(fc='white', ec='none', pad=1.2, alpha=.9), zorder=5)
    ax.axhline(0, color='k', lw=1, zorder=2); ax.set_xticks(range(4), [n[1] for n in names]); ax.set_title(title, pad=12)
    ax.grid(axis='y', alpha=.22, zorder=0); ax.spines[['top', 'right']].set_visible(False); ax.set_xlim(-.6, 3.6)
axs[0].set_ylabel('Lowlight − Normal (mAP50-95)'); axs[0].set_ylim(-.09, .05)
fig.suptitle('SSD ISP 효과: 같은 모델에서 Lowlight(BLC16)와 Normal의 차이 (95% 신뢰구간)', fontsize=16)
fig.tight_layout(rect=(0, 0, 1, .94)); p6 = OUT / 'fig6_ssd_isp_effect.png'; fig.savefig(p6, dpi=170, bbox_inches='tight'); plt.close(fig)

# ---- Fig7: SE fix effect on existing weights
fig, axs = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
for ax, (s, title) in zip(axs, SUB):
    for gi, (g, _) in enumerate(ARMS):
        f = fx[f'{s}_{g}']
        ax.bar(gi - .19, f['old_nofix'], .36, color='#c9715c', zorder=3, label='수정 전' if gi == 0 and s == 'night' else None)
        ax.bar(gi + .19, f['old_fix'], .36, color=C_OLD, zorder=3, label='SE 수정 후' if gi == 0 and s == 'night' else None)
        ax.text(gi - .19, f['old_nofix'] + .012, f"{f['old_nofix']:.3f}", ha='center', fontsize=10.5); ax.text(gi + .19, f['old_fix'] + .012, f"{f['old_fix']:.3f}", ha='center', fontsize=10.5)
    ax.set_xticks(range(3), [a[1] for a in ARMS], fontsize=10.5); ax.set_title(title, pad=12); ax.set_ylim(0, .72)
    ax.grid(axis='y', alpha=.22, zorder=0); ax.spines[['top', 'right']].set_visible(False)
axs[0].set_ylabel('mAP50-95 (보드 DPU, 기존 가중치)')
h, l = axs[0].get_legend_handles_labels(); fig.legend(h, l, loc='lower center', ncol=2, frameon=False, bbox_to_anchor=(.5, -.02))
fig.suptitle('SE 결함 수정 자체의 효과 — 같은 가중치·같은 보정·같은 400장', fontsize=16)
fig.tight_layout(rect=(0, .05, 1, .94)); p7 = OUT / 'fig7_ssd_se_fix_effect.png'; fig.savefig(p7, dpi=170, bbox_inches='tight'); plt.close(fig)
with (OUT / 'fig4_data.csv').open('w') as f:
    w = csv.writer(f); w.writerow(['subset', 'arm', 'orig_deployed_xmodel', 'old_weights_se_fix', 's0', 's1', 's2', 'new_mean']); w.writerows(rows)
print(p4, p5, p6, p7)
