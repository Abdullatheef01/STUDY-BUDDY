/* Mock interview flow: setup -> timed questions -> rubric-scored results. */
(function () {
    'use strict';

    var tokenMeta = document.querySelector('meta[name="csrf-token"]');
    function headers() {
        var h = { 'Content-Type': 'application/json' };
        if (tokenMeta) h['X-CSRFToken'] = tokenMeta.getAttribute('content');
        return h;
    }
    function el(id) { return document.getElementById(id); }
    function setText(node, text) { node.textContent = text; }

    var sessionId = null;
    var questions = [];
    var answers = [];
    var idx = 0;
    var timerInt = null;
    var secondsLeft = 0;

    function fmtTime(s) {
        var m = Math.floor(s / 60), sec = s % 60;
        return (m < 10 ? '0' : '') + m + ':' + (sec < 10 ? '0' : '') + sec;
    }

    function startTimer(minutes) {
        stopTimer();
        secondsLeft = minutes * 60;
        var t = el('q-timer');
        function tick() {
            setText(t, 'Time left ' + fmtTime(secondsLeft));
            t.classList.toggle('urgent', secondsLeft <= 60);
            if (secondsLeft <= 0) { stopTimer(); setText(t, 'Time is up - finish when ready'); return; }
            secondsLeft--;
        }
        tick();
        timerInt = setInterval(tick, 1000);
    }
    function stopTimer() { if (timerInt) { clearInterval(timerInt); timerInt = null; } }

    el('btn-start').addEventListener('click', function () {
        var err = el('setup-error');
        setText(err, '');
        var btn = el('btn-start');
        btn.disabled = true;
        fetch('/interview/start', {
            method: 'POST',
            headers: headers(),
            body: JSON.stringify({
                company: el('sel-company').value,
                role: el('sel-role').value,
                category: el('sel-category').value,
                num_questions: el('sel-n').value
            })
        }).then(function (r) { return r.json().then(function (d) { return { status: r.status, body: d }; }); })
        .then(function (res) {
            btn.disabled = false;
            if (res.status === 401) { window.location.href = '/login?next=/interview'; return; }
            if (!res.body.success) { setText(err, res.body.error || 'Could not start.'); return; }
            sessionId = res.body.session_id;
            questions = res.body.questions;
            answers = new Array(questions.length).fill('');
            idx = 0;
            el('setup-card').style.display = 'none';
            el('quiz-area').style.display = 'block';
            renderQ();
        })
        .catch(function () { btn.disabled = false; setText(err, 'Network error. Please try again.'); });
    });

    function renderQ() {
        var q = questions[idx];
        stopTimer();
        setText(el('q-count'), 'Question ' + (idx + 1) + ' of ' + questions.length);
        var diff = el('q-diff');
        setText(diff, q.difficulty);
        diff.className = 'iv-chip diff-' + q.difficulty;
        setText(el('q-cat'), (q.category || '').replace(/_/g, ' '));
        setText(el('q-text'), q.question);
        el('q-answer').value = answers[idx] || '';
        var kp = el('q-keypoints');
        kp.innerHTML = '';
        (q.key_points || []).forEach(function (k) {
            var li = document.createElement('li');
            setText(li, k);
            kp.appendChild(li);
        });
        el('quiz-progress').style.width = ((idx) / questions.length * 100) + '%';
        setText(el('btn-back'), idx === 0 ? 'Cancel' : 'Back');
        setText(el('btn-next'), idx === questions.length - 1 ? 'Finish & Score' : 'Next');
        startTimer(q.time_minutes || 3);
        el('q-answer').focus();
    }

    el('btn-back').addEventListener('click', function () {
        answers[idx] = el('q-answer').value;
        if (idx === 0) {
            if (confirm('Cancel this interview? Your progress will be lost.')) {
                el('quiz-area').style.display = 'none';
                el('setup-card').style.display = 'block';
                stopTimer();
            }
            return;
        }
        idx--;
        renderQ();
    });

    el('btn-next').addEventListener('click', function () {
        answers[idx] = el('q-answer').value;
        if (!answers[idx].trim()) {
            if (!confirm('Answer is empty. Continue anyway?')) return;
        }
        if (idx < questions.length - 1) { idx++; renderQ(); return; }
        submitAll();
    });

    function submitAll() {
        stopTimer();
        var btn = el('btn-next');
        btn.disabled = true;
        setText(btn, 'Scoring...');
        var payload = questions.map(function (q, i) {
            return { question_id: q.id, answer: answers[i] || '' };
        });
        fetch('/interview/' + sessionId + '/submit', {
            method: 'POST',
            headers: headers(),
            body: JSON.stringify({ answers: payload })
        }).then(function (r) { return r.json().then(function (d) { return { status: r.status, body: d }; }); })
        .then(function (res) {
            if (!res.body.success) {
                btn.disabled = false;
                setText(btn, 'Finish & Score');
                alert(res.body.error || 'Scoring failed.');
                return;
            }
            renderResults(res.body);
        })
        .catch(function () {
            btn.disabled = false;
            setText(btn, 'Finish & Score');
            alert('Network error. Please try again.');
        });
    }

    function scoreColor(v) {
        return v >= 70 ? '#10b981' : (v >= 45 ? '#f59e0b' : '#ef4444');
    }

    function renderResults(data) {
        el('quiz-area').style.display = 'none';
        var area = el('results-area');
        area.style.display = 'block';
        area.innerHTML = '';

        var head = document.createElement('div');
        head.className = 'iv-card';
        head.style.textAlign = 'center';
        var ring = document.createElement('div');
        ring.className = 'iv-score-ring';
        var total = data.total_score;
        ring.style.border = '4px solid ' + scoreColor(total);
        ring.style.color = scoreColor(total);
        setText(ring, total);
        head.appendChild(ring);
        var h2 = document.createElement('h2');
        setText(h2, 'Interview complete');
        head.appendChild(h2);
        var p = document.createElement('p');
        p.style.color = 'var(--text-muted, #94a3b8)';
        setText(p, data.results.length + ' questions scored' + (data.ai_powered ? ' - AI-polished feedback' : ' - rule-based feedback') + '.');
        head.appendChild(p);
        var link = document.createElement('a');
        link.className = 'iv-btn';
        link.href = data.report_url;
        link.style.marginTop = '0.8rem';
        setText(link, 'View saved report');
        head.appendChild(link);
        var again = document.createElement('button');
        again.className = 'iv-btn iv-btn-ghost';
        again.style.marginTop = '0.8rem';
        again.style.marginLeft = '0.6rem';
        setText(again, 'New interview');
        again.addEventListener('click', function () { window.location.reload(); });
        head.appendChild(again);
        area.appendChild(head);

        var labels = { correctness: 'Correctness / approach (40)', communication: 'Communication (25)', depth: 'Depth (20)', edge_cases: 'Edge cases (15)' };
        data.results.forEach(function (r, i) {
            var card = document.createElement('div');
            card.className = 'iv-card';
            var meta = document.createElement('div');
            meta.className = 'iv-qmeta';
            var chip = document.createElement('span');
            chip.className = 'iv-score-ring';
            chip.style.width = '64px'; chip.style.height = '64px'; chip.style.fontSize = '1.1rem'; chip.style.margin = '0';
            chip.style.border = '3px solid ' + scoreColor(r.total);
            chip.style.color = scoreColor(r.total);
            setText(chip, r.total);
            meta.appendChild(chip);
            var qt = document.createElement('div');
            qt.style.fontWeight = '700';
            qt.style.flex = '1';
            qt.style.minWidth = '220px';
            setText(qt, 'Q' + (i + 1) + ': ' + (questions[i] ? questions[i].question : ''));
            meta.appendChild(qt);
            card.appendChild(meta);

            var bd = document.createElement('div');
            bd.className = 'iv-breakdown';
            Object.keys(labels).forEach(function (k) {
                var row = document.createElement('div');
                row.className = 'iv-bar-row';
                var lab = document.createElement('span'); setText(lab, labels[k]); row.appendChild(lab);
                var bar = document.createElement('div'); bar.className = 'iv-bar';
                var fill = document.createElement('div');
                var maxv = { correctness: 40, communication: 25, depth: 20, edge_cases: 15 }[k];
                fill.style.width = Math.min(100, r.scores[k] / maxv * 100) + '%';
                bar.appendChild(fill); row.appendChild(bar);
                var val = document.createElement('span'); setText(val, r.scores[k]); row.appendChild(val);
                bd.appendChild(row);
            });
            card.appendChild(bd);

            var fb = document.createElement('div');
            fb.className = 'iv-fb';
            var fbData = r.feedback || { strengths: [], improvements: [] };
            if (fbData.strengths && fbData.strengths.length) {
                var hs = document.createElement('h4'); setText(hs, 'Strengths'); fb.appendChild(hs);
                var ul = document.createElement('ul');
                fbData.strengths.forEach(function (s) { var li = document.createElement('li'); setText(li, s); ul.appendChild(li); });
                fb.appendChild(ul);
            }
            if (fbData.improvements && fbData.improvements.length) {
                var hi = document.createElement('h4'); hi.className = 'fix'; setText(hi, 'What to improve'); fb.appendChild(hi);
                var ul2 = document.createElement('ul');
                fbData.improvements.forEach(function (s) { var li = document.createElement('li'); setText(li, s); ul2.appendChild(li); });
                fb.appendChild(ul2);
            }
            card.appendChild(fb);
            area.appendChild(card);
        });
        window.scrollTo(0, 0);
    }
})();
