(() => {
    if (navigator.maxTouchPoints > 0) return;
    let cursor;
    function show(event, clicked) {
        if (event.pointerType === 'touch') return;
        if (event.target.tagName === 'IFRAME') {
            if (cursor) cursor.style.visibility = 'hidden';
            return;
        }
        if (!cursor) {
            cursor = document.createElement('div');
            cursor.setAttribute('aria-hidden', 'true');
            cursor.dataset.diffStageCursor = '';
            cursor.style.cssText = 'position:fixed;pointer-events:none;z-index:2147483647;width:24px;height:30px;contain:layout style;';
            cursor.attachShadow({ mode: 'closed' }).innerHTML = '<svg width="24" height="30" viewBox="0 0 24 30" style="overflow:visible;filter:drop-shadow(0 1px 1px #0008)"><path d="M1 1 L1 23 L7 17 L12 28 L16 26 L11 15 L20 15 Z" fill="white" stroke="#111827" stroke-width="1.5" stroke-linejoin="round"/></svg>';
            document.documentElement.appendChild(cursor);
        }
        cursor.style.visibility = 'visible';
        cursor.style.left = `${event.clientX - 1}px`;
        cursor.style.top = `${event.clientY - 1}px`;
        if (clicked) {
            const ring = document.createElement('div');
            ring.style.cssText = `position:fixed;pointer-events:none;z-index:2147483646;left:${event.clientX}px;top:${event.clientY}px;width:18px;height:18px;border:2px solid #2563eb;border-radius:50%;transform:translate(-50%,-50%);`;
            document.documentElement.appendChild(ring);
            ring.animate([
                { transform: 'translate(-50%,-50%) scale(0.6)', opacity: 0.8 },
                { transform: 'translate(-50%,-50%) scale(1.8)', opacity: 0 },
            ], { duration: 350 }).onfinish = () => ring.remove();
        }
    }
    document.addEventListener('pointermove', event => show(event, false), { capture: true, passive: true });
    document.addEventListener('pointerout', event => {
        if (cursor && (!event.relatedTarget || event.relatedTarget.tagName === 'IFRAME')) cursor.style.visibility = 'hidden';
    }, { capture: true, passive: true });
    document.addEventListener('pointerdown', event => show(event, true), { capture: true, passive: true });
})();
