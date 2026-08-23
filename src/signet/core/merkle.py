"""Daily batching, so DNS writes do not scale with document volume.

One record per issuer per day carries that day's root. A document proves it was
issued inside that batch with an inclusion proof, which keeps DNS writes constant
whether the issuer emits ten documents or two million.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

# Leaves and internal nodes are hashed under different prefixes. Without that,
# sha256(payload) and sha256(left + right) live in one space, so a sixty four
# byte leaf whose bytes happen to be two sibling hashes is indistinguishable
# from the node above them. An attacker who can choose a document then presents
# an internal node as a leaf and proves inclusion of something never issued.
# This is the second preimage attack RFC 6962 separates domains to defeat.
_LEAF_PREFIX: Final = b"\x00"
_NODE_PREFIX: Final = b"\x01"


def leaf_hash(payload: bytes) -> bytes:
    return hashlib.sha256(_LEAF_PREFIX + payload).digest()


def _pair_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(_NODE_PREFIX + left + right).digest()


@dataclass(frozen=True, slots=True)
class InclusionProof:
    """Sibling hashes from a leaf to the root, innermost first."""

    steps: tuple[tuple[bool, bytes], ...]

    @property
    def size(self) -> int:
        return len(self.steps)


@dataclass(frozen=True, slots=True)
class MerkleTree:
    layers: tuple[tuple[bytes, ...], ...]

    @property
    def root(self) -> bytes:
        return self.layers[-1][0]

    def proof(self, index: int) -> InclusionProof:
        """Build the inclusion proof for the leaf at index.

        Raises IndexError when the index is outside the tree.
        """
        if not 0 <= index < len(self.layers[0]):
            raise IndexError(f"leaf index {index} outside tree of {len(self.layers[0])}")
        steps: list[tuple[bool, bytes]] = []
        for layer in self.layers[:-1]:
            sibling = index ^ 1
            if sibling < len(layer):
                steps.append((bool(sibling & 1), layer[sibling]))
            index //= 2
        return InclusionProof(steps=tuple(steps))


def build_tree(payloads: Sequence[bytes]) -> MerkleTree:
    """Build a tree over document payloads, hashing each one as a leaf here.

    Taking payloads rather than hashes is the point. When this took hashes it
    could not tell a leaf from an internal node, both being thirty two opaque
    bytes, so a caller could pass the root of a subtree as a leaf and produce a
    tree of a different shape with an identical root. Hashing here makes that
    unrepresentable rather than merely discouraged.

    Raises ValueError on an empty sequence: a batch with no documents has no root
    to publish, and silently returning a zero hash would make that indistinguishable
    from a real one.
    """
    if not payloads:
        raise ValueError("cannot build a tree over zero leaves")
    layers: list[tuple[bytes, ...]] = [tuple(leaf_hash(payload) for payload in payloads)]
    while len(layers[-1]) > 1:
        current = layers[-1]
        nxt = [
            _pair_hash(current[i], current[i + 1]) if i + 1 < len(current) else current[i]
            for i in range(0, len(current), 2)
        ]
        layers.append(tuple(nxt))
    return MerkleTree(layers=tuple(layers))


def verify_inclusion(payload: bytes, proof: InclusionProof, root: bytes) -> bool:
    computed = leaf_hash(payload)
    for sibling_on_right, sibling in proof.steps:
        computed = (
            _pair_hash(computed, sibling) if sibling_on_right else _pair_hash(sibling, computed)
        )
    return computed == root
