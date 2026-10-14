/* Communication coach client (Wave 2 #14). XSS-safe: textContent only. */
(function () {
    "use strict";

    var textarea = document.getElementById("coach-text");
    var btn = document.getElementById("analyze-btn");
    var errBox = document.getElementById("coach-error");
    var results = document.getElementById("results");
    var charCount = document.getElementById("char-count");
    if (!textarea || !btn) return;

    var CSRF = (document.querySelector('meta[name="csrf-token"]') || {})
        .content || "";

    textarea.addEventListener("input", function () {
        if (charCount) charCount.textContent = String(textarea.value.length);
    });

    function el(tag, cls, text) {
        var n = document.createElement(tag);
        if (cls) n.className = cls;
        if (text !== undefined && text !== null) n.textContent = text;
        return n;
    }

    function scoreColor(s) {
        return s >= 75 ? "#10b981" : s >= 50 ? "#f59e0b" : "#ef4444";
    }

    function buildHighlighted(text, report) {
        // Collect highlight spans: filler hits + passive hits.
        var spans = [];
        (report.filler_hits || []).forEach(function (h) {
            (h.positions || []).forEach(function (pos) {
                spans.push({ start: pos, end: pos + h.word.length,
                             cls: "sev-" + h.severity,
                             title: h.word + " (" + h.category + ", severity " +
                                    h.severity + "/3)" +
                                    (h.alternatives && h.alternatives[0]
                                        ? " — try: " + h.alternatives[0] : "") });
            });
        });
        (report.passive_hits || []).forEach(function (p) {
            spans.push({ start: p.position,
                         end: p.position + (p.match || "").length,
                         cls: "passive", title: "Passive construction — prefer active voice" });
        });
        // drop overlaps, keep earlier start
        spans.sort(function (a, b) { return a.start - b.start; });
        var clean = [], lastEnd = -1;
        spans.forEach(function (sp) {
            if (sp.start >= lastEnd) { clean.push(sp); lastEnd = sp.end; }
        });
        var p = el("p", "ch-hl");
        var idx = 0;
        clean.forEach(function (sp) {
            if (sp.start > idx) p.appendChild(document.createTextNode(text.slice(idx, sp.start)));
            var m = document.createElement("mark");
            m.className = sp.cls;
            m.title = sp.title;
            m.textContent = text.slice(sp.start, sp.end);
            p.appendChild(m);
            idx = sp.end;
        });
        if (idx < text.length) p.appendChild(document.createTextNode(text.slice(idx)));
        return p;
    }

    function renderReport(text, report) {
        results.innerHTML = "";
        var card = el("div", "ch-card");

        var score = report.clarity_score || 0;
        var ring = el("div", "ch-score-ring");
        ring.style.border = "6px solid " + scoreColor(score);
        ring.textContent = Math.round(score);
        card.appendChild(ring);
        var sub = el("p", null, "Clarity score / 100" +
                     (report.ai_powered ? " · AI-polished rewrite" : ""));
        sub.style.textAlign = "center";
        sub.style.color = "var(--text-muted,#94a3b8)";
        sub.style.fontSize = "0.9rem";
        card.appendChild(sub);

        var h = el("h3", "ch-h3", "Score breakdown");
        card.appendChild(h);
        var bd = report.breakdown || {};
        [["Filler load", "filler_load", 40], ["Pacing", "pacing", 25],
         ["Voice & hedges", "voice_and_hedges", 20],
         ["Structure", "structure", 15]].forEach(function (row) {
            var v = bd[row[1]] || 0;
            var r = el("div", "ch-bar-row");
            r.appendChild(el("span", null, row[0]));
            var bar = el("div", "ch-bar");
            var fill = el("div");
            fill.style.width = (v / row[2] * 100).toFixed(1) + "%";
            bar.appendChild(fill);
            r.appendChild(bar);
            r.appendChild(el("span", null, v.toFixed(1) + "/" + row[2]));
            card.appendChild(r);
        });

        var m = report.metrics || {};
        card.appendChild(el("h3", "ch-h3", "Metrics"));
        var grid = el("div", "ch-metrics");
        [["Words", m.word_count], ["Sentences", m.sentence_count],
         ["Avg words/sentence", m.avg_words_per_sentence],
         ["Filler events", m.filler_events],
         ["Passive voice", m.passive_constructions],
         ["Hedges", m.hedge_events]].forEach(function (kv) {
            var box = el("div", "ch-metric");
            box.appendChild(el("div", "v", String(kv[1] === undefined ? "—" : kv[1])));
            box.appendChild(el("div", "l", kv[0]));
            grid.appendChild(box);
        });
        card.appendChild(grid);
        results.appendChild(card);

        var card2 = el("div", "ch-card");
        card2.appendChild(el("h3", "ch-h3", "Your answer — problem spots"));
        card2.appendChild(buildHighlighted(text, report));
        var legend = el("div", "ch-legend");
        legend.innerHTML = "";
        [["#ef4444", "Severe filler"], ["#f59e0b", "Moderate filler"],
         ["#3b82f6", "Mild filler"], ["#a855f7", "Passive voice"]].forEach(function (kv) {
            var s = el("span");
            var dot = el("span", "dot");
            dot.style.background = kv[0];
            s.appendChild(dot);
            s.appendChild(document.createTextNode(kv[1]));
            legend.appendChild(s);
        });
        card2.appendChild(legend);
        results.appendChild(card2);

        var sugg = report.suggestions || [];
        if (sugg.length) {
            var card3 = el("div", "ch-card");
            card3.appendChild(el("h3", "ch-h3 fix", "What to improve"));
            var ul = el("ul", "ch-sugg");
            sugg.forEach(function (s) {
                ul.appendChild(el("li", null, s));
            });
            card3.appendChild(ul);
            results.appendChild(card3);
        }

        if (report.cleaned_version) {
            var card4 = el("div", "ch-card");
            card4.appendChild(el("h3", "ch-h3", "Cleaned version"));
            var clean = el("div", "ch-clean", report.cleaned_version);
            card4.appendChild(clean);
            results.appendChild(card4);
        }

        var drills = report.drills || [];
        if (drills.length) {
            var card5 = el("div", "ch-card");
            card5.appendChild(el("h3", "ch-h3", "Practice drills"));
            card5.appendChild(el("p", null, "Rewrite each sentence without the flagged issue."));
            drills.forEach(function (d) {
                var box = el("div", "ch-drill");
                box.appendChild(el("div", "before", "\u201C" + d.sentence + "\u201D"));
                box.appendChild(el("div", "issues",
                    "Issues: " + (d.issues || []).join(", ")));
                card5.appendChild(box);
            });
            results.appendChild(card5);
        }

        var link = el("a", null, "View saved report");
        link.href = report.report_url || "#";
        link.style.color = "var(--accent-primary)";
        link.style.fontWeight = "700";
        results.appendChild(link);

        var reduced = window.matchMedia &&
            window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (!reduced && results.scrollIntoView) {
            results.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }

    btn.addEventListener("click", function () {
        errBox.textContent = "";
        var text = textarea.value.trim();
        if (text.length < 50) {
            errBox.textContent = "Please paste at least 50 characters of your answer.";
            return;
        }
        btn.disabled = true;
        btn.textContent = "Analyzing…";
        fetch("/coach/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json",
                       "X-CSRFToken": CSRF },
            body: JSON.stringify({ text: text })
        }).then(function (r) {
            return r.json().then(function (d) {
                return { status: r.status, body: d };
            });
        }).then(function (res) {
            btn.disabled = false;
            btn.textContent = "Analyze My Answer";
            if (res.status !== 200 || !res.body.success) {
                errBox.textContent = (res.body && res.body.error) ||
                    "Analysis failed. Please try again.";
                return;
            }
            res.body.report.report_url = res.body.report_url;
            renderReport(text, res.body.report);
        }).catch(function () {
            btn.disabled = false;
            btn.textContent = "Analyze My Answer";
            errBox.textContent = "Network error. Please try again.";
        });
    });
})();
