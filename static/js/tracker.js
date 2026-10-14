/**
 * Application Tracker Kanban (Wave 1, feature #6) - Frontend
 * Drag-and-drop between stages (HTML5) with a move-dropdown fallback for
 * touch devices. All mutations go through CSRF-protected JSON endpoints.
 * All user content is HTML-escaped before insertion.
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

    function csrfHeaders() {
        var headers = { 'Content-Type': 'application/json' };
        var tokenMeta = document.querySelector('meta[name="csrf-token"]');
        if (tokenMeta) headers['X-CSRFToken'] = tokenMeta.getAttribute('content');
        return headers;
    }

    function setError(msg) {
        var box = document.getElementById('tkError');
        if (!box) return;
        box.textContent = msg || '';
        box.hidden = !msg;
    }

    function api(path, payload) {
        return fetch(path, {
            method: 'POST',
            headers: csrfHeaders(),
            body: JSON.stringify(payload || {})
        }).then(function (resp) {
            return resp.json().then(function (data) {
                return { status: resp.status, data: data };
            });
        });
    }

    function stageLabel(stage) {
        var sel = document.querySelector('.tk-move option[value="' + stage + '"]');
        return sel ? sel.textContent : stage;
    }

    function cardHtml(a) {
        var html = '<div class="tk-card b-kcard" draggable="true" data-id="' + a.id + '" data-stage="' + esc(a.stage) + '">';
        html += '<h4>' + esc(a.company) + '</h4>';
        html += '<div class="tk-role">' + esc(a.role) + '</div>';
        if (a.applied_date) html += '<div class="tk-meta">Applied ' + esc(a.applied_date) + '</div>';
        if (a.notes) html += '<div class="tk-notes">' + esc(a.notes) + '</div>';
        html += '<div class="tk-actions">';
        if (a.jd_url) html += '<a class="tk-mini" href="' + esc(a.jd_url) + '" target="_blank" rel="noopener" style="text-decoration:none;">JD link</a>';
        html += '<select class="tk-move" aria-label="Move to stage">' + moveOptions(a.stage) + '</select>';
        html += '<button class="tk-mini tk-edit" type="button">Edit</button>';
        html += '<button class="tk-mini danger tk-del" type="button">Delete</button>';
        html += '</div></div>';
        return html;
    }

    function moveOptions(current) {
        var stages = [];
        document.querySelectorAll('.tk-col').forEach(function (col) {
            stages.push({ id: col.getAttribute('data-stage'), label: col.querySelector('h3').textContent });
        });
        return stages.map(function (s) {
            return '<option value="' + esc(s.id) + '"' + (s.id === current ? ' selected' : '') + '>' + esc(s.label) + '</option>';
        }).join('');
    }

    function refreshColumnCounts() {
        document.querySelectorAll('.tk-col').forEach(function (col) {
            var n = col.querySelectorAll('.tk-card').length;
            var badge = col.querySelector('.tk-count');
            if (badge) badge.textContent = n;
        });
    }

    function moveCardInDom(card, newStage) {
        var target = document.querySelector('.tk-col[data-stage="' + newStage + '"] .tk-col-body');
        if (!target) return;
        card.setAttribute('data-stage', newStage);
        var sel = card.querySelector('.tk-move');
        if (sel) sel.value = newStage;
        target.appendChild(card);
        refreshColumnCounts();
        refreshStats();
    }

    function refreshStats() {
        fetch('/tracker/stats').then(function (r) { return r.json(); }).then(function (data) {
            var stats = (data && data.stats) || {};
            var counts = stats.counts || {};
            var box = document.getElementById('tkStats');
            if (!box) return;
            var html = '<div class="tk-stat"><strong>' + esc(stats.total || 0) + '</strong><span>Total tracked</span></div>';
            html += '<div class="tk-stat"><strong>' + esc(stats.response_rate || 0) + '%</strong><span>Response rate</span></div>';
            document.querySelectorAll('.tk-col').forEach(function (col) {
                var sid = col.getAttribute('data-stage');
                var label = col.querySelector('h3').textContent;
                html += '<div class="tk-stat"><strong>' + esc(counts[sid] || 0) + '</strong><span>' + esc(label) + '</span></div>';
            });
            box.innerHTML = html;
        }).catch(function () { /* stats are best-effort */ });
    }

    function bindCard(card) {
        card.addEventListener('dragstart', function (e) {
            e.dataTransfer.setData('text/plain', card.getAttribute('data-id'));
            e.dataTransfer.effectAllowed = 'move';
            card.classList.add('tk-dragging');
        });
        card.addEventListener('dragend', function () {
            card.classList.remove('tk-dragging');
            document.querySelectorAll('.tk-col').forEach(function (c) { c.classList.remove('tk-drop'); });
        });

        var moveSel = card.querySelector('.tk-move');
        if (moveSel) {
            moveSel.addEventListener('change', function () {
                doMove(card.getAttribute('data-id'), moveSel.value, card);
            });
        }
        var editBtn = card.querySelector('.tk-edit');
        if (editBtn) editBtn.addEventListener('click', function () { openModal(card); });
        var delBtn = card.querySelector('.tk-del');
        if (delBtn) {
            delBtn.addEventListener('click', function () {
                if (!window.confirm('Delete this application?')) return;
                var id = card.getAttribute('data-id');
                api('/tracker/' + id + '/delete').then(function (out) {
                    if (!out.data || !out.data.success) {
                        setError((out.data && out.data.error) || 'Delete failed.');
                        return;
                    }
                    card.remove();
                    refreshColumnCounts();
                    refreshStats();
                }).catch(function () { setError('Delete failed. Check your connection.'); });
            });
        }
    }

    function doMove(id, newStage, card) {
        setError('');
        api('/tracker/' + id + '/move', { stage: newStage }).then(function (out) {
            if (!out.data || !out.data.success) {
                setError((out.data && out.data.error) || 'Move failed.');
                return;
            }
            if (card) moveCardInDom(card, newStage);
        }).catch(function () { setError('Move failed. Check your connection.'); });
    }

    /* ---------- modal ---------- */

    function openModal(card) {
        var back = document.getElementById('tkModalBack');
        var title = document.getElementById('tkModalTitle');
        document.getElementById('tkFormError').hidden = true;
        if (card) {
            title.textContent = 'Edit application';
            document.getElementById('tkId').value = card.getAttribute('data-id');
            document.getElementById('tkCompany').value = card.querySelector('h4').textContent;
            document.getElementById('tkRole').value = card.querySelector('.tk-role').textContent;
            document.getElementById('tkStage').value = card.getAttribute('data-stage');
        } else {
            title.textContent = 'Add application';
            document.getElementById('tkForm').reset();
            document.getElementById('tkId').value = '';
        }
        back.hidden = false;
        document.getElementById('tkCompany').focus();
    }

    function closeModal() {
        document.getElementById('tkModalBack').hidden = true;
    }

    function initModal() {
        var back = document.getElementById('tkModalBack');
        if (!back) return;
        document.getElementById('tkAddBtn').addEventListener('click', function () { openModal(null); });
        document.getElementById('tkCancel').addEventListener('click', closeModal);
        back.addEventListener('click', function (e) { if (e.target === back) closeModal(); });
        document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeModal(); });

        document.getElementById('tkForm').addEventListener('submit', function (e) {
            e.preventDefault();
            var errBox = document.getElementById('tkFormError');
            errBox.hidden = true;
            var id = document.getElementById('tkId').value;
            var payload = {
                company: document.getElementById('tkCompany').value.trim(),
                role: document.getElementById('tkRole').value.trim(),
                stage: document.getElementById('tkStage').value,
                applied_date: document.getElementById('tkDate').value,
                jd_url: document.getElementById('tkUrl').value.trim(),
                notes: document.getElementById('tkNotes').value.trim()
            };
            if (!payload.company || !payload.role) {
                errBox.textContent = 'Company and role are required.';
                errBox.hidden = false;
                return;
            }
            var path = id ? '/tracker/' + encodeURIComponent(id) + '/edit' : '/tracker/add';
            api(path, payload).then(function (out) {
                if (out.status === 429) {
                    errBox.textContent = 'Too many requests. Please wait a moment and retry.';
                    errBox.hidden = false;
                    return;
                }
                if (!out.data || !out.data.success) {
                    errBox.textContent = (out.data && out.data.error) || 'Save failed.';
                    errBox.hidden = false;
                    return;
                }
                // Simplest correct refresh: reload the board.
                window.location.reload();
            }).catch(function () {
                errBox.textContent = 'Save failed. Check your connection.';
                errBox.hidden = false;
            });
        });
    }

    /* ---------- drag & drop ---------- */

    function initDnD() {
        document.querySelectorAll('.tk-col').forEach(function (col) {
            col.addEventListener('dragover', function (e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                col.classList.add('tk-drop');
            });
            col.addEventListener('dragleave', function () { col.classList.remove('tk-drop'); });
            col.addEventListener('drop', function (e) {
                e.preventDefault();
                col.classList.remove('tk-drop');
                var id = e.dataTransfer.getData('text/plain');
                var card = document.querySelector('.tk-card[data-id="' + id + '"]');
                var newStage = col.getAttribute('data-stage');
                if (!card || card.getAttribute('data-stage') === newStage) return;
                doMove(id, newStage, card);
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.tk-card').forEach(bindCard);
        initDnD();
        initModal();
    });

    window.tkCardHtml = cardHtml;
})();
