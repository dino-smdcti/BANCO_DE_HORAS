// Workforce "magic button" mode switch.
//
// The server stamps the mode on <html data-app-mode="work|clock"> by path
// (workforce pages -> "work", everything else -> "clock"). This file adds a
// floating toggle that lets the user override the automatic mode and persists
// the choice in localStorage so it survives reloads. The clock experience keeps
// the default brand; the workforce area uses the [data-app-mode="work"] palette.
(() => {
    'use strict';

    var STORAGE_KEY = 'bh_app_mode';
    var root = document.documentElement;

    function serverMode() {
        return root.getAttribute('data-app-mode') || 'clock';
    }

    function currentMode() {
        return root.getAttribute('data-app-mode') || 'clock';
    }

    function applyMode(mode) {
        root.setAttribute('data-app-mode', mode);
        try { window.localStorage.setItem(STORAGE_KEY, mode); } catch (e) { /* ignore */ }
    }

    function readStored() {
        try { return window.localStorage.getItem(STORAGE_KEY); } catch (e) { return null; }
    }

    // Landing page for each mode, resolved at runtime from data attributes.
    function homeFor(mode) {
        if (mode === 'work') {
            var el = document.getElementById('appModeWorkHome');
            return el ? el.getAttribute('data-url') : '/work/tasks';
        }
        var clock = document.getElementById('appModeClockHome');
        return clock ? clock.getAttribute('data-url') : '/';
    }

    function buildToggle() {
        if (document.getElementById('appModeToggle')) return;
        var btn = document.createElement('button');
        btn.id = 'appModeToggle';
        btn.type = 'button';
        btn.title = 'Alternar entre Banco de Horas e Workforce';
        btn.setAttribute('aria-label', btn.title);
        btn.innerHTML = '<i class="bi bi-arrow-left-right"></i>';
        btn.addEventListener('click', function () {
            var next = currentMode() === 'work' ? 'clock' : 'work';
            window.location.href = homeFor(next);
        });
        document.body.appendChild(btn);
    }

    // Restore a persisted manual override, preferring the server default unless
    // the user has explicitly opted into the branch palette on work pages.
    function init() {
        var stored = readStored();
        if (stored === 'clock') {
            // User prefers the branch look everywhere, including work pages.
            applyMode('clock');
        } else {
            applyMode(serverMode());
        }
        buildToggle();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();