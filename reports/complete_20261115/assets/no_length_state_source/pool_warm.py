from ablation import *
def main():
 guard();assert (OUT/'preflight/manifest.json').exists()
 deadline=time.time()+6400;os.environ['LOCALIZER_DEADLINE']=str(deadline-180)
 claims=OUT/'claims';claims.mkdir(exist_ok=True);fails=OUT/'failures';fails.mkdir(exist_ok=True)
 for u in units():
  key='--'.join(u);cl=claims/key
  if done(u) or not ready(u) or (fails/(key+'.json')).exists():continue
  try:cl.mkdir()
  except FileExistsError:continue
  c.save(cl/'owner.json',dict(job=os.environ['SLURM_JOB_ID'],array=os.getenv('SLURM_ARRAY_TASK_ID'),unit=u,warm=True))
  print('CLAIM_WARM',u,flush=True)
  try:ok=unit(*u)
  except Exception as e:
   c.save(fails/(key+'.json'),dict(unit=u,error=repr(e),job=os.getenv('SLURM_JOB_ID')));raise
  finally:(cl/'owner.json').unlink();cl.rmdir()
  if ok is False or time.time()>deadline-240:sys.exit(75)
 print('WARM_END','completed',sum(done(u) for u in units()),flush=True)
if __name__=='__main__':main()
