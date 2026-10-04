(() => {
    let cursor;
    function show(event, clicked) {
        if (!cursor) {
            cursor = document.createElement('div');
            cursor.setAttribute('aria-hidden', 'true');
            cursor.style.cssText = 'position:fixed;pointer-events:none;z-index:2147483647;width:22px;height:22px;border:3px solid #2563eb;border-radius:50%;background:#ffffff80;transform:translate(-50%,-50%);box-sizing:border-box;';
            document.documentElement.appendChild(cursor);
        }
        cursor.style.left = `${event.clientX}px`;
        cursor.style.top = `${event.clientY}px`;
        if (clicked) {
            cursor.animate([
                { transform: 'translate(-50%,-50%) scale(1)', background: '#2563ebaa' },
                { transform: 'translate(-50%,-50%) scale(2)', background: '#2563eb00' },
            ], { duration: 450 });
        }
    }
    document.addEventListener('pointermove', event => show(event, false), { capture: true, passive: true });
    document.addEventListener('pointerdown', event => show(event, true), { capture: true, passive: true });
})();
