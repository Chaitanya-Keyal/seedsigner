"""Render the advisory PR comment markdown from a validated review manifest.

This runs in the trusted follow-up job from default-branch code, but the
manifest it consumes was produced by untrusted PR code. The source strings are
shown inside a ``diff`` fenced code block so GitHub colours them red/green, and
every entry line is prefixed with ``+``/``-`` with newlines flattened, so no
attacker-controlled text can start a line and break out of the code fence or
inject markup. (Fenced code is rendered literally, so HTML in a msgid shows as
text rather than executing.)

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


def _clean(text: str) -> str:
    """Flatten to a single line and bound the length for safe fenced display."""
    flat = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
    if len(flat) > _MAX_MSGID_CHARS:
        flat = flat[:_MAX_MSGID_CHARS] + "..."
    return flat


def _annotations(entry: dict, *, include_plural: bool) -> List[str]:
    annos: List[str] = []
    ctx = entry.get("msgctxt")
    if ctx:
        annos.append(f"ctx: {_clean(str(ctx))}")
    if include_plural and entry.get("plural"):
        annos.append("plural")
    return annos


def _row(prefix: str, msgid: str, annos: List[str]) -> str:
    tail = f"    [{'; '.join(annos)}]" if annos else ""
    return f"{prefix} {_clean(msgid)}{tail}"


def _diff_block(impact: dict) -> List[str]:
    ic = impact["counts"]
    lines: List[str] = ["```diff"]

    for e in impact["added"]:
        lines.append(_row("+", e.get("msgid", ""), _annotations(e, include_plural=True)))
    if ic["added"] > len(impact["added"]):
        lines.append(f"  ...and {ic['added'] - len(impact['added'])} more added (count above)")

    for e in impact["removed"]:
        lines.append(_row("-", e.get("msgid", ""), _annotations(e, include_plural=True)))
    if ic["removed"] > len(impact["removed"]):
        lines.append(f"  ...and {ic['removed'] - len(impact['removed'])} more removed (count above)")

    for e in impact["changed"]:
        now_plural = bool(e.get("plural"))
        ctx = _annotations(e, include_plural=False)
        lines.append(_row("-", e.get("msgid", ""), ctx + [f"was {'singular' if now_plural else 'plural'} form"]))
        lines.append(_row("+", e.get("msgid", ""), ctx + [f"now {'plural' if now_plural else 'singular'} form"]))
    if ic["changed"] > len(impact["changed"]):
        lines.append(f"  ...and {ic['changed'] - len(impact['changed'])} more changed (count above)")

    lines.append("```")
    return lines


def render(manifest: dict) -> str:
    impact = manifest["source_strings"]
    ic = impact["counts"]
    base_ref = (manifest["pr"].get("base_ref") or "base").replace("`", "")

    lines: List[str] = [COMMENT_MARKER, "## Localization: source-string impact", ""]

    if not manifest.get("regen_ok", True):
        lines += ["> **Warning:** Could not fully regenerate `messages.pot` from "
                  "this PR's source; the impact below may be incomplete.", ""]

    if ic["added"] == ic["removed"] == ic["changed"] == 0:
        lines += [f"This PR makes no changes to the translatable source strings "
                  f"(compared with `{base_ref}`)."]
    else:
        lines += [
            f"This PR changes the translatable source strings, compared with "
            f"`{base_ref}` ({ic['total_head']} strings total):",
            "",
            "| Added | Removed | Changed |",
            "| ----: | ------: | ------: |",
            f"| {ic['added']} | {ic['removed']} | {ic['changed']} |",
            "",
        ]
        lines += _diff_block(impact)

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
