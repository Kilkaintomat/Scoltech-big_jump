"""Lean 4 verification: exact per-step labels for proof traces (Section 5.1, Appendix B.2)."""

from .environment import LeanEnvironment, LeanNotAvailable, discover
from .problems import (
    Problem,
    build_prompt,
    extract_lean_block,
    load_problems,
    split_problems,
)
from .schemas import ProofTrace, StepLabel, StepStatus, TraceOutcome, VerificationSummary
from .segmentation import Segment, segment_proof, split_header_and_proof, strip_comments
from .verifier import LeanREPL, ReplError, verify_trace

__all__ = [
    "LeanEnvironment",
    "LeanNotAvailable",
    "LeanREPL",
    "Problem",
    "ProofTrace",
    "ReplError",
    "Segment",
    "StepLabel",
    "StepStatus",
    "TraceOutcome",
    "VerificationSummary",
    "build_prompt",
    "discover",
    "extract_lean_block",
    "load_problems",
    "segment_proof",
    "split_header_and_proof",
    "split_problems",
    "strip_comments",
    "verify_trace",
]
