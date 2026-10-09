<?php

declare(strict_types=1);

namespace DiffStage\Recorder;

use DOMDocument;
use RuntimeException;

/**
 * Finds selected browser tests with Pest itself, so names match exactly what will run.
 */
final class Scenarios
{
    /**
     * Returns how many tests a file or exact scenario runs, counting each dataset variant.
     */
    public static function count(string $file, ?string $test): int
    {
        if (! preg_match('#\A[a-zA-Z0-9_./-]+\.php\z#', $file) || str_starts_with($file, '/') || str_contains($file, '..') || ! is_file($file)) {
            throw new RuntimeException('Selection must contain existing relative PHP files and exact scenario names.');
        }

        $list = tempnam(sys_get_temp_dir(), 'diff-stage-tests-');
        try {
            $command = [PHP_BINARY, 'vendor/bin/pest', $file];
            if ($test !== null) {
                array_push($command, '--filter', self::filter([$test]));
            }
            array_push($command, '--list-tests-xml', $list);
            if (self::run($command, true) !== 0) {
                throw new RuntimeException('Pest could not discover tests in '.$file.'.');
            }
            $xml = new DOMDocument;
            $count = $xml->load($list, LIBXML_NONET) ? $xml->getElementsByTagName('testMethod')->length : 0;
            if ($count === 0) {
                throw new RuntimeException('No tests match '.$file.($test === null ? '' : '::'.$test).'. Use the complete Pest name, including "it" and describe groups.');
            }

            return $count;
        } finally {
            unlink($list);
        }
    }

    /**
     * @param  list<string>  $tests
     */
    public static function filter(array $tests): string
    {
        return '/::(?:'.implode('|', array_map(fn (string $test): string => preg_quote($test, '/'), $tests)).')(?: with data set .+)?$/u';
    }

    /**
     * @param  list<string>  $command
     */
    public static function run(array $command, bool $quiet = false): int
    {
        $process = proc_open($command, [0 => STDIN, 1 => $quiet ? ['pipe', 'w'] : STDOUT, 2 => STDERR], $pipes);
        if ($process === false) {
            throw new RuntimeException('Could not start Pest.');
        }

        $output = $quiet ? stream_get_contents($pipes[1]) : '';
        if ($quiet) {
            fclose($pipes[1]);
        }
        $status = proc_close($process);
        if ($quiet && $status !== 0) {
            fwrite(STDERR, $output);
        }

        return $status;
    }
}
