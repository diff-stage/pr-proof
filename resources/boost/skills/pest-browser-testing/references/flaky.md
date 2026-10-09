# Fixing a flaky or failing browser test

Work through the steps in order. Each ends on a check; finish it before moving on.

## 1. Find the first failure

Read the output from the top and take the **first** failing browser test. When start-up times out, every later test fails with a bare `Assertion error` and no detail; those are fallout from the first.

Done when you have one test name and its full failure message.

## 2. Rule out the environment

1. Versions match the table in `SKILL.md` (`composer show pestphp/pest-plugin-browser`, `npx playwright --version`).
2. Assets are built: `public/build/manifest.json` exists and is newer than your front-end changes.
3. No orphaned Playwright servers: `pgrep -af 'playwright run-server'` prints nothing while no tests are running. Kill leftovers with `pkill -f '[p]laywright run-server'`.
4. The run's summary lists the number of tests you expect. A crash can exit with code 0 and no output.

Done when all four are checked and any problem is fixed.

## 3. Match the symptom

| Symptom | Cause | Fix |
|---|---|---|
| Text typed twice, form submitted twice, a toggle flips back, or the trace shows repeated 1000ms attempts | A retry ran the action again after it had already worked (see Retries in `api-traps.md`) | Make the request it triggers faster (fake queues, mail, APIs). Move side effects to an action that runs once on your version |
| The run hangs with no output while processes sit idle | Playwright newer than the version table in `SKILL.md` allows: a selector matching nothing waits forever | Match the version table, and keep the CI hard timeout |
| First test times out, every later test fails with `Assertion error` | Playwright start-up took longer than the timeout and the connection can't recover | Raise the timeout in CI (see `ci.md`) and fix the first failure only |
| Every test passes, then the process never exits | Browser tests outside `tests/`, an orphaned Playwright server, or piped output | Move tests to `tests/Browser`, run step 2.3, add a hard timeout |
| Random timeouts in different tests, worse as the day goes on | Orphaned Playwright servers eating memory on a long-lived runner | Kill orphans before and after each run (see `ci.md`) |
| Blank white page or `SyntaxError` at column 8193 | Assets missing, or truncated by plugin 4.x/5.0.0 | `npm run build`; upgrade to 5.0.1+ |
| Uploaded file never reaches the app, or a form posted with `FormData` fails validation with "field is required" | The 4.x and 5.0 test server drops every field of a multipart request | Upgrade to 5.1 (see Actions in `api-traps.md`) |
| Screenshot comparison fails only in CI | Fonts differ between machines | Generate baselines in the CI container (see `ci.md`) |
| Passes alone, fails in the full suite | State leaking from an earlier test | Go to step 4 and run neighbours together |
| Passes serially, fails under `--parallel` | Two tests sharing data or files | Unique values per test; per-test storage paths |

Done when you've matched a row, or confirmed none fits.

## 4. Reproduce it locally

Run in this order and stop at the first red:

1. The test alone.
2. The test repeated: a temporary `->repeat(20)` on the test. The `--repeat` flag runs browser tests only once.
3. The whole file, then the whole browser suite.
4. The suite with `--parallel`.
5. With CI's timeout and environment variables.

Done when it goes red locally. If it never does, list what differs from CI (core count, timeout, fonts, host, env file); those differences are your suspects.

## 5. Look at the evidence

- Failure message: includes console logs, JavaScript errors and the last exception the app threw.
- Screenshot: a failed assertion saves the page to `tests/Browser/Screenshots`.
- Trace (plugin 5.1+): rerun with `--trace`. Locally the first failed trace opens by itself; open others with `npx playwright show-trace tests/Browser/Traces/<test>.zip`. Each browser call shows as a step linked to its line in the test, with DOM snapshots before and after.
- Watch it: `--headed` or `--debug` locally.

Done when you can say what the page showed at the moment the test failed.

## 6. Name the cause

Classify it as one of:

- **Timing**: the test asserted before the app finished.
- **Isolation**: tests share data, files or cache.
- **Order**: an earlier test leaves state behind.
- **Environment**: fonts, assets, host, versions or resources differ.
- **Real bug**: the app genuinely fails sometimes (a race in your JavaScript, a missing loading state). Fix the app, not the test.

Done when the cause fits one class and explains every red run you saw.

## 7. Fix the cause

- Timing: assert the state the test was waiting for.
- Isolation: give each test its own data and storage.
- Order: reset the leaking state in the test that creates it.
- Environment: make CI and local match (see `ci.md`).

Fix the cause you named in step 6. Use `--retry`, longer timeouts or sleeps only to diagnose; they make the failure rarer and leave the cause in place.

Done when the step 3 proof in `SKILL.md` passes (`->repeat()` plus `--parallel`) and the commit message states the cause in one sentence.
