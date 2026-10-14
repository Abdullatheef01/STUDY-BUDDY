/* Citation formatter page (study feature). XSS-safe: textContent only. */
(function () {
    'use strict';

    function $(id) { return document.getElementById(id); }

    function csrfHeaders(extra) {
        var headers = extra || {};
        var m = document.querySelector('meta[name="csrf-token"]');
        if (m) headers['X-CSRFToken'] = m.getAttribute('content');
        return headers;
    }

    function showError(msg) {
        var box = $('cite-error');
        box.textContent = msg;
        box.style.display = 'block';
    }

    function hideError() { $('cite-error').style.display = 'none'; }

    var state = { style: 'ieee', timer: null };

    /* -- form <-> metadata ------------------------------------------------ */

    function readMeta() {
        var authorsRaw = $('cite-authors').value || '';
        var authors = authorsRaw.split(/\r?\n|;/).map(function (a) {
            return a.trim();
        }).filter(Boolean);
        return {
            title: $('cite-title').value.trim(),
            authors: authors,
            year: $('cite-year').value.trim(),
            venue: $('cite-venue').value.trim(),
            volume: $('cite-volume').value.trim(),
            issue: $('cite-issue').value.trim(),
            pages: $('cite-pages').value.trim(),
            doi: $('cite-doi').value.trim(),
            arxiv_id: $('cite-arxiv').value.trim(),
            url: $('cite-url').value.trim(),
            pubtype: $('cite-pubtype').value
        };
    }

    function fillForm(meta) {
        if (!meta) return;
        if (meta.title !== undefined) $('cite-title').value = meta.title || '';
        if (meta.authors) $('cite-authors').value = meta.authors.join('\n');
        if (meta.year !== undefined) $('cite-year').value = meta.year || '';
        if (meta.venue !== undefined) $('cite-venue').value = meta.venue || '';
        if (meta.volume !== undefined) $('cite-volume').value = meta.volume || '';
        if (meta.issue !== undefined) $('cite-issue').value = meta.issue || '';
        if (meta.pages !== undefined) $('cite-pages').value = meta.pages || '';
        if (meta.doi !== undefined) $('cite-doi').value = meta.doi || '';
        if (meta.arxiv_id !== undefined) $('cite-arxiv').value = meta.arxiv_id || '';
        if (meta.url !== undefined) $('cite-url').value = meta.url || '';
        if (meta.pubtype) $('cite-pubtype').value = meta.pubtype;
    }

    function prefillFromQuery() {
        var q = new URLSearchParams(window.location.search);
        var meta = {};
        ['title', 'year', 'venue', 'doi', 'arxiv_id', 'url'].forEach(function (k) {
            if (q.get(k)) meta[k] = q.get(k);
        });
        if (q.get('authors')) meta.authors = q.get('authors').split(/\r?\n|;/);
        if (q.get('volume')) meta.volume = q.get('volume');
        if (q.get('issue')) meta.issue = q.get('issue');
        if (q.get('pages')) meta.pages = q.get('pages');
        if (Object.keys(meta).length) fillForm(meta);
    }

    /* -- style pills ------------------------------------------------------- */

    function setPill(btn, on) {
        btn.classList.toggle('b-btn--primary', on);
        btn.classList.toggle('b-btn--ghost', !on);
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    }

    function selectStyle(style, btn) {
        state.style = style;
        Array.prototype.forEach.call(
            document.querySelectorAll('.cite-pill'),
            function (b) { setPill(b, b === btn); });
        loadGuide();
        reformat();
    }

    /* -- formatting -------------------------------------------------------- */

    function reformat() {
        hideError();
        var payload = { meta: readMeta(), style: state.style };
        fetch('/api/cite/format', {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(payload)
        }).then(function (resp) {
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            return resp.json();
        }).then(function (data) {
            $('cite-output').textContent = data.citation || '';
        }).catch(function () {
            showError('Could not format the citation. Check the details and try again.');
        });
    }

    function reformatDebounced() {
        clearTimeout(state.timer);
        state.timer = setTimeout(reformat, 350);
    }

    /* -- BibTeX ------------------------------------------------------------ */

    function exportBibtex() {
        hideError();
        fetch('/api/cite/bibtex/export', {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ meta: readMeta() })
        }).then(function (resp) {
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            return resp.json();
        }).then(function (data) {
            $('cite-bibtex-out').value = data.bibtex || '';
        }).catch(function () {
            showError('Could not generate BibTeX. Check the details and try again.');
        });
    }

    function downloadBib() {
        var text = $('cite-bibtex-out').value;
        if (!text) { exportBibtex(); return; }
        var blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'citation.bib';
        document.body.appendChild(a);
        a.click();
        setTimeout(function () {
            URL.revokeObjectURL(a.href);
            a.remove();
        }, 500);
    }

    function importBibtex() {
        hideError();
        var text = $('cite-bibtex-in').value;
        if (!text.trim()) {
            showError('Paste a BibTeX entry first.');
            return;
        }
        fetch('/api/cite/bibtex/import', {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ text: text })
        }).then(function (resp) {
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            return resp.json();
        }).then(function (data) {
            var metas = data.metas || [];
            if (!metas.length) {
                showError('No valid BibTeX entries found in the pasted text.');
                return;
            }
            fillForm(metas[0]);
            reformat();
        }).catch(function () {
            showError('Could not import BibTeX. Check the pasted text and try again.');
        });
    }

    /* -- style guide ------------------------------------------------------- */

    function loadGuide() {
        var box = $('cite-guide');
        fetch('/api/cite/guide/' + encodeURIComponent(state.style), {
            headers: csrfHeaders({})
        }).then(function (resp) {
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            return resp.json();
        }).then(function (g) {
            while (box.firstChild) box.removeChild(box.firstChild);
            $('cite-guide-style').textContent = '— ' + state.style.toUpperCase();

            var h3 = document.createElement('h3');
            h3.textContent = 'In-text citation';
            h3.style.margin = '0 0 .4rem';
            h3.style.fontSize = '1rem';
            box.appendChild(h3);
            var p = document.createElement('p');
            p.textContent = g.in_text || '';
            p.style.margin = '0 0 1rem';
            p.style.color = 'var(--b-muted)';
            box.appendChild(p);

            var h32 = document.createElement('h3');
            h32.textContent = 'Reference-list rules';
            h32.style.margin = '0 0 .4rem';
            h32.style.fontSize = '1rem';
            box.appendChild(h32);
            var ul = document.createElement('ul');
            ul.style.margin = '0 0 1rem';
            ul.style.paddingLeft = '1.2rem';
            ul.style.lineHeight = '1.7';
            (g.reference_rules || []).forEach(function (rule) {
                var li = document.createElement('li');
                li.textContent = rule;
                ul.appendChild(li);
            });
            box.appendChild(ul);

            if (g.notes) {
                var note = document.createElement('p');
                note.style.margin = '0';
                note.style.fontSize = '.9rem';
                note.style.color = 'var(--b-muted)';
                var strong = document.createElement('strong');
                strong.textContent = 'Note: ';
                note.appendChild(strong);
                note.appendChild(document.createTextNode(g.notes));
                box.appendChild(note);
            }
        }).catch(function () {
            box.textContent = 'Style guidance is unavailable right now.';
        });
    }

    /* -- tabs -------------------------------------------------------------- */

    function selectTab(name, btn) {
        Array.prototype.forEach.call(
            document.querySelectorAll('.cite-tab'),
            function (b) {
                var on = b === btn;
                b.classList.toggle('b-btn--primary', on);
                b.classList.toggle('b-btn--ghost', !on);
                b.setAttribute('aria-pressed', on ? 'true' : 'false');
            });
        $('cite-pane-formatted').hidden = name !== 'formatted';
        $('cite-pane-bibtex').hidden = name !== 'bibtex';
        if (name === 'bibtex' && !$('cite-bibtex-out').value) exportBibtex();
    }

    /* -- copy -------------------------------------------------------------- */

    function copyCitation() {
        var text = $('cite-output').textContent;
        if (!text) return;
        function done() {
            var el = $('cite-copied');
            el.style.display = 'inline';
            setTimeout(function () { el.style.display = 'none'; }, 1800);
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(done, function () {
                fallbackCopy(text);
                done();
            });
        } else {
            fallbackCopy(text);
            done();
        }
    }

    function fallbackCopy(text) {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); } catch (e) { /* noop */ }
        ta.remove();
    }

    /* -- init -------------------------------------------------------------- */

    function init() {
        prefillFromQuery();

        Array.prototype.forEach.call(
            document.querySelectorAll('.cite-pill'),
            function (btn) {
                btn.addEventListener('click', function () {
                    selectStyle(btn.getAttribute('data-style'), btn);
                });
            });

        Array.prototype.forEach.call(
            document.querySelectorAll('.cite-tab'),
            function (btn) {
                btn.addEventListener('click', function () {
                    selectTab(btn.getAttribute('data-tab'), btn);
                });
            });

        ['cite-title', 'cite-authors', 'cite-year', 'cite-venue',
         'cite-volume', 'cite-issue', 'cite-pages', 'cite-doi',
         'cite-arxiv', 'cite-url'].forEach(function (id) {
            $(id).addEventListener('input', reformatDebounced);
        });
        $('cite-pubtype').addEventListener('change', reformat);

        $('cite-copy').addEventListener('click', copyCitation);
        $('cite-bibtex-export').addEventListener('click', exportBibtex);
        $('cite-bibtex-download').addEventListener('click', downloadBib);
        $('cite-bibtex-import').addEventListener('click', importBibtex);

        loadGuide();
        reformat();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
