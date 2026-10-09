<?php

use DiffStage\Recorder\Recorder;

it('moves the pointer visibly before clicking a scrolled control', function () {
    $page = visit(getenv('DIFF_STAGE_TEST_URL').'/?token=query-secret');
    $page->script(<<<'JS'
        () => {
            document.body.style.minHeight = '1600px';
            const button = document.querySelector('button');
            button.style.cssText = 'position:absolute;top:1200px;left:650px;width:200px;height:70px';
            document.querySelector('#result').style.cssText = 'position:absolute;top:1280px;left:650px';
            window.moves = [];
            document.addEventListener('pointermove', e => window.moves.push({ x: e.clientX, y: e.clientY, at: performance.now() }));
            button.addEventListener('pointerdown', e => {
                const cursor = document.querySelector('[data-diff-stage-cursor]');
                window.clickPoint = { x: e.clientX, y: e.clientY, tipX: cursor ? parseFloat(cursor.style.left) + 1 : null, tipY: cursor ? parseFloat(cursor.style.top) + 1 : null };
            });
        }
        JS);

    $page->type('message', 'Compatibility verified')
        ->keys('message', ['7']);
    $page->script('() => window.moves = []');
    $page->click('Save message')
        ->assertSeeIn('#result', 'Compatibility verified')
        ->assertNoJavaScriptErrors();

    if (Recorder::enabled() && ! Recorder::fast()) {
        $moves = $page->script('() => window.moves');
        expect(count($moves))->toBeGreaterThan(15);
        expect(end($moves)['at'] - $moves[0]['at'])->toBeGreaterThan(250);
        $click = $page->script('() => window.clickPoint');
        expect($click['tipX'])->toEqual($click['x']);
        expect($click['tipY'])->toEqual($click['y']);
        expect($page->script('() => window.scrollY'))->toBeGreaterThan(0);
        $start = $moves[0];
        $end = end($moves);
        $deviations = array_map(fn (array $move): float => abs(($end['x'] - $start['x']) * ($move['y'] - $start['y']) - ($end['y'] - $start['y']) * ($move['x'] - $start['x'])) / hypot($end['x'] - $start['x'], $end['y'] - $start['y']), $moves);
        expect(max($deviations))->toBeGreaterThan(5);
    }
});

it('acts through the page straight after opening it', function () {
    $page = visit(getenv('DIFF_STAGE_TEST_URL').'/?token=query-secret');
    $page->page()->getByRole('textbox', ['name' => 'Message'])->fill('Compatibility verified');

    $page->keys('message', ['7'])
        ->click('Save message')
        ->assertSeeIn('#result', 'Compatibility verified')
        ->assertNoJavaScriptErrors();
});

it('opens a menu through real pointer movement', function () {
    $page = visit(getenv('DIFF_STAGE_TEST_URL').'/?token=query-secret');
    $page->script(<<<'JS'
        () => {
            const menu = document.createElement('div');
            menu.innerHTML = '<button id="menu">Actions</button><button id="choice" style="display:none">Choose message</button>';
            menu.style.cssText = 'position:absolute;top:350px;left:700px;padding:20px';
            menu.addEventListener('pointerenter', () => document.querySelector('#choice').style.display = 'inline-block');
            document.body.appendChild(menu);
            document.querySelector('#choice').onclick = () => document.querySelector('#saved').textContent = 'Menu choice saved';
        }
        JS);

    $page->type('message', 'Compatibility verified')
        ->keys('message', ['7'])
        ->hover('#menu')
        ->click('Choose message')
        ->assertSee('Menu choice saved')
        ->assertNoJavaScriptErrors();
});

it('keeps touch recordings free of a mouse cursor', function () {
    $page = visit(getenv('DIFF_STAGE_TEST_URL').'/?token=query-secret')->on()->mobile()->assertSee('Recorder compatibility');

    $page->type('message', 'Compatibility verified')
        ->keys('message', ['7'])
        ->click('Save message')
        ->assertSeeIn('#result', 'Compatibility verified')
        ->assertNoJavaScriptErrors();

    expect($page->script('() => document.querySelector("[data-diff-stage-cursor]") === null'))->toBeTrue();
});

it('lands on an explicit click position inside a bordered control', function () {
    $page = visit(getenv('DIFF_STAGE_TEST_URL').'/?token=query-secret');
    $page->type('message', 'Compatibility verified')->keys('message', ['7']);
    $page->script(<<<'JS'
        () => {
            const button = document.querySelector('button');
            button.style.cssText = 'margin:250px 400px;width:220px;height:90px;border:8px solid black';
            window.moves = [];
            document.addEventListener('pointermove', e => window.moves.push({ x: e.clientX, y: e.clientY }));
            button.addEventListener('pointerdown', e => window.clickPoint = { x: e.clientX, y: e.clientY });
        }
        JS);

    $page->page()->locator('button')->click(['position' => ['x' => 17, 'y' => 23]]);
    $page->assertSeeIn('#result', 'Compatibility verified')->assertNoJavaScriptErrors();

    if (Recorder::fast()) {
        expect($page->script('() => document.querySelector("[data-diff-stage-cursor]") === null'))->toBeTrue();
        expect(count($page->script('() => window.moves')))->toBeLessThan(3);
        file_put_contents(Recorder::pathForCurrentTest().'.expected', json_encode($page->script('() => window.clickPoint')));
    }

    if (Recorder::enabled() && ! Recorder::fast()) {
        $moves = $page->script('() => window.moves');
        $click = $page->script('() => window.clickPoint');
        $last = end($moves);
        $before = $moves[count($moves) - 2];
        expect(abs($before['x'] - $click['x']))->toBeLessThan(2);
        expect(abs($before['y'] - $click['y']))->toBeLessThan(2);
        expect(abs($last['x'] - $click['x']))->toBeLessThan(1);
        expect(abs($last['y'] - $click['y']))->toBeLessThan(1);
    }
});

it('shows one cursor while clicking inside an iframe', function () {
    $page = visit(getenv('DIFF_STAGE_TEST_URL').'/?token=query-secret');
    $page->type('message', 'Compatibility verified')->keys('message', ['7']);
    $page->script(<<<'JS'
        () => {
            const frame = document.createElement('iframe');
            frame.style.cssText = 'position:absolute;left:650px;top:300px;width:350px;height:250px';
            frame.srcdoc = '<button style="margin:80px" onclick="parent.document.querySelector(\'#saved\').textContent = \'Frame choice saved\'">Save in frame</button>';
            document.body.appendChild(frame);
        }
        JS);

    $page->page()->locator('iframe >> internal:control=enter-frame >> button')->click();
    $page->assertSee('Frame choice saved')->assertNoJavaScriptErrors();

    if (Recorder::enabled() && ! Recorder::fast()) {
        expect($page->script(<<<'JS'
            () => {
                const frame = document.querySelector('iframe');
                const parentCursor = document.querySelector('[data-diff-stage-cursor]');
                const frameCursor = frame.contentDocument.querySelector('[data-diff-stage-cursor]');
                return { parent: parentCursor.style.visibility, child: frameCursor.style.visibility };
            }
            JS))->toBe(['parent' => 'hidden', 'child' => 'visible']);
    }
});
