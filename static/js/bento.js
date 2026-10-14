/* bento.js — shared motion/interaction layer for the dark bento theme.
 *
 * Progressive enhancement ONLY: no layout, content, or app behavior depends
 * on this file. Every effect is gated on prefers-reduced-motion and degrades
 * to fully-visible static content when JS is disabled or motion is reduced.
 */
(function () {
  'use strict';

  var reduce = window.matchMedia
    ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
    : false;
  var finePointer = window.matchMedia
    ? window.matchMedia('(pointer: fine)').matches
    : true;

  /* 1. Cursor-tracked sheen on bento cards.
     Delegated pointermove, rAF-throttled; sets --mx/--my consumed by
     bento.css ::before. Skipped on touch / reduced motion. */
  if (!reduce && finePointer) {
    var sheenQueued = false;
    var lastEvent = null;
    document.addEventListener('pointermove', function (e) {
      lastEvent = e;
      if (sheenQueued) return;
      sheenQueued = true;
      requestAnimationFrame(function () {
        sheenQueued = false;
        if (!lastEvent || !lastEvent.target || !lastEvent.target.closest) return;
        var card = lastEvent.target.closest('.b-card');
        if (!card) return;
        var r = card.getBoundingClientRect();
        if (r.width === 0) return;
        card.style.setProperty('--mx', (((lastEvent.clientX - r.left) / r.width) * 100).toFixed(1) + '%');
        card.style.setProperty('--my', (((lastEvent.clientY - r.top) / r.height) * 100).toFixed(1) + '%');
      });
    }, { passive: true });
  }

  /* 2. Scroll reveals: .b-reveal -> .in via IntersectionObserver.
     Fallback (no IO or reduced motion): reveal immediately so content is
     never stuck invisible. */
  var revealEls = document.querySelectorAll('.b-reveal:not(.in)');
  if ('IntersectionObserver' in window && !reduce) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add('in');
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.12 });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add('in'); });
  }

  /* 3. Animated stat counters: .b-stat-num[data-count].
     Final value is already in the markup (server-rendered); JS counts up
     to it. Runs once when visible. */
  function countUp(el) {
    var target = parseInt(el.getAttribute('data-count'), 10);
    if (isNaN(target)) return;
    if (reduce) {
      el.textContent = String(target);
      return;
    }
    var t0 = null;
    var dur = 1200;
    function step(t) {
      if (!t0) t0 = t;
      var p = Math.min((t - t0) / dur, 1);
      el.textContent = String(Math.round(target * (1 - Math.pow(1 - p, 3))));
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  var counters = document.querySelectorAll('.b-stat-num[data-count]');
  if ('IntersectionObserver' in window && !reduce) {
    var so = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          countUp(en.target);
          so.unobserve(en.target);
        }
      });
    }, { threshold: 0.5 });
    counters.forEach(function (el) { so.observe(el); });
  } else {
    counters.forEach(countUp);
  }

  /* 4. Marquee / ticker: pause when scrolled out of view (CSS :hover /
     :focus-within already pause on interaction). Saves CPU on long pages. */
  var streams = document.querySelectorAll('.b-marquee, .b-ticker');
  if ('IntersectionObserver' in window && streams.length) {
    var mo = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        en.target.classList.toggle('is-paused', !en.isIntersecting);
      });
    }, { threshold: 0 });
    streams.forEach(function (el) { mo.observe(el); });
  }

  /* 5. Magnetic CTA buttons: subtle pull toward the cursor (max 12px),
     transform-only. Desktop pointers only, never moves the button away
     from the click point. */
  if (!reduce && finePointer) {
    document.querySelectorAll('.b-magnet').forEach(function (btn) {
      btn.addEventListener('pointermove', function (e) {
        var r = btn.getBoundingClientRect();
        var dx = e.clientX - (r.left + r.width / 2);
        var dy = e.clientY - (r.top + r.height / 2);
        var dist = Math.sqrt(dx * dx + dy * dy);
        var R = 12;
        if (dist < 90 && dist > 0) {
          var pull = Math.min(R, (dist / 90) * R);
          btn.style.transform =
            'translate(' + ((dx / dist) * pull).toFixed(1) + 'px,' + ((dy / dist) * pull).toFixed(1) + 'px)';
        } else {
          btn.style.transform = '';
        }
      });
      btn.addEventListener('pointerleave', function () {
        btn.style.transform = '';
      });
    });
  }

  /* 6. Scroll-progress hairline: [data-scroll-progress] gets scaleX
     updated on scroll (rAF-throttled, passive). */
  var prog = document.querySelector('[data-scroll-progress]');
  if (prog) {
    var ticking = false;
    function update() {
      ticking = false;
      var h = document.documentElement;
      var max = h.scrollHeight - h.clientHeight;
      var p = max > 0 ? h.scrollTop / max : 0;
      prog.style.transform = 'scaleX(' + p.toFixed(4) + ')';
    }
    window.addEventListener('scroll', function () {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(update);
      }
    }, { passive: true });
    update();
  }
})();
