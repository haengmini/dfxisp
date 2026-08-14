#!/usr/bin/env python3
import csv,json,random
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'results/checker_validation_2026-08-06'; TH=4096
NORMAL,LOW=0,1; BANDS=(("none_62_62",62,62),("delta1_63_61",63,61),("deployed_64_60",64,60),("delta4_66_58",66,58)); SEED=20260806
@dataclass(frozen=True)
class F:
 source:str; stem:str; w:int; h:int; truth:int; path:Path; csv_ratio:float; dark:int
 @property
 def n(self): return self.w*self.h
 @property
 def ratio(self): return self.dark/self.n
def select(d,n,v=62,e=64,x=60):
 # HLS `int` is 32-bit; mirror the synthesized two's-complement multiply.
 p=((d*100+(1<<31))%(1<<32))-(1<<31)
 return (LOW if p>v*n else NORMAL),(1 if p>e*n else 0)|(2 if p<x*n else 0)
def count_dark(p,n):
 a=np.memmap(p,dtype='<u2',mode='r',shape=(n,)); total=0
 for i in range(0,n,1_000_000): total+=int(np.count_nonzero(a[i:i+1_000_000]<TH))
 del a; return total
def load():
 fs=[]
 with (ROOT/'data/pascal_split_100_2026-08-06.csv').open(newline='') as z: rows=list(csv.DictReader(z))
 for r in rows:
  s=r['stem']; p=ROOT/f'data/pascal_split_100/raw_bin/{s}.bin'
  with Image.open(ROOT/f'data/pascal_split_100/images/{s}.jpg') as im: w,h=im.size
  fs.append(F('day',s,w,h,LOW if r['gt_lowlight'].lower()=='true' else NORMAL,p,float(r['dark16']),count_dark(p,w*h)))
  if len(fs)%25==0: print(f'PYTHON_DECODE_PROGRESS frames={len(fs)}',flush=True)
 with (ROOT/'data/split_nod/frames_meta.csv').open(newline='') as z: rows=list(csv.DictReader(z))
 for r in rows:
  s=r['stem'];w=int(r['w']);h=int(r['h']);p=ROOT/f'data/split_nod/raw_bin/{s}.bin'
  fs.append(F('night',s,w,h,LOW if int(r['illum_label'])==1 else NORMAL,p,float(r['dark16']),count_dark(p,w*h)))
  if len(fs)%25==0: print(f'PYTHON_DECODE_PROGRESS frames={len(fs)}',flush=True)
 assert len(fs)==200; return fs
def seqs(fs):
 d=[f for f in fs if f.source=='day'];n=[f for f in fs if f.source=='night'];m=d+n;random.Random(SEED).shuffle(m);rng=random.Random(SEED+1);cs=[]
 for g in (d,n):
  i=0
  while i<len(g): q=rng.randint(5,10);cs.append(g[i:i+q]);i+=q
 rng.shuffle(cs);return {'block_day_night':d+n,'block_night_day':n+d,'random_interleave':m,'chunk_shuffle':sum(cs,[])}
def sim(s,e,x,dwell):
 mode=NORMAL;dc=sw=n2l=l2n=fsw=nt=nl=dt=dl=ok=0
 for f in s:
  v,fl=select(f.dark,f.n,62,e,x);ok+=v==f.truth
  if dc: dc-=1
  elif mode==NORMAL and fl&1: mode=LOW;dc=dwell;sw+=1;n2l+=1;fsw+=f.truth==NORMAL
  elif mode==LOW and fl&2: mode=NORMAL;dc=dwell;sw+=1;l2n+=1
  if f.truth==LOW:nt+=1;nl+=mode==LOW
  else:dt+=1;dl+=mode==LOW
 return dict(frames=len(s),swaps=sw,normal_to_low_swaps=n2l,low_to_normal_swaps=l2n,false_trigger_swaps=fsw,recall=nl/nt,false_trigger_frame_rate=dl/dt,false_trigger_frames=dl,thrashing_per_100_frames=sw*100/len(s),single_frame_accuracy=ok/len(s))
def wc(p,rs):
 with p.open('w',newline='') as z:w=csv.DictWriter(z,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def plots(rs):
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 ps=[]
 for sn in sorted({r['sequence'] for r in rs}):
  fig,ax=plt.subplots(figsize=(8,5))
  for b,_,_ in BANDS:
   q=[r for r in rs if r['sequence']==sn and r['band']==b];ax.plot([r['dwell_frames'] for r in q],[r['swaps'] for r in q],marker='o',label=b)
  ax.set(title=f'RAW-decoded checker swaps: {sn}',xlabel='DWELL_FRAMES',ylabel='swaps');ax.set_xticks(range(4));ax.grid(alpha=.3);ax.legend(fontsize=8);fig.tight_layout();p=OUT/f'checker_raw_swaps_{sn}_2026-08-06.png';fig.savefig(p,dpi=160);plt.close(fig);ps.append(p)
 fig,ax=plt.subplots(figsize=(7,4.5));bs=['none_62_62','deployed_64_60'];vals=[sum(r['swaps'] for r in rs if r['band']==b and r['dwell_frames']==0)/4 for b in bs];ax.bar(bs,vals);ax.set_ylabel('mean swaps (4 orders, dwell=0)');fig.tight_layout();p=OUT/'checker_band_comparison_2026-08-06.png';fig.savefig(p,dpi=160);plt.close(fig);ps.append(p);return ps
def main():
 OUT.mkdir(parents=True,exist_ok=True);fs=load();detail=[];mm=0
 for f in fs:
  v,fl=select(f.dark,f.n);diff=abs(f.ratio-f.csv_ratio);tol=1e-12 if f.source=='day' else 5.0000001e-6;bad=diff>tol;mm+=bad
  detail.append(dict(source=f.source,stem=f.stem,width=f.w,height=f.h,n=f.n,raw_path=f.path,dark_count=f.dark,dark_pct100=f.dark*100,decoded_dark16=f.ratio,csv_dark16=f.csv_ratio,abs_diff=diff,tolerance=tol,csv_mismatch=int(bad),python_selected_mode=v,python_hyst_flags=fl))
 wc(OUT/'checker_raw_decode_frames_2026-08-06.csv',detail);rs=[]
 for sn,s in seqs(fs).items():
  for b,e,x in BANDS:
   for d in range(4):rs.append(dict(sequence=sn,band=b,enter_pct=e,exit_pct=x,verdict_pct=62,dwell_frames=d,seed=SEED,**sim(s,e,x,d)))
 wc(OUT/'checker_hysteresis_sequence_metrics_2026-08-06.csv',rs);ps=plots(rs);crop=[];(OUT/'crops').mkdir(exist_ok=True)
 for source in ('day','night'):
  g=[f for f in fs if f.source==source]
  for f in (min(g,key=lambda q:q.ratio),max(g,key=lambda q:q.ratio)):
   a=np.memmap(f.path,dtype='<u2',mode='r',shape=(f.h,f.w));y=(f.h-32)//2;x=(f.w-32)//2;c=np.array(a[y:y+32,x:x+32],copy=True);del a;p=OUT/f'crops/{source}_{f.stem}_32x32.bin';c.astype('<u2').tofile(p);dark=int((c<TH).sum());v,fl=select(dark,1024);crop.append(dict(source=source,stem=f.stem,width=32,height=32,raw_path=p,full_ratio=f.ratio,crop_dark_count=dark,python_selected_mode=v,python_hyst_flags=fl))
 wc(OUT/'checker_cosim_crops_2026-08-06.csv',crop);mx=max(abs(f.ratio-f.csv_ratio) for f in fs);(OUT/'checker_python_summary_2026-08-06.json').write_text(json.dumps(dict(frames=200,day=100,night=100,threshold=TH,csv_mismatches=int(mm),max_abs_diff=mx,combinations=len(rs),plots=[str(p) for p in ps]),indent=2)+'\n')
 print('PYTHON_DECODE frames=200 day=100 night=100 threshold=4096');print(f'PYTHON_CSV_COMPARE mismatches={mm}/200 max_abs_diff={mx:.12g}');print(f'PYTHON_SEQUENCE combinations={len(rs)}')
if __name__=='__main__':main()
