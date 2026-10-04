<?php

declare(strict_types=1);

namespace PrProof;

use Pest\Browser\Playwright\Client;

/**
 * Collects what happened during one recorded test: the steps a reviewer
 * would describe, and any problems the browser reported along the way.
 */
final class Telemetry
{
    private const ACTIONS = ['click', 'dblclick', 'check', 'uncheck', 'fill', 'type', 'press', 'selectOption', 'hover', 'tap', 'setInputFiles'];

    private static ?float $startedAt = null;

    private static ?string $videoPath = null;

    private static ?string $pageGuid = null;

    private static bool $capturing = false;

    /**
     * @var array<int, array{at: float, text: string, attempts?: int, failed?: bool, screenshot?: string}>
     */
    private static array $steps = [];

    /**
     * @var array<int, array{at: float, kind: string, text: string, count?: int}>
     */
    private static array $problems = [];

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

    public static function begin(string $videoPath): void
    {
        self::$startedAt = microtime(true);
        self::$videoPath = $videoPath;
        self::$pageGuid = null;
        self::$steps = [];
        self::$problems = [];
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
     * Screenshots the page for every step that does not have one yet, so each
     * step shows the screen once that step has finished.
     */
    public static function captureScreen(): void
    {
        if (! self::active() || self::$capturing || self::$pageGuid === null || self::$videoPath === null) {
            return;
        }

        $pending = array_keys(array_filter(self::$steps, static fn (array $step): bool => ! isset($step['screenshot'])));

        if ($pending === []) {
            return;
        }

        self::$capturing = true;

        try {
            $binary = null;

            foreach (Client::instance()->execute(self::$pageGuid, 'screenshot', ['type' => 'jpeg', 'quality' => 70, 'scale' => 'css']) as $message) {
                if (isset($message['result']['binary'])) {
                    $binary = base64_decode((string) $message['result']['binary']);
                }
            }
        } catch (\Throwable) {
            $binary = null;
        } finally {
            self::$capturing = false;
        }

        if ($binary === null) {
            return;
        }

        $directory = (string) preg_replace('/\.webm$/', '', self::$videoPath);

        if (! is_dir($directory)) {
            mkdir($directory, 0777, true);
        }

        $file = sprintf('%02d.jpg', end($pending) + 1);
        file_put_contents("{$directory}/{$file}", $binary);

        foreach ($pending as $index) {
            self::$steps[$index]['screenshot'] = basename($directory)."/{$file}";
        }
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
        self::$lastActionFailed = self::$lastAction !== null;
    }

    /**
     * @param  array<string, mixed>  $params
     */
    public static function action(string $method, array $params): void
    {
        if (! self::active() || ! in_array($method, self::ACTIONS, true)) {
            return;
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
            'press' => 'Pressed '.($params['key'] ?? 'a key').($target === '' ? '' : " in {$target}"),
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
     * @return array{steps: array<int, array{at: float, text: string, attempts?: int, failed?: bool, screenshot?: string}>, problems: array<int, array{at: float, kind: string, text: string, count?: int}>}
     */
    public static function finish(): array
    {
        if (self::$lastActionFailed && self::$steps !== []) {
            self::$steps[array_key_last(self::$steps)]['failed'] = true;
        }

        $result = ['steps' => self::$steps, 'problems' => self::$problems];

        self::$startedAt = null;

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
            self::$pageGuid ??= $guid;
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

    private static function typed(string $target, string $value): string
    {
        if (preg_match('/pass(word)?|secret|card|cvc|token/i', $target)) {
            return "Typed into {$target}";
        }

        $shown = mb_strlen($value) > 40 ? mb_substr($value, 0, 40).'…' : $value;

        return $value === '' ? "Cleared {$target}" : "Typed \"{$shown}\" into {$target}";
    }

    private static function path(string $url): string
    {
        $parts = parse_url($url);

        if ($parts === false || ! isset($parts['path'])) {
            return $url;
        }

        return $parts['path'].(isset($parts['query']) ? '?'.$parts['query'] : '');
    }

    private static function now(): float
    {
        return round(microtime(true) - (self::$startedAt ?? microtime(true)), 2);
    }
}
