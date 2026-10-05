<?php

declare(strict_types=1);

namespace Pest\Browser\Playwright;

use Amp\Websocket\Client\WebsocketConnection;
use Generator;
use Pest\Browser\Exceptions\PlaywrightOutdatedException;
use PHPUnit\Framework\ExpectationFailedException;
use DiffStage\Recorder\Overrides;
use DiffStage\Recorder\Recorder;
use DiffStage\Recorder\Telemetry;

use function Amp\Websocket\Client\connect;

/**
 * @internal
 */
final class Client
{
    private const PAUSED_ACTIONS = ['click', 'dblclick', 'check', 'uncheck', 'fill', 'type', 'press', 'selectOption', 'hover', 'tap', 'setInputFiles'];

    /**
     * Client instance.
     */
    private static ?Client $instance = null;

    /**
     * WebSocket client instance.
     */
    private ?WebsocketConnection $websocketConnection = null;

    /**
     * Default timeout for requests in milliseconds.
     */
    private int $timeout = 5_000;

    /** @var array<string, array<int, array{file: string, line: int, function: string}>> */
    private array $stacks = [];

    /**
     * Returns the current client instance.
     */
    public static function instance(): self
    {
        if (! self::$instance instanceof self) {
            self::$instance = new self;
        }

        return self::$instance;
    }

    /**
     * Connects to the Playwright server.
     */
    public function connectTo(string $url): void
    {
        if (! $this->websocketConnection instanceof WebsocketConnection) {
            $browser = Playwright::defaultBrowserType()->toPlaywrightName();

            $launchOptions = json_encode([
                'headless' => Playwright::isHeadless(),
                'ignoreHTTPSErrors' => true,
                'bypassCSP' => true,
            ]);

            $this->websocketConnection = connect(
                "ws://$url?browser=$browser&launch-options=$launchOptions",
            );
        }
    }

    /**
     * Executes a method on the Playwright instance.
     *
     * @param  array<string, mixed>  $params
     * @param  array<string, mixed>  $meta
     * @return Generator<array<string, mixed>>
     */
    public function execute(string $guid, string $method, array $params = [], array $meta = []): Generator
    {
        assert($this->websocketConnection instanceof WebsocketConnection, 'WebSocket client is not connected.');

        $requestId = uniqid();

        if (Overrides::supportsTracing() && Tracing::isRecording()) {
            $this->recordStack($requestId);
        }

        $timeout = is_numeric($params['timeout'] ?? null) ? (int) $params['timeout'] : $this->timeout;

        $requestJson = (string) json_encode([
            'id' => $requestId,
            'guid' => $guid,
            'method' => $method,
            'params' => ['timeout' => $timeout, ...$params],
            // Playwright 1.62+ reads action timeouts from metadata.
            'metadata' => ['timeout' => $timeout, ...$meta],
        ]);

        $retry = Telemetry::isRetry($method, $params);

        if (! $retry && Recorder::enabled() && in_array($method, self::PAUSED_ACTIONS, true) && Recorder::pathForCurrentTest() !== null) {
            usleep(Recorder::pause() * 1000);
        }

        Telemetry::action($method, $params);

        $this->websocketConnection->sendText($requestJson);

        while (true) {
            $responseJson = $this->fetch($this->websocketConnection);
            /** @var array{id: string|null, params: array{add: string|null}, error: array{error: array{message: string|null}}} $response */
            $response = json_decode($responseJson, true);

            if (is_array($response)) {
                Telemetry::observe($response);
            }

            if (isset($response['error']['error']['message'])) {
                $message = $response['error']['error']['message'];

                if (str_contains($message, 'Playwright was just installed or updated')) {
                    throw new PlaywrightOutdatedException;
                }

                Telemetry::actionFailed();

                throw new ExpectationFailedException($message);
            }

            yield $response;

            if (
                (isset($response['id']) && $response['id'] === $requestId)
                || (isset($params['waitUntil']) && isset($response['params']['add']) && $params['waitUntil'] === $response['params']['add'])
            ) {
                break;
            }
        }
    }

    /**
     * Sets the timeout in milliseconds for requests.
     */
    public function setTimeout(int $timeout): void
    {
        $this->timeout = $timeout;
    }

    /**
     * Returns the current timeout for requests.
     */
    public function timeout(): int
    {
        return $this->timeout;
    }

    /**
     * Returns the PHP call stacks of the requests made while tracing.
     *
     * @return array<string, array<int, array{file: string, line: int, function: string}>>
     */
    public function stacks(): array
    {
        return $this->stacks;
    }

    /**
     * Forgets the PHP call stacks of the requests made while tracing.
     */
    public function flushStacks(): void
    {
        $this->stacks = [];
    }

    /**
     * Records the PHP call stack of the given request, so the trace viewer can show the test's source.
     */
    private function recordStack(string $requestId): void
    {
        $src = dirname(__DIR__);
        $backtrace = debug_backtrace(DEBUG_BACKTRACE_IGNORE_ARGS);
        $frames = [];

        foreach ($backtrace as $index => $trace) {
            if (! isset($trace['file'], $trace['line'])) {
                continue;
            }

            if (str_starts_with($trace['file'], $src) || str_contains($trace['file'], DIRECTORY_SEPARATOR.'vendor'.DIRECTORY_SEPARATOR)) {
                continue;
            }

            $frames[] = [
                'file' => $trace['file'],
                'line' => $trace['line'],
                'function' => $backtrace[$index + 1]['function'] ?? '',
            ];
        }

        if ($frames !== []) {
            $this->stacks[$requestId] = $frames;
        }
    }

    /**
     * Fetches the response from the Playwright server.
     */
    private function fetch(WebsocketConnection $client): string
    {
        return (string) $client->receive()?->read();
    }
}
