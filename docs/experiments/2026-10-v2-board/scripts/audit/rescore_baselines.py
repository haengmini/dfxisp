from pathlib import Path
import json,sys,io,contextlib,csv,re
import numpy as np
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
O=Path(__file__).parent;E=Path('/home/mini/Desktop/dfxisp/hw/DFXISP/deploy/experiment_v2');sys.path.insert(0,str(E/'app'));import eval_map as EM
classes=['person','car','bicycle'];rows=[];counts=[]
for variant in ['v5','blc16']:
 for p in sorted((O/variant).glob('*dpu*.jsonl')):
  name=p.stem;parts=name.split('_');model=parts[1];subset='_'.join(parts[2:]);records=[json.loads(l) for l in p.read_text().splitlines()]
  n=200 if subset.startswith('mixed') else 100
  assert len(records)==n and len({r['id'] for r in records})==n,(p,n)
  data={'classes':classes,'images':{r['id']:{'width':r['width'],'height':r['height'],'detections':r['detections']} for r in records}}
  buf=io.StringIO()
  with contextlib.redirect_stdout(buf):ap50,ap=EM.evaluate(data,str(E/'labels'))
  base={'variant':variant,'run':name,'model':model,'subset':subset,'n':n}
  rows.append({**base,'scorer':'board_allpoint','class':'all','AP50_95':ap,'AP50':ap50,'APsmall':None,'AR100':None})
  for line in buf.getvalue().splitlines():
   v=line.split()
   if v and v[0] in classes:
    rows.append({**base,'scorer':'board_allpoint','class':v[0],'AP50_95':float(v[3]),'AP50':float(v[2]),'APsmall':None,'AR100':None})
  size=640 if model=='yolov8n' else 320
  images=[];anns=[];dets=[]
  for i,r in enumerate(records,1):
   gt=EM.load_labels(str(E/'labels'),r['id'],size,size);images.append({'id':i,'width':size,'height':size})
   for g in gt:
    x,y,x2,y2=map(float,g[1:]);b=[x,y,x2-x,y2-y];anns.append({'id':len(anns)+1,'image_id':i,'category_id':int(g[0])+1,'bbox':b,'area':b[2]*b[3],'iscrowd':0})
   for d in r['detections']:
    x,y,x2,y2=[float(d[k]*size/(r['width'] if k%2==0 else r['height'])) for k in range(4)];dets.append({'image_id':i,'category_id':int(d[5])+1,'bbox':[x,y,x2-x,y2-y],'score':float(d[4])})
  with contextlib.redirect_stdout(io.StringIO()):
   c=COCO();c.dataset={'images':images,'annotations':anns,'categories':[{'id':i+1,'name':s} for i,s in enumerate(classes)]};c.createIndex();dt=c.loadRes(dets)
   ev=COCOeval(c,dt,'bbox');ev.evaluate();ev.accumulate();ev.summarize()
  rows.append({**base,'scorer':'coco101_max100_detector_coords','class':'all','AP50_95':float(ev.stats[0]),'AP50':float(ev.stats[1]),'APsmall':float(ev.stats[3]),'AR100':float(ev.stats[8])})
  for ci,cl in enumerate(classes):
   a=ev.eval['precision'][:,:,ci,0,2];valid=a[a>=0];a50=ev.eval['precision'][0,:,ci,0,2];a50=a50[a50>=0]
   rows.append({**base,'scorer':'coco101_max100_detector_coords','class':cl,'AP50_95':float(valid.mean()) if valid.size else None,'AP50':float(a50.mean()) if a50.size else None,'APsmall':None,'AR100':None})
  counts.append({'file':str(p.relative_to(O)),'records':len(records),'gt_boxes':len(anns),'det_boxes':len(dets)})
  print('SCORED',variant,name,'board',round(ap,4),'coco',round(ev.stats[0],4),flush=True)
with (O/'rescore.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(O/'coverage.json').write_text(json.dumps(counts,indent=1));(O/'DONE.json').write_text(json.dumps({'groups':len(counts),'score_rows':len(rows),'records':sum(x['records'] for x in counts),'notes':'Repeated frames across subsets. Detector-coordinate small/medium areas; no resize policy changes. board scorer untouched; COCO maxDets100 differs. Perclass board AP rounded by original print.'}))
assert len(counts)==28 and len(rows)==224
print('VERIFIED_RESCORE_COMPLETE 28 groups 224 score rows',flush=True)
