/**
 * LinkedIn Profile Grader (Wave 1, feature #5) - Frontend
 * Handles the profile-text form and renders the 0-100 grading report.
 * All user/AI content is HTML-escaped before insertion.
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
        if (score >= 85) return 'Recruiter-ready';
        if (score >= 70) return 'Strong profile';
        if (score >= 55) return 'Decent profile';
        if (score >= 40) return 'Needs work';
        return 'Weak profile';
    }

    var BREAKDOWN_LABELS = {
        headline_strength: 'Headline strength',
        about_quality: 'About section',
        experience_quantification: 'Experience quantification',
        skills_relevance: 'Skills relevance',
        completeness: 'Completeness'
    };

    /**
     * Render a LinkedIn grading report dict into a container element.
     * The report shape is produced server-side by linkedin_grader.grade_linkedin_profile.
     */
    function renderLinkedInReport(report, container) {
        if (!report || !container) return;
        var bd = report.breakdown || {};
        var order = ['headline_strength', 'about_quality', 'experience_quantification',
                     'skills_relevance', 'completeness'];
        var score = Number(report.score) || 0;
        var color = scoreColor(score);
        var circ = 2 * Math.PI * 54;
        var offset = circ * (1 - Math.min(Math.max(score, 0), 100) / 100);

        var html = '';
        html += '<div class="jd-report">';
        html += '<div class="jd-score-head">';
        html += '<div class="jd-ring" role="img" aria-label="Profile grade ' + esc(score) + ' out of 100">';
        html += '<svg viewBox="0 0 120 120" width="120" height="120">'
            + '<circle cx="60" cy="60" r="54" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="10"/>'
            + '<circle cx="60" cy="60" r="54" fill="none" stroke="' + color + '" stroke-width="10"'
            + ' stroke-linecap="round" stroke-dasharray="' + circ.toFixed(1) + '"'
            + ' stroke-dashoffset="' + offset.toFixed(1) + '" transform="rotate(-90 60 60)"/></svg>';
        html += '<div class="jd-ring-label"><strong>' + esc(score) + '</strong><span>/100</span></div>';
        html += '</div>';
        html += '<div class="jd-score-meta"><h3>' + esc(scoreLabel(score)) + '</h3>';
        if (report.summary) html += '<p>' + esc(report.summary) + '</p>';
        if (report.ai_powered) {
            html += '<p class="jd-ai-badge">AI-polished suggestions</p>';
        }
        html += '</div></div>';

        html += '<div class="jd-breakdown">';
        order.forEach(function (key) {
            var val = Number(bd[key]) || 0;
            var label = BREAKDOWN_LABELS[key] || key;
            html += '<div class="jd-bar-row"><span class="jd-bar-label">' + esc(label) + '</span>'
                + '<span class="jd-bar-track"><span class="jd-bar-fill" style="width:'
                + Math.min(Math.max(val, 0), 100) + '%;background:' + scoreColor(val) + ';"></span></span>'
                + '<span class="jd-bar-val">' + esc(val) + '</span></div>';
        });
        html += '</div>';

        var fixes = report.suggestions || [];
        if (fixes.length) {
            html += '<h4 class="jd-subhead">Prioritized fixes</h4><ol class="jd-fixes">';
            fixes.forEach(function (f) {
                html += '<li><strong>' + esc(f.section) + ':</strong> ' + esc(f.fix) + '</li>';
            });
            html += '</ol>';
        }
        html += '</div>';
        container.innerHTML = html;
    }

    function initForm() {
        var form = document.getElementById('linkedinForm');
        if (!form) return;
        var errorBox = document.getElementById('liError');
        var resultBox = document.getElementById('liResult');
        var submitBtn = document.getElementById('liBtn');

        function setError(msg) {
            errorBox.textContent = msg;
            errorBox.hidden = !msg;
        }

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            setError('');
            var fields = {
                headline: document.getElementById('liHeadline').value,
                about: document.getElementById('liAbout').value,
                experience: document.getElementById('liExperience').value,
                skills: document.getElementById('liSkills').value
            };
            if (!fields.headline.trim() && !fields.about.trim()
                && !fields.experience.trim() && !fields.skills.trim()) {
                setError('Paste at least one profile section to grade.');
                return;
            }

            var tokenMeta = document.querySelector('meta[name="csrf-token"]');
            var headers = { 'Content-Type': 'application/json' };
            if (tokenMeta) headers['X-CSRFToken'] = tokenMeta.getAttribute('content');

            submitBtn.disabled = true;
            submitBtn.querySelector('span').textContent = 'Grading…';
            resultBox.innerHTML = '<div class="jd-loading"><div class="jd-spinner"></div>'
                + '<p>Grading your LinkedIn profile…</p></div>';

            fetch('/linkedin-grade', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(fields)
            })
                .then(function (resp) {
                    return resp.json().then(function (data) {
                        return { status: resp.status, data: data };
                    });
                })
                .then(function (out) {
                    if (out.status === 401) {
                        setError('Please log in to grade your profile.');
                        resultBox.innerHTML = '';
                        return;
                    }
                    if (out.status === 429) {
                        setError('Too many grading requests. Please try again later.');
                        resultBox.innerHTML = '';
                        return;
                    }
                    if (!out.data || !out.data.success) {
                        setError((out.data && out.data.error) || 'Grading failed. Please try again.');
                        resultBox.innerHTML = '';
                        return;
                    }
                    renderLinkedInReport(out.data.report, resultBox);
                    resultBox.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    var link = document.getElementById('liSavedLink');
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
                    submitBtn.querySelector('span').textContent = 'Grade My Profile';
                });
        });
    }

    // Saved-report page: the server embeds the report JSON; render on load.
    function initSavedReport() {
        var mount = document.getElementById('liSavedReport');
        if (!mount || !window.__LINKEDIN_REPORT__) return;
        renderLinkedInReport(window.__LINKEDIN_REPORT__, mount);
    }

    document.addEventListener('DOMContentLoaded', function () {
        initForm();
        initSavedReport();
    });

    window.renderLinkedInReport = renderLinkedInReport;
})();
