# pr-proof plugin

pr-proof records readable videos of Pest browser tests and posts them on pull requests. This repo is the public, MIT-licensed half: a Pest plugin plus two GitHub Actions. The hosted service lives in `~/code/pr-proof-app` (private, Laravel Cloud).

## How it fits together

- `src/Plugin.php` reads `--record-videos`, `--record-videos-only` and `--record-videos-pause`.
- `src/bootstrap.php` (Composer `autoload.files`) swaps three Pest Browser classes for the copies in `overrides/` before Pest loads them. They support `pestphp/pest-plugin-browser` v4.3.1 and v5.1.2 exactly. Browser 5 tracing is preserved.
- `select/action.yml` picks test files from the PR diff and any `Browser videos:` line in the description.
- `publish/action.yml` compresses videos, uploads them to the service and keeps one PR comment up to date. `publish/review.jq` reads the `Browser review:` list from the PR description.
- `skills/pr-proof-evidence` is the published agent skill. Users copy it from `vendor/wardy484/pr-proof`, so keep it to one self-contained `SKILL.md`.

## Working here

- Tutora (`TutoraUK/tutora`, draft PR #11124, worktree `~/code/tutorful/tutora-pr-videos`) is the first real user. Test plugin changes there before pushing.
- Several agent threads work on this repo. Stage files by name, never `git add -A`, and pull before committing.
- Run the `unslop` skill on README text and anything users will read.
