import pytest

from signet.core.merkle import build_tree, leaf_hash, verify_inclusion


def _leaves(count: int) -> list[bytes]:
    return [leaf_hash(f"document-{i}".encode()) for i in range(count)]


@pytest.mark.parametrize("count", [1, 2, 3, 8, 9, 1024])
def test_every_leaf_proves_inclusion(count: int) -> None:
    leaves = _leaves(count)
    tree = build_tree(leaves)
    for index, leaf in enumerate(leaves):
        assert verify_inclusion(leaf, tree.proof(index), tree.root)


def test_a_forged_leaf_does_not_prove_inclusion() -> None:
    leaves = _leaves(64)
    tree = build_tree(leaves)
    assert not verify_inclusion(leaf_hash(b"forged"), tree.proof(7), tree.root)


def test_proof_grows_logarithmically() -> None:
    assert build_tree(_leaves(1024)).proof(0).size == 10


def test_empty_batch_is_refused() -> None:
    with pytest.raises(ValueError, match="zero leaves"):
        build_tree([])


def test_index_outside_tree_is_refused() -> None:
    with pytest.raises(IndexError):
        build_tree(_leaves(4)).proof(9)
