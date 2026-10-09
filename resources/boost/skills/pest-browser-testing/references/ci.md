# Browser tests in CI

## What CI needs

When fixing a failing CI job, check the workflow against every item below, not just the one in the log. A CI log stops at the first failure, so each fix otherwise costs another red run.

- PHP with the `sockets` extension. The plugin requires it.
- `npm ci` with the project's pinned Playwright version, then the browser binaries and their system libraries: `npx playwright install --with-deps chromium`.
- Built assets: `npm run build`. `public/build` is usually gitignored, so a fresh checkout has none and every page fails.
- A hard time limit around the run. Some plugin failures hang instead of failing.
- A longer browser timeout than locally. Playwright start-up on a cold runner uses the same timeout, and a timed-out start-up fails every later test.
- Screenshots and traces of failed tests uploaded as artifacts.
- `.gitignore` entries for `tests/Browser/Screenshots` and `tests/Browser/Traces`.

Make the timeout configurable in `tests/Pest.php`:

```php
pest()->browser()->timeout((int) env('BROWSER_TIMEOUT', 5_000));
```

## GitHub Actions

Adapt the PHP version, database and env setup to match the project's existing test job.

```yaml
name: Browser tests

on:
  pull_request:
  push:
    branches: [main]

concurrency:
  group: browser-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  browser:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3]
    env:
      BROWSER_TIMEOUT: 15000
    steps:
      - uses: actions/checkout@v5

      - uses: shivammathur/setup-php@v2
        with:
          php-version: '8.4'
          extensions: sockets

      - uses: actions/setup-node@v4
        with:
          node-version: lts/*
          cache: npm

      - run: composer install --no-interaction --prefer-dist
      - run: npm ci

      - name: Read Playwright version
        id: playwright
        run: echo "version=$(npx playwright --version | awk '{print $2}')" >> "$GITHUB_OUTPUT"

      - uses: actions/cache@v4
        id: playwright-cache
        with:
          path: ~/.cache/ms-playwright
          key: playwright-${{ runner.os }}-${{ steps.playwright.outputs.version }}

      - run: npx playwright install --with-deps chromium
        if: steps.playwright-cache.outputs.cache-hit != 'true'
      - run: npx playwright install-deps chromium
        if: steps.playwright-cache.outputs.cache-hit == 'true'

      - run: cp .env.example .env && php artisan key:generate
      - run: npm run build

      - name: Run browser tests
        run: timeout 15m vendor/bin/pest tests/Browser --ci --parallel --shard=${{ matrix.shard }}/${{ strategy.job-total }} --trace

      - name: Upload failure evidence
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: browser-failures-${{ matrix.shard }}
          path: |
            tests/Browser/Screenshots
            tests/Browser/Traces
          if-no-files-found: ignore
```

Version notes:

- `--trace` needs plugin 5.1+. On 4.x and 5.0, drop it and rely on the failure screenshots.
- `--shard` exists since Pest 4.0. For shards balanced by run time (Pest 4.6+), run `--update-shards` locally and commit `tests/.pest/shards.json`.
- On GitHub Actions, `--trace` also lists the saved traces in the job summary.

Open a downloaded trace with `npx playwright show-trace <file>.zip`, or drop it on trace.playwright.dev.

Done when a pull request run is green on every shard, and a deliberately failing test uploads its screenshot (and trace on 5.1+).

## Self-hosted runners and long-lived containers

A cancelled job, or a Linux shell wrapper, can leave `playwright run-server` processes running after the run. They pile up and cause random timeouts in later runs. Clean up before and after:

```yaml
      - run: pkill -f '[p]laywright run-server' || true
      # … run the tests …
      - if: always()
        run: pkill -f '[p]laywright run-server' || true
```

Use a Debian or Ubuntu base image; Playwright's browsers don't run on Alpine.

## Screenshot comparisons

`assertScreenshotMatches()` compares against baselines in `tests/.pest/snapshots`. Before you rely on it in CI:

- Any pixel difference fails. The plugin's tolerance settings never let a mismatch pass.
- The plugin forces Arial for the screenshot. Ubuntu runners don't have Arial and substitute another font, so baselines made on a laptop never match CI.
- Pest 5.1.1+ fails in CI when a baseline is missing, instead of creating it.

To keep it deterministic, generate the baselines on CI itself. Add a manually triggered job that runs the screenshot tests with `--update-snapshots`, uploads `tests/.pest/snapshots` as an artifact, and commit what it produced. Re-run that job after intended visual changes.
