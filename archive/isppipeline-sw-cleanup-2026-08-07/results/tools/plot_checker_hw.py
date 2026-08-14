#!/usr/bin/env python3
from pathlib import Path
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[1]; out=root/'checker_validation_2026-08-06'
fig,ax=plt.subplots(figsize=(6,4)); ax.bar(['Python↔CSim\n200 frames','Crop Python↔CSim\n4 crops'],[100,100],color=['#2878b5','#59a14f']);ax.set_ylim(0,105);ax.set_ylabel('bit-exact match (%)')
for i,v in enumerate([100,100]):ax.text(i,v-7,f'{v:.2f}%',ha='center',color='white',weight='bold')
ax.set_title('Executed C-model agreement (RTL co-sim unavailable)');fig.tight_layout();fig.savefig(out/'checker_csim_match_rates_2026-08-06.png',dpi=170);plt.close(fig)
fig,ax=plt.subplots(figsize=(7,4)); names=['BRAM_18K','DSP','FF / 100','LUT / 100'];vals=[1,12,17.25,22.75];ax.bar(names,vals,color='#e07b39');ax.set_title('checker_scan HLS synthesis resources');ax.set_ylabel('count (FF/LUT scaled ÷100)');fig.tight_layout();fig.savefig(out/'checker_csynth_resources_2026-08-06.png',dpi=170);plt.close(fig)
print('HW_PLOTS_WRITTEN count=2')
