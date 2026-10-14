/* Opportunity Radar bookmarks (Wave 1 #9). */
(function () {
    'use strict';
    var grid = document.getElementById('oppGrid');
    if (!grid) return;
    var tokenMeta = document.querySelector('meta[name="csrf-token"]');

    function headers() {
        var h = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
        if (tokenMeta) h['X-CSRFToken'] = tokenMeta.getAttribute('content');
        return h;
    }

    grid.addEventListener('click', function (ev) {
        var btn = ev.target.closest('.opp-bm');
        if (!btn) return;
        var card = btn.closest('[data-opp-id]');
        if (!card) return;
        var oppId = card.getAttribute('data-opp-id');
        var saved = btn.getAttribute('data-bookmarked') === '1';
        btn.disabled = true;
        fetch(saved ? '/opportunities/bookmark/remove' : '/opportunities/bookmark', {
            method: 'POST',
            headers: headers(),
            body: JSON.stringify({ opp_id: oppId }),
        })
            .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
            .then(function (res) {
                btn.disabled = false;
                if (!res.body || !res.body.success) return;
                var nowSaved = !saved;
                btn.setAttribute('data-bookmarked', nowSaved ? '1' : '0');
                btn.classList.toggle('saved', nowSaved);
                btn.textContent = nowSaved ? '★ Saved' : '☆ Save';
            })
            .catch(function () { btn.disabled = false; });
    });
})();
