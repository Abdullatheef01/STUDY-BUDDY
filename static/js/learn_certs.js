/* Certification guidance page JS (Wave 3 #20): recommender, domain browse, study plans. */
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
    function inr(n) {
        return '₹' + Number(n).toLocaleString('en-IN');
    }

    /* ---- recommender ---- */
    var runBtn = el('rec-run');
    if (runBtn) {
        runBtn.addEventListener('click', function () {
            var skills = el('rec-skills').value.split(',')
                .map(function (s) { return s.trim(); })
                .filter(Boolean);
            var payload = {
                skills: skills,
                target_role: el('rec-role').value || null,
                budget_inr: el('rec-budget').value ? parseFloat(el('rec-budget').value) : null,
                top_n: parseInt(el('rec-n').value, 10)
            };
            el('rec-status').textContent = 'Ranking certifications…';
            el('rec-result').innerHTML = '';
            fetch('/learn/certs/recommend', {
                method: 'POST', headers: headers(), body: JSON.stringify(payload)
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.success) {
                    el('rec-status').textContent = data.error || 'Recommendation failed.';
                    return;
                }
                el('rec-status').textContent = '';
                renderRecs(data.recommendations);
            })
            .catch(function () { el('rec-status').textContent = 'Network error. Please try again.'; });
        });
    }

    function renderRecs(recs) {
        var root = el('rec-result');
        if (!recs.length) {
            root.innerHTML = '<div class="b-flash b-flash--info">No certifications match. Try widening your budget.</div>';
            return;
        }
        root.innerHTML = recs.map(function (r, i) {
            var c = r.cert;
            var validity = c.validity_years ? c.validity_years + ' yrs' : 'Lifetime';
            var reasons = (r.reasons || []).map(function (x) {
                return '<li style="margin-bottom:.25rem;">' + esc(x) + '</li>';
            }).join('');
            return '<div class="b-card b-card--lite">'
                + '<div style="display:flex;justify-content:space-between;gap:.6rem;align-items:baseline;">'
                + '<h3 style="margin:0;">' + (i + 1) + '. ' + esc(c.name) + '</h3>'
                + '<span class="b-tag">' + esc(c.difficulty) + '</span></div>'
                + '<div style="color:var(--b-muted);font-size:.88rem;margin:.3rem 0;">' + esc(c.provider) + ' · ' + esc(c.domain) + '</div>'
                + '<div class="b-kv" style="margin:.6rem 0;">'
                + '<div class="b-kv-row"><span class="b-kv-label">Cost</span><span class="b-kv-val">' + inr(c.cost_inr) + '</span></div>'
                + '<div class="b-kv-row"><span class="b-kv-label">Validity</span><span class="b-kv-val">' + esc(validity) + '</span></div>'
                + '</div>'
                + '<ul style="margin:.4rem 0;padding-left:1.2rem;font-size:.9rem;">' + reasons + '</ul>'
                + '<p style="font-size:.88rem;color:var(--b-muted);">' + esc(c.career_value) + '</p>'
                + '<a class="b-btn b-btn--ghost b-btn--sm" style="margin-top:.6rem;" href="/learn/certs/' + encodeURIComponent(c.id) + '">Details &amp; study plan</a>'
                + '</div>';
        }).join('');
        root.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    /* ---- domain browse ---- */
    document.querySelectorAll('.cert-domain').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var list = el('cert-list');
            list.innerHTML = '<div class="b-flash b-flash--info">Loading ' + esc(btn.dataset.domain) + ' certifications…</div>';
            fetch('/learn/certs/browse?domain=' + encodeURIComponent(btn.dataset.domain))
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.success) {
                    list.innerHTML = '<div class="b-flash b-flash--error">Could not load.</div>';
                    return;
                }
                list.innerHTML = '<div class="b-bento">' + data.certifications.map(function (c) {
                    var validity = c.validity_years ? c.validity_years + ' yrs' : 'Lifetime';
                    return '<a class="b-card b-card--lite" href="' + esc(c.url) + '">'
                        + '<h3 style="margin:0 0 .3rem;">' + esc(c.name) + '</h3>'
                        + '<div style="color:var(--b-muted);font-size:.85rem;">' + esc(c.provider) + '</div>'
                        + '<div class="b-kv" style="margin-top:.6rem;">'
                        + '<div class="b-kv-row"><span class="b-kv-label">Cost</span><span class="b-kv-val">' + inr(c.cost_inr) + ' <span style="font-size:.75rem;color:var(--b-muted);">approx</span></span></div>'
                        + '<div class="b-kv-row"><span class="b-kv-label">Level</span><span class="b-kv-val">' + esc(c.difficulty) + '</span></div>'
                        + '<div class="b-kv-row"><span class="b-kv-label">Valid</span><span class="b-kv-val">' + esc(validity) + '</span></div>'
                        + '</div></a>';
                }).join('') + '</div>';
                list.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            })
            .catch(function () {
                list.innerHTML = '<div class="b-flash b-flash--error">Network error.</div>';
            });
        });
    });

    /* ---- study plan generator (cert detail) ---- */
    var planBtn = el('plan-generate');
    if (planBtn) {
        planBtn.addEventListener('click', function () {
            var status = el('plan-status'), out = el('plan-result');
            status.textContent = 'Building your week-by-week plan…';
            out.innerHTML = '';
            fetch('/learn/certs/plan', {
                method: 'POST', headers: headers(),
                body: JSON.stringify({
                    cert_id: planBtn.dataset.cert,
                    weeks: parseInt(el('plan-weeks').value, 10)
                })
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.success) {
                    status.textContent = data.error || 'Plan generation failed.';
                    return;
                }
                status.textContent = 'Plan saved to your account.';
                renderPlan(out, data.plan);
            })
            .catch(function () { status.textContent = 'Network error. Please try again.'; });
        });
    }

    function renderPlan(root, plan) {
        var html = '<h3>' + esc(plan.cert_name) + ' — ' + plan.weeks + '-week plan</h3>'
            + '<p style="color:var(--b-muted);font-size:.9rem;">Exam format: ' + esc(plan.exam_format) + '</p>'
            + '<ol>';
        plan.plan.forEach(function (w) {
            html += '<li style="margin-bottom:1rem;"><strong>Week ' + w.week + ' — ' + esc(w.focus) + '</strong>';
            if (w.topics && w.topics.length) {
                html += '<ul style="margin:.3rem 0;">' + w.topics.slice(0, 4).map(function (t) {
                    return '<li style="font-size:.9rem;">' + esc(t.topic) + ' <span style="color:var(--b-muted);">(' + esc(t.skill) + ')</span></li>';
                }).join('') + '</ul>';
            }
            if (w.resources && w.resources.length) {
                html += '<div style="font-size:.88rem;">Resources: ' + w.resources.map(function (r) {
                    return '<a href="' + esc(r.url) + '" target="_blank" rel="noopener noreferrer">' + esc(r.title) + '</a>';
                }).join(' · ') + '</div>';
            }
            html += '</li>';
        });
        html += '</ol>';
        root.innerHTML = html;
        root.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
})();
