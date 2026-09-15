import copy,unittest
import numpy as np
from policy import clean_length,slice_states,fit_calibration
from onebigjump.e1.measurement import transformed_norms
VERIFIED={"old_category":"verified","whole_verdict_agrees":True,"p2_eligible":False}
def observation(label,closed=False):
    status="post_completion" if label=="post_completion" else "observed"
    return {"trace_label":label,"execution_status":status,"source_points":[{"trace_label":label,"execution_status":status,
        "root_closed_before":closed,"active_goal_ids":[] if closed else ["goal"]}]}
def exp(tags):return {"observation_rows":[observation(x,x=="post_completion") for x in tags]}
class Tests(unittest.TestCase):
    def test_terminal_suffix_preserves_closing_observation(self):
        self.assertEqual(clean_length(exp(["verified_trace","verified_trace","post_completion","post_completion"]),VERIFIED),(2,None))
    def test_local_goal_closure_does_not_trigger_trimming(self):
        e=exp(["verified_trace"]*3);e["observation_rows"][1]["source_points"][0]["active_goal_ids"]=[]
        self.assertEqual(clean_length(e,VERIFIED),(3,None))
    def test_no_suffix_unchanged(self):
        self.assertEqual(clean_length(exp(["verified_trace"]*2),VERIFIED),(2,None))
    def test_nonterminal_suffix_blocked(self):
        with self.assertRaisesRegex(ValueError,"terminal"):clean_length(exp(["verified_trace","post_completion","verified_trace"]),VERIFIED)
    def test_missing_root_evidence_blocked(self):
        e=exp(["verified_trace","post_completion"]);e["observation_rows"][1]["source_points"][0].pop("root_closed_before")
        with self.assertRaisesRegex(ValueError,"root"):clean_length(e,VERIFIED)
    def test_mixed_boundary_blocked(self):
        e=exp(["verified_trace","post_completion"]);e["observation_rows"][1]["source_points"].append(observation("verified_trace")["source_points"][0])
        with self.assertRaisesRegex(ValueError,"mixed"):clean_length(e,VERIFIED)
    def test_empty_content_blocked(self):
        with self.assertRaisesRegex(ValueError,"no retained"):clean_length(exp(["post_completion"]),VERIFIED)
    def test_refuted_post_error_recovery_is_retained(self):
        e=exp(["pre","at","post"]);e["observation_rows"][2]["source_points"][0].update(execution_status="post_completion",root_closed_before=True,active_goal_ids=[])
        self.assertEqual(clean_length(e,{"old_category":"localized_tactic_failure","p2_eligible":True}),(3,1))
    def test_original_states_and_surprisal_preserved(self):
        states=np.arange(15).reshape(5,3);surprisal=np.asarray([1.,2.,3.,4.])
        original=states.copy();x,s=slice_states(states,surprisal,4,2)
        np.testing.assert_array_equal(np.diff(x,axis=0),np.diff(states,axis=0)[:2])
        np.testing.assert_array_equal(s,surprisal[:2]);x[0]=99;np.testing.assert_array_equal(states,original)
    def test_shape_mismatch_blocked(self):
        with self.assertRaises(ValueError):slice_states(np.zeros((4,2)),np.zeros(4),4,2)
    def test_refit_ignores_evaluation_and_failed_calibration(self):
        records=[{"trace_id":"c"+str(i),"problem_id":"c"+str(i),"role":"calibration","star":None,
                  "states":np.asarray([[0.,0.],[i+1.,2.],[3.,i+1.]])} for i in range(2)]
        settings={"min_main_tasks":2,"min_main_increments":2,"shrinkage":.1,"ridge":1.}
        a,_=fit_calibration(records,settings)
        records += [{"trace_id":"e","problem_id":"e","role":"evaluation","star":None,"states":np.full((3,2),1e8)},
                    {"trace_id":"f","problem_id":"f","role":"calibration","star":0,"states":np.full((3,2),-1e8)}]
        b,info=fit_calibration(records,settings)
        for key in a:np.testing.assert_array_equal(a[key],b[key])
        self.assertEqual(info["tasks"],2);self.assertEqual(info["increments"],4)
    def test_refit_changes_transform_after_tail_removal(self):
        states=np.asarray([[0.,0.],[1.,2.],[3.,1.],[100.,-100.]])
        base=[{"trace_id":"c","problem_id":"c","role":"calibration","star":None,"states":states}]
        settings={"min_main_tasks":1,"min_main_increments":2,"shrinkage":.1,"ridge":1.}
        old,_=fit_calibration(base,settings)
        clean=[{**base[0],"states":states[:3]}];new,info=fit_calibration(clean,settings)
        self.assertEqual(int(new["n_increments"]),2)
        self.assertFalse(np.allclose(old["mean"],new["mean"]))
        np.testing.assert_array_equal(transformed_norms(states[:3],old)["raw"],transformed_norms(states[:3],new)["raw"])
    def test_calibration_task_overlap_blocked(self):
        r=[{"trace_id":"c","problem_id":"p","role":"calibration","star":None,"states":np.zeros((3,2))},
           {"trace_id":"e","problem_id":"p","role":"evaluation","star":None,"states":np.zeros((3,2))}]
        with self.assertRaisesRegex(ValueError,"overlap"):fit_calibration(r,{"min_main_tasks":20,"min_main_increments":200})
if __name__=="__main__":unittest.main()
