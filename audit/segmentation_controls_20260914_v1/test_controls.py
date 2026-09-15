"""Regression checks for boundary opportunities, prompt resampling and positional confounding."""
import ast,unittest
from pathlib import Path
import numpy as np
import pandas as pd
from controls import trials,features,bootstrap,positional_null
def row(f,j,L=3,p="p",family="a",lo=0):
    return dict(f=f,j=j,s=j,L=L,problem_id=p,task_family=family,lo=lo,trace_id=p,
                tied_jump=False,tied_surprisal=False)
class Tests(unittest.TestCase):
    def test_impossible_neighbors_are_misses(self):
        x,a=features([row(0,1),row(2,1),row(0,0,1)])
        np.testing.assert_equal(x[:,0,:],[[0,0,1,1],[1,0,0,1],[0,1,0,1]])
        np.testing.assert_equal(a,[[0,1,1,1],[1,1,0,1],[0,1,0,1]])
        np.testing.assert_allclose(x[:,3,:],[[0,1/3,1/3,2/3],[1/3,1/3,0,2/3],[0,1,0,1]])
    def test_drop_first_recomputes_max_without_index_shift(self):
        f=pd.DataFrame([dict(trace_id="a",prompt_id="p",task_family="x",t=t,t_star=1,z=z,surprisal=s)
                       for t,(z,s) in enumerate(zip([100,2,8],[100,8,1]))])
        a=trials(f,"error_after_first_with_original_scores")[0]
        b=trials(f,"error_after_first_excluding_first_increment")[0]
        self.assertEqual((a["f"],a["j"],a["s"],a["lo"]),(1,0,0,0))
        self.assertEqual((b["f"],b["j"],b["s"],b["lo"]),(1,2,1,1))
        np.testing.assert_allclose(features([b])[0][0,3,:],[0,.5,.5,1])
    def test_first_and_last_subset_exclusions(self):
        f=pd.DataFrame([dict(trace_id=str(k),prompt_id=str(k),task_family="x",t=t,t_star=k,z=t,surprisal=t)
                       for k in range(3) for t in range(3)])
        self.assertEqual(len(trials(f,"all")),3)
        self.assertEqual(len(trials(f,"error_after_first_with_original_scores")),2)
        self.assertEqual([r["f"] for r in trials(f,"both_neighbors")],[1])
    def test_ties_use_earliest(self):
        f=pd.DataFrame([dict(trace_id="a",prompt_id="p",task_family="x",t=t,t_star=1,z=2,surprisal=2) for t in range(3)])
        r=trials(f,"all")[0]
        self.assertEqual(r["j"],0);self.assertTrue(r["tied_jump"])
    def test_no_interval_below_twenty_tasks(self):
        rows=[row(0,0,p=str(i)) for i in range(19)]
        self.assertFalse(bootstrap(rows,np.ones((19,1)))["available"])
    def test_task_duplication_not_extra_independent_evidence(self):
        rows=[row(0,0,p=str(i)) for i in range(20)];v=np.arange(20,dtype=float)[:,None]
        a=bootstrap(rows,v,replicates=500)
        b=bootstrap([r for r in rows for _ in range(5)],np.repeat(v,5,axis=0),replicates=500)
        np.testing.assert_allclose(a["ci"],b["ci"]);self.assertEqual(a["tasks"],20)
    def test_positional_perfection_is_not_coupling(self):
        rows=[row(0,1,p=str(i)) for i in range(20)]
        r=positional_null(rows,permutations=199,adjust=True)
        self.assertEqual(r["pvalues"]["D=+1"],1)
        self.assertEqual(r["excess"][2],0)
    def test_real_pairing_beats_same_marginal_null(self):
        rows=[row(i%2,i%2+1,L=4,p=f"p{i:02}") for i in range(40)]
        r=positional_null(rows,permutations=1999,adjust=True)
        self.assertLess(r["pvalues"]["D=+1"],.01)
        self.assertAlmostEqual(r["observed"][2],1)
        self.assertEqual(r["adjusted_pvalues"]["D=+1"],12*r["pvalues"]["D=+1"])
    def test_exact_family_length_strata_and_one_trace_per_task(self):
        rows=[row(i%2,i%2+1,L=3,p=str(i),family="a" if i<10 else "b") for i in range(20)]
        rows +=[row(0,0,L=5,p="singleton",family="a"),{**rows[0],"trace_id":"z-duplicate"}]
        r=positional_null(rows,permutations=49)
        self.assertEqual(r["tasks"],20);self.assertEqual(r["tasks_before_matching"],21)
        self.assertEqual(r["excluded_singleton_tasks"],1)
        self.assertEqual({(g["family"],g["L"],g["tasks"]) for g in r["strata"]},{("a",3,10),("b",3,10)})
        self.assertNotIn("z-duplicate",r["selected_trace_ids"])
    def test_no_positional_test_below_twenty(self):
        rows=[row(0,0,p=str(i)) for i in range(19)]
        r=positional_null(rows,permutations=19)
        self.assertFalse(r["available"]);self.assertIsNone(r["pvalues"])
    def test_paired_identical_scores_gap_zero(self):
        rows=[row(i%3,i%3,p=str(i)) for i in range(20)]
        x,_=features(rows);b=bootstrap(rows,x[:,0,:]-x[:,1,:],replicates=99)
        np.testing.assert_equal(b["ci"],np.zeros((4,2)))
    def test_sources_parse(self):
        for name in ["controls.py","profile.py","test_controls.py"]:
            ast.parse(Path(__file__).with_name(name).read_text(encoding="utf-8"))
if __name__=="__main__":unittest.main()
