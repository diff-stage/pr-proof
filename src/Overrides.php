<?php

declare(strict_types=1);

namespace DiffStage\Recorder;

use Composer\InstalledVersions;
use RuntimeException;

/**
 * Swaps four Pest Browser classes for copies that can record video.
 * This runs from Composer's autoloader, before Pest loads any of them.
 */
final class Overrides
{
    public const SUPPORTED_BROWSER_PLUGINS = ['v4.3.1', 'v5.1.2'];

    public static function supportsTracing(): bool
    {
        return InstalledVersions::getPrettyVersion('pestphp/pest-plugin-browser') === 'v5.1.2';
    }

    private const CLASSES = [
        'Pest\\Browser\\Api\\AwaitableWebpage' => 'Api/AwaitableWebpage.php',
        'Pest\Browser\Api\PendingAwaitablePage' => 'Api/PendingAwaitablePage.php',
        'Pest\Browser\Playwright\Context' => 'Playwright/Context.php',
        'Pest\Browser\Playwright\Client' => 'Playwright/Client.php',
    ];

    public static function registerWhenRecording(): void
    {
        $arguments = $_SERVER['argv'] ?? [];

        foreach ($arguments as $argument) {
            if (is_string($argument) && str_starts_with($argument, '--record-videos')) {
                self::register();

                return;
            }
        }
    }

    private static function register(): void
    {
        $installed = InstalledVersions::getPrettyVersion('pestphp/pest-plugin-browser');

        if (! in_array($installed, self::SUPPORTED_BROWSER_PLUGINS, true)) {
            throw new RuntimeException('The Diff Stage recorder supports pestphp/pest-plugin-browser '.implode(' or ', self::SUPPORTED_BROWSER_PLUGINS).", but {$installed} is installed.");
        }

        spl_autoload_register(static function (string $class): void {
            if (isset(self::CLASSES[$class])) {
                require __DIR__.'/../overrides/'.self::CLASSES[$class];
            }
        }, prepend: true);
    }
}
