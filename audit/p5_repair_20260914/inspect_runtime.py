import inspect,importlib.metadata,json
from vllm.sampling_params import SamplingParams,GuidedDecodingParams
import xgrammar
from vllm.model_executor.guided_decoding import get_local_guided_decoding_logits_processor
print('VERSIONS',{n:importlib.metadata.version(n) for n in ['vllm','xgrammar','transformers']})
print('GUIDED',inspect.getsource(GuidedDecodingParams))
print('LOCAL_FACTORY',inspect.signature(get_local_guided_decoding_logits_processor))
print('XGRAMMAR',inspect.signature(xgrammar.TokenizerInfo.from_huggingface),inspect.signature(xgrammar.GrammarCompiler),inspect.signature(xgrammar.GrammarCompiler.compile_grammar),inspect.signature(xgrammar.GrammarMatcher),inspect.signature(xgrammar.GrammarMatcher.accept_token))
print('SAMPLING_GUIDED',SamplingParams(guided_decoding=GuidedDecodingParams(grammar='root ::= \"ok\"',backend='xgrammar:no-fallback')))
