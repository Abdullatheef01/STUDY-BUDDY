/* DSA problem workspace: progressive hints, approach, status (Wave 2 #15). XSS-safe. */
(function () {
    "use strict";
    var CSRF = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";

    function el(tag, cls, text) {
        var n = document.createElement(tag);
        if (cls) n.className = cls;
        if (text !== undefined && text !== null) n.textContent = text;
        return n;
    }
    function post(url, body) {
        return fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": CSRF },
            body: JSON.stringify(body || {})
        }).then(function (r) {
            return r.json().then(function (d) { return { status: r.status, body: d }; });
        });
    }

    var hintBtn = document.getElementById("hint-btn");
    if (hintBtn) {
        hintBtn.addEventListener("click", function () {
            var pid = hintBtn.getAttribute("data-pid");
            hintBtn.disabled = true;
            post("/dsa/" + encodeURIComponent(pid) + "/hint").then(function (res) {
                hintBtn.disabled = false;
                if (res.status !== 200 || !res.body.success) return;
                if (res.body.hint) {
                    var box = el("div", "dp-hint");
                    box.appendChild(el("span", "n", "Hint " + res.body.hints_used));
                    box.appendChild(document.createTextNode(res.body.hint));
                    document.getElementById("hint-list").appendChild(box);
                }
                if (res.body.exhausted) {
                    hintBtn.disabled = true;
                    hintBtn.textContent = "All hints revealed";
                }
            }).catch(function () { hintBtn.disabled = false; });
        });
    }

    var approachBtn = document.getElementById("approach-btn");
    if (approachBtn) {
        approachBtn.addEventListener("click", function () {
            var pid = approachBtn.getAttribute("data-pid");
            approachBtn.disabled = true;
            approachBtn.textContent = "Loading…";
            post("/dsa/" + encodeURIComponent(pid) + "/approach").then(function (res) {
                if (res.status === 200 && res.body.success) {
                    var box = document.getElementById("approach-box");
                    box.innerHTML = "";
                    var h = el("h4", null, "Approach outline");
                    h.style.cssText = "color:var(--accent-primary);margin:1rem 0 0.5rem;font-size:0.95rem;";
                    box.appendChild(h);
                    box.appendChild(el("div", "dp-approach", res.body.approach));
                    approachBtn.style.display = "none";
                } else {
                    approachBtn.disabled = false;
                    approachBtn.textContent = "Show approach outline";
                }
            }).catch(function () {
                approachBtn.disabled = false;
                approachBtn.textContent = "Show approach outline";
            });
        });
    }

    var msg = document.getElementById("dsa-msg");
    function setMsg(text, ok) {
        if (!msg) return;
        msg.textContent = text;
        msg.className = "dp-msg " + (ok ? "ok" : "err");
    }
    function saveStatus(pid, status) {
        var code = document.getElementById("dsa-code");
        post("/dsa/" + encodeURIComponent(pid) + "/status",
             { status: status, code: code ? code.value : "" })
        .then(function (res) {
            if (res.status === 200 && res.body.success) {
                setMsg(status === "solved" ? "Nice work — marked as solved!"
                     : status === "stuck" ? "Marked as stuck. Check your diagnosis for targeted practice."
                     : "Progress saved.", true);
            } else {
                setMsg((res.body && res.body.error) || "Could not save. Try again.", false);
            }
        }).catch(function () { setMsg("Network error. Try again.", false); });
    }
    [["solved-btn", "solved"], ["stuck-btn", "stuck"], ["save-btn", "attempted"]]
    .forEach(function (pair) {
        var b = document.getElementById(pair[0]);
        if (b) b.addEventListener("click", function () {
            saveStatus(b.getAttribute("data-pid"), pair[1]);
        });
    });
})();
