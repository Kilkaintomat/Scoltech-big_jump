from ablation import *
import importlib.util
assert os.getenv('SLURM_JOB_ID')
paths=list(HERE.glob('*.py'))+list(HERE.glob('*.md'))+list(HERE.glob('*.sbatch'))+[Path(c.__file__)]
c.save(HERE/'freeze.json',{str(p):c.sha(p) for p in paths})
c.save(OUT/'planned_units_v2.json',[list(u) for u in units()])
spec=importlib.util.spec_from_file_location('state_noN_preflight',HERE/'preflight.py')
checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
assert Path(checks.__file__).resolve()==HERE/'preflight.py'
checks.main()
