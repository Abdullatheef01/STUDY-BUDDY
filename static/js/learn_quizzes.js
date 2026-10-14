/* Skill quizzes page JS (Wave 3 #19): setup, runner with instant feedback, submit. */
(function () {
    'use strict';

    var tokenMeta = document.querySelector('meta[name="csrf-token"]');
    function headers() {
        var h = { 'Content-Type': 'application/json' };
        if (tokenMeta) h['X-CSRFToken'] = tokenMeta.getAttribute('content');
        return h;
    }
    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    function el(id) { return document.getElementById(id); }

    var timedBox = el('quiz-timed');
    if (timedBox) {
        timedBox.addEventListener('change', function () {
            el('quiz-time-wrap').style.display = timedBox.checked ? '' : 'none';
        });
    }

    var state = null; // {attemptId, questions, idx, answers, timerInt, timeLeft}

    var startBtn = el('quiz-start');
    if (startBtn) {
        startBtn.addEventListener('click', function () {
            var diffs = [];
            document.querySelectorAll('.quiz-diff:checked').forEach(function (cb) {
                diffs.push(cb.value);
            });
            var payload = {
                skill: el('quiz-skill').value,
                num_questions: parseInt(el('quiz-n').value, 10),
                difficulties: diffs,
                timed: timedBox.checked,
                time_limit_sec: timedBox.checked ? parseInt(el('quiz-time').value, 10) * 60 : 0
            };
            el('quiz-status').textContent = 'Preparing your quiz…';
            fetch('/learn/quizzes/start', {
                method: 'POST', headers: headers(), body: JSON.stringify(payload)
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.success) {
                    el('quiz-status').textContent = data.error || 'Could not start quiz.';
                    return;
                }
                el('quiz-status').textContent = '';
                beginQuiz(data);
            })
            .catch(function () { el('quiz-status').textContent = 'Network error. Please try again.'; });
        });
    }

    function beginQuiz(data) {
        state = {
            attemptId: data.attempt_id, questions: data.questions,
            idx: 0, answers: {},
            timerInt: null, timeLeft: data.time_limit_sec
        };
        el('quiz-setup').style.display = 'none';
        el('quiz-done').style.display = 'none';
        el('quiz-run').style.display = '';
        if (data.timed && data.time_limit_sec) {
            var tag = el('quiz-timer');
            tag.style.display = '';
            state.timerInt = setInterval(function () {
                state.timeLeft -= 1;
                if (state.timeLeft <= 0) {
                    clearInterval(state.timerInt);
                    finishQuiz(true);
                    return;
                }
                var m = Math.floor(state.timeLeft / 60), s = state.timeLeft % 60;
                tag.textContent = m + ':' + (s < 10 ? '0' : '') + s;
            }, 1000);
        } else {
            el('quiz-timer').style.display = 'none';
        }
        renderQuestion();
    }

    function renderQuestion() {
        var q = state.questions[state.idx];
        var total = state.questions.length;
        el('quiz-progress-label').textContent =
            'Question ' + (state.idx + 1) + ' of ' + total;
        el('quiz-progress-bar').style.width = (state.idx / total * 100) + '%';
        var html = '<div style="display:flex;gap:.5rem;margin-bottom:.8rem;">'
            + '<span class="b-tag">' + esc(q.topic) + '</span>'
            + '<span class="b-tag">' + esc(q.difficulty) + '</span></div>'
            + '<p style="font-size:1.05rem;white-space:pre-wrap;">' + esc(q.question) + '</p>'
            + '<div style="display:flex;flex-direction:column;gap:.6rem;margin-top:1rem;">';
        q.options.forEach(function (opt, i) {
            var checked = state.answers[q.id] === i ? 'checked' : '';
            html += '<label class="b-card b-card--lite" style="display:flex;gap:.7rem;align-items:flex-start;cursor:pointer;padding:.9rem 1.1rem;">'
                + '<input type="radio" class="b-radio" name="qopt" value="' + i + '" ' + checked + '>'
                + '<span><strong>' + String.fromCharCode(65 + i) + '.</strong> <span style="white-space:pre-wrap;">' + esc(opt) + '</span></span>'
                + '</label>';
        });
        html += '</div>';
        el('quiz-question').innerHTML = html;
        el('quiz-feedback').innerHTML = '';
        el('quiz-check').disabled = false;
        el('quiz-next').disabled = true;
        el('quiz-finish').style.display = state.idx === total - 1 ? '' : 'none';
        el('quiz-next').style.display = state.idx === total - 1 ? 'none' : '';
    }

    el('quiz-check').addEventListener('click', function () {
        if (!state) return;
        var q = state.questions[state.idx];
        var sel = document.querySelector('input[name="qopt"]:checked');
        if (!sel) {
            el('quiz-feedback').innerHTML =
                '<div class="b-flash b-flash--error">Pick an option first.</div>';
            return;
        }
        var chosen = parseInt(sel.value, 10);
        state.answers[q.id] = chosen;
        fetch('/learn/quizzes/' + state.attemptId + '/check', {
            method: 'POST', headers: headers(),
            body: JSON.stringify({ question_id: q.id, answer: chosen })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (!data.success) {
                el('quiz-feedback').innerHTML =
                    '<div class="b-flash b-flash--error">' + esc(data.error || 'Check failed.') + '</div>';
                return;
            }
            var cls = data.correct ? 'b-flash--success' : 'b-flash--error';
            var head = data.correct ? 'Correct!' : 'Not quite — the answer is '
                + String.fromCharCode(65 + data.correct_index) + '.';
            el('quiz-feedback').innerHTML =
                '<div class="b-flash ' + cls + '"><strong>' + esc(head) + '</strong><br>' + esc(data.explanation) + '</div>';
            el('quiz-check').disabled = true;
            el('quiz-next').disabled = false;
            el('quiz-progress-bar').style.width = ((state.idx + 1) / state.questions.length * 100) + '%';
        })
        .catch(function () {
            el('quiz-feedback').innerHTML =
                '<div class="b-flash b-flash--error">Network error.</div>';
        });
    });

    el('quiz-next').addEventListener('click', function () {
        if (!state || state.idx >= state.questions.length - 1) return;
        state.idx += 1;
        renderQuestion();
    });

    el('quiz-finish').addEventListener('click', function () { finishQuiz(false); });

    function finishQuiz(timeUp) {
        if (!state) return;
        if (state.timerInt) clearInterval(state.timerInt);
        fetch('/learn/quizzes/' + state.attemptId + '/submit', {
            method: 'POST', headers: headers(),
            body: JSON.stringify({ answers: state.answers })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (!data.success) {
                el('quiz-feedback').innerHTML =
                    '<div class="b-flash b-flash--error">' + esc(data.error || 'Submit failed.') + '</div>';
                return;
            }
            showSummary(data.summary, data.report_url, timeUp);
        })
        .catch(function () {
            el('quiz-feedback').innerHTML =
                '<div class="b-flash b-flash--error">Network error.</div>';
        });
    }

    function showSummary(summary, reportUrl, timeUp) {
        el('quiz-run').style.display = 'none';
        el('quiz-done').style.display = '';
        var html = '<div class="b-bento" style="margin-bottom:1.2rem;">'
            + '<div class="b-card b-card--stat"><div class="b-stat-num">' + summary.score + '/' + summary.total + '</div>'
            + '<div class="b-stat-label">' + summary.pct + '%' + (timeUp ? ' — time expired' : '') + '</div></div>'
            + '<div class="b-card"><h3 style="margin-top:0;">By difficulty</h3><div class="b-kv">';
        Object.keys(summary.by_difficulty).forEach(function (d) {
            var a = summary.by_difficulty[d];
            html += '<div class="b-kv-row"><span class="b-kv-label">' + esc(d) + '</span>'
                + '<span class="b-kv-val">' + a.correct + '/' + a.total + ' (' + a.pct + '%)</span></div>';
        });
        html += '</div></div></div>'
            + '<p style="color:var(--b-muted);">' + esc(summary.verdict) + '</p>';
        if (summary.weak_topics && summary.weak_topics.length) {
            html += '<h3>Weak topics</h3><div style="display:flex;gap:.5rem;flex-wrap:wrap;">'
                + summary.weak_topics.map(function (t) {
                    return '<span class="b-tag" style="color:var(--b-warn);border-color:rgba(251,191,36,.4);">' + esc(t) + '</span>';
                }).join('') + '</div>'
                + '<p style="margin-top:.8rem;"><a href="' + esc(summary.roadmap_url) + '">Revisit these in the roadmap &rarr;</a></p>';
        }
        el('quiz-summary').innerHTML = html;
        el('quiz-report-link').href = reportUrl;
        el('quiz-done').scrollIntoView({ behavior: 'smooth' });
        state = null;
    }

    el('quiz-again').addEventListener('click', function () {
        el('quiz-done').style.display = 'none';
        el('quiz-setup').style.display = '';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
})();
