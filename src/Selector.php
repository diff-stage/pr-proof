<?php

declare(strict_types=1);

namespace PrProof;

/**
 * Turns a Playwright selector into the name a person would use for the element.
 */
final class Selector
{
    public static function describe(string $selector): string
    {
        if ($selector === '') {
            return '';
        }

        $patterns = [
            '/internal:role=\w+\[name="(.+?)"[si]?\]/',
            '/internal:(?:text|label|attr=\[placeholder)="(.+?)"[si]?/',
            '/aria-label[\^\*\$]?="(.+?)"/',
            '/:has-text\("(.+?)"\)/',
            '/\[placeholder[\^\*\$]?="(.+?)"\]/',
            '/\[name="(.+?)"\]/',
            '/^text=(.+)$/',
        ];

        foreach ($patterns as $pattern) {
            if (preg_match($pattern, $selector, $match)) {
                return '"'.stripslashes($match[1]).'"';
            }
        }

        return '`'.(mb_strlen($selector) > 60 ? mb_substr($selector, 0, 60).'…' : $selector).'`';
    }
}
