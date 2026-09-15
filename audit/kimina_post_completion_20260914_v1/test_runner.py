import io,unittest
from support import *
import test_analysis
check_code();check_code("analysis-source-manifest.json")
out=OUT/"analysis-tests";out.mkdir(exist_ok=False)
buf=io.StringIO();result=unittest.TextTestRunner(stream=buf,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_analysis))
log=out/"tests.log";log.write_text(buf.getvalue(),encoding="utf-8");print(buf.getvalue(),flush=True)
finish(out,{"passed":result.wasSuccessful(),"tests_run":result.testsRun,"live_lean":False,"live_gpu":False},
 [HERE/"core-source-manifest.json",HERE/"analysis-source-manifest.json"],[log])
if not result.wasSuccessful():raise RuntimeError("analysis adapter tests failed")
