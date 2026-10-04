<?php

declare(strict_types=1);

namespace PrProof;

use Pest\TestSuite;
use PHPUnit\Framework\TestCase;
use ReflectionProperty;

final class Recorder
{
    private static ?string $directory = null;

    /**
     * @var array<int, string>|null
     */
    private static ?array $only = null;

    private static int $pause = 700;

    /**
     * @param  array<int, string>|null  $only
     */
    public static function enable(string $directory, ?array $only, int $pause): void
    {
        self::$directory = rtrim($directory, '/');
        self::$only = $only;
        self::$pause = $pause;

        if (! is_dir(self::$directory)) {
            mkdir(self::$directory, 0777, true);
        }
    }

    public static function enabled(): bool
    {
        return self::$directory !== null;
    }

    /**
     * The video path for the running test, or null when it should not be recorded.
     */
    public static function pathForCurrentTest(): ?string
    {
        if (self::$directory === null) {
            return null;
        }

        $test = TestSuite::getInstance()->test;

        if (! $test instanceof TestCase || ! method_exists($test, 'getPrintableTestCaseMethodName')) {
            return null;
        }

        $file = self::relativeFile(self::testFile($test));

        if (self::$only !== null && ! in_array($file, self::$only, true)) {
            return null;
        }

        $class = $test::getPrintableTestCaseName();
        $name = self::slug(substr($class, (int) strrpos('\\'.$class, '\\')).' '.$test->getPrintableTestCaseMethodName());

        return self::$directory."/{$name}.webm";
    }

    public static function pause(): int
    {
        return self::$pause;
    }

    public static function cursorOverlay(): string
    {
        return (string) file_get_contents(__DIR__.'/../resources/cursor-overlay.js');
    }

    private static function testFile(TestCase $test): string
    {
        $property = new ReflectionProperty($test, '__filename');

        return (string) $property->getValue();
    }

    private static function slug(string $text): string
    {
        return trim((string) preg_replace('/[^a-z0-9]+/', '-', strtolower($text)), '-');
    }

    private static function relativeFile(string $path): string
    {
        $root = TestSuite::getInstance()->rootPath;

        return ltrim(str_replace($root, '', $path), '/');
    }
}
