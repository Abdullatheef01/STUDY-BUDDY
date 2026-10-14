/* AI Bullet Rewriter (Wave 1, feature #2) — XSS-safe renderer. */
(function () {
    'use strict';

    function el(tag, cls, text) {
        var node = document.createElement(tag);
        if (cls) node.className = cls;
        if (text !== undefined && text !== null) node.textContent = text;
        return node;
    }

    function setError(msg) {
        var box = document.getElementById('bulletError');
        if (!box) return;
        if (!msg) { box.hidden = true; box.textContent = ''; return; }
        box.hidden = false;
        box.textContent = msg;
    }

    function renderRewrites(data, box) {
        box.innerHTML = '';
        var badge = el('div', 'jd-score-hero');
        var title = el('div', 'jd-score-label', data.ai_powered ? 'Rewrites ready — AI-polished' : 'Rewrites ready');
        badge.appendChild(title);
        box.appendChild(badge);

        var list = el('div', 'jd-suggest-list');
        (data.rewrites || []).forEach(function (v) {
            var card = el('div', 'jd-suggest-card');
            card.appendChild(el('div', 'jd-suggest-section', v.label || 'Rewrite'));
            card.appendChild(el('p', 'jd-suggest-fix', v.text || ''));
            if (v.tip) card.appendChild(el('p', 'jd-suggest-tip', v.tip));

            var copyBtn = el('button', 'jd-copy-btn', 'Copy');
            copyBtn.type = 'button';
            copyBtn.addEventListener('click', function () {
                var done = function () {
                    copyBtn.textContent = 'Copied!';
                    setTimeout(function () { copyBtn.textContent = 'Copy'; }, 1500);
                };
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(v.text || '').then(done, done);
                } else {
                    var ta = document.createElement('textarea');
                    ta.value = v.text || '';
                    document.body.appendChild(ta);
                    ta.select();
                    try { document.execCommand('copy'); } catch (e) { /* noop */ }
                    document.body.removeChild(ta);
                    done();
                }
            });
            card.appendChild(copyBtn);
            list.appendChild(card);
        });
        box.appendChild(list);

        var note = el('p', 'jd-saved-link', 'Saved to your dashboard history.');
        box.appendChild(note);
    }

    function init() {
        var form = document.getElementById('bulletForm');
        if (!form) return;
        var input = document.getElementById('bulletText');
        var btn = document.getElementById('bulletBtn');
        var box = document.getElementById('bulletResult');

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            setError('');
            var bullet = (input.value || '').trim();
            if (!bullet) { setError('Please enter a bullet to rewrite.'); return; }

            var tokenMeta = document.querySelector('meta[name="csrf-token"]');
            var headers = { 'Content-Type': 'application/json' };
            if (tokenMeta) headers['X-CSRFToken'] = tokenMeta.getAttribute('content');

            btn.disabled = true;
            btn.querySelector('span').textContent = 'Rewriting…';
            box.innerHTML = '<div class="jd-loading"><div class="jd-spinner"></div>'
                + '<p>Strengthening your bullet…</p></div>';

            fetch('/rewrite-bullet', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({ bullet_text: bullet })
            })
                .then(function (resp) {
                    return resp.json().then(function (data) {
                        return { status: resp.status, data: data };
                    });
                })
                .then(function (out) {
                    if (out.status === 401) {
                        setError('Please log in to rewrite bullets.');
                        box.innerHTML = '';
                        return;
                    }
                    if (out.status === 429) {
                        setError('Too many rewrites — please try again in a little while.');
                        box.innerHTML = '';
                        return;
                    }
                    if (!out.data || !out.data.success) {
                        setError((out.data && out.data.error) || 'Rewrite failed. Please try again.');
                        box.innerHTML = '';
                        return;
                    }
                    renderRewrites(out.data, box);
                    box.scrollIntoView({ behavior: 'smooth', block: 'start' });
                })
                .catch(function () {
                    setError('Something went wrong. Please check your connection and try again.');
                    box.innerHTML = '';
                })
                .finally(function () {
                    btn.disabled = false;
                    btn.querySelector('span').textContent = 'Rewrite My Bullet';
                });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
