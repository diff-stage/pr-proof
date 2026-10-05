# Diff Stage recorder

The Diff Stage recorder records readable videos of Pest browser tests and posts them on pull requests. This repo is the public, MIT-licensed half: a Pest plugin plus two GitHub Actions. The hosted service lives in `~/code/pr-proof-app` (`diff-stage/pr-proof-app`, private, Laravel Cloud).

## How it fits together

- `src/Plugin.php` reads `--record-videos`, `--record-videos-only` and `--record-videos-pause`.
- `src/bootstrap.php` (Composer `autoload.files`) swaps four Pest Browser classes for the copies in `overrides/` before Pest loads them. They support `pestphp/pest-plugin-browser` v4.3.1 and v5.1.2 exactly. Browser 5 tracing is preserved.
- `select/action.yml` picks only test files explicitly listed in `Browser videos:` lines in the PR description. Changed browser tests are not added automatically.
- `publish/action.yml` compresses videos, uploads them to the service and keeps one PR comment up to date. `publish/review.jq` reads the `Browser review:` list from the PR description.
- `skills/diff-stage-evidence` is the published agent skill. Users copy it from `vendor/diff-stage/recorder`, so keep it to one self-contained `SKILL.md`.

## Working here

- Tutora (`TutoraUK/tutora`, draft PR #11124, worktree `~/code/tutorful/tutora-pr-videos`) is the first real user. Test plugin changes there before pushing.
- Several agent threads work on this repo. Stage files by name, never `git add -A`, and pull before committing.
- Run the `unslop` skill on README text and anything users will read.
- The service pins tag `v0.1.0` and commit `5892c51`. Never move or delete them. Publish still recognises the old `<!-- pr-proof -->` comment marker.
