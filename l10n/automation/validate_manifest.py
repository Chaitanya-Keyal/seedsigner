"""Validate a review manifest before the trusted job acts on it.

The manifest was produced by untrusted PR code, so the trusted follow-up job
validates it against the JSON Schema and checks two trust anchors that GitHub
sets authoritatively:

* ``--expect-repository`` must equal ``manifest.repository``
* ``--expect-head-sha`` (the triggering workflow_run head SHA) must equal
  ``manifest.pr.head_sha``

The PR-number<->head-SHA binding is completed in the workflow by fetching the
PR and confirming its head SHA matches too; this script covers the data layer.
"""

from __future__ import annotations

import argparse
import json
import sys


def validate(manifest_path: str, schema_path: str, expect_head_sha: str,
             expect_repository: str) -> list:
    import jsonschema

    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    with open(schema_path, encoding="utf-8") as fh:
        schema = json.load(fh)

    errors = []
    validator = jsonschema.Draft202012Validator(schema)
    # Sort on the stringified path: error paths mix str (object keys) and int
    # (array indices), which are not orderable against each other directly.
    for err in sorted(validator.iter_errors(manifest), key=lambda e: list(map(str, e.path))):
        errors.append(f"schema: {'/'.join(map(str, err.path)) or '<root>'}: {err.message}")

    head = manifest.get("pr", {}).get("head_sha")
    if head != expect_head_sha:
        errors.append(f"pr.head_sha {head!r} != triggering run head {expect_head_sha!r}")

    repo = manifest.get("repository")
    if repo != expect_repository:
        errors.append(f"repository {repo!r} != running repository {expect_repository!r}")

    return errors


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Validate an l10n review manifest.")
    p.add_argument("--manifest", required=True)
    p.add_argument("--schema", required=True)
    p.add_argument("--expect-head-sha", required=True)
    p.add_argument("--expect-repository", required=True)
    args = p.parse_args(argv)

    errors = validate(args.manifest, args.schema, args.expect_head_sha,
                       args.expect_repository)
    if errors:
        print("Manifest rejected:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("Manifest OK")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
