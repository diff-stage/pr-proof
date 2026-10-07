# Diff Stage recorder

The Diff Stage recorder records readable videos of Pest browser tests and posts them on pull requests. This repo is the public, MIT-licensed half: a Pest plugin, a scenario runner and GitHub Actions. The hosted service lives in `~/code/pr-proof-app` (`diff-stage/pr-proof-app`, private, Laravel Cloud).

## How it fits together

- `src/Plugin.php` reads `--record-videos`, `--record-videos-only` and `--record-videos-pause`.
- `src/bootstrap.php` (Composer `autoload.files`) swaps four Pest Browser classes for the copies in `overrides/` before Pest loads them. They support `pestphp/pest-plugin-browser` v4.3.1 and v5.1.2 exactly. Browser 5 tracing is preserved.
- `select/action.yml` reads explicit `Browser videos:` selections from the PR description. Pass its JSON `selection` output to `bin/diff-stage-record` for individual scenarios. File-only selections run the whole file.
- `preflight/action.yml` checks repository publication access in a trusted job before app preparation, without application checkout.
- `publish/action.yml` compresses videos, uploads them to the service and keeps one PR comment up to date. `publish/review.jq` reads the `Browser review:` list from the PR description.
- `skills/diff-stage-evidence` is the published agent skill. Users copy it from `vendor/diff-stage/recorder`, so keep it to one self-contained `SKILL.md`.

## Working here

- Tutora (`TutoraUK/tutora`, draft PR #11124, worktree `~/code/tutorful/tutora-pr-videos`) is the first real user. Test plugin changes there before pushing.
- Several agent threads work on this repo. Stage files by name, never `git add -A`, and pull before committing.
- Run the `unslop` skill on README text and anything users will read.
- Preserve released tags and commits used by customers. Check the service manifest and workflows for its current pins. Publish still recognises the old `<!-- pr-proof -->` comment marker.
