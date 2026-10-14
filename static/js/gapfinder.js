/* Research-gap finder UI. */
(function () {
    'use strict';
    function csrfHeaders(extra) {
        var headers = extra || {};
        var m = document.querySelector('meta[name="csrf-token"]');
        if (m) headers['X-CSRFToken'] = m.getAttribute('content');
        return headers;
    }
    function $(id) { return document.getElementById(id); }
    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    function showError(msg) {
        var e = $('gf-error');
        e.textContent = msg; e.style.display = 'block';
    }
    function setStatus(msg) {
        var s = $('gf-status');
        if (!msg) { s.style.display = 'none'; return; }
        s.textContent = msg; s.style.display = 'inline-flex';
    }

    function renderReport(report) {
        var wrap = $('gf-results-wrap'), box = $('gf-results');
        wrap.style.display = 'block';
        var gaps = report.gaps || [];
        $('gf-count').textContent = gaps.length + ' gap' + (gaps.length === 1 ? '' : 's') + ' found';
        if (!gaps.length) {
            box.innerHTML = '<div class="b-card"><p style="color:var(--b-muted);margin:0;">' +
                esc(report.note || 'No gaps detected in this collection.') + '</p></div>';
        } else {
            box.innerHTML = gaps.map(function (g) {
                var ev = (g.evidence || []).map(function (e) {
                    return '<li>[ ' + esc(e.doc) + ', p.' + esc(e.page) + ' ] — ' + esc(e.excerpt) + '</li>';
                }).join('');
                var qs = (g.suggested_questions || []).map(function (q) {
                    return '<li>' + esc(q) + '</li>';
                }).join('');
                return '<article class="b-card b-card--lite">' +
                    '<span class="b-tag">' + esc(g.type || 'gap') + '</span>' +
                    '<h3 style="margin:.4rem 0;">' + esc(g.title) + '</h3>' +
                    (ev ? '<p style="color:var(--b-muted);font-size:.85rem;margin:.3rem 0;">Evidence:</p><ul style="color:var(--b-muted);font-size:.85rem;">' + ev + '</ul>' : '') +
                    (qs ? '<p style="color:var(--b-muted);font-size:.85rem;margin:.3rem 0;">Suggested questions:</p><ul style="font-size:.9rem;">' + qs + '</ul>' : '') +
                    '</article>';
            }).join('');
        }
        var next = report.next_papers || [];
        if (next.length) {
            box.innerHTML += '<div class="b-card"><div class="b-sec-head" style="margin-top:0;"><h2>Papers to <span class="b-grad">read next</span></h2></div><ul>' +
                next.map(function (p) {
                    return '<li><strong>' + esc(p.title) + '</strong>' +
                        (p.year ? ' (' + esc(p.year) + ')' : '') +
                        (p.reason ? ' <span style="color:var(--b-muted);font-size:.85rem;">— ' + esc(p.reason) + '</span>' : '') + '</li>';
                }).join('') + '</ul></div>';
        }
        wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    var btn = $('gf-analyze');
    if (!btn) return;
    btn.addEventListener('click', function () {
        $('gf-error').style.display = 'none';
        var ids = Array.prototype.map.call(
            document.querySelectorAll('.gf-doc:checked'),
            function (c) { return parseInt(c.value, 10); }
        ).filter(function (n) { return !isNaN(n); });
        btn.disabled = true;
        setStatus('Analyzing…');
        fetch('/research/api/gaps/analyze', {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ doc_ids: ids })
        })
        .then(function (r) { return r.json().catch(function () { return { error: 'Bad response' }; }); })
        .then(function (data) {
            btn.disabled = false;
            setStatus(null);
            if (data.error) { showError(data.error); return; }
            renderReport(data.report || {});
        })
        .catch(function () {
            btn.disabled = false;
            setStatus(null);
            showError('Network error — please try again.');
        });
    });

    Array.prototype.forEach.call(document.querySelectorAll('.gf-open'), function (b) {
        b.addEventListener('click', function () {
            fetch('/research/api/gaps/' + b.getAttribute('data-id'), { headers: csrfHeaders() })
            .then(function (r) { return r.json().catch(function () { return {}; }); })
            .then(function (data) {
                if (data.report) renderReport(data.report);
                else showError(data.error || 'Could not load report.');
            });
        });
    });
})();
