/* Literature review generator UI. */
(function () {
    'use strict';
    function csrfHeaders(extra) {
        var headers = extra || {};
        var m = document.querySelector('meta[name="csrf-token"]');
        if (m) headers['X-CSRFToken'] = m.getAttribute('content');
        return headers;
    }
    function $(id) { return document.getElementById(id); }
    function showError(msg) {
        var e = $('lr-error');
        e.textContent = msg; e.style.display = 'block';
    }
    function setStatus(msg) {
        var s = $('lr-status');
        if (!msg) { s.style.display = 'none'; return; }
        s.textContent = msg; s.style.display = 'inline-flex';
    }

    var genBtn = $('lr-generate');
    if (!genBtn) return;
    genBtn.addEventListener('click', function () {
        $('lr-error').style.display = 'none';
        var ids = Array.prototype.map.call(
            document.querySelectorAll('.lr-doc:checked'),
            function (c) { return parseInt(c.value, 10); }
        ).filter(function (n) { return !isNaN(n); });
        if (ids.length < 2) { showError('Select at least 2 documents.'); return; }
        var title = ($('lr-title').value || '').trim();
        genBtn.disabled = true;
        setStatus('Generating review…');
        fetch('/research/api/review/generate', {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ doc_ids: ids, title: title })
        })
        .then(function (r) { return r.json().catch(function () { return { error: 'Bad response' }; }); })
        .then(function (data) {
            genBtn.disabled = false;
            setStatus(null);
            if (data.error) { showError(data.error); return; }
            window.location.href = '/research/review/' + data.id;
        })
        .catch(function () {
            genBtn.disabled = false;
            setStatus(null);
            showError('Network error — please try again.');
        });
    });

    Array.prototype.forEach.call(document.querySelectorAll('.lr-delete'), function (btn) {
        btn.addEventListener('click', function () {
            if (!confirm('Delete this review?')) return;
            fetch('/research/api/review/' + btn.getAttribute('data-id'), {
                method: 'DELETE', headers: csrfHeaders()
            })
            .then(function (r) { return r.json().catch(function () { return {}; }); })
            .then(function (data) {
                if (data.success) window.location.reload();
                else showError(data.error || 'Could not delete.');
            });
        });
    });
})();
