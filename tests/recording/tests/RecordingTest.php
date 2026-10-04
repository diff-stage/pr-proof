<?php

use Pest\Browser\Playwright\Client;
use PrProof\Recorder;

it('records real typing and clicking', function () {
    $source = (new ReflectionClass(Client::class))->getFileName();
    expect(str_contains($source, '/overrides/'))->toBe(Recorder::enabled());

    $page = visit(getenv('PR_PROOF_TEST_URL').'/?token=query-secret');
    $page->assertSee('Recorder compatibility')
        ->type('message', 'Compatibility verified')
        ->keys('message', ['7'])
        ->click('Save message')
        ->assertSeeIn('#result', 'Compatibility verified')
        ->assertNoJavaScriptErrors();
});
