<?php

namespace Composer {
    final class InstalledVersions
    {
        public static function getPrettyVersion(string $package): string
        {
            return 'v5.1.1';
        }
    }
}

namespace {
    use PrProof\Overrides;

    require __DIR__.'/../../src/Overrides.php';
    $_SERVER['argv'] = ['pest', '--record-videos'];

    try {
        Overrides::registerWhenRecording();
        throw new LogicException('Unsupported version was accepted');
    } catch (RuntimeException $exception) {
        if (! str_contains($exception->getMessage(), 'v5.1.1 is installed')) {
            throw $exception;
        }
    }
}
