"""Summarize measured past fine-tuning; never compare its scorer directly with board AP."""
from pathlib import Path
import csv,json,statistics
P=Path(__file__).parent
r=list(csv.DictReader((P/'ft_results.csv').open()))
assert len(r)==180
rows=[]
for act in ['silu','hswish']:
 for model,arm in [('base','normal'),('base','lowlight'),('ft_normal','normal'),('ft_lowlight','lowlight')]:
  for subset in ['day','night','mixed']:
   x=[v for v in r if v['act']==act and v['input_arm']==arm and v['subset']==subset and (v['model']==model if model=='base' else v['model'].startswith(model+'_s'))]
   assert len(x)==(1 if model=='base' else 3)
   vals=[float(v['mAP_50_95']) for v in x]
   rows.append({'activation':act,'model':model,'input':arm,'subset':subset,'runs':len(vals),'mean_mAP50_95':statistics.mean(vals),'min':min(vals),'max':max(vals)})
(P/'ft_summary.json').write_text(json.dumps(rows,indent=2))
for row in rows:
 if row['activation']=='hswish':print(row)
print('VERIFIED: 180 source rows; 24 summary rows; all fine-tuning groups have 3 seeds')
