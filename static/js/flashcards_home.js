/* Flashcards home: deck generation. */
(function () {
    'use strict';
    function csrfHeaders(extra) {
        var headers = extra || {};
        var m = document.querySelector('meta[name="csrf-token"]');
        if (m) headers['X-CSRFToken'] = m.getAttribute('content');
        return headers;
    }
    function $(id) { return document.getElementById(id); }
    var btn = $('fc-generate');
    if (!btn) return;
    btn.addEventListener('click', function () {
        var err = $('fc-error');
        err.style.display = 'none';
        var docId = parseInt(($('fc-doc').value || ''), 10);
        if (!docId) { err.textContent = 'Select a document first.'; err.style.display = 'block'; return; }
        btn.disabled = true;
        var st = $('fc-status');
        st.textContent = 'Generating deck…'; st.style.display = 'inline-flex';
        fetch('/research/api/flashcards/generate', {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ doc_id: docId })
        })
        .then(function (r) { return r.json().catch(function () { return { error: 'Bad response' }; }); })
        .then(function (data) {
            btn.disabled = false;
            st.style.display = 'none';
            if (data.error) { err.textContent = data.error; err.style.display = 'block'; return; }
            window.location.href = '/research/flashcards/' + data.id;
        })
        .catch(function () {
            btn.disabled = false;
            st.style.display = 'none';
            err.textContent = 'Network error — please try again.';
            err.style.display = 'block';
        });
    });
})();
