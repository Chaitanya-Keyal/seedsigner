# Throwaway demo to exercise the l10n diff-comment rendering. DO NOT MERGE.
# Nothing imports this module; it exists only so extract_messages sees these
# strings as the PR "head".
from gettext import ngettext, pgettext

from seedsigner.helpers.l10n import mark_for_translation as _mft

_mft("Demo: unchanged label")
_mft("Demo: brand new label")
pgettext("toolbar", "Demo: new contextual label")
ngettext("Demo: new plural label", "Demo: new plural labels", 2)
# "Demo: turns plural" was singular in base; now it is a plural form -> changed.
ngettext("Demo: turns plural", "Demo: turn plural", 2)
