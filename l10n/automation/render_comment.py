"""Render the advisory PR comment markdown from a validated review manifest.

This runs in the trusted follow-up job from default-branch code, but the
manifest it consumes was produced by untrusted PR code. Every string that
originates from the manifest (source-string text) is HTML-escaped and wrapped
so it cannot break out of its context or inject markup into the comment.

The comment is informational: it shows which translatable source strings the PR
changes. The canonical messages.pot is regenerated automatically after merge, so
the comment never asks the author to update or commit the catalog.
"""

from __future__ import annotations

import argparse
import html
import json
from typing import List

COMMENT_MARKER = "<!-- l10n-automation:comment=messages-pot -->"

# Keep individual rendered strings bounded regardless of source length.
_MAX_MSGID_CHARS = 200


def _code(text: str) -> str:
    """Escape arbitrary source text for safe inline display."""
    flattened = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
    if len(flattened) > _MAX_MSGID_CHARS:
        flattened = flattened[:_MAX_MSGID_CHARS] + "..."
    return "<code>" + html.escape(flattened, quote=True) + "</code>"


def _format_entry(entry: dict) -> str:
    line = _code(entry.get("msgid", ""))
    ctx = entry.get("msgctxt")
    if ctx:
        line += f" <sub>ctx: {html.escape(str(ctx))}</sub>"
    if entry.get("plural"):
        line += " <sub>(plural)</sub>"
    return line


def _entry_list(title: str, entries: List[dict], total: int, truncated: bool) -> List[str]:
    if total == 0:
        return []
    lines = [f"<details><summary>{html.escape(title)} ({total})</summary>", ""]
    lines += [f"- {_format_entry(e)}" for e in entries]
    if truncated or len(entries) < total:
        lines.append(f"- _and {total - len(entries)} more (see counts above)_")
    lines += ["", "</details>"]
    return lines


def render(manifest: dict) -> str:
    impact = manifest["source_strings"]
    ic = impact["counts"]
    base_ref = manifest["pr"].get("base_ref", "base")

    lines: List[str] = [COMMENT_MARKER, "## Localization: source-string impact", ""]

    if not manifest.get("regen_ok", True):
        lines += ["> **Warning:** Could not fully regenerate `messages.pot` from "
                  "this PR's source; the impact below may be incomplete.", ""]

    if ic["added"] == ic["removed"] == ic["changed"] == 0:
        lines += [f"This PR makes no changes to the translatable source strings "
                  f"(compared with `{html.escape(base_ref)}`)."]
    else:
        lines += [
            f"This PR changes the translatable source strings extracted from the "
            f"code, compared with `{html.escape(base_ref)}`:",
            "",
            "| Added | Removed | Changed | Total strings |",
            "| ----: | ------: | ------: | ------------: |",
            f"| {ic['added']} | {ic['removed']} | {ic['changed']} | {ic['total_head']} |",
            "",
        ]
        lines += _entry_list("Added", impact["added"], ic["added"], impact["truncated"])
        lines += _entry_list("Removed", impact["removed"], ic["removed"], impact["truncated"])
        lines += _entry_list("Changed (plural form)", impact["changed"], ic["changed"], impact["truncated"])

    for note in manifest.get("notes", []):
        lines += ["", f"> **Note:** {html.escape(note)}"]

    lines += [
        "",
        "<sub>Advisory only; this check never blocks the PR. The canonical "
        "`l10n/messages.pot` is regenerated automatically after merge, so no "
        "manual update is needed.</sub>",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Render advisory comment from a manifest.")
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", default="-")
    args = p.parse_args(argv)

    with open(args.manifest, encoding="utf-8") as fh:
        manifest = json.load(fh)

    body = render(manifest)
    if args.out == "-":
        print(body)
    else:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(body)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
