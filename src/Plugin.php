<?php

declare(strict_types=1);

namespace DiffStage\Recorder;

use Pest\Contracts\Plugins\HandlesArguments;

/**
 * Records a readable video of each Pest browser test.
 *
 *   --record-videos[=DIR]           Record into DIR (default: tests/Browser/Videos)
 *   --record-videos-only=A.php,B.php  Only record tests from these files
 *   --record-videos-pause=MS        Pause before each action (default: 700)
 */
final class Plugin implements HandlesArguments
{
    public function handleArguments(array $arguments): array
    {
        $directory = $this->takeOption($arguments, '--record-videos', 'tests/Browser/Videos');

        if ($directory === null) {
            return $arguments;
        }

        $only = $this->takeOption($arguments, '--record-videos-only', '');
        $pause = $this->takeOption($arguments, '--record-videos-pause', '700') ?? '700';

        Recorder::enable(
            $directory,
            $only === null ? null : array_values(array_filter(explode(',', $only))),
            (int) $pause,
        );

        return $arguments;
    }

    /**
     * Removes an option from the arguments and returns its value, or null when absent.
     *
     * @param  array<int, string>  $arguments
     */
    private function takeOption(array &$arguments, string $name, string $default): ?string
    {
        foreach ($arguments as $index => $argument) {
            if ($argument === $name || str_starts_with($argument, "{$name}=")) {
                unset($arguments[$index]);
                $arguments = array_values($arguments);

                return str_contains($argument, '=') ? substr($argument, strlen($name) + 1) : $default;
            }
        }

        return null;
    }
}
