/**
 * JD-Matched ATS Scoring (Wave 1, feature #1) - Frontend
 * Handles the "Match my resume to a job description" form and renders the
 * ATS-style report. All user/AI content is HTML-escaped before insertion.
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

    function scoreColor(score) {
        if (score >= 75) return '#10b981';
        if (score >= 50) return '#f59e0b';
        return '#f87171';
    }

    function scoreLabel(score) {
        if (score >= 85) return 'Excellent match';
        if (score >= 70) return 'Strong match';
        if (score >= 55) return 'Decent match';
        if (score >= 40) return 'Needs work';
        return 'Weak match';
    }

    function chip(word, kind) {
        return '<span class="jd-chip jd-chip-' + kind + '">' + esc(word) + '</span>';
    }

    /**
     * Render a JD-match report dict into a container element.
     * The report shape is produced server-side by jd_matcher.score_jd_match.
     */
    function renderJDMatchReport(report, container) {
        if (!report || !container) return;
        var bd = report.breakdown || {};
        var order = ['keyword_coverage', 'skills_hit_rate', 'experience_alignment', 'ats_friendliness'];
        var score = Number(report.score) || 0;
        var color = scoreColor(score);
        var circ = 2 * Math.PI * 54;
        var offset = circ * (1 - Math.min(Math.max(score, 0), 100) / 100);

        var html = '';
        html += '<div class="jd-report">';
        html += '<div class="jd-score-head">';
        html += '<div class="jd-ring" role="img" aria-label="Match score ' + esc(score) + ' out of 100">';
        html += '<svg viewBox="0 0 120 120" width="120" height="120">'
            + '<circle cx="60" cy="60" r="54" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="10"/>'
            + '<circle cx="60" cy="60" r="54" fill="none" stroke="' + color + '" stroke-width="10"'
            + ' stroke-linecap="round" stroke-dasharray="' + circ.toFixed(1) + '"'
            + ' stroke-dashoffset="' + offset.toFixed(1) + '" transform="rotate(-90 60 60)"/></svg>';
        html += '<div class="jd-ring-label"><strong>' + esc(score) + '</strong><span>/100</span></div>';
        html += '</div>';
        html += '<div class="jd-score-meta">';
        html += '<h3>' + esc(scoreLabel(score)) + '</h3>';
        if (report.job_title) html += '<p class="jd-job-title">' + esc(report.job_title) + '</p>';
        if (report.filename) html += '<p class="jd-file">Resume: ' + esc(report.filename) + '</p>';
        html += '<p class="jd-ai-note">' + (report.ai_powered
            ? 'Suggestions refined by AI'
            : 'AI unavailable — showing rule-based suggestions') + '</p>';
        html += '</div></div>';

        html += '<div class="jd-breakdown">';
        order.forEach(function (key) {
            var b = bd[key] || {};
            var bs = Number(b.score) || 0, max = Number(b.max) || 1;
            var pct = Math.min(Math.max(bs / max * 100, 0), 100);
            html += '<div class="jd-bar-row">';
            html += '<div class="jd-bar-head"><span>' + esc(b.label || key) + '</span>'
                + '<span><strong>' + esc(bs) + '</strong>/' + esc(max) + '</span></div>';
            html += '<div class="jd-bar"><div class="jd-bar-fill" style="width:' + pct.toFixed(1)
                + '%;background:' + scoreColor(pct) + '"></div></div>';
            if (b.details) html += '<p class="jd-bar-detail">' + esc(b.details) + '</p>';
            html += '</div>';
        });
        html += '</div>';

        var matched = report.matched_keywords || [];
        var missing = report.missing_keywords || [];
        html += '<div class="jd-kw-grid">';
        html += '<div class="jd-kw-col"><h4>Matched keywords (' + matched.length + ')</h4><div class="jd-chips">'
            + (matched.slice(0, 40).map(function (w) { return chip(w, 'ok'); }).join('')
                || '<span class="jd-none">None yet</span>') + '</div></div>';
        html += '<div class="jd-kw-col"><h4>Missing — add these (' + missing.length + ')</h4><div class="jd-chips">'
            + (missing.slice(0, 40).map(function (w) { return chip(w, 'miss'); }).join('')
                || '<span class="jd-none">None — great coverage</span>') + '</div></div>';
        html += '</div>';

        var suggestions = report.suggestions || [];
        if (suggestions.length) {
            html += '<div class="jd-sugg"><h4>Fix suggestions</h4>';
            suggestions.forEach(function (s, i) {
                html += '<div class="jd-sugg-item"><div class="jd-sugg-num">' + (i + 1) + '</div>'
                    + '<div><p class="jd-sugg-sec">' + esc(s.section) + '</p>'
                    + '<p class="jd-sugg-issue">' + esc(s.issue) + '</p>'
                    + '<p class="jd-sugg-fix">' + esc(s.fix) + '</p></div></div>';
            });
            html += '</div>';
        }
        html += '</div>';
        container.innerHTML = html;
    }

    function setError(msg) {
        var el = document.getElementById('jdError');
        if (!el) return;
        if (!msg) { el.hidden = true; el.textContent = ''; return; }
        el.hidden = false;
        el.textContent = msg;
    }

    function initForm() {
        var form = document.getElementById('jdMatchForm');
        if (!form) return;
        var resultBox = document.getElementById('jdMatchResult');
        var submitBtn = document.getElementById('jdMatchBtn');
        var fileInput = document.getElementById('jdMatchFile');
        var sourceRadios = form.querySelectorAll('input[name="resume_source"]');

        function syncSourceUI() {
            var checked = form.querySelector('input[name="resume_source"]:checked');
            var useUpload = !checked || checked.value === 'upload';
            var wrap = document.getElementById('jdFileWrap');
            if (wrap) wrap.style.display = useUpload ? '' : 'none';
            if (fileInput) fileInput.required = useUpload;
        }
        sourceRadios.forEach(function (r) { r.addEventListener('change', syncSourceUI); });
        syncSourceUI();

        form.addEventListener('submit', function (ev) {
            ev.preventDefault();
            setError('');
            var jdText = (document.getElementById('jdText').value || '').trim();
            if (jdText.length < 50) {
                setError('Please paste the full job description (at least 50 characters).');
                return;
            }
            if (jdText.length > 20000) {
                setError('The job description is too long (max 20,000 characters).');
                return;
            }
            var checked = form.querySelector('input[name="resume_source"]:checked');
            var source = checked ? checked.value : 'upload';
            if (source === 'upload' && (!fileInput.files || !fileInput.files.length)) {
                setError('Please choose your resume file, or pick your saved resume.');
                return;
            }

            var fd = new FormData();
            fd.append('jd_text', jdText);
            fd.append('resume_source', source);
            if (source === 'upload' && fileInput.files.length) {
                fd.append('resume', fileInput.files[0]);
            }

            var tokenMeta = document.querySelector('meta[name="csrf-token"]');
            var headers = {};
            if (tokenMeta) headers['X-CSRFToken'] = tokenMeta.getAttribute('content');

            submitBtn.disabled = true;
            submitBtn.querySelector('span').textContent = 'Matching…';
            resultBox.innerHTML = '<div class="jd-loading"><div class="jd-spinner"></div>'
                + '<p>Comparing your resume against the job description…</p></div>';

            fetch('/jd-match', { method: 'POST', headers: headers, body: fd })
                .then(function (resp) {
                    return resp.json().then(function (data) {
                        return { status: resp.status, data: data };
                    });
                })
                .then(function (out) {
                    if (out.status === 401) {
                        setError('Please log in to use JD matching.');
                        resultBox.innerHTML = '';
                        return;
                    }
                    if (!out.data || !out.data.success) {
                        setError((out.data && out.data.error) || 'Matching failed. Please try again.');
                        resultBox.innerHTML = '';
                        return;
                    }
                    renderJDMatchReport(out.data.report, resultBox);
                    resultBox.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    var link = document.getElementById('jdSavedLink');
                    if (link && out.data.saved_url) {
                        link.hidden = false;
                        link.querySelector('a').setAttribute('href', out.data.saved_url);
                    }
                })
                .catch(function () {
                    setError('Something went wrong. Please check your connection and try again.');
                    resultBox.innerHTML = '';
                })
                .finally(function () {
                    submitBtn.disabled = false;
                    submitBtn.querySelector('span').textContent = 'Check My Match';
                });
        });
    }

    // Saved-report page: the server embeds the report JSON; render on load.
    function initSavedReport() {
        var mount = document.getElementById('jdSavedReport');
        if (!mount || !window.__JD_REPORT__) return;
        renderJDMatchReport(window.__JD_REPORT__, mount);
    }

    document.addEventListener('DOMContentLoaded', function () {
        initForm();
        initSavedReport();
    });

    window.renderJDMatchReport = renderJDMatchReport;
})();
