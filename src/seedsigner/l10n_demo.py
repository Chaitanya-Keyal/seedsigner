# Throwaway demo to exercise the l10n diff-comment rendering. DO NOT MERGE.
# Nothing imports this module; it exists only so extract_messages sees these
# strings as the PR "base".
from seedsigner.helpers.l10n import mark_for_translation as _mft

_mft("Demo: unchanged label")
_mft("Demo: removed label one")
_mft("Demo: removed label two")
_mft("Demo: turns plural")
