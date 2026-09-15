import json,os,platform,resource
from pathlib import Path
r={"node":platform.node(),"job":os.environ.get("SLURM_JOB_ID"),"file_nr":Path("/proc/sys/fs/file-nr").read_text().strip(),"file_max":Path("/proc/sys/fs/file-max").read_text().strip(),"open_file_limits":resource.getrlimit(resource.RLIMIT_NOFILE)}
print(json.dumps(r),flush=True)
