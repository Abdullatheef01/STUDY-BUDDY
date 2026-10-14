/* India Salary Explorer (Wave 1 #8) — XSS-safe rendering via textContent only. */
(function () {
    'use strict';
    var opts = window.SALARY_OPTIONS || {};
    var authed = !!window.SALARY_AUTHED;
    var roles = opts.roles || [];
    var tiers = opts.tiers || {};
    var bands = opts.experience_bands || [];
    var meta = opts.meta || {};

    var fRole = document.getElementById('fRole');
    var fTier = document.getElementById('fTier');
    var fBand = document.getElementById('fBand');
    var grid = document.getElementById('salGrid');
    var countEl = document.getElementById('salCount');
    var compareVal = null;

    function el(tag, cls, text) {
        var n = document.createElement(tag);
        if (cls) n.className = cls;
        if (text !== undefined && text !== null) n.textContent = text;
        return n;
    }

    function fillSelect(sel, items, allLabel) {
        sel.textContent = '';
        var all = document.createElement('option');
        all.value = '';
        all.textContent = allLabel;
        sel.appendChild(all);
        items.forEach(function (it) {
            var o = document.createElement('option');
            o.value = it.value;
            o.textContent = it.label;
            sel.appendChild(o);
        });
    }

    fillSelect(fRole, roles.map(function (r) { return { value: r, label: r }; }), 'All roles');
    fillSelect(fTier, Object.keys(tiers).map(function (k) {
        return { value: k, label: tiers[k].label + ' — ' + tiers[k].cities.join(', ') };
    }), 'All tiers');
    fillSelect(fBand, bands.map(function (b) { return { value: b, label: b + ' yrs' }; }), 'All experience');

    function fmt(n) { return '₹' + n + ' LPA'; }

    function renderCard(e) {
        var card = el('div', 'sal-card b-card b-card--lite');
        card.appendChild(el('h3', null, e.role));
        card.appendChild(el('div', 'sal-sub',
            e.tier_label + ' · ' + e.cities.join(', ') + ' · ' + e.experience_band + ' yrs exp'));

        // Range bar: pad the domain a little so markers never sit on the edge.
        var lo = e.min_lpa, md = e.median_lpa, hi = e.max_lpa;
        var pad = Math.max((hi - lo) * 0.08, 0.2);
        var dMin = Math.max(0, lo - pad), dMax = hi + pad;
        var pct = function (v) { return ((v - dMin) / (dMax - dMin)) * 100; };

        var bar = el('div', 'sal-bar');
        bar.setAttribute('role', 'img');
        bar.setAttribute('aria-label', 'Salary range ' + fmt(lo) + ' to ' + fmt(hi) + ', median ' + fmt(md));
        var fill = el('div', 'fill');
        fill.style.left = pct(lo) + '%';
        fill.style.width = (pct(hi) - pct(lo)) + '%';
        bar.appendChild(fill);
        var med = el('div', 'med');
        med.style.left = 'calc(' + pct(md) + '% - 1.5px)';
        med.title = 'Median ' + fmt(md);
        bar.appendChild(med);
        if (compareVal !== null) {
            var c = Math.min(Math.max(compareVal, dMin), dMax);
            var you = el('div', 'you');
            you.style.left = 'calc(' + pct(c) + '% - 1px)';
            you.title = 'Your expected: ' + fmt(compareVal);
            bar.appendChild(you);
        }
        card.appendChild(bar);

        var nums = el('div', 'sal-nums');
        nums.appendChild(el('span', 'lo', 'Min ' + fmt(lo)));
        nums.appendChild(el('span', 'md', 'Median ' + fmt(md)));
        nums.appendChild(el('span', 'hi', 'Max ' + fmt(hi)));
        card.appendChild(nums);
        return card;
    }

    function render(entries) {
        grid.textContent = '';
        if (!entries.length) {
            grid.appendChild(el('div', 'sal-empty', 'No ranges match these filters.'));
        } else {
            entries.forEach(function (e) { grid.appendChild(renderCard(e)); });
        }
        countEl.textContent = entries.length
            ? 'Showing ' + entries.length + ' indicative range' + (entries.length === 1 ? '' : 's') + '.'
            : '';
    }

    function load() {
        var q = new URLSearchParams();
        if (fRole.value) q.set('role', fRole.value);
        if (fTier.value) q.set('tier', fTier.value);
        if (fBand.value) q.set('band', fBand.value);
        fetch('/salary/data?' + q.toString(), { headers: { 'Accept': 'application/json' } })
            .then(function (r) { return r.json(); })
            .then(function (body) {
                if (!body || !body.success) { render([]); return; }
                render(body.entries || []);
            })
            .catch(function () { render([]); });
    }

    [fRole, fTier, fBand].forEach(function (s) {
        s.addEventListener('change', load);
    });

    if (authed) {
        var cmpInput = document.getElementById('cmpVal');
        document.getElementById('cmpBtn').addEventListener('click', function () {
            var v = parseFloat(cmpInput.value);
            if (isNaN(v) || v <= 0 || v > 200) {
                cmpInput.style.borderColor = 'var(--accent-danger)';
                return;
            }
            cmpInput.style.borderColor = '';
            compareVal = Math.round(v * 2) / 2;
            load();
        });
        document.getElementById('cmpClear').addEventListener('click', function () {
            compareVal = null;
            cmpInput.value = '';
            load();
        });
    }

    // Disclaimer note is rendered server-side in the template.

    load();
})();
