from stage_support import start
from portable_runtime import finish_portable
import p2_verify
if __name__=="__main__":
 start("portable_runtime")
 p2_verify.artifact_finish=finish_portable
 p2_verify.main()
