// Workforce mode switch (navbar day/night-style toggle).
//
// The server stamps the mode on <html data-app-mode="work|clock"> and renders
// the appropriate navbar set + palette entirely by URL path (workforce pages ->
// "work", everything else -> "clock"). This file only wires the single navbar
// switch control: clicking it navigates to the other mode's landing page. The
// palette/nav are always driven by the path so directly visiting a workforce
// URL always shows the workforce theme and navigation.
(() => {
    'use strict';

    var root = document.documentElement;

    function currentMode() {
        return root.getAttribute('data-app-mode') || 'clock';
    }

    // Landing page for the target mode, resolved from data attributes on the
    // hidden spans rendered in base.html.
    function homeFor(mode) {
        if (mode === 'work') {
            var el = document.getElementById('appModeWorkHome');
            return el ? el.getAttribute('data-url') : '/work/tasks';
        }
        var clock = document.getElementById('appModeClockHome');
        return clock ? clock.getAttribute('data-url') : '/';
    }

    function wireSwitch() {
        var btn = document.getElementById('appModeSwitch');
        if (!btn) return;
        btn.addEventListener('click', function () {
            var target = currentMode() === 'work' ? 'clock' : 'work';
            window.location.href = homeFor(target);
        });
    }

    function init() {
        wireSwitch();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();