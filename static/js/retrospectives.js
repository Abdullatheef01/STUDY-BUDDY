/* Rejection retrospectives: wizard step saving, starter/template card picks,
   experiment logging on the hub. Wave 5 #29.
   All POSTs carry the CSRF token via the X-CSRFToken header. */
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
    function showOk(id, msg) {
        var el = $(id);
        if (!el) return;
        el.textContent = msg || 'Saved.';
        el.style.display = 'block';
    }
    function hideMsg(id) {
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

    var APP_ID = (typeof window.RT_APP_ID === 'number') ? window.RT_APP_ID : null;

    /* ---- wizard step navigation ---- */
    function gotoPane(n) {
        var steps = document.querySelectorAll('.rw-step');
        Array.prototype.forEach.call(steps, function (s) {
            var active = s.getAttribute('data-pane') === String(n);
            s.classList.toggle('rw-step--active', active);
            if (active) s.classList.add('rw-step--done');
        });
        var panes = document.querySelectorAll('.rw-pane');
        Array.prototype.forEach.call(panes, function (p) {
            p.classList.toggle('rw-pane--active',
                p.getAttribute('data-pane-body') === String(n));
        });
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    var stepBtns = document.querySelectorAll('.rw-step');
    Array.prototype.forEach.call(stepBtns, function (b) {
        b.addEventListener('click', function () { gotoPane(b.getAttribute('data-pane')); });
    });
    var gotoBtns = document.querySelectorAll('[data-goto]');
    Array.prototype.forEach.call(gotoBtns, function (b) {
        b.addEventListener('click', function () { gotoPane(b.getAttribute('data-goto')); });
    });

    /* ---- category filters ---- */
    function wireFilter(filterId, cardsId) {
        var filter = $(filterId);
        if (!filter) return;
        var btns = filter.querySelectorAll('button[data-cat]');
        var cards = document.querySelectorAll('#' + cardsId + ' .rw-card');
        Array.prototype.forEach.call(btns, function (b) {
            b.addEventListener('click', function () {
                Array.prototype.forEach.call(btns, function (x) { x.classList.remove('rw-cat--on'); });
                b.classList.add('rw-cat--on');
                var cat = b.getAttribute('data-cat');
                Array.prototype.forEach.call(cards, function (c) {
                    c.style.display = (cat === 'all' || c.getAttribute('data-cat') === cat) ? '' : 'none';
                });
            });
        });
    }
    wireFilter('rw-h-filter', 'rw-h-cards');
    wireFilter('rw-t-filter', 'rw-t-cards');

    /* ---- starter cards: tap to append to the hypotheses textarea ---- */
    var hyps = $('rw-hyps');
    var hCards = document.querySelectorAll('#rw-h-cards .rw-card');
    Array.prototype.forEach.call(hCards, function (c) {
        c.addEventListener('click', function () {
            var text = c.getAttribute('data-text') || '';
            if (!text || !hyps) return;
            var cur = hyps.value.trim();
            hyps.value = cur ? (cur + '\n\n' + text) : text;
            c.classList.add('rw-card--sel');
        });
    });

    /* ---- template cards: tap to pre-fill the experiment form ---- */
    var tCards = document.querySelectorAll('#rw-t-cards .rw-card');
    Array.prototype.forEach.call(tCards, function (c) {
        c.addEventListener('click', function () {
            var h = $('rw-e-hyp'), ch = $('rw-e-change'), tg = $('rw-e-target'), du = $('rw-e-dur');
            if (h) h.value = c.getAttribute('data-hypothesis') || '';
            if (ch) ch.value = c.getAttribute('data-change') || '';
            if (tg) tg.value = c.getAttribute('data-target') || '';
            if (du) du.value = c.getAttribute('data-duration') || '';
            Array.prototype.forEach.call(tCards, function (x) { x.classList.remove('rw-card--sel'); });
            c.classList.add('rw-card--sel');
        });
    });

    /* ---- wizard saves ---- */
    function wizardBody(step) {
        var body = { application_id: APP_ID, step: step };
        if (step === 'facts') {
            body.facts = $('rw-facts') ? $('rw-facts').value : '';
            body.timeline = $('rw-timeline') ? $('rw-timeline').value : '';
            body.stage_reached = $('rw-stage') ? $('rw-stage').value : '';
        } else if (step === 'patterns') {
            body.observed_patterns = $('rw-patterns') ? $('rw-patterns').value : '';
        } else if (step === 'hypotheses') {
            body.hypotheses = hyps ? hyps.value : '';
        } else if (step === 'experiment') {
            body.experiment = {
                hypothesis: $('rw-e-hyp') ? $('rw-e-hyp').value : '',
                change: $('rw-e-change') ? $('rw-e-change').value : '',
                target: $('rw-e-target') ? $('rw-e-target').value : '',
                duration: $('rw-e-dur') ? $('rw-e-dur').value : ''
            };
        }
        return body;
    }
    var saveBtns = document.querySelectorAll('[data-save]');
    Array.prototype.forEach.call(saveBtns, function (btn) {
        btn.addEventListener('click', function () {
            var step = btn.getAttribute('data-save');
            hideMsg('rw-err-' + step);
            hideMsg('rw-ok-' + step);
            btn.disabled = true;
            post('/retrospectives/api/save', wizardBody(step))
                .then(function (data) {
                    btn.disabled = false;
                    if (data.error) {
                        showErr('rw-err-' + step, data.error);
                        return;
                    }
                    showOk('rw-ok-' + step, 'Saved.');
                    var paneOrder = { facts: '1', patterns: '2', hypotheses: '3', experiment: '4' };
                    var tab = document.querySelector('.rw-step[data-pane="' + (paneOrder[step] || '1') + '"]');
                    if (tab) tab.classList.add('rw-step--done');
                })
                .catch(function () {
                    btn.disabled = false;
                    showErr('rw-err-' + step, 'Network error — please try again.');
                });
        });
    });

    /* ---- complete retrospective ---- */
    var completeBtn = $('rw-complete');
    if (completeBtn && APP_ID) {
        completeBtn.addEventListener('click', function () {
            hideMsg('rw-err-experiment');
            completeBtn.disabled = true;
            post('/retrospectives/api/complete/' + APP_ID, {})
                .then(function (data) {
                    if (data.error) {
                        completeBtn.disabled = false;
                        showErr('rw-err-experiment', data.error);
                        return;
                    }
                    window.location.href = '/retrospectives';
                })
                .catch(function () {
                    completeBtn.disabled = false;
                    showErr('rw-err-experiment', 'Network error — please try again.');
                });
        });
    }

    /* ---- hub: new experiment form ---- */
    var expForm = $('rt-exp-form');
    if (expForm) {
        expForm.addEventListener('submit', function (ev) {
            ev.preventDefault();
            hideMsg('rt-exp-error');
            var btn = expForm.querySelector('button[type="submit"]');
            if (btn) btn.disabled = true;
            post('/retrospectives/api/experiments', {
                hypothesis: $('rt-hyp') ? $('rt-hyp').value : '',
                change: $('rt-change') ? $('rt-change').value : '',
                target: $('rt-target') ? $('rt-target').value : '',
                duration: $('rt-dur') ? $('rt-dur').value : ''
            }).then(function (data) {
                if (btn) btn.disabled = false;
                if (data.error) {
                    showErr('rt-exp-error', data.error);
                    return;
                }
                window.location.reload();
            }).catch(function () {
                if (btn) btn.disabled = false;
                showErr('rt-exp-error', 'Network error — please try again.');
            });
        });
    }

    /* ---- hub: advance experiment status ---- */
    var advBtns = document.querySelectorAll('.rt-adv');
    Array.prototype.forEach.call(advBtns, function (btn) {
        btn.addEventListener('click', function () {
            var id = btn.getAttribute('data-id');
            var to = btn.getAttribute('data-to');
            btn.disabled = true;
            var result = '';
            if (to === 'done') {
                result = window.prompt('What was the outcome of this experiment?', '') || '';
            }
            post('/retrospectives/api/experiments/' + encodeURIComponent(id) + '/result',
                { status: to, result: result })
                .then(function (data) {
                    if (data.error) {
                        btn.disabled = false;
                        window.alert(data.error);
                        return;
                    }
                    window.location.reload();
                })
                .catch(function () {
                    btn.disabled = false;
                    window.alert('Network error — please try again.');
                });
        });
    });
})();
