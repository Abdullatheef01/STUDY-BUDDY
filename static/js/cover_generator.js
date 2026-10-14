/* Cover Letter + Cold Outreach Generator (Wave 1, feature #4). XSS-safe. */
(function () {
    'use strict';

    function el(tag, cls, text) {
        var node = document.createElement(tag);
        if (cls) node.className = cls;
        if (text !== undefined && text !== null) node.textContent = text;
        return node;
    }

    function csrfHeaders(extra) {
        var headers = extra || {};
        var tokenMeta = document.querySelector('meta[name="csrf-token"]');
        if (tokenMeta) headers['X-CSRFToken'] = tokenMeta.getAttribute('content');
        return headers;
    }

    function setError(msg) {
        var box = document.getElementById('coverError');
        if (!box) return;
        if (!msg) { box.hidden = true; box.textContent = ''; return; }
        box.hidden = false;
        box.textContent = msg;
    }

    function docCard(title, content) {
        var card = el('div', 'jd-suggest-card');
        var head = el('div', 'jd-score-head', '');
        head.style.marginBottom = '0.6rem';
        head.appendChild(el('strong', '', title));
        var copyBtn = el('button', 'jd-mini-btn', 'Copy');
        copyBtn.type = 'button';
        copyBtn.addEventListener('click', function () {
            var done = function () {
                copyBtn.textContent = 'Copied!';
                setTimeout(function () { copyBtn.textContent = 'Copy'; }, 1500);
            };
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(content).then(done, done);
            } else {
                var ta = document.createElement('textarea');
                ta.value = content;
                document.body.appendChild(ta);
                ta.select();
                try { document.execCommand('copy'); } catch (e) { /* noop */ }
                document.body.removeChild(ta);
                done();
            }
        });
        head.appendChild(copyBtn);
        card.appendChild(head);
        var body = el('div', 'jd-doc-body', content);
        card.appendChild(body);
        return card;
    }

    function renderDocs(data, box) {
        box.innerHTML = '';
        var badge = el('div', 'jd-score-hero');
        badge.appendChild(el('div', 'jd-score-label',
            data.ai_powered ? 'Documents ready — AI-tailored' : 'Documents ready'));
        box.appendChild(badge);
        var list = el('div', 'jd-suggest-list');
        list.appendChild(docCard('Cover Letter', data.cover_letter || ''));
        list.appendChild(docCard('Cold Outreach (LinkedIn / email)', data.outreach || ''));
        box.appendChild(list);
        box.appendChild(el('p', 'jd-saved-link', 'Saved to your dashboard history.'));
    }

    function loadVersionOptions() {
        var sel = document.getElementById('coverVersionSelect');
        if (!sel) return;
        fetch('/resume-versions', { headers: csrfHeaders() })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                (data.versions || []).forEach(function (v) {
                    var opt = document.createElement('option');
                    opt.value = v.id;
                    opt.textContent = v.name + (v.is_default ? ' (default)' : '');
                    sel.appendChild(opt);
                });
            })
            .catch(function () { /* select keeps the default option */ });
    }

    function init() {
        var form = document.getElementById('coverForm');
        if (!form) return;
        loadVersionOptions();
        var box = document.getElementById('coverResult');
        var btn = document.getElementById('coverBtn');

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            setError('');
            var jdText = document.getElementById('coverJdText').value.trim();
            if (!jdText) { setError('Please paste the job description or describe the role.'); return; }
            var toneEl = form.querySelector('input[name="tone"]:checked');
            var versionId = document.getElementById('coverVersionSelect').value || null;

            btn.disabled = true;
            btn.querySelector('span').textContent = 'Generating…';
            box.innerHTML = '<div class="jd-loading"><div class="jd-spinner"></div>'
                + '<p>Writing your cover letter and outreach message…</p></div>';

            fetch('/generate-cover', {
                method: 'POST',
                headers: csrfHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({ jd_text: jdText, tone: toneEl ? toneEl.value : 'professional', version_id: versionId })
            })
                .then(function (resp) {
                    return resp.json().then(function (data) {
                        return { status: resp.status, data: data };
                    });
                })
                .then(function (out) {
                    if (out.status === 401) {
                        setError('Please log in to generate documents.');
                        box.innerHTML = '';
                        return;
                    }
                    if (out.status === 429) {
                        setError('Too many requests — please try again in a little while.');
                        box.innerHTML = '';
                        return;
                    }
                    if (!out.data || !out.data.success) {
                        setError((out.data && out.data.error) || 'Generation failed. Please try again.');
                        box.innerHTML = '';
                        return;
                    }
                    renderDocs(out.data, box);
                    box.scrollIntoView({ behavior: 'smooth', block: 'start' });
                })
                .catch(function () {
                    setError('Something went wrong. Please check your connection and try again.');
                    box.innerHTML = '';
                })
                .finally(function () {
                    btn.disabled = false;
                    btn.querySelector('span').textContent = 'Generate Documents';
                });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
