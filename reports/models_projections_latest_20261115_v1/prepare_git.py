from mp_common import *
import shutil
def main():
 d=ROOT/"runs/models_projections_latest_20261115_v1/publication"
 verify_manifest(d)
 (d/".gitattributes").write_text("*.csv -text\n*.csv.gz -text\n*.png -text\n",encoding="utf8")
 shutil.copyfile(__file__,d/"prepare_git.py")
 (d/"manifest.json").rename(d/"pre_git_manifest.json")
 finish(d,dict(purpose="Preserve exact data-file bytes under repository text=auto/eol=lf attributes",scientific_metrics_unchanged=True))
 print("GIT_PACKAGE_READY",str(d),flush=True)
if __name__=="__main__":main()
