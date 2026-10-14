/* Learn roadmaps page JS (Wave 3 #18): skill filter, gap analyzer, progress toggles. */
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

    /* ---- skill domain filter (roadmaps home) ---- */
    var filter = document.getElementById('skill-filter');
    if (filter) {
        filter.addEventListener('change', function () {
            var want = filter.value;
            document.querySelectorAll('.skill-card').forEach(function (card) {
                card.style.display = (!want || card.dataset.domain === want) ? '' : 'none';
            });
        });
    }

    /* ---- gap analyzer ---- */
    var runBtn = document.getElementById('gap-run');
    if (runBtn) {
        runBtn.addEventListener('click', function () {
            var role = document.getElementById('gap-role').value;
            var status = document.getElementById('gap-status');
            var result = document.getElementById('gap-result');
            if (!role) {
                status.textContent = 'Please choose a target role first.';
                return;
            }
            var current = [];
            document.querySelectorAll('.gap-skill:checked').forEach(function (cb) {
                var stageSel = cb.closest('label').querySelector('.gap-stage');
                current.push({ skill_id: cb.value, stage: stageSel ? stageSel.value : 'beginner' });
            });
            status.textContent = 'Analyzing gaps…';
            result.innerHTML = '';
            fetch('/learn/roadmaps/gap', {
                method: 'POST', headers: headers(),
                body: JSON.stringify({ target_role: role, current_skills: current })
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.success) {
                    status.textContent = data.error || 'Analysis failed.';
                    return;
                }
                status.textContent = '';
                renderGap(result, data);
            })
            .catch(function () { status.textContent = 'Network error. Please try again.'; });
        });
    }

    function renderGap(root, data) {
        var html = '';
        html += '<div class="b-card b-card--lite" style="margin-bottom:1rem;"><div class="b-kv">'
            + '<div class="b-kv-row"><span class="b-kv-label">Target role</span><span class="b-kv-val">' + esc(data.role.name) + '</span></div>'
            + '<div class="b-kv-row"><span class="b-kv-label">Skills to close</span><span class="b-kv-val">' + data.num_skills + '</span></div>'
            + '<div class="b-kv-row"><span class="b-kv-label">Estimated effort</span><span class="b-kv-val">' + data.total_weeks + ' weeks</span></div>'
            + '</div>'
            + '<div class="b-flash b-flash--info" style="margin:1rem 0 0;"><strong>Study tip' + (data.ai_powered ? ' (AI)' : '') + ':</strong> ' + esc(data.study_tip) + '</div></div>';
        if (!data.gaps.length) {
            html += '<div class="b-flash b-flash--success"><strong>No gaps found</strong> — you already meet every required skill for this role. Consider a harder target role.</div>';
        } else {
            html += '<div class="b-bento">';
            data.gaps.forEach(function (g, i) {
                html += '<div class="b-card b-card--lite">'
                    + '<div style="display:flex;justify-content:space-between;gap:.6rem;align-items:baseline;">'
                    + '<h3 style="margin:0;">' + (i + 1) + '. ' + esc(g.skill_name) + '</h3>'
                    + '<span class="b-tag">priority ' + g.priority + '/5</span></div>'
                    + '<p style="color:var(--b-muted);font-size:.9rem;">' + esc(g.reason) + '</p>'
                    + '<div class="b-kv">'
                    + '<div class="b-kv-row"><span class="b-kv-label">You are at</span><span class="b-kv-val">' + esc(g.current_stage || 'not started') + '</span></div>'
                    + '<div class="b-kv-row"><span class="b-kv-label">Need</span><span class="b-kv-val">' + esc(g.min_stage) + '</span></div>'
                    + '<div class="b-kv-row"><span class="b-kv-label">Effort</span><span class="b-kv-val">' + g.weeks_needed + ' weeks</span></div>'
                    + '</div>'
                    + '<a class="b-btn b-btn--ghost b-btn--sm" style="margin-top:.8rem;" href="/learn/roadmaps/' + encodeURIComponent(g.skill_id) + '">Open roadmap</a>'
                    + '</div>';
            });
            html += '</div>';
        }
        root.innerHTML = html;
        root.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    /* ---- stage progress toggles (roadmap detail) ---- */
    document.querySelectorAll('.stage-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var payload = {
                skill_id: btn.dataset.skill,
                stage: btn.dataset.stage,
                status: btn.dataset.status
            };
            fetch('/learn/roadmaps/progress', {
                method: 'POST', headers: headers(), body: JSON.stringify(payload)
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.success) return;
                // refresh the button group to reflect the new state
                var group = btn.parentElement;
                group.querySelectorAll('.stage-btn').forEach(function (b) {
                    var active = b.dataset.status === data.status;
                    b.classList.toggle('b-btn--primary', active);
                    b.classList.toggle('b-btn--ghost', !active);
                });
            })
            .catch(function () { /* silent: non-critical */ });
        });
    });
})();
