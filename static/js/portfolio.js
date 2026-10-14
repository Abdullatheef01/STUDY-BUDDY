/* Portfolio builder (Wave 1 #12) — XSS-safe: textContent only, no innerHTML. */
(function () {
    'use strict';
    var existing = window.PORTFOLIO_EXISTING || null;
    var tokenMeta = document.querySelector('meta[name="csrf-token"]');

    var fName = document.getElementById('fName');
    var fHeadline = document.getElementById('fHeadline');
    var fBio = document.getElementById('fBio');
    var fSkills = document.getElementById('fSkills');
    var projRows = document.getElementById('projRows');
    var linkRows = document.getElementById('linkRows');
    var saveBtn = document.getElementById('saveBtn');
    var msg = document.getElementById('pbMsg');

    function el(tag, cls, text) {
        var n = document.createElement(tag);
        if (cls) n.className = cls;
        if (text !== undefined && text !== null) n.textContent = text;
        return n;
    }

    function inputRow(fields, values) {
        var row = el('div', 'pb-row' + (fields.length === 3 ? ' pb-row3' : ''));
        var inputs = [];
        fields.forEach(function (f, i) {
            var inp = document.createElement('input');
            inp.type = 'text';
            inp.placeholder = f;
            inp.maxLength = i === 0 ? 80 : 500;
            if (values && values[i]) inp.value = values[i];
            inp.addEventListener('input', renderPreview);
            row.appendChild(inp);
            inputs.push(inp);
        });
        var del = el('button', 'pb-mini', '✕');
        del.type = 'button';
        del.setAttribute('aria-label', 'Remove row');
        del.addEventListener('click', function () { row.remove(); renderPreview(); });
        row.appendChild(del);
        return { row: row, inputs: inputs };
    }

    var projInputs = [];
    var linkInputs = [];

    function addProject(values) {
        var r = inputRow(['Title', 'Description', 'Link (https://…)'], values);
        projRows.appendChild(r.row);
        projInputs.push(r.inputs);
    }
    function addLink(values) {
        var r = inputRow(['Label', 'URL (https://…)'], values);
        linkRows.appendChild(r.row);
        linkInputs.push(r.inputs);
    }

    document.getElementById('addProj').addEventListener('click', function () { addProject(); });
    document.getElementById('addLink').addEventListener('click', function () { addLink(); });

    if (existing) {
        (existing.projects || []).forEach(function (p) { addProject([p.title, p.description, p.link || '']); });
        (existing.links || []).forEach(function (l) { addLink([l.label, l.url]); });
    }
    if (!projInputs.length) addProject();
    if (!linkInputs.length) addLink();

    function collect() {
        var projects = projInputs
            .map(function (ins) { return { title: ins[0].value.trim(), description: ins[1].value.trim(), link: ins[2].value.trim() }; })
            .filter(function (p) { return p.title || p.description || p.link; });
        var links = linkInputs
            .map(function (ins) { return { label: ins[0].value.trim(), url: ins[1].value.trim() }; })
            .filter(function (l) { return l.label || l.url; });
        var gh = document.getElementById('fGithub');
        var lc = document.getElementById('fLeetcode');
        return {
            display_name: fName.value.trim(),
            headline: fHeadline.value.trim(),
            bio: fBio.value.trim(),
            skills: fSkills.value.split(',').map(function (s) { return s.trim(); }).filter(Boolean),
            projects: projects,
            links: links,
            show_github: gh ? gh.checked : false,
            show_leetcode: lc ? lc.checked : false,
            is_published: document.getElementById('fPublish').checked,
        };
    }

    // ---- live preview ----
    var pvName = document.getElementById('pvName');
    var pvHeadline = document.getElementById('pvHeadline');
    var pvBio = document.getElementById('pvBio');
    var pvSkills = document.getElementById('pvSkills');
    var pvProjects = document.getElementById('pvProjects');
    var pvLinks = document.getElementById('pvLinks');

    function renderPreview() {
        var d = collect();
        pvName.textContent = d.display_name || 'Your name';
        pvHeadline.textContent = d.headline;
        pvBio.textContent = d.bio;
        pvSkills.textContent = '';
        if (!d.skills.length) pvSkills.appendChild(el('span', 'pv-empty', 'Add skills to see them here.'));
        d.skills.forEach(function (s) { pvSkills.appendChild(el('span', 'pv-chip', s)); });
        pvProjects.textContent = '';
        if (!d.projects.length) pvProjects.appendChild(el('p', 'pv-empty', 'Add projects to see them here.'));
        d.projects.forEach(function (p) {
            var card = el('div', 'pv-proj');
            card.appendChild(el('h3', null, p.title || 'Untitled project'));
            if (p.description) card.appendChild(el('p', null, p.description));
            if (p.link) card.appendChild(el('span', 'pv-plink', p.link));
            pvProjects.appendChild(card);
        });
        pvLinks.textContent = '';
        d.links.forEach(function (l) {
            if (l.label) pvLinks.appendChild(el('span', null, l.label));
        });
    }

    [fName, fHeadline, fBio, fSkills].forEach(function (i) {
        i.addEventListener('input', renderPreview);
    });

    function setMsg(text, ok) {
        msg.textContent = text;
        msg.className = 'pb-msg ' + (ok ? 'ok' : 'err');
    }

    saveBtn.addEventListener('click', function () {
        var headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
        if (tokenMeta) headers['X-CSRFToken'] = tokenMeta.getAttribute('content');
        saveBtn.disabled = true;
        setMsg('Saving…', true);
        fetch('/portfolio/save', { method: 'POST', headers: headers, body: JSON.stringify(collect()) })
            .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
            .then(function (res) {
                saveBtn.disabled = false;
                if (!res.body || !res.body.success) {
                    setMsg((res.body && res.body.error) || 'Could not save. Please try again.', false);
                    return;
                }
                setMsg('Saved!' + (res.body.is_published ? ' Your portfolio is live.' : ' Publish it to share the link.'), true);
                var wrap = document.getElementById('pubLinkWrap');
                var link = document.getElementById('pubLink');
                if (wrap && link && res.body.public_url) {
                    wrap.style.display = '';
                    link.href = res.body.public_url;
                    link.textContent = res.body.public_url;
                }
            })
            .catch(function () {
                saveBtn.disabled = false;
                setMsg('Network error. Please try again.', false);
            });
    });

    renderPreview();
})();
