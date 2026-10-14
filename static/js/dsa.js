/* DSA problem list with topic/difficulty filters (Wave 2 #15). XSS-safe. */
(function () {
    "use strict";
    var topicSel = document.getElementById("f-topic");
    var diffSel = document.getElementById("f-diff");
    var list = document.getElementById("dsa-list");
    var count = document.getElementById("dsa-count");
    if (!topicSel || !list) return;

    function el(tag, cls, text) {
        var n = document.createElement(tag);
        if (cls) n.className = cls;
        if (text !== undefined && text !== null) n.textContent = text;
        return n;
    }

    function statusChip(s) {
        if (!s) return null;
        var c = el("span", "dsa-chip st-" + s, s);
        return c;
    }

    function load() {
        var q = "?topic=" + encodeURIComponent(topicSel.value) +
                "&difficulty=" + encodeURIComponent(diffSel.value);
        list.innerHTML = "";
        count.textContent = "Loading…";
        fetch("/api/dsa/problems" + q).then(function (r) { return r.json(); })
        .then(function (d) {
            var problems = d.problems || [];
            count.textContent = problems.length + " problem" +
                (problems.length === 1 ? "" : "s");
            if (!problems.length) {
                list.appendChild(el("p", null,
                    "No problems match these filters. Try widening them."));
                return;
            }
            problems.forEach(function (p) {
                var a = document.createElement("a");
                a.className = "dsa-prob b-card b-card--lite";
                a.href = "/dsa/" + encodeURIComponent(p.id);
                var left = el("div");
                left.appendChild(el("div", "t", p.title));
                left.appendChild(el("div", "tags",
                    (p.topics || []).join(" · ")));
                var right = el("div");
                right.style.display = "flex";
                right.style.gap = "0.4rem";
                right.appendChild(el("span", "dsa-chip diff-" + p.difficulty,
                    p.difficulty));
                var sc = statusChip(p.my_status);
                if (sc) right.appendChild(sc);
                a.appendChild(left);
                a.appendChild(right);
                list.appendChild(a);
            });
        }).catch(function () {
            count.textContent = "Could not load problems. Please reload.";
        });
    }

    topicSel.addEventListener("change", load);
    diffSel.addEventListener("change", load);
    load();
})();
