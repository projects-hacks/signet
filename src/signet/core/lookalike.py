"""Names that read as another name.

A valid signature from northpost.dev and a valid signature from north-post.dev
are the same event to a hurried reader, and only one of them is the supplier they
meant to pay. So confusability lives in core rather than in a vendor's scoring
endpoint: it decides a verdict, and a verdict has to be replayable a year later
without asking anyone's API what it thinks today.

Comparison normalises before it measures. Hyphens and homoglyph pairs are
presentation rather than content, so n0rth-post reduces to northpost and the two
read as one name instead of as a near miss. Whatever survives normalisation is
measured with a single edit of tolerance, because every permutation class below
is exactly one edit from its origin, and at two edits unrelated brands that share
a stem begin colliding with each other. False alarms are the expensive direction
here: this feeds a check that fails documents, and a supplier wrongly accused of
impersonating a name it merely resembles is the harm Signet exists to avoid.

Generation is capped at MAX_PERMUTATIONS. Every permutation becomes a registrar
lookup during an enrolment sweep, so an uncapped set is an uncapped bill against
a service that allows twenty requests a second. Classes are emitted in descending
order of how often they appear in real squat registrations, so the cap truncates
the least likely tail first rather than an arbitrary slice.

Insertion of a neighbouring key is generated even though nobody types it more
often than they drop a character, because it is the inverse of omission. Without
it the neighbourhood is not closed under its own operations, and a caller that
can only ask "is this specific name enrolled" would miss the domain that dropped
one letter from theirs.
"""

from __future__ import annotations

from typing import Final

# A few hundred names is one sweep of a handful of batched registrar calls, and
# it covers every class below for any label short enough to print on an invoice.
MAX_PERMUTATIONS: Final = 400

# One edit after normalisation. Every permutation class is exactly one edit from
# its origin, so this admits all of them and nothing beyond them.
MAX_CONFUSABLE_EDITS: Final = 1

# One edit has to be a small enough share of the name to be a plausible slip. In
# a three letter label it is most of the name, and three letter labels differ
# from each other by one letter constantly.
CONFUSABLE_THRESHOLD: Final = 0.75

# The same label under a different suffix is confusable but not identical, and a
# reader who checks the suffix does catch it. It scores just below an exact match.
DIFFERENT_SUFFIX_FACTOR: Final = 0.95

# The suffixes a squatter reaches for first, cheapest and most familiar first.
TLD_SWAPS: Final[tuple[str, ...]] = (
    "com",
    "net",
    "org",
    "co",
    "io",
    "dev",
    "app",
    "info",
    "biz",
    "online",
    "site",
    "xyz",
    "shop",
    "live",
)

# Registry suffixes that occupy two labels, so the name being imitated is the
# third from the right. Not a public suffix list, and deliberately not: a list
# that ships in core would rot silently. These are the ones an issuer of
# invoices actually turns up under.
MULTI_LABEL_SUFFIXES: Final[frozenset[str]] = frozenset(
    {
        "co.uk",
        "org.uk",
        "ac.uk",
        "com.au",
        "net.au",
        "co.nz",
        "co.jp",
        "co.in",
        "co.za",
        "com.br",
        "com.mx",
        "com.sg",
    }
)

# Substitutions that survive a glance at printed paper. Both directions, because
# the forger picks whichever one their target does not use.
GLYPH_SWAPS: Final[tuple[tuple[str, str], ...]] = (
    ("rn", "m"),
    ("m", "rn"),
    ("cl", "d"),
    ("d", "cl"),
    ("i", "l"),
    ("l", "i"),
    ("i", "1"),
    ("1", "i"),
    ("l", "1"),
    ("1", "l"),
    ("o", "0"),
    ("0", "o"),
)

# Applied in this order, longest first, so cl reduces to d before l reduces to i.
_NORMALISATIONS: Final[tuple[tuple[str, str], ...]] = (
    ("rn", "m"),
    ("cl", "d"),
    ("1", "i"),
    ("l", "i"),
    ("0", "o"),
)

_KEYBOARD_ROWS: Final[tuple[str, ...]] = (
    "1234567890",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
)


def _build_adjacency() -> dict[str, tuple[str, ...]]:
    """Physical neighbours on a staggered QWERTY board.

    Each row sits half a key to the right of the one above it, so the keys above
    a given key are at the same index and the one after it, and the keys below
    are at the same index and the one before it.
    """
    adjacency: dict[str, tuple[str, ...]] = {}
    for row_number, row in enumerate(_KEYBOARD_ROWS):
        for column, key in enumerate(row):
            near: set[str] = set()
            if column > 0:
                near.add(row[column - 1])
            if column + 1 < len(row):
                near.add(row[column + 1])
            if row_number > 0:
                above = _KEYBOARD_ROWS[row_number - 1]
                near.update(above[index] for index in (column, column + 1) if index < len(above))
            if row_number + 1 < len(_KEYBOARD_ROWS):
                below = _KEYBOARD_ROWS[row_number + 1]
                near.update(
                    below[index] for index in (column - 1, column) if 0 <= index < len(below)
                )
            adjacency[key] = tuple(sorted(near))
    return adjacency


_ADJACENT: Final[dict[str, tuple[str, ...]]] = _build_adjacency()


def _split(domain: str) -> tuple[str, str]:
    """Separate the imitated label from the suffix it sits under.

    Subdomains are dropped. A mark is signed by a registrable name, and the label
    to the left of the suffix is the part a forger has to buy.
    """
    cleaned = domain.strip().casefold().strip(".")
    parts = [part for part in cleaned.split(".") if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    tail = ".".join(parts[-2:])
    if len(parts) >= 3 and tail in MULTI_LABEL_SUFFIXES:
        return parts[-3], tail
    return parts[-2], parts[-1]


def _join(label: str, suffix: str) -> str:
    return f"{label}.{suffix}" if suffix else label


def _normalise(label: str) -> str:
    text = label.casefold().replace("-", "")
    for source, target in _NORMALISATIONS:
        text = text.replace(source, target)
    return text


def _replace_nth(text: str, source: str, target: str, ordinal: int) -> str:
    position = -1
    for _ in range(ordinal + 1):
        position = text.find(source, position + 1)
        if position < 0:
            return text
    return f"{text[:position]}{target}{text[position + len(source) :]}"


def _homoglyph_variants(label: str) -> list[str]:
    variants: list[str] = []
    for source, target in GLYPH_SWAPS:
        occurrences = label.count(source)
        for ordinal in range(occurrences):
            variants.append(_replace_nth(label, source, target, ordinal))
        if occurrences > 1:
            variants.append(label.replace(source, target))
    return variants


def _hyphen_variants(label: str) -> list[str]:
    """Hyphens in and hyphens out.

    Where the word boundaries fall needs a dictionary this module refuses to
    carry, so every interior position is treated as a candidate boundary. The
    wrong guesses cost one registrar lookup each and the right one is in the set.
    """
    variants = [
        f"{label[:index]}-{label[index:]}"
        for index in range(1, len(label))
        if label[index - 1] != "-" and label[index] != "-"
    ]
    if "-" in label:
        variants.append(label.replace("-", ""))
        variants.extend(
            f"{label[:index]}{label[index + 1 :]}"
            for index, character in enumerate(label)
            if character == "-"
        )
    return variants


def _omissions(label: str) -> list[str]:
    if len(label) < 2:
        return []
    return [f"{label[:index]}{label[index + 1 :]}" for index in range(len(label))]


def _doublings(label: str) -> list[str]:
    return [f"{label[:index]}{label[index]}{label[index:]}" for index in range(len(label))]


def _substitutions(label: str) -> list[str]:
    return [
        f"{label[:index]}{key}{label[index + 1 :]}"
        for index, character in enumerate(label)
        for key in _ADJACENT.get(character, ())
    ]


def _insertions(label: str) -> list[str]:
    variants: list[str] = []
    for index in range(len(label) + 1):
        anchors: set[str] = set()
        if index > 0:
            anchors.add(label[index - 1])
        if index < len(label):
            anchors.add(label[index])
        for anchor in sorted(anchors):
            variants.extend(
                f"{label[:index]}{key}{label[index:]}" for key in _ADJACENT.get(anchor, ())
            )
    return variants


def permutations(domain: str) -> tuple[str, ...]:
    """Realistic confusable variants of a domain's second-level label.

    Deduplicated, deterministic, never containing the input, and never longer
    than MAX_PERMUTATIONS. An empty or suffix-only input yields nothing rather
    than raising, because a sweep over a malformed name is a no-op, not an error.
    """
    label, suffix = _split(domain)
    if not label:
        return ()

    candidates = [
        _join(variant, suffix)
        for variant in (*_homoglyph_variants(label), *_hyphen_variants(label))
    ]
    candidates.extend(_join(label, tld) for tld in TLD_SWAPS if tld != suffix)
    candidates.extend(
        _join(variant, suffix)
        for variant in (
            *_omissions(label),
            *_doublings(label),
            *_substitutions(label),
            *_insertions(label),
        )
    )

    seen = {_join(label, suffix), domain.strip().casefold()}
    chosen: list[str] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        chosen.append(candidate)
        if len(chosen) == MAX_PERMUTATIONS:
            break
    return tuple(chosen)


def _distance(left: str, right: str) -> int:
    """Optimal string alignment distance.

    Adjacent transposition counts as one edit rather than two, because a
    transposed pair is one slip of the fingers and reads as the original name.
    """
    if left == right:
        return 0
    if not left or not right:
        return max(len(left), len(right))

    previous = list(range(len(right) + 1))
    before_previous = previous[:]
    for row, left_character in enumerate(left, start=1):
        current = [row] + [0] * len(right)
        for column, right_character in enumerate(right, start=1):
            cost = 0 if left_character == right_character else 1
            current[column] = min(
                previous[column] + 1,
                current[column - 1] + 1,
                previous[column - 1] + cost,
            )
            if (
                row > 1
                and column > 1
                and left_character == right[column - 2]
                and left[row - 2] == right_character
            ):
                current[column] = min(current[column], before_previous[column - 2] + cost)
        before_previous, previous = previous, current
    return previous[-1]


def confusability(left: str, right: str) -> float:
    """How readily one domain passes for the other, from 0.0 to 1.0.

    1.0 means the two names are the same once presentation is stripped. The score
    is graded so a sweep can rank what it found; the yes or no answer that a
    check acts on is is_confusable.
    """
    left_label, left_suffix = _split(left)
    right_label, right_suffix = _split(right)
    first, second = _normalise(left_label), _normalise(right_label)
    if not first or not second:
        return 0.0

    span = max(len(first), len(second))
    score = 1.0 - _distance(first, second) / span
    if score <= 0.0:
        return 0.0
    if left_suffix != right_suffix:
        score *= DIFFERENT_SUFFIX_FACTOR
    return score


def is_confusable(left: str, right: str) -> bool:
    """Would a reader who knows one of these names accept the other as it?

    Two conditions, both required. The names must be within one edit once
    normalised, and that edit must be a small enough share of the name to be a
    slip rather than a different word.
    """
    first = _normalise(_split(left)[0])
    second = _normalise(_split(right)[0])
    if not first or not second:
        return False
    return (
        _distance(first, second) <= MAX_CONFUSABLE_EDITS
        and confusability(left, right) >= CONFUSABLE_THRESHOLD
    )
