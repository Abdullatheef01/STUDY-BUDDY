/* Saved Resume Versions (Wave 1, feature #3) — XSS-safe via textContent. */
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
        var box = document.getElementById('versionError');
        if (!box) return;
        if (!msg) { box.hidden = true; box.textContent = ''; return; }
        box.hidden = false;
        box.textContent = msg;
    }

    function fmtDate(iso) {
        try { return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }); }
        catch (e) { return ''; }
    }

    var versionsCache = [];

    function renderList() {
        var box = document.getElementById('versionList');
        if (!box) return;
        box.innerHTML = '';
        if (!versionsCache.length) {
            box.appendChild(el('p', 'jd-saved-link', 'No saved versions yet — save your first one above.'));
            return;
        }
        var list = el('div', 'jd-suggest-list');
        versionsCache.forEach(function (v) {
            var card = el('div', 'jd-suggest-card');
            var head = el('div', 'jd-score-head', '');
            head.style.marginBottom = '0.4rem';
            head.appendChild(el('strong', '', v.name));
            if (v.is_default) {
                var badge = el('span', 'jd-default-badge', 'Default');
                head.appendChild(badge);
            }
            head.appendChild(el('span', 'jd-suggest-tip', fmtDate(v.created_at)));
            card.appendChild(head);
            if (v.preview) card.appendChild(el('p', 'jd-suggest-tip', v.preview + '…'));

            var row = el('div', 'jd-btn-row');
            if (!v.is_default) {
                var defBtn = el('button', 'jd-mini-btn', 'Set default');
                defBtn.type = 'button';
                defBtn.addEventListener('click', function () { setDefault(v.id); });
                row.appendChild(defBtn);
            }
            var diffBtn = el('button', 'jd-mini-btn', 'Compare');
            diffBtn.type = 'button';
            diffBtn.addEventListener('click', function () { showDiffPicker(v.id); });
            row.appendChild(diffBtn);
            var delBtn = el('button', 'jd-mini-btn jd-danger', 'Delete');
            delBtn.type = 'button';
            delBtn.addEventListener('click', function () {
                if (confirm('Delete version "' + v.name + '"?')) deleteVersion(v.id);
            });
            row.appendChild(delBtn);
            card.appendChild(row);
            list.appendChild(card);
        });
        box.appendChild(list);
    }

    function fillSelects() {
        var jdSel = document.getElementById('jdVersionSelect');
        var bSel = document.getElementById('bulletVersionSelect');
        [[jdSel, 'Choose a version…'], [bSel, 'Choose a version…']].forEach(function (pair) {
            var sel = pair[0];
            if (!sel) return;
            sel.innerHTML = '';
            var ph = document.createElement('option');
            ph.value = '';
            ph.textContent = pair[1];
            sel.appendChild(ph);
            versionsCache.forEach(function (v) {
                var opt = document.createElement('option');
                opt.value = v.id;
                opt.textContent = v.name + (v.is_default ? ' (default)' : '');
                sel.appendChild(opt);
            });
        });
    }

    function loadVersions() {
        if (!document.getElementById('versionList')) return;
        fetch('/resume-versions', { headers: csrfHeaders() })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                versionsCache = (data && data.versions) || [];
                renderList();
                fillSelects();
            })
            .catch(function () { /* list stays empty */ });
    }

    function setDefault(id) {
        fetch('/resume-versions/' + id + '/set-default', {
            method: 'POST', headers: csrfHeaders()
        }).then(function () { loadVersions(); });
    }

    function deleteVersion(id) {
        fetch('/resume-versions/' + id + '/delete', {
            method: 'POST', headers: csrfHeaders()
        }).then(function () {
            document.getElementById('versionDiff').innerHTML = '';
            loadVersions();
        });
    }

    function showDiffPicker(versionId) {
        var box = document.getElementById('versionDiff');
        box.innerHTML = '';
        var v = versionsCache.find(function (x) { return x.id === versionId; });
        var wrap = el('div', 'jd-suggest-card');
        wrap.appendChild(el('div', 'jd-suggest-section', 'Compare "' + (v ? v.name : '') + '" against…'));
        var sel = el('select', 'jd-textarea');
        sel.style.minHeight = '0';
        versionsCache.forEach(function (o) {
            if (o.id === versionId) return;
            var opt = document.createElement('option');
            opt.value = o.id;
            opt.textContent = o.name;
            sel.appendChild(opt);
        });
        if (!sel.options.length) {
            wrap.appendChild(el('p', 'jd-suggest-tip', 'Save at least two versions to compare.'));
            box.appendChild(wrap);
            return;
        }
        var go = el('button', 'jd-submit', 'Show diff');
        go.type = 'button';
        go.style.marginTop = '0.8rem';
        go.addEventListener('click', function () { fetchDiff(versionId, parseInt(sel.value, 10)); });
        wrap.appendChild(sel);
        wrap.appendChild(go);
        wrap.appendChild(el('div', 'jd-diff-out'));
        box.appendChild(wrap);
        box.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function fetchDiff(versionId, againstId) {
        var out = document.querySelector('#versionDiff .jd-diff-out');
        out.innerHTML = '<div class="jd-loading"><div class="jd-spinner"></div></div>';
        fetch('/resume-versions/' + versionId + '/diff?against=' + againstId, { headers: csrfHeaders() })
            .then(function (r) { return r.json().then(function (d) { return { s: r.status, d: d }; }); })
            .then(function (res) {
                out.innerHTML = '';
                if (res.s !== 200 || !res.d.success) {
                    out.appendChild(el('p', 'jd-error', (res.d && res.d.error) || 'Diff failed.'));
                    return;
                }
                var sum = el('p', 'jd-suggest-tip',
                    '+' + res.d.summary.added + ' lines, −' + res.d.summary.removed + ' lines vs "' + res.d.against.name + '"');
                out.appendChild(sum);
                var pre = el('div', 'jd-diff-lines');
                res.d.lines.forEach(function (ln) {
                    var div = el('div', 'jd-diff-' + ln.type, ln.text || ' ');
                    pre.appendChild(div);
                });
                out.appendChild(pre);
            })
            .catch(function () {
                out.innerHTML = '';
                out.appendChild(el('p', 'jd-error', 'Diff failed. Please try again.'));
            });
    }

    function initVersionForm() {
        var form = document.getElementById('versionForm');
        if (!form) return;
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            setError('');
            var name = document.getElementById('versionName').value.trim();
            var text = document.getElementById('versionText').value.trim();
            if (!name) { setError('Please give this version a name.'); return; }
            if (text.length < 50) { setError('Resume text looks too short to save.'); return; }
            var btn = document.getElementById('versionBtn');
            btn.disabled = true;
            fetch('/resume-versions', {
                method: 'POST',
                headers: csrfHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({ name: name, resume_text: text })
            })
                .then(function (r) { return r.json().then(function (d) { return { s: r.status, d: d }; }); })
                .then(function (res) {
                    if (res.s !== 200 || !res.d.success) {
                        setError((res.d && res.d.error) || 'Save failed. Please try again.');
                        return;
                    }
                    document.getElementById('versionName').value = '';
                    document.getElementById('versionText').value = '';
                    loadVersions();
                })
                .catch(function () { setError('Something went wrong. Please try again.'); })
                .finally(function () { btn.disabled = false; });
        });
    }

    function initJdVersionToggle() {
        var wrap = document.getElementById('jdVersionWrap');
        var form = document.getElementById('jdMatchForm');
        if (!wrap || !form) return;
        form.addEventListener('change', function (e) {
            if (e.target && e.target.name === 'resume_source') {
                wrap.hidden = e.target.value !== 'version';
            }
        });
    }

    function initBulletVersionPicker() {
        var sel = document.getElementById('bulletVersionSelect');
        var picker = document.getElementById('bulletLinePicker');
        var input = document.getElementById('bulletText');
        if (!sel || !picker || !input) return;
        sel.addEventListener('change', function () {
            picker.innerHTML = '';
            picker.hidden = true;
            if (!sel.value) return;
            fetch('/resume-versions/' + sel.value, { headers: csrfHeaders() })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (!data.success) return;
                    var lines = (data.version.resume_text || '').split('\n')
                        .map(function (l) { return l.trim(); })
                        .filter(function (l) { return l.length >= 10 && l.length <= 1000; })
                        .slice(0, 40);
                    if (!lines.length) return;
                    picker.hidden = false;
                    picker.appendChild(el('p', 'jd-suggest-tip', 'Click a line to load it into the rewriter:'));
                    var chips = el('div', 'jd-chips');
                    lines.forEach(function (ln) {
                        var chip = el('button', 'jd-line-chip', ln.length > 90 ? ln.slice(0, 90) + '…' : ln);
                        chip.type = 'button';
                        chip.title = ln;
                        chip.addEventListener('click', function () {
                            input.value = ln;
                            input.focus();
                            input.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        });
                        chips.appendChild(chip);
                    });
                    picker.appendChild(chips);
                })
                .catch(function () { /* picker stays hidden */ });
        });
    }

    function init() {
        initVersionForm();
        initJdVersionToggle();
        initBulletVersionPicker();
        loadVersions();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
