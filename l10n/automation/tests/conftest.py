"""Make the l10n automation modules importable when these tests run.

These tests are intentionally outside the project's configured `testpaths`
(["tests"]), so they are not collected by the main pytest run. Run them with:

    python -m pytest l10n/automation/tests
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
