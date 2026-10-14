/* Flashcard review + quiz mode UI. */
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

    var dataEl = $('fc-data');
    if (!dataEl) return;
    var cards = [];
    try { cards = JSON.parse(dataEl.textContent || '[]'); } catch (e) { cards = []; }
    var setId = window.location.pathname.split('/').filter(Boolean).pop();
    var idx = 0, flipped = false;

    function showError(msg) {
        var e = $('fc-error');
        e.textContent = msg; e.style.display = 'block';
    }

    /* ---------- flashcard mode ---------- */
    function renderCard() {
        var c = cards[idx];
        if (!c) {
            $('fc-q').textContent = 'No cards in this deck.';
            return;
        }
        flipped = false;
        $('fc-progress').textContent = 'Card ' + (idx + 1) + ' of ' + cards.length;
        $('fc-kind').textContent = c.kind === 'mcq' ? 'Multiple choice' : (c.kind === 'cloze' ? 'Fill in the blank' : 'Q & A');
        $('fc-q').textContent = c.question;
        $('fc-a').style.display = 'none';
        $('fc-src').style.display = 'none';
        if (c.kind === 'mcq' && c.options) {
            $('fc-a').innerHTML = 'Answer: <strong>' + esc(c.answer) + '</strong>';
        } else {
            $('fc-a').textContent = c.answer;
        }
        var src = [];
        if (c.doc_title) src.push(esc(c.doc_title));
        if (c.page) src.push('p.' + esc(c.page));
        $('fc-src').innerHTML = src.length ? 'Source: ' + src.join(', ') : '';
    }
    function flip() {
        if (!cards[idx]) return;
        flipped = !flipped;
        $('fc-a').style.display = flipped ? 'block' : 'none';
        $('fc-src').style.display = flipped ? 'block' : 'none';
    }
    $('fc-card').addEventListener('click', flip);
    $('fc-card').addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); flip(); }
    });
    $('fc-flip').addEventListener('click', flip);
    $('fc-prev').addEventListener('click', function () {
        if (idx > 0) { idx--; renderCard(); }
    });
    $('fc-next').addEventListener('click', function () {
        if (idx < cards.length - 1) { idx++; renderCard(); }
    });

    function mark(known) {
        var c = cards[idx];
        if (!c) return;
        fetch('/research/api/flashcards/' + setId + '/progress', {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ card_id: c.id, known: known })
        })
        .then(function (r) { return r.json().catch(function () { return {}; }); })
        .then(function (data) {
            if (data.stats) {
                $('fc-stats-line').textContent = 'Mastery: ' + data.stats.mastery_pct +
                    '% · ' + data.stats.known + '/' + data.stats.total + ' known';
            }
            if (idx < cards.length - 1) { idx++; renderCard(); }
        })
        .catch(function () { showError('Could not save progress.'); });
    }
    $('fc-known').addEventListener('click', function () { mark(true); });
    $('fc-unknown').addEventListener('click', function () { mark(false); });

    /* ---------- quiz mode ---------- */
    var mcqs = cards.filter(function (c) { return c.kind === 'mcq'; });
    var answers = {};
    function renderQuiz() {
        var box = $('fq-options');
        box.innerHTML = '';
        mcqs.forEach(function (c, i) {
            var wrap = document.createElement('div');
            wrap.className = 'b-card b-card--lite';
            wrap.style.marginBottom = '.6rem';
            var opts = (c.options || []).map(function (o, oi) {
                return '<label style="display:flex;gap:.5rem;align-items:center;cursor:pointer;padding:.3rem 0;">' +
                    '<input type="radio" class="b-check" name="fq-' + esc(c.id) + '" value="' + oi + '"> ' +
                    '<span>' + esc(o) + '</span></label>';
            }).join('');
            wrap.innerHTML = '<p style="margin:0 0 .5rem;"><strong>Q' + (i + 1) + '.</strong> ' + esc(c.question) + '</p>' + opts;
            box.appendChild(wrap);
        });
        $('fq-progress').textContent = mcqs.length + ' questions';
    }
    $('fc-mode-cards').addEventListener('click', function () {
        $('fc-cards-mode').style.display = 'block';
        $('fc-quiz-mode').style.display = 'none';
    });
    $('fc-mode-quiz').addEventListener('click', function () {
        $('fc-cards-mode').style.display = 'none';
        $('fc-quiz-mode').style.display = 'block';
        renderQuiz();
    });
    $('fq-submit').addEventListener('click', function () {
        answers = {};
        mcqs.forEach(function (c) {
            var sel = document.querySelector('input[name="fq-' + c.id + '"]:checked');
            if (sel) answers[c.id] = parseInt(sel.value, 10);
        });
        var fb = $('fq-feedback');
        fb.style.display = 'none';
        fetch('/research/api/flashcards/' + setId + '/quiz', {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ answers: answers })
        })
        .then(function (r) { return r.json().catch(function () { return { error: 'Bad response' }; }); })
        .then(function (data) {
            if (data.error) { showError(data.error); return; }
            var sc = $('fq-score');
            sc.textContent = 'Score: ' + data.score + '/' + data.total;
            sc.style.display = 'inline-flex';
            var details = (data.details || []).map(function (d) {
                return '<p style="font-size:.88rem;margin:.4rem 0;">' +
                    (d.correct ? '✓' : '✗') + ' <strong>' + esc(d.chosen || '—') + '</strong>' +
                    (d.correct ? '' : ' → correct: <strong>' + esc(d.answer) + '</strong>') + '</p>';
            }).join('');
            fb.className = '';
            fb.innerHTML = details;
            fb.style.display = 'block';
        })
        .catch(function () { showError('Network error — please try again.'); });
    });

    renderCard();
})();
