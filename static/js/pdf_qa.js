/* Source-grounded PDF Q&A — study library frontend (feature #21).
 * XSS-safe: textContent / createTextNode only, never innerHTML.
 * Routes are wired by the integrator; this module talks to:
 *   POST   /study/api/upload            (FormData: file)
 *   POST   /study/api/ask               (JSON: {doc_id, question})
 *   GET    /study/api/documents/<id>/history
 *   DELETE /study/api/documents/<id>
 */
(function () {
    'use strict';

    var API = {
        upload: '/study/api/upload',
        ask: '/study/api/ask',
        history: function (id) { return '/study/api/documents/' + encodeURIComponent(id) + '/history'; },
        remove: function (id) { return '/study/api/documents/' + encodeURIComponent(id); },
    };

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

    function showError(id, msg) {
        var box = document.getElementById(id);
        box.textContent = msg;
        box.style.display = 'block';
    }

    function hideError(id) {
        document.getElementById(id).style.display = 'none';
    }

    function setStatus(id, text) {
        var pill = document.getElementById(id);
        if (!text) {
            pill.style.display = 'none';
            return;
        }
        pill.textContent = text;
        pill.style.display = '';
    }

    var state = { docId: null, docTitle: '' };

    /* ---------- document selection ---------- */

    function openDoc(id, title) {
        state.docId = id;
        state.docTitle = title;
        document.getElementById('qa-doc-title').textContent = title;
        var view = document.getElementById('qa-doc-view');
        view.hidden = false;
        document.getElementById('qa-answer-wrap').style.display = 'none';
        document.getElementById('qa-question').value = '';
        hideError('qa-ask-error');
        loadHistory();
        view.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function loadHistory() {
        var list = document.getElementById('qa-history');
        list.textContent = '';
        fetch(API.history(state.docId), { headers: csrfHeaders() })
            .then(function (res) { return res.ok ? res.json() : { history: [] }; })
            .then(function (data) {
                var items = (data && data.history) || [];
                if (!items.length) {
                    var row = el('div', 'b-kv-row');
                    var label = el('span', 'b-kv-label', 'No questions asked about this document yet.');
                    label.style.color = 'var(--b-muted)';
                    row.appendChild(label);
                    list.appendChild(row);
                    return;
                }
                items.forEach(function (h) {
                    var row = el('div', 'b-kv-row');
                    row.appendChild(el('span', 'b-kv-label', h.question));
                    row.appendChild(el('span', 'b-kv-val', h.created || ''));
                    row.title = h.answer || '';
                    list.appendChild(row);
                });
            })
            .catch(function () { /* history is best-effort; the Q&A still works */ });
    }

    /* ---------- asking ---------- */

    // Render answer text, turning [doc, p.X] markers into citation chips.
    function renderAnswer(text, citations) {
        var wrap = document.getElementById('qa-answer');
        wrap.textContent = '';
        var parts = String(text).split(/(\[doc, p\.\d+\])/g);
        parts.forEach(function (part) {
            var m = /^\[doc, p\.(\d+)\]$/.exec(part);
            if (m) {
                wrap.appendChild(el('span', 'b-pill', 'p.' + m[1] + ' cited'));
            } else {
                wrap.appendChild(document.createTextNode(part));
            }
        });

        var chips = document.getElementById('qa-citations');
        chips.textContent = '';
        (citations || []).forEach(function (c) {
            chips.appendChild(el('span', 'b-pill', c.doc + ' · p.' + c.page));
        });

        var plist = document.getElementById('qa-passages-list');
        plist.textContent = '';
        var passages = citations || [];
        document.getElementById('qa-passages').style.display = passages.length ? '' : 'none';
        passages.forEach(function (c, i) {
            var card = el('div', 'b-card b-card--lite');
            card.appendChild(el('span', 'b-tag', 'Passage ' + (i + 1) + ' · page ' + c.page));
            card.appendChild(el('p', null, c.excerpt));
            plist.appendChild(card);
        });

        document.getElementById('qa-answer-wrap').style.display = '';
    }

    function ask() {
        if (!state.docId) return;
        var q = document.getElementById('qa-question').value.trim();
        hideError('qa-ask-error');
        if (!q) {
            showError('qa-ask-error', 'Type a question first.');
            return;
        }
        var btn = document.getElementById('qa-ask-btn');
        btn.disabled = true;
        setStatus('qa-ask-status', 'Searching the document…');
        fetch(API.ask, {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ doc_id: state.docId, question: q }),
        })
            .then(function (res) {
                return res.json().then(function (data) {
                    return { ok: res.ok, data: data };
                });
            })
            .then(function (result) {
                btn.disabled = false;
                setStatus('qa-ask-status', null);
                if (!result.ok) {
                    showError('qa-ask-error',
                        (result.data && result.data.error) || 'Could not answer that question.');
                    return;
                }
                renderAnswer(result.data.answer, result.data.citations);
                loadHistory();
            })
            .catch(function () {
                btn.disabled = false;
                setStatus('qa-ask-status', null);
                showError('qa-ask-error', 'Network error — please try again.');
            });
    }

    /* ---------- upload ---------- */

    function upload(file) {
        hideError('qa-upload-error');
        if (!file) {
            showError('qa-upload-error', 'Choose a PDF file first.');
            return;
        }
        if (file.size > 25 * 1024 * 1024) {
            showError('qa-upload-error', 'File exceeds the 25 MB limit.');
            return;
        }
        var btn = document.getElementById('qa-upload-btn');
        btn.disabled = true;
        setStatus('qa-upload-status', 'Uploading & indexing…');
        var form = new FormData();
        form.append('file', file, file.name);
        fetch(API.upload, {
            method: 'POST',
            headers: csrfHeaders(),
            body: form,
        })
            .then(function (res) {
                return res.json().then(function (data) {
                    return { ok: res.ok, data: data };
                });
            })
            .then(function (result) {
                btn.disabled = false;
                setStatus('qa-upload-status', null);
                if (!result.ok) {
                    showError('qa-upload-error',
                        (result.data && result.data.error) || 'Upload failed.');
                    return;
                }
                // Server re-renders the library grid; reload to show the new doc.
                window.location.reload();
            })
            .catch(function () {
                btn.disabled = false;
                setStatus('qa-upload-status', null);
                showError('qa-upload-error', 'Network error — please try again.');
            });
    }

    /* ---------- delete ---------- */

    function removeDoc(id, title) {
        if (!window.confirm('Delete "' + title + '" and all its questions? This cannot be undone.')) {
            return;
        }
        fetch(API.remove(id), {
            method: 'DELETE',
            headers: csrfHeaders(),
        })
            .then(function (res) { return res.ok; })
            .then(function (ok) {
                if (!ok) {
                    window.alert('Could not delete the document. Please try again.');
                    return;
                }
                var card = document.querySelector('[data-doc-id="' + id + '"]');
                if (card) card.remove();
                if (state.docId === id) {
                    state.docId = null;
                    document.getElementById('qa-doc-view').hidden = true;
                }
                var remaining = document.querySelectorAll('#qa-library [data-doc-id]').length;
                document.getElementById('qa-lib-count').textContent =
                    remaining + ' document' + (remaining === 1 ? '' : 's');
                if (!remaining) window.location.reload();
            })
            .catch(function () {
                window.alert('Network error — please try again.');
            });
    }

    /* ---------- wiring ---------- */

    function init() {
        var dropzone = document.getElementById('qa-dropzone');
        var fileInput = document.getElementById('qa-file');
        if (!dropzone || !fileInput) return;

        dropzone.addEventListener('click', function () { fileInput.click(); });
        dropzone.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                fileInput.click();
            }
        });
        ['dragenter', 'dragover'].forEach(function (evt) {
            dropzone.addEventListener(evt, function (e) {
                e.preventDefault();
                dropzone.style.borderColor = 'var(--b-accent, #22d3ee)';
            });
        });
        ['dragleave', 'drop'].forEach(function (evt) {
            dropzone.addEventListener(evt, function (e) {
                e.preventDefault();
                dropzone.style.borderColor = '';
            });
        });
        dropzone.addEventListener('drop', function (e) {
            var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
            if (f) upload(f);
        });
        fileInput.addEventListener('change', function () {
            if (fileInput.files[0]) {
                document.getElementById('qa-upload-hint').style.display = 'none';
            }
        });
        document.getElementById('qa-upload-btn').addEventListener('click', function () {
            upload(fileInput.files[0]);
        });
        document.getElementById('qa-ask-btn').addEventListener('click', ask);
        document.getElementById('qa-question').addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) ask();
        });

        document.getElementById('qa-library').addEventListener('click', function (e) {
            var openBtn = e.target.closest('.qa-open-doc');
            if (openBtn) {
                openDoc(openBtn.getAttribute('data-doc-id'),
                    openBtn.getAttribute('data-doc-title'));
                return;
            }
            var delBtn = e.target.closest('.qa-delete-doc');
            if (delBtn) {
                removeDoc(delBtn.getAttribute('data-doc-id'),
                    delBtn.getAttribute('data-doc-title'));
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
