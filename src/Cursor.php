<?php

declare(strict_types=1);

namespace DiffStage\Recorder;

use Pest\Browser\Playwright\Client;
use Pest\Browser\Support\JavaScriptSerializer;

final class Cursor
{
    /** @var array<string, string> */
    private static array $pages = [];

    private static ?string $currentPage = null;

    /** @var array<string, array<string, mixed>> */
    private static array $contexts = [];

    /** @var array<string, array<string, mixed>> */
    private static array $viewports = [];

    /** @var array<string, array{x: float, y: float}> */
    private static array $positions = [];

    /** @param array<string, mixed> $message */
    public static function observe(array $message): void
    {
        if (($message['method'] ?? null) === '__create__') {
            $params = $message['params'];
            if ($params['type'] === 'Page') {
                self::$currentPage = $params['guid'];
            }
            if ($params['type'] === 'BrowserContext') {
                self::$contexts[$params['guid']] = $params['initializer']['options'];
            } elseif ($params['type'] === 'Page' && ! (self::$contexts[$message['guid']]['hasTouch'] ?? false)) {
                self::$pages[$params['initializer']['mainFrame']['guid']] = $params['guid'];
                self::$positions[$params['guid']] = ['x' => 0.0, 'y' => 0.0];
                self::$viewports[$params['guid']] = $params['initializer']['viewportSize'] ?? [];
            } elseif ($params['type'] === 'Frame' && isset(self::$positions[$message['guid']])) {
                self::$pages[$params['guid']] = $message['guid'];
            }
        }

        if (($message['method'] ?? null) === 'viewportSizeChanged') {
            self::$viewports[$message['guid']] = $message['params']['viewportSize'] ?? [];
        }

        if (($message['method'] ?? null) === '__dispose__') {
            $guid = $message['guid'];
            if (self::$currentPage === $guid) {
                self::$currentPage = null;
            }
            unset(self::$positions[$guid], self::$viewports[$guid], self::$contexts[$guid], self::$pages[$guid]);
            self::$pages = array_filter(self::$pages, fn (string $page): bool => $page !== $guid);
        }
    }

    /** @param array<string, mixed> $params */
    public static function approach(Client $client, string $frame, string $method, array $params): void
    {
        if (! in_array($method, ['click', 'dblclick', 'check', 'uncheck', 'hover', 'fill', 'type', 'selectOption'], true)
            || ! isset(self::$pages[$frame], $params['selector']) || ($params['trial'] ?? false)) {
            return;
        }

        $page = self::$pages[$frame];
        $result = self::request($client, $frame, 'waitForSelector', [
            'selector' => $params['selector'], 'state' => 'visible', 'strict' => $params['strict'] ?? true,
            'timeout' => $params['timeout'] ?? $client->timeout(),
        ]);
        $element = $result['element']['guid'];

        try {
            self::request($client, $element, 'scrollIntoViewIfNeeded');
            $box = self::request($client, $element, 'boundingBox')['value'];
            if ($box === null) {
                return;
            }

            $viewport = self::$viewports[$page];
            $left = max(0, $box['x']);
            $top = max(0, $box['y']);
            $right = min($viewport['width'] ?? INF, $box['x'] + $box['width']);
            $bottom = min($viewport['height'] ?? INF, $box['y'] + $box['height']);
            $target = ['x' => ($left + $right) / 2, 'y' => ($top + $bottom) / 2];
            if (isset($params['position'])) {
                $border = self::request($client, $element, 'evaluateExpression', [
                    'expression' => '(element) => ({ x: element.clientLeft, y: element.clientTop })',
                    'isFunction' => true, 'arg' => ['value' => ['v' => 'undefined'], 'handles' => []],
                ])['value'];
                $border = JavaScriptSerializer::parseValue($border);
                $target = ['x' => $box['x'] + $border['x'] + $params['position']['x'], 'y' => $box['y'] + $border['y'] + $params['position']['y']];
            }

            if (Recorder::fast()) {
                usleep(120_000);
                Telemetry::cursor($target, $method, self::request($client, $page, 'screenshot', ['type' => 'png', 'fullPage' => false, 'scale' => 'css'])['binary']);

                return;
            }

            $start = self::$positions[$page];
            $dx = $target['x'] - $start['x'];
            $dy = $target['y'] - $start['y'];
            $distance = hypot($dx, $dy);
            if ($distance < 1) {
                return;
            }

            $duration = min(650, 180 + $distance * 0.45);
            $steps = (int) ceil($duration / 16);
            $bend = min(45, $distance * 0.08);
            $started = microtime(true);
            for ($step = 1; $step <= $steps; $step++) {
                $t = $step / $steps;
                $progress = $t * $t * (3 - 2 * $t);
                $arc = sin(M_PI * $progress) * $bend;
                $point = [
                    'x' => $start['x'] + $dx * $progress - $dy / $distance * $arc,
                    'y' => $start['y'] + $dy * $progress + $dx / $distance * $arc,
                ];
                $remaining = $started + $t * $duration / 1000 - microtime(true);
                if ($remaining > 0) {
                    usleep((int) ($remaining * 1_000_000));
                }
                self::request($client, $page, 'mouseMove', $point);
                self::$positions[$page] = $point;
            }
        } finally {
            self::request($client, $element, 'dispose');
        }
    }

    public static function readingHold(): void
    {
        if (Recorder::fast() && Telemetry::active() && self::$currentPage !== null) {
            Telemetry::hold(self::request(Client::instance(), self::$currentPage, 'screenshot', ['type' => 'png', 'fullPage' => false, 'scale' => 'css'])['binary']);
        }
    }

    /**
     * @param  array<string, mixed>  $params
     * @return array<string, mixed>
     */
    private static function request(Client $client, string $guid, string $method, array $params = []): array
    {
        foreach ($client->execute($guid, $method, $params) as $message) {
            if (isset($message['result'])) {
                return $message['result'];
            }
        }

        return [];
    }
}
