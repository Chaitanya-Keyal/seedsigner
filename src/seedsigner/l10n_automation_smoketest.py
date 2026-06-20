# Throwaway smoke-test for the l10n source-string automation. DO NOT MERGE.
# Nothing imports this module; it exists only so `extract_messages` finds one
# new source string, which the advisory PR comment should report as +1 added.
from seedsigner.helpers.l10n import mark_for_translation as _mft

L10N_AUTOMATION_SMOKE_TEST = _mft("SeedSigner l10n automation smoke-test string")
