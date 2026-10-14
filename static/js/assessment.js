/**
 * Career Discovery Assessment (Wave 1, feature #7) - Frontend
 * Stepper quiz UI: one question at a time, answers collected client-side,
 * submitted as JSON with the CSRF header. All content HTML-escaped.
 */

(function () {
    'use strict';

    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    var DIM_LABELS = {
        interests: 'Your interests',
        strengths: 'Your strengths',
        workstyle: 'Work style',
        subjects: 'Subjects you enjoy'
    };

    var questions = window.__ASSESSMENT_QUESTIONS__ || [];
    var answers = {};   // question_id -> option_index
    var current = 0;

    function $(id) { return document.getElementById(id); }

    function render() {
        var q = questions[current];
        if (!q) return;
        $('asDim').textContent = (DIM_LABELS[q.dimension] || q.dimension)
            + '  ·  Question ' + (current + 1) + ' of ' + questions.length;
        $('asQ').textContent = q.text;
        var box = $('asOpts');
        box.innerHTML = '';
        q.options.forEach(function (optText, idx) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'as-opt' + (answers[q.id] === idx ? ' selected' : '');
            btn.textContent = optText;
            btn.addEventListener('click', function () {
                answers[q.id] = idx;
                Array.prototype.forEach.call(box.children, function (c) {
                    c.classList.remove('selected');
                });
                btn.classList.add('selected');
                $('asError').hidden = true;
                // Auto-advance after a short beat (skip on reduced motion).
                var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                setTimeout(next, reduce ? 0 : 220);
            });
            box.appendChild(btn);
        });
        $('asBar').style.width = Math.round(100 * current / questions.length) + '%';
        $('asBack').style.visibility = current === 0 ? 'hidden' : 'visible';
        $('asNext').textContent = current === questions.length - 1 ? 'See my results' : 'Next';
    }

    function next() {
        var q = questions[current];
        if (answers[q.id] === undefined) {
            var err = $('asError');
            err.textContent = 'Please pick an option to continue.';
            err.hidden = false;
            return;
        }
        if (current < questions.length - 1) {
            current += 1;
            render();
        } else {
            submit();
        }
    }

    function back() {
        if (current > 0) { current -= 1; render(); }
    }

    function submit() {
        var btn = $('asNext');
        btn.disabled = true;
        btn.textContent = 'Analyzing…';
        var headers = { 'Content-Type': 'application/json' };
        var tokenMeta = document.querySelector('meta[name="csrf-token"]');
        if (tokenMeta) headers['X-CSRFToken'] = tokenMeta.getAttribute('content');
        fetch('/assessment/submit', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({ answers: answers })
        })
            .then(function (resp) {
                return resp.json().then(function (data) {
                    return { status: resp.status, data: data };
                });
            })
            .then(function (out) {
                if (out.status === 429) {
                    showError('Too many attempts. Please try again later.');
                    return;
                }
                if (!out.data || !out.data.success) {
                    showError((out.data && out.data.error) || 'Could not score your assessment.');
                    return;
                }
                renderResults(out.data.result, out.data.saved_url);
            })
            .catch(function () { showError('Something went wrong. Check your connection and retry.'); })
            .finally(function () { btn.disabled = false; btn.textContent = 'See my results'; });
    }

    function showError(msg) {
        var err = $('asError');
        err.textContent = msg;
        err.hidden = false;
        err.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function renderResults(result, savedUrl, mount) {
        var quiz = $('asQuiz');
        if (quiz) quiz.hidden = true;
        var box = mount || $('asResult');
        if (!box) return;
        box.hidden = false;
        var html = '<div class="as-head"><h1>Your <span class="gradient-text">matches</span></h1>';
        html += '<p>Based on your answers, here are your top career paths. '
            + '<a href="' + esc(savedUrl || '/dashboard') + '" style="color:var(--accent-secondary);">View saved result</a> · '
            + '<a href="/assessment" style="color:var(--accent-secondary);">Retake quiz</a></p></div>';
        if (result.ai_powered) {
            html += '<div class="as-ai-badge">AI-personalized explanations</div>';
        }
        (result.clusters || []).forEach(function (c, i) {
            html += '<div class="as-result-card">';
            html += '<div style="display:flex;justify-content:space-between;align-items:baseline;gap:1rem;">'
                + '<h3>#' + (i + 1) + ' ' + esc(c.name) + '</h3>'
                + '<span class="as-match">' + esc(c.match) + '%</span></div>';
            html += '<div class="as-tagline">' + esc(c.tagline) + '</div>';
            if (c.why) html += '<div class="as-why">' + esc(c.why) + '</div>';
            html += '<div style="font-size:0.85rem;font-weight:700;margin-bottom:0.4rem;">Skills to build</div>';
            html += '<div class="as-skills">' + (c.skills || []).map(function (s) {
                return '<span class="as-chip">' + esc(s) + '</span>';
            }).join('') + '</div>';
            html += '<div class="as-tools"><span style="font-size:0.85rem;font-weight:700;">Try next: </span>';
            (c.tools || []).forEach(function (t, ti) {
                var link = (c.tool_links || [])[ti] || '/resume';
                html += '<a href="' + esc(link) + '">' + esc(t) + '</a>';
            });
            html += '</div></div>';
        });
        box.innerHTML = html;
        window.scrollTo({ top: 0, behavior: 'smooth' });
        window.renderAssessmentResults = renderResults;
    }

    // Saved-result page: server embeds clusters JSON; render on load.
    function initSavedResult() {
        var mount = document.getElementById('asSavedResult');
        if (!mount || !window.__ASSESSMENT_RESULT__) return;
        var data = window.__ASSESSMENT_RESULT__;
        renderResults({ clusters: data.clusters || [], ai_powered: !!data.ai_powered }, null, mount);
        var head = mount.querySelector('.as-head p');
        if (head) head.innerHTML = '<a href="/dashboard" style="color:var(--accent-secondary);">&larr; Back to dashboard</a> · <a href="/assessment" style="color:var(--accent-secondary);">Retake quiz</a>';
    }

    document.addEventListener('DOMContentLoaded', function () {
        if (document.getElementById('asQuiz')) {
            if (!questions.length) {
                showError('Could not load the quiz. Please reload the page.');
                return;
            }
            render();
            $('asNext').addEventListener('click', next);
            $('asBack').addEventListener('click', back);
        }
        initSavedResult();
    });
})();
