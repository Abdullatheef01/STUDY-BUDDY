/* Timed Aptitude Tests (Wave 2, feature #16). XSS-safe: textContent only. */
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
        var m = document.querySelector('meta[name="csrf-token"]');
        if (m) headers['X-CSRFToken'] = m.getAttribute('content');
        return headers;
    }

    function showError(id, msg) {
        var box = document.getElementById(id);
        box.textContent = msg;
        box.style.display = 'block';
    }

    function hideError(id) {
        document.getElementById(id).style.display = 'none';
    }

    var state = {
        attemptId: null,
        questions: [],
        answers: {},
        timeLeft: 0,
        timerId: null,
        submitted: false,
    };

    function fmtTime(s) {
        s = Math.max(0, Math.floor(s));
        var m = Math.floor(s / 60), r = s % 60;
        return (m < 10 ? '0' + m : '' + m) + ':' + (r < 10 ? '0' + r : '' + r);
    }

    function updateProgress() {
        var done = Object.keys(state.answers).length;
        var pct = state.questions.length ? (done / state.questions.length * 100) : 0;
        document.getElementById('ap-prog').style.width = pct + '%';
    }

    function tick() {
        state.timeLeft -= 1;
        var t = document.getElementById('ap-timer');
        t.textContent = fmtTime(state.timeLeft);
        if (state.timeLeft <= 60) t.classList.add('urgent');
        if (state.timeLeft <= 0) {
            clearInterval(state.timerId);
            submitAnswers(true);
        }
    }

    function renderQuestions() {
        var box = document.getElementById('ap-questions');
        box.innerHTML = '';
        state.questions.forEach(function (q, i) {
            var card = el('div', 'ap-q');
            var meta = el('div', 'ap-qmeta');
            meta.appendChild(el('span', 'ap-chip', 'Q' + (i + 1)));
            meta.appendChild(el('span', 'ap-chip', q.category));
            meta.appendChild(el('span', 'ap-chip diff-' + q.difficulty, q.difficulty));
            card.appendChild(meta);
            card.appendChild(el('div', 'ap-qtext', q.statement));
            q.options.forEach(function (opt, oi) {
                var lab = el('label', 'ap-opt');
                var radio = document.createElement('input');
                radio.type = 'radio';
                radio.name = 'q_' + q.id;
                radio.value = oi;
                radio.addEventListener('change', function () {
                    state.answers[q.id] = oi;
                    Array.prototype.forEach.call(card.querySelectorAll('.ap-opt'), function (o) {
                        o.classList.remove('sel');
                    });
                    lab.classList.add('sel');
                    updateProgress();
                });
                lab.appendChild(radio);
                lab.appendChild(el('span', null, opt));
                card.appendChild(lab);
            });
            box.appendChild(card);
        });
        updateProgress();
    }

    function startTest() {
        hideError('setup-error');
        var btn = document.getElementById('btn-start');
        btn.disabled = true;
        var payload = {
            category: document.getElementById('sel-category').value,
            num_questions: parseInt(document.getElementById('sel-count').value, 10),
            time_limit: parseInt(document.getElementById('sel-time').value, 10),
        };
        fetch('/aptitude/start', {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(payload),
        }).then(function (r) {
            return r.json().then(function (d) { return { status: r.status, body: d }; });
        }).then(function (res) {
            btn.disabled = false;
            if (res.status !== 200 || !res.body.success) {
                showError('setup-error', (res.body && res.body.error) || 'Could not start the test.');
                return;
            }
            state.attemptId = res.body.attempt_id;
            state.questions = res.body.questions;
            state.answers = {};
            state.timeLeft = res.body.time_limit_sec;
            state.submitted = false;
            document.getElementById('setup-card').style.display = 'none';
            document.getElementById('result-view').style.display = 'none';
            document.getElementById('test-view').style.display = 'block';
            renderQuestions();
            var t = document.getElementById('ap-timer');
            t.textContent = fmtTime(state.timeLeft);
            t.classList.remove('urgent');
            clearInterval(state.timerId);
            state.timerId = setInterval(tick, 1000);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }).catch(function () {
            btn.disabled = false;
            showError('setup-error', 'Network error. Please try again.');
        });
    }

    function submitAnswers(auto) {
        if (state.submitted || !state.attemptId) return;
        state.submitted = true;
        clearInterval(state.timerId);
        hideError('test-error');
        fetch('/aptitude/' + state.attemptId + '/submit', {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ answers: state.answers }),
        }).then(function (r) {
            return r.json().then(function (d) { return { status: r.status, body: d }; });
        }).then(function (res) {
            if (res.status !== 200 || !res.body.success) {
                state.submitted = false;
                showError('test-error', (res.body && res.body.error) || 'Submit failed. Try again.');
                return;
            }
            renderResult(res.body.summary, res.body.results, auto);
        }).catch(function () {
            state.submitted = false;
            showError('test-error', 'Network error. Please try again.');
        });
    }

    function barRow(label, pct) {
        var row = el('div', 'ap-bar-row');
        row.appendChild(el('span', null, label));
        var bar = el('div', 'ap-bar');
        var fill = el('div');
        fill.style.width = Math.max(0, Math.min(100, pct)) + '%';
        bar.appendChild(fill);
        row.appendChild(bar);
        row.appendChild(el('span', null, pct.toFixed(1) + '%'));
        return row;
    }

    function renderResult(summary, results, auto) {
        document.getElementById('test-view').style.display = 'none';
        var view = document.getElementById('result-view');
        view.innerHTML = '';
        view.style.display = 'block';

        var head = el('div', 'ap-card');
        var h = el('h2', null, auto ? 'Time\u2019s up! Here is your report.' : 'Test submitted. Here is your report.');
        h.style.marginBottom = '1rem';
        head.appendChild(h);
        var ring = el('div', 'ap-score-ring', summary.score_pct.toFixed(1) + '%');
        var hue = summary.score_pct >= 70 ? '#10b981' : (summary.score_pct >= 40 ? '#f59e0b' : '#ef4444');
        ring.style.border = '6px solid ' + hue;
        ring.style.color = hue;
        head.appendChild(ring);
        var sub = el('p', null, summary.correct + ' of ' + summary.total + ' correct');
        sub.style.textAlign = 'center';
        sub.style.color = 'var(--text-muted, #94a3b8)';
        head.appendChild(sub);
        if (summary.expired) {
            var exp = el('div', 'ap-weak', 'Submitted after the time limit — scored as expired.');
            head.appendChild(exp);
        }

        var bdTitle = el('h3', null, 'Accuracy by category');
        bdTitle.style.margin = '1.2rem 0 0.7rem';
        head.appendChild(bdTitle);
        Object.keys(summary.by_category || {}).forEach(function (k) {
            var v = summary.by_category[k];
            head.appendChild(barRow(k, v.pct));
        });
        var bdTitle2 = el('h3', null, 'Accuracy by difficulty');
        bdTitle2.style.margin = '1.2rem 0 0.7rem';
        head.appendChild(bdTitle2);
        Object.keys(summary.by_difficulty || {}).forEach(function (k) {
            var v = summary.by_difficulty[k];
            head.appendChild(barRow(k, v.pct));
        });
        if (summary.weak_areas && summary.weak_areas.length) {
            head.appendChild(el('div', 'ap-weak',
                'Weak areas to practice: ' + summary.weak_areas.join(', ')));
        }
        var actions = el('div', 'ap-actions');
        var again = el('button', 'ap-btn ap-btn-ghost', 'Retake Test');
        again.addEventListener('click', function () {
            document.getElementById('result-view').style.display = 'none';
            document.getElementById('setup-card').style.display = 'block';
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
        var dash = el('a', 'ap-btn ap-btn-ghost', 'View History');
        dash.href = '/dashboard';
        dash.style.textDecoration = 'none';
        actions.appendChild(again);
        actions.appendChild(dash);
        head.appendChild(actions);
        view.appendChild(head);

        var revTitle = el('h3', null, 'Question review');
        revTitle.style.margin = '0.4rem 0 1rem';
        view.appendChild(revTitle);
        results.forEach(function (r, i) {
            var card = el('div', 'ap-q');
            var meta = el('div', 'ap-qmeta');
            meta.appendChild(el('span', 'ap-chip', 'Q' + (i + 1)));
            meta.appendChild(el('span', 'ap-chip', r.category));
            meta.appendChild(el('span', 'ap-chip ' + (r.correct ? '' : 'diff-Hard'),
                r.correct ? 'Correct' : (r.chosen === null || r.chosen === undefined ? 'Skipped' : 'Wrong')));
            card.appendChild(meta);
            card.appendChild(el('div', 'ap-qtext', r.statement));
            r.options.forEach(function (opt, oi) {
                var cls = 'ap-opt';
                if (oi === r.correct_index) cls += ' correct';
                else if (oi === r.chosen) cls += ' wrong';
                var lab = el('div', cls);
                lab.appendChild(el('span', null, opt));
                card.appendChild(lab);
            });
            var expl = el('div', 'ap-expl');
            expl.appendChild(el('strong', null, 'Why: '));
            expl.appendChild(el('span', null, r.explanation));
            card.appendChild(expl);
            view.appendChild(card);
        });
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // Saved-report page support: server embeds JSON in #saved-data.
    function renderSaved() {
        var holder = document.getElementById('saved-data');
        if (!holder) return;
        try {
            var data = JSON.parse(holder.textContent);
            renderResult(data.summary, data.results, false);
        } catch (e) { /* leave empty */ }
    }

    document.addEventListener('DOMContentLoaded', function () {
        var startBtn = document.getElementById('btn-start');
        if (startBtn) startBtn.addEventListener('click', startTest);
        var subBtn = document.getElementById('btn-submit');
        if (subBtn) subBtn.addEventListener('click', function () { submitAnswers(false); });
        renderSaved();
    });
})();
