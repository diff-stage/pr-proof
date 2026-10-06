<?php

it('names CSS targets and ignores fragment changes in recorded steps', function (bool $mobile) {
    $page = visit(getenv('DIFF_STAGE_TEST_URL').'/?token=query-secret', ['viewport' => ['width' => 800, 'height' => 600], 'hasTouch' => $mobile]);
    $page->script(<<<'JS'
        () => {
            document.querySelector('button').id = 'save';
            const controls = document.createElement('div');
            controls.innerHTML = '<button id="settings" aria-label="Player settings">⚙</button><label id="seek-label">Playback position</label><input id="seek" type="range" aria-labelledby="seek-label"><input id="private" placeholder="Private message"><button id="echo">Echo message</button><button id="unnamed"></button>';
            document.body.appendChild(controls);
            document.querySelector('#settings').onclick = () => {
                const count = Number(document.body.dataset.clicks || 0) + 1;
                document.body.dataset.clicks = count;
                history.replaceState(null, '', '#recording-' + count);
            };
        }
        JS);
    if ($mobile) {
        expect($page->script('() => navigator.maxTouchPoints'))->toBeGreaterThan(0);
    }
    $page->type('message', 'Compatibility verified')->keys('message', ['7'])
        ->click('#save')->assertSeeIn('#result', 'Compatibility verified')
        ->click('#settings')->click('#settings')
        ->hover('#seek')
        ->type('#private', 'Disposable private message');
    $page->script('() => document.querySelector("#echo").textContent = document.querySelector("#private").value');
    $page->click('#echo')->click('#unnamed')
        ->assertScript('document.body.dataset.clicks', '2')
        ->assertNoJavaScriptErrors();
})->with(['desktop' => false, 'touch' => true]);
