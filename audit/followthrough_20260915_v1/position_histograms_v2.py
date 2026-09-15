"""Layout-only render revision, preserving all frozen numerical metrics."""
import shutil
from stage_support import ROOT, HERE, OUT, read, start, finish, digest
from position_histograms_render_v2 import render

def main():
    stage="position_histograms_v2"
    start(stage)
    source=OUT/"position_histograms"
    manifest_path=source/"manifest.json"
    provenance=read(manifest_path)
    folder=OUT/stage
    folder.mkdir(parents=True,exist_ok=True)
    inputs=[manifest_path]
    copied=[]
    for name in ["metrics.json","histograms.csv","README_RU.md"]:
        src=source/name
        assert digest(src)==provenance["outputs"][str(src)]
        dst=folder/name
        shutil.copyfile(src,dst)
        assert digest(src)==digest(dst)
        inputs.append(src)
        if name!="metrics.json":copied.append(dst)
    outputs=render(folder/"metrics.json",folder)
    finish(stage,read(folder/"metrics.json"),inputs,[*outputs,*copied])
    assert digest(folder/"metrics.json")==digest(source/"metrics.json")
    print("LAYOUT REVISION COMPLETE; ALL NUMERICAL METRICS IDENTICAL",flush=True)

if __name__=="__main__":main()
