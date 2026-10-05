<?php

declare(strict_types=1);

namespace DiffStage\Recorder;

/**
 * Collects what happened during one recorded test: the steps a reviewer
 * would describe, and any problems the browser reported along the way.
 */
final class Telemetry
{
    private const ACTIONS = ['click', 'dblclick', 'check', 'uncheck', 'fill', 'type', 'press', 'selectOption', 'hover', 'tap', 'setInputFiles'];

    private const ASSERTIONS = ['assertSee', 'assertDontSee', 'assertSeeIn', 'assertDontSeeIn', 'assertPathIs', 'assertUrlIs', 'assertVisible', 'assertChecked', 'assertNotChecked', 'assertEnabled', 'assertButtonEnabled', 'assertDisabled', 'assertButtonDisabled', 'assertValue', 'assertSelected'];

    private static ?float $startedAt = null;

    /**
     * @var array<int, array{at: float, text: string, attempts?: int, failed?: bool}>
     */
    private static array $steps = [];

    /**
     * @var array<int, array{at: float, kind: string, text: string, count?: int}>
     */
    private static array $problems = [];

    /** @var array<int, array{at: float, text: string, finished_at?: float, passed?: bool}> */
    private static array $assertions = [];

    /** @var list<string> */
    private static array $typedValues = [];

    private static int $assertionsRunning = 0;

    /**
     * @var array<string, array{method: string, url: string}>
     */
    private static array $requests = [];

    /**
     * @var array<string, true>
     */
    private static array $mainFrames = [];

    private static ?string $lastUrl = null;

    private static ?string $lastAction = null;

    private static bool $lastActionFailed = false;

    public static function begin(): void
    {
        self::$startedAt = microtime(true);
        self::$steps = [];
        self::$problems = [];
        self::$assertions = [];
        self::$typedValues = [];
        self::$assertionsRunning = 0;
        self::$requests = [];
        self::$mainFrames = [];
        self::$lastUrl = null;
        self::$lastAction = null;
        self::$lastActionFailed = false;
    }

    public static function active(): bool
    {
        return self::$startedAt !== null;
    }

    /**
     * Whether this action repeats one the browser just failed to perform.
     *
     * @param  array<string, mixed>  $params
     */
    public static function isRetry(string $method, array $params): bool
    {
        return self::active() && self::$lastActionFailed && self::$lastAction === self::key($method, $params);
    }

    public static function actionFailed(): void
    {
        if (self::$assertionsRunning === 0) {
            self::$lastActionFailed = self::$lastAction !== null;
        }
    }

    /** @param array<int, mixed> $arguments */
    public static function beginAssertion(string $method, array $arguments): ?int
    {
        if (! self::active() || ! in_array($method, self::ASSERTIONS, true)) {
            return null;
        }

        $target = Selector::describe((string) ($arguments[0] ?? ''));
        $expectedText = self::assertionText((string) ($arguments[1] ?? $arguments[0] ?? ''));
        $text = match ($method) {
            'assertSee' => "Text {$expectedText} is visible",
            'assertDontSee' => "Text {$expectedText} is not visible",
            'assertSeeIn' => "Text {$expectedText} is visible in {$target}",
            'assertDontSeeIn' => "Text {$expectedText} is not visible in {$target}",
            'assertPathIs' => 'Page path matches '.self::path((string) $arguments[0]),
            'assertUrlIs' => 'Page URL matches the expected address',
            'assertVisible' => "{$target} is visible",
            'assertChecked' => "Checkbox {$target} is checked",
            'assertNotChecked' => "Checkbox {$target} is not checked",
            'assertEnabled', 'assertButtonEnabled' => "{$target} is enabled",
            'assertDisabled', 'assertButtonDisabled' => "{$target} is disabled",
            'assertValue' => "Value in {$target} matches the expected value",
            'assertSelected' => "Selection in {$target} matches the expected option",
            default => null,
        };

        if ($text === null) {
            return null;
        }

        self::$assertions[] = ['at' => self::now(), 'text' => $text];
        self::$assertionsRunning++;

        return array_key_last(self::$assertions);
    }

    public static function endAssertion(?int $index, bool $passed): void
    {
        if ($index === null) {
            return;
        }

        self::$assertions[$index]['finished_at'] = self::now();
        self::$assertions[$index]['passed'] = $passed;
        self::$assertionsRunning--;
    }

    /**
     * @param  array<string, mixed>  $params
     */
    public static function action(string $method, array $params): void
    {
        if (! self::active() || ! in_array($method, self::ACTIONS, true)) {
            return;
        }

        if (in_array($method, ['fill', 'type'], true)) {
            $value = (string) ($params['value'] ?? $params['text'] ?? '');
            if ($value !== '') {
                self::$typedValues[] = $value;
            }
        }

        if (self::isRetry($method, $params)) {
            $last = array_key_last(self::$steps);
            self::$steps[$last]['attempts'] = (self::$steps[$last]['attempts'] ?? 1) + 1;
            self::$lastActionFailed = false;

            return;
        }

        self::$lastAction = self::key($method, $params);
        self::$lastActionFailed = false;

        $target = Selector::describe((string) ($params['selector'] ?? ''));

        $text = match ($method) {
            'click', 'tap' => "Clicked {$target}",
            'dblclick' => "Double-clicked {$target}",
            'check' => "Ticked {$target}",
            'uncheck' => "Unticked {$target}",
            'hover' => "Hovered over {$target}",
            'press' => 'Pressed '.self::keyName((string) ($params['key'] ?? '')).($target === '' ? '' : " in {$target}"),
            'selectOption' => "Chose an option in {$target}",
            'setInputFiles' => "Attached a file to {$target}",
            default => self::typed($target, (string) ($params['value'] ?? $params['text'] ?? '')),
        };

        self::$steps[] = ['at' => self::now(), 'text' => $text];
    }

    /**
     * @param  array<string, mixed>  $message
     */
    public static function observe(array $message): void
    {
        if (! self::active() || ! isset($message['method'])) {
            return;
        }

        $params = is_array($message['params'] ?? null) ? $message['params'] : [];

        match ($message['method']) {
            '__create__' => self::created($params),
            'navigated' => self::navigated((string) ($message['guid'] ?? ''), $params),
            'console' => self::console($params),
            'pageError' => self::problem('error', (string) ($params['error']['error']['message'] ?? 'Uncaught error')),
            'requestFailed' => self::requestFailed($params),
            default => null,
        };
    }

    /**
     * @return array{steps: array<int, array{at: float, text: string, attempts?: int, failed?: bool}>, problems: array<int, array{at: float, kind: string, text: string, count?: int}>, assertions: array<int, array{at: float, text: string, finished_at?: float, passed?: bool}>}
     */
    public static function finish(): array
    {
        if (self::$lastActionFailed && self::$steps !== []) {
            self::$steps[array_key_last(self::$steps)]['failed'] = true;
        }

        $result = ['steps' => self::$steps, 'problems' => self::$problems, 'assertions' => self::$assertions];

        self::$startedAt = null;
        self::$typedValues = [];

        return $result;
    }

    /**
     * @param  array<string, mixed>  $params
     */
    private static function created(array $params): void
    {
        $type = $params['type'] ?? null;
        $guid = (string) ($params['guid'] ?? '');
        $initializer = is_array($params['initializer'] ?? null) ? $params['initializer'] : [];

        if ($type === 'Page' && isset($initializer['mainFrame']['guid'])) {
            self::$mainFrames[(string) $initializer['mainFrame']['guid']] = true;
        }

        if ($type === 'Request') {
            self::$requests[$guid] = [
                'method' => (string) ($initializer['method'] ?? 'GET'),
                'url' => (string) ($initializer['url'] ?? ''),
            ];
        }

        if ($type === 'Response' && (int) ($initializer['status'] ?? 0) >= 400) {
            $request = self::$requests[(string) ($initializer['request']['guid'] ?? '')] ?? null;
            $method = $request['method'] ?? 'GET';

            self::problem('http', ((int) $initializer['status'])." {$method} ".self::path((string) ($initializer['url'] ?? '')));
        }
    }

    /**
     * @param  array<string, mixed>  $params
     */
    private static function navigated(string $frame, array $params): void
    {
        $url = (string) ($params['url'] ?? '');

        if (! isset(self::$mainFrames[$frame]) || $url === '' || str_starts_with($url, 'about:') || $url === self::$lastUrl) {
            return;
        }

        self::$lastUrl = $url;
        self::$steps[] = ['at' => self::now(), 'text' => 'Opened '.self::path($url)];
    }

    /**
     * @param  array<string, mixed>  $params
     */
    private static function console(array $params): void
    {
        if (($params['type'] ?? null) === 'error') {
            self::problem('console', (string) ($params['text'] ?? 'Console error'));
        }
    }

    /**
     * @param  array<string, mixed>  $params
     */
    private static function requestFailed(array $params): void
    {
        $failure = (string) ($params['failureText'] ?? 'failed');

        if (str_contains($failure, 'ERR_ABORTED')) {
            return;
        }

        $request = self::$requests[(string) ($params['request']['guid'] ?? '')] ?? ['method' => 'GET', 'url' => ''];

        self::problem('network', "{$request['method']} ".self::path($request['url'])." failed: {$failure}");
    }

    private static function problem(string $kind, string $text): void
    {
        if ($kind === 'console' && str_starts_with($text, 'Failed to load resource')) {
            return;
        }

        $text = mb_substr($text, 0, 500);

        foreach (self::$problems as $index => $problem) {
            if ($problem['kind'] === $kind && $problem['text'] === $text) {
                self::$problems[$index]['count'] = ($problem['count'] ?? 1) + 1;

                return;
            }
        }

        self::$problems[] = ['at' => self::now(), 'kind' => $kind, 'text' => $text];
    }

    /**
     * @param  array<string, mixed>  $params
     */
    private static function key(string $method, array $params): string
    {
        return $method.'|'.($params['selector'] ?? '').'|'.($params['value'] ?? $params['key'] ?? '');
    }

    /**
     * Named keys like Enter or Control+A, but never a typed character.
     */
    private static function keyName(string $key): string
    {
        return $key === '' || mb_strlen((string) preg_replace('/^Shift\+/', '', $key)) === 1 ? 'a key' : $key;
    }

    private static function typed(string $target, string $value): string
    {
        return $value === '' ? "Cleared {$target}" : "Typed into {$target}";
    }

    private static function assertionText(string $text): string
    {
        foreach (self::$typedValues as $value) {
            if ($text === $value) {
                return '(entered text)';
            }
            if (mb_strlen($value) >= 4) {
                $text = str_replace($value, '(entered text)', $text);
            }
        }

        return '"'.(mb_strlen($text) > 100 ? mb_substr($text, 0, 100).'…' : $text).'"';
    }

    /**
     * The path and query keys of a URL. Query values can hold tokens, so they're never kept.
     */
    private static function path(string $url): string
    {
        $parts = parse_url($url);

        if ($parts === false) {
            return (string) preg_replace('/[?#].*/s', '', $url);
        }

        $path = $parts['path'] ?? '/';

        if (! isset($parts['query'])) {
            return $path;
        }

        $keys = array_filter(array_map(fn (string $pair): string => explode('=', $pair, 2)[0], explode('&', $parts['query'])), fn (string $key): bool => $key !== '');

        return $path.'?'.implode('&', array_map(fn (string $key): string => "{$key}=…", $keys));
    }

    private static function now(): float
    {
        return round(microtime(true) - (self::$startedAt ?? microtime(true)), 2);
    }
}
