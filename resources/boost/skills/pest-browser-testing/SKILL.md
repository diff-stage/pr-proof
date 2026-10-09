---
name: pest-browser-testing
description: Pest browser tests (pest-plugin-browser, `visit()`, files in `tests/Browser`). Use whenever you write, edit, review or debug one, check a page works in a real browser, fix a flaky or CI-only browser failure, or change a CI workflow that runs them (Playwright install, GitHub Actions).
license: MIT
metadata:
  author: diff-stage
  tags: laravel,php,pest,testing,browser
---

# Pest browser testing

A permanent browser test runs on every push for years. Aim for **deterministic**: green on every run, red only when the feature breaks.

Your testing guidelines (e.g. Boost's `testing-best-practices`) decide whether a behaviour deserves a browser test. This skill covers writing, reviewing and fixing the permanent test.

For a quick one-off "does this work?" check, use `pest --agent` if the project has it (`pestphp/pest-plugin-agent`). Otherwise write a throwaway test in `tests/Browser`, run it with `vendor/bin/pest`, report what it showed, and delete it. Don't drive Playwright by hand: the plugin already boots the app with its database, fakes and assets.

## 1. Read the setup

1. Read the existing browser CI first, including its Docker image and services. Run `composer show pestphp/pest-plugin-browser` and `npx --no-install playwright --version` in that environment, then find your row. Keep the Playwright version the tests already pass with. The versions below are setup and debugging notes, not a reason to change a green project. If Diff Stage is installed, check which Browser versions the recorder supports before changing the plugin. Do not edit bundled skills to invent a required pairing.

   | Plugin | Playwright notes | Plan around |
   |---|---|---|
   | 4.x, 5.0.0 | `1.61.1` is a tested version | Newer Playwright makes a missing selector hang. No `--trace`. |
   | 5.0.1 – 5.0.x | 1.62.1+ | Older click handling. No `--trace`. |
   | 5.1+ | 1.62.1+ (1.63+ from 5.1.1) | Clicks run once with the full timeout. `--trace` available. |

   On anything below 5.1, clicks also retry in 1s attempts: see [references/api-traps.md](references/api-traps.md).

2. Read `tests/Pest.php` and two existing browser tests. Note the setup helpers, viewport, timeout and fakes they use.

Done when you know your row and can name the conventions you'll reuse (or confirm there are none).

## 2. Write the test

### Shape

- **One thing per test.** One user goal, named as the outcome: `it('pays for an order with a saved card')`. Browser setup is expensive, so assert heavily along that one journey instead of splitting it into thin tests.
- **Arrange in PHP.** Factories for data, `actingAs($user)` before `visit()`, shared helpers for repeated setup.
- **Fake at the boundary.** The app server runs inside the test process, so `Http::fake()`, `Queue::fake()`, `Mail::fake()`, `Notification::fake()`, `travelTo()` and `RefreshDatabase` all apply to browser requests. Add `Http::preventStrayRequests()` so a missing fake fails loudly. The browser's JavaScript clock stays on real time.
- **Act like the user.** Click visible text, fill fields by name.
- **Assert each transition, UI first.** After an action, assert what the user now sees (`assertPathIs`, `assertSee`), then check the database and side effects in PHP. The UI assertion waits for the request to finish; a database check reads immediately.
- **Check every side effect.** Read the controller or action behind the journey and list what it does. Assert each item in PHP after the last UI assertion:
  - every record created or changed, with its key values (`expect($order->total_pence)->toBe(2160)`), not just that one exists;
  - every email, notification and queued job (`Mail::assertSent(OrderPlaced::class)`);
  - every outgoing request with its payload (`Http::assertSent(fn ($request) => $request['amount'] === 2160)`);
  - everything cleared or removed (basket emptied, session key forgotten).

  A test that checks only some of these stays green when the rest break.
- **Assert what the user sees**: text, path, field values, enabled and disabled state. Framework state, CSS classes and pixel sizes change without the feature changing.
- **Desktop by default.** Add a mobile case only where layout or interaction differs.
- **Smoke check each page.** Call `assertNoJavaScriptErrors()` before navigating away. It only catches thrown errors, so the visible assertions carry the proof.

```php
it('pays for an order with a saved card', function () {
    Http::preventStrayRequests();
    Http::fake(['api.stripe.com/*' => Http::response(['status' => 'succeeded'])]);
    $user = User::factory()->withSavedCard()->create();
    $order = Order::factory()->for($user)->pending()->create();

    $this->actingAs($user);

    visit(route('orders.show', $order, absolute: false))
        ->assertSee('Total £24.00')
        ->assertNoJavaScriptErrors()
        ->click('Pay with card ending 4242')
        ->assertPathIs("/orders/{$order->id}/receipt")
        ->assertSee('Payment received')
        ->assertNoJavaScriptErrors();

    expect($order->fresh()->status)->toBe(OrderStatus::Paid);
    Http::assertSentCount(1);
});
```

### Selectors

The plugin resolves a string in this order:

1. Starts with `.`, contains `.` followed by a letter, or contains `# [ ] > + ~ : * | ^ , = ( )`: a CSS selector.
2. Starts with `@`: `[data-testid="…"], [data-test="…"]`.
3. Anything else: the first element whose `id`, then `name`, then exact case-sensitive text matches. The first match wins, even a hidden one.

Choose in this order:

- Visible text for buttons and links: `click('Place order')`.
- Field `name` for inputs: `fill('email', 'ada@example.test')`.
- `@testid` when the text repeats on the page, would parse as CSS (`Next: Pay`, `example.com`), or is copy that changes often.
- `assertSeeIn('#basket', 'Total £24.00')` to scope text that appears in several places. The text must match exactly one element inside the scope, so "Total" fails when the basket also shows "Subtotal".

Never select by styling classes (`.bg-zinc-900`, `.btn-primary`), Tailwind utilities or position (`:nth-child`, `:first`). They change with every redesign while the feature stays the same. When text and name won't work, add a `data-testid` to the view and use `@testid`.

Don't hard-code database IDs in paths (`/orders/1`). Assert the shape with `assertPathBeginsWith('/orders/')`, then load the record in PHP and check it.

Confirm every method in `vendor/pestphp/pest-plugin-browser/src/Api` before you use it. Several popular "methods" don't exist or silently do nothing: see [references/api-traps.md](references/api-traps.md).

### Waiting

Assertions are the waits. Assertions retry until the timeout (default 5s, set with `pest()->browser()->timeout()` in `tests/Pest.php`), so wait by asserting the state you expect: `->click('Save')->assertSee('Saved')`.

Hard guardrail: never call these. A test that needs one is asserting too early; assert the state it was waiting for instead.

- `wait(2)` and `pressAndWaitFor()` sleep for a fixed time.
- `wait()` with no argument waits for a key press, which hangs CI.
- `waitForEvent()`, `waitForLoadState()`, `waitForFunction()` and `waitForURL()` are no-ops: they never reach the browser and return immediately. Remove them when you find them, and say so when explaining a flaky test.

### Navigation

- After an action that loads a page or an Inertia/Livewire visit, assert the destination first: `->click('Checkout')->assertPathIs('/checkout')`.
- Trigger side effects with `click` or `press`, and keep the requests they trigger well under a second by faking queues, mail and external APIs. Slow requests behind other actions can run twice: see [references/api-traps.md](references/api-traps.md).
- Pass `visit()` and `navigate()` a path starting with `/`, e.g. `route('orders.show', $order, absolute: false)`.

### Isolation

- Use `RefreshDatabase` for browser tests in `tests/Pest.php`.
- Each test creates its own data with factories and unique values, so it passes alone, in any order and under `--parallel`.
- Keep browser tests in `tests/Browser`. Files there are always detected as browser tests, and the plugin only cleans up after tests inside the test directory.
- Build assets with `npm run build` before running: browser tests load the real Vite bundle.
- Assert text and elements rather than screenshots. Use `assertScreenshotMatches()` only when visual testing is the explicit goal, set up as in [references/ci.md](references/ci.md).

Done when the test follows every point under Shape, every method it calls exists in `src/Api`, and assertions do all of the waiting.

## 3. Prove it

1. Break the behaviour once (comment out the save, change the redirect) and watch the test go red with a message that names the problem. Restore it.
2. Run the file alone, then repeated: add a temporary `->repeat(5)` to the test and remove it after. The `--repeat` flag runs browser tests only once.
3. Run the browser suite with `--parallel`.

Done when the test went red for the right reason, every run in steps 2 and 3 is green, and the file contains no `wait(`, `sleep(`, `debug(`, `tinker(`, `->only(` or `->repeat(`.

## Reviewing a browser test

Check it against every point in section 2 and the done list in section 3. Report each miss with its line and the fix.

## When a browser test fails

- Flaky, CI-only, timing out, hanging, or a cascade of bare `Assertion error`s: work through [references/flaky.md](references/flaky.md) in order.
- Setting up or changing CI (Playwright install, sharding, traces as artifacts, screenshot baselines): [references/ci.md](references/ci.md).
