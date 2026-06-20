# SeedSigner localization automation

Automates the source-string half of the localization workflow: keeping
`l10n/messages.pot` in sync with the code and getting it to Transifex without
manual coordination. It advises authors on PRs, then after merge proposes the
regenerated catalog as a rolling PR and mirrors it to the translations repo's
Transifex source.

This covers the `messages.pot` (source-string) stream only. Screenshot review
and `.po` round-trip are separate streams handled elsewhere.

## Components

| File | Role |
| --- | --- |
| `schema/review-manifest.schema.json` | Contract for the data passed from the untrusted diff job to the trusted comment job. |
| `pot_diff.py` | Structured, translator-meaningful diff between two catalogs; builds the review manifest. |
| `render_comment.py` | Renders the advisory comment markdown from a validated manifest (escapes all untrusted text). |
| `validate_manifest.py` | Validates a manifest against the schema and trust anchors before the trusted job acts. |
| `pot_sync_helper.py` | Decides whether a regeneration is a meaningful change (ignores header and location churn). |
| `config.yml` | Reference for naming conventions and the repo variables and secrets. |

Workflows in `.github/workflows/`:

| Workflow | Trigger | Privilege |
| --- | --- | --- |
| `l10n-pot-diff.yml` | `pull_request` | Read-only, no secrets. Extracts the catalog from the base and PR-head source, diffs them, uploads a manifest artifact. |
| `l10n-pot-comment.yml` | `workflow_run` (after the diff) | Trusted, write. Runs default-branch code, validates the manifest, maintains one advisory comment. |
| `l10n-pot-sync.yml` | `push` to `dev` | Bot App tokens. Regenerates, opens or updates the rolling PR from the bot fork, mirrors source to the translations bot fork. |

## Why two workflows for the advisory comment

Regenerating `messages.pot` means running the PR's own `setup.py` and source,
which is untrusted on fork PRs. So the work is split into a read-only producer
and a trusted consumer:

1. `l10n-pot-diff.yml` runs in the PR context with a read-only token and no
   secrets. Even fully malicious PR code can do nothing but produce a manifest
   artifact.
2. `l10n-pot-comment.yml` runs from default-branch code with write access. It
   never executes PR code, and treats the manifest as untrusted data:
   - validates it against `review-manifest.schema.json`;
   - confirms `manifest.repository` is this repo and `manifest.pr.head_sha`
     equals the triggering run's head SHA;
   - fetches the PR and confirms its authoritative head SHA matches the run head
     SHA before commenting, which binds the PR number to the commit so a PR
     cannot target another PR's thread;
   - re-renders the comment from validated fields, HTML-escaping every source
     string.

## How the automation stays idempotent

Reruns never create duplicates, because each artifact is located the same way
every time (see `config.yml`):

- Rolling branch in the bot fork: `automation/messages-pot`, force-pushed so it
  always sits on the latest default branch.
- Rolling PR into the main repo: located with a native GitHub query for an open
  PR whose head is `<bot>:automation/messages-pot` and whose base is the default
  branch. It is updated in place by force-pushing the branch; no marker is
  involved.
- Advisory comment: one per PR. GitHub has no native "find my comment" query, so
  the bot finds its previous comment by a hidden marker
  (`<!-- l10n-automation:comment=messages-pot -->`) and by the comment being
  authored by a bot, then edits that comment instead of posting a new one.
- The sync acts only when source strings actually change; pure
  `POT-Creation-Date` and source-location churn is ignored.

## Credentials: a GitHub App

The bot authenticates as a GitHub App (no long-lived PATs): the workflow mints a
short-lived, least-privilege installation token at runtime. There are two
logical roles:

- PR role: `pull-requests: write` on the main repo; opens the rolling PR.
- Fork role: `contents: write` on the bot forks; pushes the rolling branch and
  mirrors the `.pot`.

These cannot share one installation because no upstream repo may ever be granted
`contents: write`; branch mutation happens only in bot forks. So production uses
two separate Apps. For testing you can collapse them into one (below).

### Testing setup (recommended): one App

Since you control both the upstream fork and the bot account, use a single App:

1. GitHub: Settings, Developer settings, GitHub Apps, New GitHub App.
   - Permissions: `Contents: Read & write`, `Workflows: Read & write`,
     `Pull requests: Read & write`, `Metadata: Read`. Webhook: uncheck Active.
   - `Workflows: Read & write` is required because the rolling branch pushed to
     the bot fork is based on the upstream default branch, which contains
     `.github/workflows/` files; an App token cannot push commits that touch
     workflow files without it. It is granted only on the bot's own forks.
2. Generate a private key (downloads a `.pem`) and note the **Client ID** (shown
   on the app's General page; the legacy numeric App ID is deprecated).
3. Install it on both:
   - `Chaitanya-Keyal/seedsigner` (the test upstream), and
   - `okaybro-bot`, with access to its `seedsigner` and `seedsigner-translations`
     forks.
4. Put the same Client ID and key in all four secrets below.

The workflow still down-scopes each minted token (the PR token to
`pull-requests`, the fork token to `contents`), so behaviour matches production.
The only relaxation is that the App is installable with `contents:write` on the
main fork.

### Production setup: two Apps

Create two Apps so the upstream repo never carries `contents:write`:

| App | Install on | Repository permissions |
| --- | --- | --- |
| PR App | the main repo (`SeedSigner/seedsigner`) | `Pull requests: R/W`, `Metadata: R` |
| Fork App | the bot account's `seedsigner` and `seedsigner-translations` forks | `Contents: R/W`, `Workflows: R/W`, `Metadata: R` |

Fill the `L10N_PR_*` secrets from the PR App and the `L10N_FORK_*` secrets from
the Fork App.

### Secrets and variables (on the main repo)

Settings, Secrets and variables, Actions. In testing these live on
`Chaitanya-Keyal/seedsigner`.

Secrets:

| Secret | Testing value | Production value |
| --- | --- | --- |
| `L10N_PR_CLIENT_ID` | the one App's Client ID | PR App's Client ID |
| `L10N_PR_PRIVATE_KEY` | the one App's `.pem` | PR App's `.pem` |
| `L10N_FORK_CLIENT_ID` | the one App's Client ID | Fork App's Client ID |
| `L10N_FORK_PRIVATE_KEY` | the one App's `.pem` | Fork App's `.pem` |

Variables:

| Variable | Testing value | Notes |
| --- | --- | --- |
| `L10N_BOT_FORK` | `okaybro-bot/seedsigner` | Enables the sync job. Empty means no-op. |
| `L10N_TRANSLATIONS_BOT_FORK` | `okaybro-bot/seedsigner-translations` | Empty means the mirror step is skipped. |
| `L10N_TRANSLATIONS_REPO` | `Chaitanya-Keyal/seedsigner-translations` | Upstream is `SeedSigner/...` in production. |
| `L10N_TRANSLATIONS_BRANCH` | `dev` | Branch Transifex reads source from. |
| `L10N_TRANSLATIONS_POT_PATH` | `l10n/messages.pot` | Source path in the translations repo. |

## Testing topology (external contributor)

You cannot touch `SeedSigner/*` or the official Transifex, so stand everything up
under your own accounts, with your fork playing upstream:

| Production | Test stand-in | Owner |
| --- | --- | --- |
| `SeedSigner/seedsigner` | `Chaitanya-Keyal/seedsigner` | you |
| `SeedSigner/seedsigner-translations` | `Chaitanya-Keyal/seedsigner-translations` | you |
| bot fork of main | `okaybro-bot/seedsigner` (fork of your fork) | `okaybro-bot` |
| bot fork of translations | `okaybro-bot/seedsigner-translations` | `okaybro-bot` |

- The bot forks must be real GitHub forks (same fork network) so the rolling
  cross-fork PR is allowed.
- Set the secrets and variables above on `Chaitanya-Keyal/seedsigner`.
- Transifex is optional for this phase: the deliverable ends at mirroring the
  `.pot` into the translations bot fork. To verify end-to-end, connect a free
  Transifex open-source project to that fork in direct-commit mode.

## Running the tests

These tests live outside the project's configured `testpaths` (`["tests"]`), so
the main suite does not pick them up. Run them explicitly:

```bash
python -m pytest l10n/automation/tests -q
```

These tests need `Babel`, pinned in `l10n/requirements-l10n.txt` (the message
extraction requirements, which the diff and sync workflows install):

```bash
python -m pip install -r l10n/requirements-l10n.txt
```

`validate_manifest.py` additionally needs `jsonschema`. It is not an extraction
dependency, so it lives only in the comment workflow (pinned inline) rather than
in that file.

## Local dry-run of the diff

Diff the catalog extracted from your working tree against the catalog extracted
from `HEAD` (i.e. the impact of your uncommitted changes):

```bash
python setup.py extract_messages -o /tmp/head.pot
git stash --include-untracked
python setup.py extract_messages -o /tmp/base.pot
git stash pop
python l10n/automation/pot_diff.py \
  --base /tmp/base.pot --head /tmp/head.pot \
  --repository SeedSigner/seedsigner --pr-number 0 \
  --head-sha "$(git rev-parse HEAD)" --base-ref HEAD --out /tmp/manifest.json
python l10n/automation/render_comment.py --manifest /tmp/manifest.json
```
