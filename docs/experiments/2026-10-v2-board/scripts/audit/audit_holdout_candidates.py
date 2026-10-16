"""Metadata-only holdout inventory. Unused IDs are NOT independent scenes.
Conservatively exclude the entire 1200-frame v2 selection, including dropped training frames.
No downloads, inference, selection by score, or changes to existing splits.
"""
import json
from pathlib import Path
A=Path(__file__).resolve().parent
U=json.loads((A/'night_used_ids.json').read_text())
S=json.loads(Path('/opt/data/work/dfxisp_sep_exp/ft_hw_v2/selection.json').read_text())
used=set().union(*(set(v) for v in U.values()),set(S['selected']))
rows={}
for p in sorted((A/'drive_labels').glob('*.json')):
    d=json.loads(p.read_text()); anns={}
    for a in d['annotations']: anns.setdefault(a['image_id'],[]).append(a)
    for i in d['images']:
        stem=Path(i['file_name']).stem
        if stem not in rows: rows[stem]={'id':stem,'annotation_sources':[],'boxes':len(anns.get(i['id'],[]))}
        rows[stem]['annotation_sources'].append(p.name)
nums=sorted(int(s[3:]) for s in used)
unused=[]
for s,r in sorted(rows.items()):
    if s in used: continue
    r['nearest_used_id_distance']=min(abs(int(s[3:])-n) for n in nums)
    r['status']='UNUSED_ID_ONLY_SCENE_INDEPENDENCE_UNVERIFIED'
    unused.append(r)
out={'scope':'Sony label metadata only; not independent holdout','labeled_unique_ids':len(rows),'excluded_used_ids':len(used),'unused_ids':len(unused),'unused_farther_than_3':sum(r['nearest_used_id_distance']>3 for r in unused),'unused_farther_than_20':sum(r['nearest_used_id_distance']>20 for r in unused),'candidates':unused,'blockers':['No capture-session/location scene IDs verified','No RAW hash or perceptual duplicate audit for these candidates','Original model training provenance may overlap Sony source','Day replay JPG is not independent daytime RAW']}
p=A/'holdout_candidate_inventory.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in out.items() if k!='candidates'},ensure_ascii=False,indent=2));print('saved',p)
