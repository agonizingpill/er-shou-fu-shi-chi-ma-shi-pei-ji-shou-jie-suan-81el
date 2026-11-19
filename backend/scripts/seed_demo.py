from src.database import Base,engine,Session
from src.models import *
from src.security import password_hash
from src.common import rows
from src import trial_service

def seed():
 Base.metadata.create_all(engine)
 with Session() as s:
  for r in ['operator','supervisor','viewer']:
   if not any(u.email==r+'@hesheng.local' for u in rows(s,User)):s.add(User(email=r+'@hesheng.local',password=password_hash('Fit2026!'),role=r))
  if not s.get(Shop,1):s.add(Shop(id=1,now='2026-11-18T09:00:00'))
  if not any(g.code=='G031' for g in rows(s,Garment)):
   c=Consignor(name='林禾',contact='柜台留存联系单LH031');s.add(c);s.flush();prof=FitProfile(code='P031',chest=88,shoulder=37);s.add(prof);s.flush()
   for code,ends in [('A031','2026-11-26T18:00:00'),('A032','2026-11-20T18:00:00'),('A033','2026-11-17T18:00:00')]:s.add(Agreement(code=code,consignor_id=c.id,floor_cents=18000,commission_bp=2000,ends=ends))
   s.flush();ags=rows(s,Agreement)
   for code,title,ag,state in [('G031','烟苔绿短外套',ags[0],'listed'),('G032','复检中的棉衬衣',ags[1],'inspection'),('G033','期满未售针织衫',ags[2],'listed'),('G034','赭色直筒外套',ags[0],'listed')]:
    g=Garment(code=code,title=title,agreement_id=ag.id,condition='八成新，领口轻微使用痕迹，无破损',price_cents=22000,state=state);s.add(g);s.flush();s.add(Measurement(garment_id=g.id,chest=96,shoulder=39,length=58,elasticity=.2,cut=1))
   s.flush();g=next(g for g in rows(s,Garment) if g.code=='G032');f=Fitting(garment_id=g.id,profile_id=prof.id,slot=1,starts='2026-11-16T15:00:00',ends='2026-11-16T16:00:00',state='completed');s.add(f);s.flush();sale=Sale(fitting_id=f.id,garment_id=g.id,price_cents=22000,commission_bp=2000,commission_cents=4400,net_cents=17600,sold_at='2026-11-16T15:10:00',return_deadline='2026-11-23T15:10:00',state='returned');s.add(sale);s.flush();s.add(Return(sale_id=sale.id,reason='买家反馈肩部偏紧，已按原样退回待复检'))
  # —— 试衣松紧核对演示数据（幂等补缺）——
  if not rows(s,Trial):
   gs={g.code:g for g in rows(s,Garment)};p=next(x for x in rows(s,FitProfile) if x.code=='P031')
   s.add(FitAssessment(garment_id=gs['G034'].id,profile_id=p.id,state='ready',result={'label':'合身','note':'演示用适配结果'}))
   f1=Fitting(garment_id=gs['G032'].id,profile_id=p.id,slot=2,starts='2026-11-16T10:00:00',ends='2026-11-16T11:00:00',state='completed')
   f2=Fitting(garment_id=gs['G034'].id,profile_id=p.id,slot=1,starts='2026-11-17T14:00:00',ends='2026-11-17T15:00:00',state='completed')
   s.add_all([f1,f2]);s.flush()
   t1=Trial(fitting_id=f1.id,garment_id=f1.garment_id,cut=1,suggested='合身',actual='偏紧',state='completed',version=2,fitting_day='2026-11-16',started_at='2026-11-16T10:05:00',completed_at='2026-11-16T10:40:00')
   t2=Trial(fitting_id=f2.id,garment_id=f2.garment_id,cut=1,suggested=None,actual='偏松',state='completed',version=1,fitting_day='2026-11-17',started_at='2026-11-17T14:05:00',completed_at='2026-11-17T14:45:00')
   s.add_all([t1,t2]);s.flush()
   s.add(TrialRevision(trial_id=t1.id,old_actual='合身',new_actual='偏紧',reason='买家抬臂时肩部明显发紧，顾问复核后改判偏紧',base_version=1,new_version=2,actor='operator@hesheng.local',revised_at='2026-11-16T18:20:00'))
   # 首日日报原版（改判前口径），改判后重跑产出修订版；原版哈希独立保留
   original_payload={'day':'2026-11-16','trial_total':1,'trials':[{'trial_id':t1.id,'fitting_id':f1.id,'garment_id':f1.garment_id,'cut':1,'cut_name':'标准','suggested':'合身','actual':'合身','version':1,'fitting_day':'2026-11-16'}],'by_cut':[{'cut':1,'cut_name':'标准','matrix':{'合身':{'合身':1,'偏紧':0,'偏松':0,'无建议':0},'偏紧':{'合身':0,'偏紧':0,'偏松':0,'无建议':0},'偏松':{'合身':0,'偏紧':0,'偏松':0,'无建议':0}},'total':1,'mismatch':0}]}
   s.add(DailyReport(day='2026-11-16',version=1,data_hash=trial_service._hash(original_payload),payload=original_payload,reused=0,created_at='2026-11-16T17:00:00'))
   s.flush()
   for day in ('2026-11-16','2026-11-17'):
    r=trial_service.run_report(s,{'day':day});s.add(Audit(actor='seed@hesheng.local',action='试衣日报发布',detail=str({'day':day,'version':r.version})[:500]))
  s.commit()
if __name__=='__main__':seed()
