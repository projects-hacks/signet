"""Wire formats and limits.

Values that appear in a published record or a printed mark are frozen here.
Changing one is a protocol change, not a refactor.
"""

from typing import Final

DNS_LABEL: Final = "_signet"
DNS_KEY_VERSION: Final = "SIGNET1"
DNS_KEY_ALGORITHM: Final = "ed25519"

MARK_VERSION: Final = "S1"
MARK_SEPARATOR: Final = "|"
FIELD_SEPARATOR: Final = ";"
PAIR_SEPARATOR: Final = "="

# A mark above this length pushes the QR past version 8, where a poor photograph
# of thermal paper stops decoding reliably. Encoding beyond it raises.
MAX_MARK_BYTES: Final = 300

FIELD_ISSUER: Final = "iss"
FIELD_TIMESTAMP: Final = "ts"
FIELD_DOCUMENT_ID: Final = "id"
FIELD_CLASS: Final = "cls"

REQUIRED_FIELDS: Final = frozenset({FIELD_ISSUER, FIELD_TIMESTAMP, FIELD_DOCUMENT_ID, FIELD_CLASS})
