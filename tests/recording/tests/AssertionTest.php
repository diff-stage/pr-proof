<?php

use PHPUnit\Framework\ExpectationFailedException;

it('records successful delayed checks and a failed check without exposing entered values', function () {
    $page = visit(getenv('DIFF_STAGE_TEST_URL').'/?token=query-secret');
    $page->type('message', 'Disposable private message')
        ->check('terms')
        ->click('Save message')
        ->assertSeeIn('#saved', 'Message saved')
        ->assertSeeIn('#result', 'Disposable private message')
        ->assertValue('message', 'Disposable private message')
        ->assertChecked('terms')
        ->assertPathIs('/')
        ->assertButtonEnabled('Save message')
        ->assertScript('document.querySelector("#saved").textContent', 'Message saved');

    expect(fn () => $page->assertSee('Missing confirmation'))->toThrow(ExpectationFailedException::class);
    $page->assertNoJavaScriptErrors();
});
