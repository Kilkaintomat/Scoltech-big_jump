import ast,unittest
from pathlib import Path
import numpy as np
import pandas as pd
from recompute import table_rows
from policy import slice_states
from onebigjump.experiments.dataset import validate_table
class AnalysisTests(unittest.TestCase):
    def record(self,star):
        return {"trace_id":"t","problem_id":"p","role":"evaluation","temperature":.6,"task_family":"f","category":"verified" if star is None else "localized_tactic_failure",
                "states":np.zeros((4,2)),"surprisal":np.asarray([1.,2.,3.]),"star":star}
    def test_failed_positions_and_absorption_unchanged(self):
        r=self.record(1);f=pd.DataFrame(table_rows(r,{"raw":np.asarray([2.,4.,3.])},{"model_id":"m"},17))
        validate_table(f);self.assertEqual(f.status.tolist(),["ok","error","unreached"]);self.assertEqual(f.t_star.tolist(),[1,1,1])
        self.assertEqual(f.surprisal.tolist(),[1.,2.,3.])
    def test_trimmed_verified_proof_keeps_whole_verdict(self):
        r=self.record(None);r["states"],r["surprisal"]=slice_states(r["states"],r["surprisal"],3,2)
        f=pd.DataFrame(table_rows(r,{"raw":np.asarray([2.,4.]),"whitened":np.asarray([.2,.4])},{"model_id":"m"},17))
        validate_table(f);self.assertTrue((f.L==2).all());self.assertTrue((f.outcome=="verified").all())
        self.assertTrue(f.t_star.isna().all())
    def test_deviation_length_mismatch_blocked(self):
        with self.assertRaisesRegex(ValueError,"deviation"):table_rows(self.record(None),{"raw":np.ones(2)},{"model_id":"m"},17)
    def test_source_parses(self):
        for name in ["recompute.py","compare.py","test_analysis.py"]:
            ast.parse(Path(__file__).with_name(name).read_text(encoding="utf-8"))
if __name__=="__main__":unittest.main()
