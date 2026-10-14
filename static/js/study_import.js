/* arXiv / DOI import + citation graph (Worker B, #25). XSS-safe: textContent only. */
(function () {
    'use strict';

    /* Integrator-provided endpoints. PDF_IMPORT_URL is the contract from the brief;
       the others mirror the expected route list. */
    const PDF_IMPORT_URL = "/api/study/import/pdf";
    const IMPORT_ARXIV_URL = "/api/study/import/arxiv";
    const IMPORT_DOI_URL = "/api/study/import/doi";
    const GRAPH_URL_FOR = function (openalexId) {
        return "/api/study/import/" + encodeURIComponent(openalexId) + "/graph";
    };
    const CITE_URL_BASE = "/research/cite";

    var state = { papers: [], graph: null, zoom: 1 };

    function el(tag, cls, text) {
        var node = document.createElement(tag);
        if (cls) node.className = cls;
        if (text !== undefined && text !== null) node.textContent = text;
        return node;
    }

    function csrfHeaders(extra) {
        var headers = extra || {};
        var m = document.querySelector('meta[name="csrf-token"]');
        if (m) headers['X-CSRFToken'] = m.getAttribute('content');
        return headers;
    }

    function showStatus(msg) {
        var box = document.getElementById('si-status');
        box.textContent = msg;
        box.classList.add('show');
    }

    function hideStatus() {
        document.getElementById('si-status').classList.remove('show');
    }

    function setMsg(id, msg, kind) {
        var box = document.getElementById(id);
        box.textContent = msg;
        box.className = 'si-msg ' + (kind || '');
    }

    function clearMsg(id) {
        var box = document.getElementById(id);
        box.textContent = '';
        box.className = 'si-msg';
    }

    function normArxivId(s) {
        s = (s || '').trim()
            .replace(/^https?:\/\/(export\.)?arxiv\.org\/(abs|pdf)\//i, '')
            .replace(/^arxiv:/i, '').replace(/\.pdf$/i, '').replace(/v\d+$/, '');
        return s;
    }

    function normDoi(s) {
        s = (s || '').trim()
            .replace(/^https?:\/\/(dx\.)?doi\.org\//i, '')
            .replace(/^doi:\s*/i, '').replace(/\/$/, '');
        return s;
    }

    var ARXIV_NEW_RE = /^\d{2}(0[1-9]|1[0-2])\.\d{4,5}$/;
    var ARXIV_OLD_RE = /^[a-z\-]+(\.[A-Z]{2})?\/\d{2}(0[1-9]|1[0-2])\d{3}$/;
    var DOI_RE = /^10\.\d{4,9}\/[-._;()/:A-Z0-9]+$/i;

    /* ------------------------------------------------------------ import */
    function importPaper(kind, rawValue, msgId) {
        hideStatus();
        clearMsg(msgId);
        var value = rawValue.trim();
        if (!value) {
            setMsg(msgId, 'Please enter a value first.', 'err');
            return;
        }
        var norm = kind === 'arxiv' ? normArxivId(value) : normDoi(value);
        var valid = kind === 'arxiv'
            ? (ARXIV_NEW_RE.test(norm) || ARXIV_OLD_RE.test(norm))
            : DOI_RE.test(norm);
        if (!valid) {
            setMsg(msgId, kind === 'arxiv'
                ? 'That does not look like a valid arXiv ID (expected YYMM.NNNNN, e.g. 1706.03762).'
                : 'That does not look like a valid DOI (expected 10.xxxx/…, e.g. 10.1038/nature12373).', 'err');
            return;
        }
        var url = kind === 'arxiv' ? IMPORT_ARXIV_URL : IMPORT_DOI_URL;
        var body = kind === 'arxiv' ? { arxiv_id: norm } : { doi: norm };
        setMsg(msgId, 'Fetching…', 'ok');
        fetch(url, {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(body),
        })
            .then(function (resp) { return resp.json().catch(function () { return { error: 'bad response' }; }); })
            .then(function (data) {
                if (data && data.error) {
                    setMsg(msgId, data.error, 'err');
                    return;
                }
                setMsg(msgId, 'Imported: ' + (data.title || 'untitled'), 'ok');
                addPaper(data);
            })
            .catch(function () {
                setMsg(msgId, 'Service unavailable — please try again.', 'err');
                showStatus('Import service unavailable — please try again.');
            });
    }

    function addPaper(paper) {
        state.papers.push(paper);
        renderResults();
    }

    function shortAuthors(paper) {
        var a = paper.authors || [];
        if (!a.length) return 'Unknown authors';
        return a.slice(0, 4).join(', ') + (a.length > 4 ? ' et al.' : '');
    }

    function trunc(s, n) {
        s = s || '';
        return s.length > n ? s.slice(0, n) + '…' : s;
    }

    function renderResults() {
        var wrap = document.getElementById('results');
        wrap.innerHTML = '';
        if (!state.papers.length) {
            var empty = el('div', 'b-card si-empty', 'No papers imported yet — try an arXiv ID or DOI above.');
            wrap.appendChild(empty);
            return;
        }
        state.papers.forEach(function (paper, idx) {
            wrap.appendChild(renderPaperCard(paper, idx));
        });
    }

    function renderPaperCard(paper, idx) {
        var card = el('div', 'b-card b-card--lite si-card');

        card.appendChild(el('h3', null, paper.title || 'Untitled'));
        var metaBits = [];
        if (paper.year) metaBits.push(String(paper.year));
        if (paper.venue) metaBits.push(paper.venue);
        if (paper.source) metaBits.push('via ' + paper.source);
        var meta = el('div', 'si-meta',
            shortAuthors(paper) + (metaBits.length ? ' · ' + metaBits.join(' · ') : ''));
        card.appendChild(meta);
        if (paper.abstract) card.appendChild(el('p', 'si-abs', trunc(paper.abstract, 320)));

        var actions = el('div', 'si-actions');

        var graphBtn = el('button', 'si-btn', 'View graph');
        graphBtn.type = 'button';
        if (!paper.openalex_id) {
            graphBtn.disabled = true;
            graphBtn.title = 'No OpenAlex record — graph unavailable';
        } else {
            graphBtn.addEventListener('click', function () { loadGraph(paper.openalex_id); });
        }
        actions.appendChild(graphBtn);

        var pdfBtn = el('button', 'si-btn primary', 'Import PDF to library');
        pdfBtn.type = 'button';
        pdfBtn.addEventListener('click', function () { importPdf(paper, pdfBtn); });
        actions.appendChild(pdfBtn);

        var cite = el('a', 'si-btn', 'Cite this');
        cite.href = CITE_URL_BASE + '?title=' + encodeURIComponent(paper.title || '') +
            '&authors=' + encodeURIComponent((paper.authors || []).join(', ')) +
            (paper.year ? '&year=' + encodeURIComponent(paper.year) : '') +
            (paper.doi ? '&doi=' + encodeURIComponent(paper.doi) : '');
        actions.appendChild(cite);

        card.appendChild(actions);
        var note = el('div', 'si-msg');
        note.id = 'paper-note-' + idx;
        card.appendChild(note);
        return card;
    }

    function importPdf(paper, btn) {
        hideStatus();
        btn.disabled = true;
        fetch(PDF_IMPORT_URL, {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({
                pdf_url: paper.pdf_url,
                title: paper.title,
                authors: paper.authors,
                year: paper.year,
                doi: paper.doi,
                arxiv_id: paper.arxiv_id,
                openalex_id: paper.openalex_id,
            }),
        })
            .then(function (resp) { return resp.json().catch(function () { return { error: 'bad response' }; }); })
            .then(function (data) {
                btn.disabled = false;
                if (data && data.error) {
                    showStatus('PDF import failed: ' + data.error);
                } else {
                    hideStatus();
                    btn.textContent = 'Added to library ✓';
                }
            })
            .catch(function () {
                btn.disabled = false;
                showStatus('Import service unavailable — please try again.');
            });
    }

    /* ------------------------------------------------------------ graph */
    function loadGraph(openalexId) {
        hideStatus();
        var svg = document.getElementById('graph-svg');
        svg.innerHTML = '';
        var loading = el('div', 'si-empty', 'Loading citation graph…');
        document.getElementById('graph-details').innerHTML = '';
        document.getElementById('graph-details').appendChild(loading);

        fetch(GRAPH_URL_FOR(openalexId), { headers: csrfHeaders() })
            .then(function (resp) { return resp.json().catch(function () { return { error: 'bad response' }; }); })
            .then(function (data) {
                document.getElementById('graph-details').innerHTML = '';
                if (data && data.error) {
                    showStatus('Graph unavailable: ' + data.error + ' — please try again.');
                    renderGraphEmpty(svg, data.error);
                    return;
                }
                state.graph = data;
                state.zoom = 1;
                renderGraph(svg, data);
            })
            .catch(function () {
                document.getElementById('graph-details').innerHTML = '';
                showStatus('Citation graph service unavailable — please try again.');
                renderGraphEmpty(svg, 'Service unavailable — please try again.');
            });
    }

    function renderGraphEmpty(svg, msg) {
        svg.innerHTML = '';
        var t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        t.setAttribute('x', '50%');
        t.setAttribute('y', '50%');
        t.setAttribute('text-anchor', 'middle');
        t.setAttribute('fill', '#94a3b8');
        t.textContent = msg;
        svg.appendChild(t);
    }

    function nodeRadius(n) {
        if (n.is_center) return 24;
        var r = 10 + Math.min(10, Math.sqrt(n.cited_by_count || 0));
        return Math.round(r);
    }

    function renderGraph(svg, data) {
        svg.innerHTML = '';
        var W = svg.clientWidth || 900, H = 460;
        var cx = W / 2, cy = H / 2;
        var R = Math.min(W, H) / 2 - 70;

        var g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('id', 'graph-g');
        svg.appendChild(g);

        var nodes = data.nodes || [];
        var center = nodes.filter(function (n) { return n.is_center; })[0] || nodes[0];
        var others = nodes.filter(function (n) { return n !== center; });

        var pos = {};
        if (center) pos[center.id] = { x: cx, y: cy };
        others.forEach(function (n, i) {
            var ang = (2 * Math.PI * i) / Math.max(others.length, 1) - Math.PI / 2;
            pos[n.id] = { x: cx + R * Math.cos(ang), y: cy + R * Math.sin(ang) };
        });

        (data.edges || []).forEach(function (e) {
            if (!pos[e.from] || !pos[e.to]) return;
            var line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', pos[e.from].x); line.setAttribute('y1', pos[e.from].y);
            line.setAttribute('x2', pos[e.to].x); line.setAttribute('y2', pos[e.to].y);
            line.setAttribute('class', 'si-edge');
            g.appendChild(line);
        });

        nodes.forEach(function (n) {
            if (!pos[n.id]) return;
            var grp = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            grp.setAttribute('class', 'si-node' + (n.is_center ? ' center' : ''));
            var c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            c.setAttribute('cx', pos[n.id].x); c.setAttribute('cy', pos[n.id].y);
            c.setAttribute('r', nodeRadius(n));
            c.setAttribute('fill', n.is_center ? 'rgba(34,211,238,.25)' : 'rgba(99,102,241,.25)');
            grp.appendChild(c);
            var label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            label.setAttribute('x', pos[n.id].x);
            label.setAttribute('y', pos[n.id].y + nodeRadius(n) + 14);
            label.setAttribute('text-anchor', 'middle');
            var words = (n.title || 'Untitled').split(' ').slice(0, 4).join(' ');
            label.textContent = words.length > 34 ? words.slice(0, 34) + '…' : words;
            grp.appendChild(label);
            var titleEl = document.createElementNS('http://www.w3.org/2000/svg', 'title');
            titleEl.textContent = n.title || 'Untitled';
            grp.appendChild(titleEl);
            grp.addEventListener('click', function () { showNodeDetails(n, data); });
            g.appendChild(grp);
        });

        applyZoom();
        var hint = document.getElementById('graph-hint');
        if (hint) hint.textContent = nodes.length + ' nodes — click any node to inspect it.';
    }

    function applyZoom() {
        var svg = document.getElementById('graph-svg');
        var g = document.getElementById('graph-g');
        if (!g) return;
        var W = svg.clientWidth || 900, H = 460;
        g.setAttribute('transform',
            'translate(' + W / 2 + ',' + H / 2 + ') scale(' + state.zoom + ')' +
            ' translate(' + (-W / 2) + ',' + (-H / 2) + ')');
    }

    function showNodeDetails(n, data) {
        var box = document.getElementById('graph-details');
        box.innerHTML = '';
        var card = el('div', 'b-card b-card--lite');
        card.appendChild(el('h3', null, n.title || 'Untitled'));
        var bits = [];
        if (n.year) bits.push(String(n.year));
        bits.push((n.cited_by_count || 0) + ' citations');
        card.appendChild(el('div', 'si-meta',
            (n.authors || []).slice(0, 5).join(', ') + (bits.length ? ' · ' + bits.join(' · ') : '')));
        if (n.is_center) {
            card.appendChild(el('p', 'si-abs', 'Center paper — the one you imported.'));
        } else if (data) {
            var center = (data.nodes || []).filter(function (x) { return x.is_center; })[0];
            var citesCenter = (data.edges || []).some(function (e) {
                return e.from === n.id && center && e.to === center.id;
            });
            card.appendChild(el('p', 'si-abs',
                citesCenter ? 'This paper cites the center paper.' : 'The center paper cites this work.'));
        }
        if (n.doi) {
            var imp = el('button', 'si-btn primary', 'Import this paper');
            imp.type = 'button';
            imp.addEventListener('click', function () {
                document.getElementById('doi-input').value = n.doi;
                importPaper('doi', n.doi, 'doi-msg');
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });
            var row = el('div', 'si-actions');
            row.appendChild(imp);
            card.appendChild(row);
        }
        box.appendChild(card);
    }

    /* ------------------------------------------------------------ wiring */
    function wire() {
        var arxivBtn = document.getElementById('arxiv-btn');
        var doiBtn = document.getElementById('doi-btn');
        var arxivInput = document.getElementById('arxiv-input');
        var doiInput = document.getElementById('doi-input');

        arxivBtn.addEventListener('click', function () { importPaper('arxiv', arxivInput.value, 'arxiv-msg'); });
        doiBtn.addEventListener('click', function () { importPaper('doi', doiInput.value, 'doi-msg'); });
        arxivInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') importPaper('arxiv', arxivInput.value, 'arxiv-msg');
        });
        doiInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') importPaper('doi', doiInput.value, 'doi-msg');
        });

        document.getElementById('zoom-in').addEventListener('click', function () {
            state.zoom = Math.min(3, state.zoom + 0.25); applyZoom();
        });
        document.getElementById('zoom-out').addEventListener('click', function () {
            state.zoom = Math.max(0.4, state.zoom - 0.25); applyZoom();
        });
        document.getElementById('zoom-reset').addEventListener('click', function () {
            state.zoom = 1; applyZoom();
        });

        renderResults();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', wire);
    } else {
        wire();
    }
})();
