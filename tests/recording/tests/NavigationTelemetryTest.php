<?php

use DiffStage\Recorder\Telemetry;

it('keeps real page and query navigations while ignoring fragment changes and child frames', function () {
    Telemetry::begin();
    Telemetry::observe(['method' => '__create__', 'params' => ['type' => 'Page', 'guid' => 'page', 'initializer' => ['mainFrame' => ['guid' => 'main']]]]);
    foreach ([
        ['main', 'https://example.test/runs/one'],
        ['main', 'https://example.test/runs/one#first'],
        ['main', 'https://example.test/runs/one#second'],
        ['main', 'https://example.test/runs/one'],
        ['child', 'https://example.test/frame'],
        ['main', 'https://example.test/runs/two'],
        ['main', 'https://example.test/runs/two?token=secret-one'],
        ['main', 'https://example.test/runs/two?token=secret-two'],
        ['main', 'https://another.test/runs/two?token=secret-two'],
    ] as [$frame, $url]) {
        Telemetry::observe(['method' => 'navigated', 'guid' => $frame, 'params' => ['url' => $url]]);
    }
    expect(array_column(Telemetry::finish()['steps'], 'text'))->toBe([
        'Opened /runs/one',
        'Opened /runs/two',
        'Opened /runs/two?token=…',
        'Opened /runs/two?token=…',
        'Opened /runs/two?token=…',
    ]);
});

it('keeps a named action when retrying a failed attempt', function () {
    Telemetry::begin();
    Telemetry::action('click', ['selector' => '#save'], 'Save message');
    Telemetry::actionFailed();
    Telemetry::action('click', ['selector' => '#save']);
    $steps = Telemetry::finish()['steps'];

    expect($steps)->toHaveCount(1);
    expect($steps[0]['text'])->toBe('Clicked "Save message"');
    expect($steps[0]['attempts'])->toBe(2);
});
