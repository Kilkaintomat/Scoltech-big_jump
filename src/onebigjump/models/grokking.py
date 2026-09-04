"""The one-layer modular-addition transformer of Nanda et al. (2023), and its progress measures.

Appendix B.5 fixes the setting: one-layer transformer, `d = 128`, 4 heads, `p = 113`, weight
decay 1, full-batch AdamW, 40,000 steps, checkpoints every 100 steps. The architecture follows
the original: no layer normalisation, learned positional embeddings, ReLU MLP, and the loss taken
at the final position only, where the answer is predicted.

The progress measures are the point of using this task. Grokking is visible in the test accuracy,
but *why* it happens is visible only in the Fourier structure: the trained model computes
`(a + b) mod p` by a trigonometric identity on a handful of frequencies. Nanda et al. measure
circuit formation with two losses derived from that structure, and P4 asks whether `gamma_hat`
drops at the same moment they move.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import numpy as np

if TYPE_CHECKING:  # pragma: no cover
    from torch import Tensor, nn

__all__ = [
    "ModularAdditionData",
    "ProgressMeasures",
    "build_model",
    "key_frequencies",
    "make_data",
    "progress_measures",
]


@dataclass
class ModularAdditionData:
    """Every `(a, b)` pair, split into train and test once and for all."""

    inputs: Any  # (p*p, 3) long: [a, b, EQUALS]
    targets: Any  # (p*p,) long: (a + b) mod p
    train_idx: Any
    test_idx: Any
    p: int

    @property
    def n(self) -> int:
        return int(self.inputs.shape[0])


def make_data(p: int = 113, train_frac: float = 0.3, seed: int = 0) -> ModularAdditionData:
    """All `p^2` pairs, shuffled once and split. The token `p` is the `=` marker."""
    import torch

    a = torch.arange(p).repeat_interleave(p)
    b = torch.arange(p).repeat(p)
    equals = torch.full_like(a, p)
    inputs = torch.stack([a, b, equals], dim=1)
    targets = (a + b) % p

    g = torch.Generator().manual_seed(seed)
    perm = torch.randperm(p * p, generator=g)
    n_train = int(train_frac * p * p)
    return ModularAdditionData(
        inputs=inputs,
        targets=targets,
        train_idx=perm[:n_train],
        test_idx=perm[n_train:],
        p=p,
    )


def build_model(
    p: int = 113,
    d_model: int = 128,
    n_heads: int = 4,
    d_mlp: int | None = None,
    seed: int = 0,
) -> nn.Module:
    """The Nanda et al. architecture: one attention block, one MLP, no layer normalisation.

    Layer normalisation is omitted deliberately, as in the original. It matters here beyond
    fidelity: the depth-wise deviation P4 measures is the block output norm, and a normalisation
    layer would rescale exactly the quantity whose tail is the observable.
    """
    import torch
    from torch import nn

    torch.manual_seed(seed)
    d_hidden: int = d_mlp if d_mlp is not None else 4 * d_model
    d_head = d_model // n_heads

    class Block(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.n_heads = n_heads
            self.d_head = d_head
            self.q = nn.Linear(d_model, d_model, bias=False)
            self.k = nn.Linear(d_model, d_model, bias=False)
            self.v = nn.Linear(d_model, d_model, bias=False)
            self.o = nn.Linear(d_model, d_model, bias=False)
            self.fc_in = nn.Linear(d_model, d_hidden, bias=False)
            self.fc_out = nn.Linear(d_hidden, d_model, bias=False)

        def forward(self, x: Tensor) -> Tensor:
            b, t, _ = x.shape
            shape = (b, t, self.n_heads, self.d_head)
            q = self.q(x).view(shape).transpose(1, 2)
            k = self.k(x).view(shape).transpose(1, 2)
            v = self.v(x).view(shape).transpose(1, 2)
            attn = torch.softmax(
                (q @ k.transpose(-2, -1)) / np.sqrt(self.d_head)
                + torch.triu(torch.full((t, t), float("-inf"), device=x.device), 1),
                dim=-1,
            )
            head_out = (attn @ v).transpose(1, 2).reshape(b, t, -1)
            h = x + self.o(head_out)
            return h + self.fc_out(torch.relu(self.fc_in(h)))

    class Grok(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.embed = nn.Embedding(p + 1, d_model)
            self.pos = nn.Parameter(torch.randn(3, d_model) / np.sqrt(d_model))
            self.block = Block()
            self.unembed = nn.Linear(d_model, p, bias=False)
            self.p = p
            self.d_model = d_model

        def residual_in(self, tokens: Tensor) -> Tensor:
            return self.embed(tokens) + self.pos[: tokens.shape[1]]

        def forward(self, tokens: Tensor) -> Tensor:
            h = self.block(self.residual_in(tokens))
            return self.unembed(h[:, -1])

        def block_increment(self, tokens: Tensor) -> Tensor:
            """`h^(1) - h^(0)` at the final position: the depth-wise step deviation of P4."""
            h0 = self.residual_in(tokens)
            return (self.block(h0) - h0)[:, -1]

    return Grok()


def key_frequencies(model: nn.Module, top_k: int = 6) -> list[int]:
    """The Fourier frequencies the model's number embeddings actually use.

    The embedding rows for `0..p-1` become, after grokking, a sum of a few sinusoids. Their
    discrete Fourier transform therefore concentrates on a handful of frequencies, and those are
    the ones the restricted and excluded losses keep or remove.
    """
    import torch

    p = int(cast(int, model.p))
    with torch.no_grad():
        emb = cast(Any, model.embed).weight[:p].detach().cpu().numpy()
    spectrum = np.abs(np.fft.rfft(emb, axis=0))
    power = (spectrum**2).sum(axis=1)
    power[0] = 0.0  # the constant component is always present and carries no frequency
    return sorted(np.argsort(power)[::-1][:top_k].tolist())


@dataclass
class ProgressMeasures:
    """Nanda et al.'s two losses, plus the accuracies they are read against."""

    train_loss: float
    test_loss: float
    train_acc: float
    test_acc: float
    restricted_loss: float
    excluded_loss: float
    key_frequencies: list[int]

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _loss_and_acc(logits: Tensor, targets: Tensor) -> tuple[float, float]:
    import torch.nn.functional as functional

    loss = functional.cross_entropy(logits, targets)
    acc = (logits.argmax(dim=-1) == targets).float().mean()
    return float(loss.item()), float(acc.item())


def progress_measures(
    model: nn.Module, data: ModularAdditionData, *, top_k: int = 6, device: str = "cpu"
) -> ProgressMeasures:
    """Train/test loss and accuracy, plus the restricted and excluded losses.

    Both derived losses are computed by masking the two-dimensional discrete Fourier transform of
    the logits over the `(a, b)` grid:

    * **restricted** keeps only the key frequencies (and the constant term) and measures how much
      of the model's competence lives in the circuit -- it falls as the circuit forms;
    * **excluded** removes them and measures how much lives outside it -- it rises as the circuit
      forms, and its rise is the sharp signal of memorisation being replaced.
    """
    import torch

    p = int(cast(int, model.p))
    model.eval()
    with torch.no_grad():
        logits = model(data.inputs.to(device)).float().cpu()
    targets = data.targets

    train_loss, train_acc = _loss_and_acc(logits[data.train_idx], targets[data.train_idx])
    test_loss, test_acc = _loss_and_acc(logits[data.test_idx], targets[data.test_idx])

    freqs = key_frequencies(model, top_k=top_k)
    grid = logits.reshape(p, p, p).numpy()
    spectrum = np.fft.fft2(grid, axes=(0, 1))

    keep = np.zeros((p, p), dtype=bool)
    keep[0, 0] = True  # the constant term belongs to both models
    for f in freqs:
        for sign_a in (f, (p - f) % p):
            keep[sign_a, :] = True
            keep[:, sign_a] = True

    restricted = np.real(np.fft.ifft2(spectrum * keep[:, :, None], axes=(0, 1)))
    excluded = np.real(np.fft.ifft2(spectrum * (~keep)[:, :, None], axes=(0, 1)))

    r_loss, _ = _loss_and_acc(torch.from_numpy(restricted.reshape(p * p, p)).float(), targets)
    e_loss, _ = _loss_and_acc(torch.from_numpy(excluded.reshape(p * p, p)).float(), targets)

    return ProgressMeasures(
        train_loss=train_loss,
        test_loss=test_loss,
        train_acc=train_acc,
        test_acc=test_acc,
        restricted_loss=r_loss,
        excluded_loss=e_loss,
        key_frequencies=freqs,
    )
