import hashlib,json
from sqlalchemy import select
from .models import *
from .common import *
from .constants import FIT_LABELS,CUT_NAMES,NONE_SUGGESTION

def _trial_for_update(s,fitting_id):
 x=s.scalars(select(Trial).where(Trial.fitting_id==fitting_id).with_for_update().execution_options(populate_existing=True)).first()
 return x

def _ready_assessment(s,garment_id,profile_id):
 rows_=s.scalars(select(FitAssessment).where(FitAssessment.garment_id==garment_id,FitAssessment.profile_id==profile_id,FitAssessment.state=='ready').order_by(FitAssessment.id.desc())).all()
 return rows_[0] if rows_ else None

def start(s,d):
 c=lock(s);f=get(s,Fitting,d['fitting_id'])
 if f.state!='reserved':fail('只有未成交的有效预约可以开试')
 if _trial_for_update(s,f.id):fail('该预约已开试，重复开试不另计')
 g=garment(s,f.garment_id);m=next((x for x in rows(s,Measurement) if x.garment_id==g.id),None)
 if not m:fail('衣物未实测，无法登记试衣')
 a=_ready_assessment(s,f.garment_id,f.profile_id)
 suggested=a.result['label'] if a and isinstance(a.result,dict) and a.result.get('label') in FIT_LABELS else None
 x=Trial(fitting_id=f.id,garment_id=f.garment_id,cut=m.cut,suggested=suggested,actual=None,state='in_progress',version=1,fitting_day=time(f.starts).date().isoformat(),started_at=c.now,completed_at='')
 s.add(x);s.flush();return x

def complete(s,d):
 lock(s);x=_trial_for_update(s,d['fitting_id'])
 if not x:fail('请先开试再登记实际松紧')
 if x.state!='in_progress':fail('试衣已登记实际松紧，如需更正请提交改判')
 f=get(s,Fitting,d['fitting_id'])
 if f.state=='cancelled':fail('预约已取消，不能登记试衣结果')
 c=s.scalars(select(Shop).where(Shop.id==1)).one()
 x.actual=d['actual'];x.state='completed';x.completed_at=c.now;s.flush();return x

def revise(s,d,u):
 lock(s);x=s.scalars(select(Trial).where(Trial.id==d['trial_id']).with_for_update().execution_options(populate_existing=True)).first()
 if not x:raise HTTPException(404,'试衣记录不存在')
 if x.state!='completed':fail('试衣尚未登记实际松紧，不能改判')
 if x.version!=d['base_version']:fail('判定已被他人更新，请查看最新判定后基于版本 %d 再改'%x.version)
 c=s.scalars(select(Shop).where(Shop.id==1)).one()
 old=x.actual;new=d['actual']
 if old==new:fail('改判类别与当前判定一致，无需修订')
 r=TrialRevision(trial_id=x.id,old_actual=old,new_actual=new,reason=d['reason'],base_version=x.version,new_version=x.version+1,actor=u['email'],revised_at=c.now)
 s.add(r);x.actual=new;x.version+=1;s.flush();return x

def _trial_snapshot(t):
 return {'trial_id':t.id,'fitting_id':t.fitting_id,'garment_id':t.garment_id,'cut':t.cut,'cut_name':CUT_NAMES[t.cut],'suggested':t.suggested,'actual':t.actual,'version':t.version,'fitting_day':t.fitting_day}

def _build_payload(s,day):
 ts=s.scalars(select(Trial).where(Trial.fitting_day==day)).all()
 items=[_trial_snapshot(t) for t in ts if t.state=='completed']
 items.sort(key=lambda z:z['trial_id'])
 by_cut={}
 for t in items:
  cell=by_cut.setdefault(t['cut'],{'cut':t['cut'],'cut_name':t['cut_name'],'matrix':{a:{b:0 for b in list(FIT_LABELS)+[NONE_SUGGESTION]} for a in FIT_LABELS},'total':0,'mismatch':0})
  sug=t['suggested'] or NONE_SUGGESTION
  cell['matrix'][t['actual']][sug]+=1;cell['total']+=1
  if t['suggested'] is None or t['suggested']!=t['actual']:cell['mismatch']+=1
 return {'day':day,'trial_total':len(items),'trials':items,'by_cut':[by_cut[k] for k in sorted(by_cut)]}

def _hash(payload):
 return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def run_report(s,d):
 c=lock(s);day=time(d['day']+'T00:00:00').date().isoformat()
 payload=_build_payload(s,day);h=_hash(payload)
 latest=s.scalars(select(DailyReport).where(DailyReport.day==day).order_by(DailyReport.version.desc())).first()
 if latest and latest.data_hash==h:
  latest.reused+=1;return latest
 version=(latest.version+1) if latest else 1
 r=DailyReport(day=day,version=version,data_hash=h,payload=payload,reused=0,created_at=c.now)
 s.add(r);s.flush();return r

def list_reports(s):
 return s.scalars(select(DailyReport).order_by(DailyReport.day,DailyReport.version)).all()
