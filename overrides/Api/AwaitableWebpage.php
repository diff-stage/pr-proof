<?php

declare(strict_types=1);

namespace Pest\Browser\Api;

use DiffStage\Recorder\Overrides;
use DiffStage\Recorder\Telemetry;
use Pest\Browser\Exceptions\BrowserExpectationFailedException;
use Pest\Browser\Execution;
use Pest\Browser\Playwright\Page;
use Pest\Browser\Playwright\Playwright;
use Pest\Browser\Playwright\Tracing;
use Pest\Browser\ServerManager;
use Pest\Browser\Support\Step;
use PHPUnit\Framework\ExpectationFailedException;
use Throwable;

/**
 * @mixin Webpage
 */
final readonly class AwaitableWebpage
{
    /** @var array<int, string> */
    private array $nonAwaitableMethods;

    /** @param array<int, string>|null $nonAwaitableMethods */
    public function __construct(
        private Page $page,
        private string $initialUrl,
        ?array $nonAwaitableMethods = null,
    ) {
        $this->nonAwaitableMethods = $nonAwaitableMethods ?? [
            'assertScreenshotMatches',
            'assertNoAccessibilityIssues',
            ...(Overrides::supportsTracing() ? ['typeSlowly', 'click', 'rightClick', 'press', 'pressAndWaitFor', 'keys', 'drag', 'append'] : []),
        ];
    }

    /**
     * Awaits for the given method to assert true or fail.
     *
     * @param  array<int, mixed>  $arguments
     */
    public function __call(string $name, array $arguments): mixed
    {
        $assertion = Telemetry::beginAssertion($name, $arguments);
        $passed = false;

        try {
            $webpage = new Webpage($this->page, $this->initialUrl);

            $call = in_array($name, $this->nonAwaitableMethods, true) || Playwright::timeout() <= 1000
                // @phpstan-ignore-next-line
                ? fn (): mixed => $webpage->{$name}(...$arguments)
                : fn (): mixed => Execution::instance()->waitForExpectation(
                    // @phpstan-ignore-next-line
                    fn () => $webpage->{$name}(...$arguments),
                );

            try {
                $tracing = Overrides::supportsTracing() ? $this->page->context()->tracing() : null;

                if ($tracing instanceof Tracing && $tracing->path() !== null) {
                    $caller = debug_backtrace(DEBUG_BACKTRACE_IGNORE_ARGS, 1)[0];

                    $result = $tracing->group(
                        Step::title($name, $arguments),
                        $caller['file'] ?? null,
                        $caller['line'] ?? null,
                        $call,
                    );
                } else {
                    $result = $call();
                }
            } catch (ExpectationFailedException $e) {
                ServerManager::instance()->http()->throwLastThrowableIfNeeded();

                try {
                    $browserException = BrowserExpectationFailedException::from($this->page, $e);
                } catch (Throwable) {
                    throw $e;
                }

                throw $browserException;
            }

            ServerManager::instance()->http()->throwLastThrowableIfNeeded();

            $passed = true;

            return $result === $webpage
                ? $this
                : $result;
        } finally {
            Telemetry::endAssertion($assertion, $passed);
        }
    }

    /**
     * Return the page instance.
     */
    public function page(): Page
    {
        return $this->page;
    }
}
