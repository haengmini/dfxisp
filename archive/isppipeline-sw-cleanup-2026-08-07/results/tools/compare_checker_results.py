#!/usr/bin/env python3
import csv,sys
from pathlib import Path
def rd(p):
 with Path(p).open(newline='') as f:return list(csv.DictReader(f))
k,gp,ap,op=sys.argv[1:5];g=rd(gp);a=rd(ap);assert len(g)==len(a);gm={(r['source'],r['stem']):r for r in g};rs=[];matched=0
for r in a:
 x=gm[(r['source'],r['stem'])];e={'dark_count':x.get('dark_count',x.get('crop_dark_count')),'hyst_flags':x['python_hyst_flags'],'selected_mode':x['python_selected_mode']};ok=all(int(r[f])==int(e[f]) for f in e);matched+=ok;rs.append({'source':r['source'],'stem':r['stem'],**{f'expected_{f}':e[f] for f in e},**{f'actual_{f}':r[f] for f in e},'bit_exact':int(ok)})
with Path(op).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
print(f'{k}_BIT_EXACT frames={len(rs)} matched={matched} mismatched={len(rs)-matched} rate={100*matched/len(rs):.2f}%')
