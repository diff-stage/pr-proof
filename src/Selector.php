<?php

declare(strict_types=1);

namespace DiffStage\Recorder;

/**
 * Turns a Playwright selector into the name a person would use for the element.
 */
final class Selector
{
    public static function labelExpression(): string
    {
        return <<<'JS'
            (element) => {
                const text = value => (value || '').replace(/\s+/g, ' ').trim();
                const labelledBy = (element.getAttribute('aria-labelledby') || '').split(/\s+/)
                    .map(id => element.ownerDocument.getElementById(id)?.textContent || '').join(' ');
                const label = text(element.getAttribute('aria-label')) || text(labelledBy)
                    || text(Array.from(element.labels || []).map(label => label.textContent).join(' '));
                if (label) return label;
                if (element.matches('button, a, [role="button"], [role="link"], option')) {
                    const content = text(element.innerText);
                    if (content) return content;
                }
                return text(element.getAttribute('title')) || text(element.getAttribute('placeholder'));
            }
            JS;
    }

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
