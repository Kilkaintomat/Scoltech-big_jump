"""Forward hooks that capture the residual stream after chosen decoder blocks.

Appendix B.1: "we register forward hooks on the decoder blocks and record the block output (the
residual stream after block `l`) at the token positions that end each step".

Two details decide whether the numbers mean what the paper says:

* **block output, not block input.** A pre-norm decoder layer returns the residual stream *after*
  its contribution has been added, which is the `X_t` of Section 2. Hooking the input would read
  the state one layer early.
* **float32 accumulation.** Models run in bfloat16, whose 8-bit mantissa cannot represent a norm
  to the precision a tail index needs; the norms are the observable, so the captured states are
  promoted to float32 before anything is computed from them.

Only the requested positions are kept. Storing the whole `(batch, seq, d)` tensor for every layer
would be tens of gigabytes over a batch of proofs, and every row but the step ends is discarded.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

__all__ = ["LayerCapture", "ResidualRecorder", "block_modules", "layer_indices", "record_residuals"]


def block_modules(model: Any) -> list[Any]:
    """The decoder blocks of a HuggingFace causal LM, across the usual layouts."""
    candidates = (
        "model.layers",  # Llama, Qwen, Mistral, DeepSeek
        "transformer.h",  # GPT-2, GPT-J
        "gpt_neox.layers",  # NeoX
        "model.decoder.layers",  # OPT
        "transformer.blocks",  # MPT
        "layers",
    )
    for path in candidates:
        node: Any = model
        for part in path.split("."):
            node = getattr(node, part, None)
            if node is None:
                break
        if node is not None and len(list(node)) > 0:
            return list(node)
    raise AttributeError(
        f"could not find the decoder blocks; pass them explicitly. Tried: {', '.join(candidates)}"
    )


def layer_indices(n_layers: int, fractions: Sequence[float]) -> list[int]:
    """`l in {floor(f * Lambda)}` for the requested fractions, deduplicated and in range.

    The paper reads out at `Lambda/4`, `Lambda/2` and `3Lambda/4`; `floor` is what it writes.
    """
    out: list[int] = []
    for f in fractions:
        idx = int(f * n_layers)
        idx = max(0, min(idx, n_layers - 1))
        if idx not in out:
            out.append(idx)
    return sorted(out)


@dataclass
class LayerCapture:
    """States captured at one layer, one row per requested position."""

    layer: int
    states: Any  # torch.Tensor of shape (n_positions, d), float32

    @property
    def n_positions(self) -> int:
        return int(self.states.shape[0])

    @property
    def d_model(self) -> int:
        return int(self.states.shape[-1])


@dataclass
class ResidualRecorder:
    """Collects block outputs at fixed token positions for a set of layers."""

    layers: Sequence[int]
    positions: Sequence[int]
    captures: dict[int, Any] = field(default_factory=dict)
    _handles: list[Any] = field(default_factory=list, repr=False)

    def _make_hook(self, layer: int) -> Any:
        import torch

        pos = list(self.positions)

        def hook(_module: Any, _inputs: Any, output: Any) -> None:
            # A decoder block returns either the hidden states or a tuple starting with them.
            hidden = output[0] if isinstance(output, tuple) else output
            if hidden.dim() == 3:
                if hidden.shape[0] != 1:
                    raise ValueError("ResidualRecorder requires exactly one sequence")
                hidden = hidden[0]  # single sequence per forward pass
            index = torch.tensor(pos, device=hidden.device)
            self.captures[layer] = hidden.index_select(0, index).detach().to(torch.float32).cpu()

        return hook

    def attach(self, blocks: Sequence[Any]) -> ResidualRecorder:
        if any(layer < 0 or layer >= len(blocks) for layer in self.layers):
            raise ValueError("readout layer outside decoder block range")
        if not self.positions or any(pos < 0 for pos in self.positions):
            raise ValueError("readout positions must be nonnegative and nonempty")
        for layer in self.layers:
            self._handles.append(blocks[layer].register_forward_hook(self._make_hook(layer)))
        return self

    def detach(self) -> None:
        for handle in self._handles:
            handle.remove()
        self._handles.clear()

    def result(self) -> dict[int, LayerCapture]:
        return {layer: LayerCapture(layer, states) for layer, states in self.captures.items()}


@contextmanager
def record_residuals(
    model: Any, layers: Sequence[int], positions: Sequence[int]
) -> Iterator[ResidualRecorder]:
    """Attach hooks for the duration of a forward pass, and always remove them.

    Hooks left attached leak into every later forward pass of the same model object, which in a
    long extraction run means silently capturing the wrong positions.
    """
    recorder = ResidualRecorder(layers=list(layers), positions=list(positions))
    try:
        recorder.attach(block_modules(model))
        yield recorder
    finally:
        recorder.detach()
