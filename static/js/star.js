/* STAR Answer Builder (Wave 2, feature #17). XSS-safe: textContent only. */
(function () {
    'use strict';

    var SECTIONS = ['situation', 'task', 'action', 'result'];

    function el(tag, cls, text) {
        var node = document.createElement(tag);
        if (cls) node.className = cls;
        if (text !== undefined && text !== null) node.textContent = text;
        return node;
    }

    function csrfHeaders(extra) {
        var headers = extra || {};
        var m = document.querySelector('meta[name="csrf-token"]');
        if (m) headers['X-CSRFToken'] = m.getAttribute('content');
        return headers;
    }

    function showError(msg) {
        var box = document.getElementById('st-error');
        box.textContent = msg;
        box.style.display = 'block';
    }

    function hideError() {
        document.getElementById('st-error').style.display = 'none';
    }

    function collectDraft() {
        var d = { competency: document.getElementById('sel-comp').value };
        SECTIONS.forEach(function (s) {
            d[s] = document.getElementById('area-' + s).value;
        });
        return d;
    }

    var lastResult = null;

    function scoreDraft() {
        hideError();
        var btn = document.getElementById('btn-score');
        btn.disabled = true;
        btn.textContent = 'Scoring…';
        fetch('/star/score', {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(collectDraft()),
        }).then(function (r) {
            return r.json().then(function (d) { return { status: r.status, body: d }; });
        }).then(function (res) {
            btn.disabled = false;
            btn.textContent = 'Score My Answer';
            if (res.status !== 200 || !res.body.success) {
                showError((res.body && res.body.error) || 'Scoring failed.');
                return;
            }
            lastResult = res.body;
            renderScores(res.body);
        }).catch(function () {
            btn.disabled = false;
            btn.textContent = 'Score My Answer';
            showError('Network error. Please try again.');
        });
    }

    function renderScores(data) {
        var scores = data.scores;
        SECTIONS.forEach(function (s) {
            var box = document.getElementById('score-' + s);
            var info = scores.sections[s];
            box.style.display = 'flex';
            box.querySelector('.st-score-num').textContent = info.score + '/25';
            box.querySelector('.st-bar > div').style.width = (info.score / 25 * 100) + '%';
            var ul = document.getElementById('sugg-' + s);
            ul.innerHTML = '';
            ul.style.display = 'block';
            (data.suggestions[s] || []).forEach(function (sg) {
                ul.appendChild(el('li', null, sg));
            });
        });
        var ob = document.getElementById('overall-box');
        ob.style.display = 'block';
        var num = document.getElementById('overall-num');
        num.textContent = scores.overall;
        num.style.color = scores.overall >= 70 ? '#10b981' :
            (scores.overall >= 45 ? '#f59e0b' : '#ef4444');
        document.getElementById('ai-badge').textContent =
            data.ai_powered ? 'Suggestions polished by AI' : 'Rule-based suggestions (AI unavailable)';
        ob.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function saveDraft() {
        hideError();
        var btn = document.getElementById('btn-save');
        btn.disabled = true;
        var payload = collectDraft();
        if (lastResult) {
            payload.scores = lastResult.scores;
            payload.suggestions = lastResult.suggestions;
            payload.ai_powered = lastResult.ai_powered;
        }
        fetch('/star/save', {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(payload),
        }).then(function (r) {
            return r.json().then(function (d) { return { status: r.status, body: d }; });
        }).then(function (res) {
            btn.disabled = false;
            if (res.status !== 200 || !res.body.success) {
                showError((res.body && res.body.error) || 'Save failed.');
                return;
            }
            btn.textContent = 'Saved ✓';
            setTimeout(function () { btn.textContent = 'Save Draft'; }, 2000);
        }).catch(function () {
            btn.disabled = false;
            showError('Network error. Please try again.');
        });
    }

    function copyAnswer() {
        var d = collectDraft();
        var parts = SECTIONS.map(function (s) {
            return s.toUpperCase() + ':\n' + (d[s] || '(empty)');
        });
        var text = parts.join('\n\n');
        function done() {
            var btn = document.getElementById('btn-copy');
            btn.textContent = 'Copied ✓';
            setTimeout(function () { btn.textContent = 'Copy Full Answer'; }, 2000);
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(done, function () { showError('Copy failed.'); });
        } else {
            var ta = document.createElement('textarea');
            ta.value = text;
            document.body.appendChild(ta);
            ta.select();
            try { document.execCommand('copy'); done(); }
            catch (e) { showError('Copy failed.'); }
            document.body.removeChild(ta);
        }
    }

    function loadExamples(comp) {
        var box = document.getElementById('examples-list');
        box.innerHTML = '';
        var loading = el('p', null, 'Loading examples…');
        loading.style.color = 'var(--text-muted, #94a3b8)';
        box.appendChild(loading);
        var url = '/api/star/examples' + (comp ? '?competency=' + encodeURIComponent(comp) : '');
        fetch(url).then(function (r) { return r.json(); }).then(function (d) {
            box.innerHTML = '';
            document.getElementById('ex-count').textContent = d.count;
            d.examples.forEach(function (e) {
                var det = el('details', 'st-ex');
                var sum = el('summary', null, e.title);
                det.appendChild(sum);
                var body = el('div', 'body');
                [['Situation', e.situation], ['Task', e.task],
                 ['Action', e.action], ['Result', e.result]].forEach(function (pair) {
                    var p = el('p');
                    p.appendChild(el('strong', null, pair[0] + ': '));
                    p.appendChild(el('span', null, pair[1]));
                    body.appendChild(p);
                });
                var whyT = el('p');
                whyT.appendChild(el('strong', null, 'Why it works:'));
                body.appendChild(whyT);
                var ul = el('ul', 'why');
                (e.why_it_works || []).forEach(function (w) {
                    ul.appendChild(el('li', null, w));
                });
                body.appendChild(ul);
                var use = el('button', 'st-btn st-btn-ghost st-use-ex', 'Use as template');
                use.addEventListener('click', function () {
                    document.getElementById('area-situation').value = '';
                    document.getElementById('area-task').value = '';
                    document.getElementById('area-action').value = '';
                    document.getElementById('area-result').value = '';
                    document.getElementById('builder-card').scrollIntoView({ behavior: 'smooth' });
                });
                body.appendChild(use);
                det.appendChild(body);
                box.appendChild(det);
            });
            if (!d.examples.length) {
                box.appendChild(el('p', null, 'No examples found.'));
            }
        }).catch(function () {
            box.innerHTML = '';
            box.appendChild(el('p', null, 'Could not load examples.'));
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('[data-toggle]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var box = document.getElementById('ex-' + btn.getAttribute('data-toggle'));
                var open = box.classList.toggle('open');
                btn.textContent = open ? 'Hide examples' : 'Show good vs weak example';
            });
        });
        var scoreBtn = document.getElementById('btn-score');
        if (scoreBtn) scoreBtn.addEventListener('click', scoreDraft);
        var saveBtn = document.getElementById('btn-save');
        if (saveBtn) saveBtn.addEventListener('click', saveDraft);
        var copyBtn = document.getElementById('btn-copy');
        if (copyBtn) copyBtn.addEventListener('click', copyAnswer);
        var compSel = document.getElementById('sel-ex-comp');
        if (compSel) {
            compSel.addEventListener('change', function () { loadExamples(compSel.value); });
            loadExamples('');
        }
    });
})();
