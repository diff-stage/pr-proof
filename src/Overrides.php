<?php

declare(strict_types=1);

namespace PrProof;

use Composer\InstalledVersions;
use RuntimeException;

/**
 * Swaps three Pest Browser classes for copies that can record video.
 * This runs from Composer's autoloader, before Pest loads any of them.
 */
final class Overrides
{
    public const SUPPORTED_BROWSER_PLUGIN = 'v4.3.1';

    private const CLASSES = [
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

        if ($installed !== self::SUPPORTED_BROWSER_PLUGIN) {
            throw new RuntimeException('pr-proof supports pestphp/pest-plugin-browser '.self::SUPPORTED_BROWSER_PLUGIN.", but {$installed} is installed.");
        }

        spl_autoload_register(static function (string $class): void {
            if (isset(self::CLASSES[$class])) {
                require __DIR__.'/../overrides/'.self::CLASSES[$class];
            }
        }, prepend: true);
    }
}
