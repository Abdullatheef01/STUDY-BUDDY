/* Momentum hub: quest claims, league join/leave, reflection save, opt-out.
   Wave 5 #27. All POSTs carry the CSRF token via the X-CSRFToken header. */
(function () {
    'use strict';
    function csrfHeaders(extra) {
        var headers = extra || {};
        var m = document.querySelector('meta[name="csrf-token"]');
        if (m) headers['X-CSRFToken'] = m.getAttribute('content');
        return headers;
    }
    function $(id) { return document.getElementById(id); }
    function showErr(id, msg) {
        var el = $(id);
        if (!el) return;
        el.textContent = msg;
        el.style.display = 'block';
    }
    function hideErr(id) {
        var el = $(id);
        if (el) el.style.display = 'none';
    }
    function post(url, body) {
        return fetch(url, {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(body || {})
        }).then(function (r) {
            return r.json().catch(function () { return { error: 'Bad response' }; });
        });
    }

    /* ---- quest claims ---- */
    var claimBtns = document.querySelectorAll('.mm-claim');
    Array.prototype.forEach.call(claimBtns, function (btn) {
        btn.addEventListener('click', function () {
            hideErr('mm-quest-error');
            btn.disabled = true;
            post('/momentum/api/quest/' + encodeURIComponent(btn.getAttribute('data-quest')) + '/claim')
                .then(function (data) {
                    if (data.error) {
                        btn.disabled = false;
                        showErr('mm-quest-error', data.error);
                        return;
                    }
                    window.location.reload();
                })
                .catch(function () {
                    btn.disabled = false;
                    showErr('mm-quest-error', 'Network error — please try again.');
                });
        });
    });

    /* ---- league join / leave ---- */
    var joinBtn = $('mm-league-join');
    if (joinBtn) {
        joinBtn.addEventListener('click', function () {
            hideErr('mm-league-error');
            joinBtn.disabled = true;
            var st = $('mm-league-status');
            if (st) { st.textContent = 'Joining…'; st.style.display = 'inline-flex'; }
            post('/momentum/api/league/join')
                .then(function (data) {
                    if (data.error) {
                        joinBtn.disabled = false;
                        if (st) st.style.display = 'none';
                        showErr('mm-league-error', data.error);
                        return;
                    }
                    window.location.reload();
                })
                .catch(function () {
                    joinBtn.disabled = false;
                    if (st) st.style.display = 'none';
                    showErr('mm-league-error', 'Network error — please try again.');
                });
        });
    }
    var leaveBtn = $('mm-league-leave');
    if (leaveBtn) {
        leaveBtn.addEventListener('click', function () {
            hideErr('mm-league-error');
            leaveBtn.disabled = true;
            post('/momentum/api/league/leave')
                .then(function (data) {
                    if (data.error) {
                        leaveBtn.disabled = false;
                        showErr('mm-league-error', data.error);
                        return;
                    }
                    window.location.reload();
                })
                .catch(function () {
                    leaveBtn.disabled = false;
                    showErr('mm-league-error', 'Network error — please try again.');
                });
        });
    }

    /* ---- reflection ---- */
    var saveBtn = $('mm-reflect-save');
    if (saveBtn) {
        saveBtn.addEventListener('click', function () {
            hideErr('mm-reflect-error');
            var st = $('mm-reflect-status');
            saveBtn.disabled = true;
            if (st) { st.textContent = 'Saving…'; st.style.display = 'inline-flex'; }
            post('/momentum/api/reflect', {
                wins: ($('mm-wins') || {}).value || '',
                focus_next: ($('mm-focus') || {}).value || ''
            })
                .then(function (data) {
                    saveBtn.disabled = false;
                    if (st) st.style.display = 'none';
                    if (data.error) { showErr('mm-reflect-error', data.error); return; }
                    if (st) { st.textContent = 'Saved — nice reflection.'; st.style.display = 'inline-flex'; }
                })
                .catch(function () {
                    saveBtn.disabled = false;
                    if (st) st.style.display = 'none';
                    showErr('mm-reflect-error', 'Network error — please try again.');
                });
        });
    }

    /* ---- opt-out / rejoin ---- */
    function setOptOut(optOut, btnId, errId, statusId) {
        var btn = $(btnId);
        if (!btn) return;
        btn.addEventListener('click', function () {
            hideErr(errId);
            btn.disabled = true;
            var st = $(statusId);
            if (st) { st.textContent = 'Updating…'; st.style.display = 'inline-flex'; }
            post('/momentum/api/opt-out', { opt_out: !!optOut })
                .then(function (data) {
                    if (data.error) {
                        btn.disabled = false;
                        if (st) st.style.display = 'none';
                        showErr(errId, data.error);
                        return;
                    }
                    window.location.reload();
                })
                .catch(function () {
                    btn.disabled = false;
                    if (st) st.style.display = 'none';
                    showErr(errId, 'Network error — please try again.');
                });
        });
    }
    setOptOut(true, 'mm-optout', 'mm-optout-error', null);
    setOptOut(false, 'mm-rejoin', 'mm-error', 'mm-status');
})();
