# API traps

The public API is the same in plugin 4.3 and 5.1. The one addition in 5.1 is `pest()->browser()->trace()` and the `--trace` flag. This file lists what the source doesn't make obvious.

## Methods that look real

| Written by agents and blogs | Reality | Use instead |
|---|---|---|
| `waitFor('#modal')`, `waitForLocation()`, `pause()` | Don't exist | `assertVisible('#modal')`, `assertPathIs()` |
| `browser()->visit()` | `browser()` only exists as `pest()->browser()` config | `visit('/path')` |
| `$this->visit()` outside `tests/Browser` | Exists, but the test isn't detected as a browser test: detection looks for a plain `visit(` call | `visit('/path')`, or move the file to `tests/Browser` |
| `->on()->tablet()`, `->firefox()` per visit | Don't exist | `->on()->iPadPro()`; `--browser firefox` for the run |
| `click('#x', options: [...])` | `click()` takes one string | `click('#x')` |
| `waitForText('Saved')` | Deprecated alias of `assertSee` | `assertSee('Saved')` |
| `wait(2)`, `pressAndWaitFor('Save', 2)` | Fixed sleeps | Assert the state you are waiting for |
| `wait()` with no argument | Blocks until someone presses a key: hangs CI | Assert the state you are waiting for |
| `waitForEvent('networkidle')` | Builds a request it never sends: a no-op | Assert the content that loads |

## Selectors

- A bare tag name is treated as text, not CSS. `attribute('img', 'alt')` looks for an element with id, name or text `img`. Use `attribute('img[src$="logo.svg"]', 'alt')`.
- A field name ending in `[]` (`tags[]`) stays a name, not CSS.
- `click()` and other actions match text exactly and case-sensitively. `assertSee()` matches a case-insensitive substring among visible elements.
- `assertCount()` counts at most 100 elements.

## Navigation and URLs

- `assertUrlIs()` compares the whole URL including scheme, host and the random port, so `assertUrlIs('/login')` fails. Use `assertPathIs('/login')`.
- A `visit()` argument without a leading `/` becomes `https://…`: `visit('dashboard')` requests `https://dashboard`.
- `navigate()` keeps the current browser context; each `visit()` opens a fresh one with new cookies and storage.
- On 4.x and 5.0, `withHost()` (subdomain apps) only applies to the first request. Redirects and Inertia/Livewire follow-up requests can lose it. Fixed in 5.1.

## Retries

Most calls run inside a retry loop. Each attempt gets 1s; the last attempt gets the full timeout. If an attempt times out after the browser already acted, the action runs again: text typed twice, a form submitted twice, a toggle flipped back.

| Version | Retried | Run once |
|---|---|---|
| 4.x | Everything except the two on the right | `assertScreenshotMatches`, `assertNoAccessibilityIssues` |
| 5.0 | Everything except the three on the right | The two above, `typeSlowly` |
| 5.1+ | `submit`, `navigate`, `refresh`, `back`, `forward`, `script`, `fill`, `type`, `select`, `check`, `uncheck`, `radio`, `attach`, `hover`, `clear`, `withKeyDown` (re-runs its callback), and assertions | The three above, plus `click`, `rightClick`, `press`, `pressAndWaitFor`, `keys`, `drag`, `append` |

- Put side effects behind actions that run once on your version, and keep their requests fast.
- App code runs on the same event loop as the test, so `sleep()` in the app stalls the browser too.
- A timeout of 1000ms or less turns retries off entirely, including for assertions.

## Actions

- `type()` and `fill()` set the value in one step, like a paste. Use `typeSlowly()` only for behaviour that reacts to individual keystrokes (autocomplete, input masks).
- `keys()` passes Playwright key names: `keys('#search', 'Enter')`, `keys('#editor', ['Control+a', 'Backspace'])`.
- The 4.x and 5.0 test server only parses url-encoded and JSON bodies. A multipart request (`fetch` with `FormData`, a form with `enctype="multipart/form-data"`, Inertia `forceFormData`) reaches the app with **no fields at all**, files included, so validation fails with "field is required". Upgrade to 5.1, or send the body as `URLSearchParams` or JSON when no file is involved.

## Devices and context options

- Set the device once, as part of the `visit()` chain: `visit('/')->on()->mobile()`. Calling `on()` again later opens a new browser context and loses state.
- When the same option is set twice before the page opens, the first setting wins.
- Defaults: locale `en-US`, timezone `UTC`. Change them with `withLocale()`, `withTimezone()` or a `from()` city such as `from()->london()`.

## Page health assertions

- `assertNoJavaScriptErrors()` only sees errors thrown on the current page. It misses `console.error`, rejected promises, failed resource loads, iframes, and errors from pages you have already left.
- `assertNoConsoleLogs()` only sees `console.log`.
- `assertNoSmoke()` is both of the above, with the same gaps.

## Debug helpers

- Any `debug(` in a test closure makes that test `only()` and switches the **whole run** to headed mode. Left in, it breaks CI runners that have no display.
- `tinker()` opens an interactive shell and `--debug` pauses for a key press. Both are for local sessions only.
- `--debug`, `--headed` and `--diff` throw when combined with `--parallel`.
