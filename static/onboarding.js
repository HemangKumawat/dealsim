/**
 * DealSim Onboarding
 *
 * A quiet, 3-step tooltip tour for first-time visitors. Points at real UI
 * elements. Never shows again after the user finishes or skips.
 *
 * Design principle: a friend showing you around, not a product manager
 * maximizing engagement. If someone wants to skip, that choice is respected
 * permanently.
 *
 * Public API: window.DealSimOnboarding = { init(), reset() }
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'dealsim_onboarded';
  var TOOLTIP_ID  = 'dsob-tooltip';
  var BACKDROP_ID = 'dsob-backdrop';

  // ── Tour definition ────────────────────────────────────────────────────
  // Each step declares how to find its target and what to say.
  // `find` returns the DOM element to point at (or null — step is skipped).
  // `prefer` is the side of the element to place the tooltip ('below', 'above',
  // 'left', 'right'). The positioner falls back gracefully when viewport clips.

  var STEPS = [
    {
      find: function () {
        // The "Try a 60-Second Negotiation" hero CTA button
        return document.querySelector('#sec-landing button[onclick*="sec-demo"]');
      },
      prefer: 'below',
      heading: 'Start here',
      body: 'Jump into a live negotiation in under a minute — no setup, no account.',
    },
    {
      find: function () {
        // Scenario card row injected by scenario-cards.js
        return document.querySelector('.sc-row');
      },
      prefer: 'below',
      heading: 'Or pick a scenario',
      body: 'Salary, rent, freelance rates — choose the situation you actually face.',
    },
    {
      find: function () {
        // Theme toggle button injected by theme-switcher.js
        return document.getElementById('theme-toggle');
      },
      prefer: 'below',
      heading: 'Make it yours',
      body: 'Three vibes: Arena, Coach, Lab. Switch any time — purely cosmetic.',
    },
  ];

  // ── State ──────────────────────────────────────────────────────────────
  var currentStep = 0;
  var running     = false;

  // ── CSS injection ──────────────────────────────────────────────────────

  function injectStyles() {
    if (document.getElementById('dsob-styles')) return;

    var style = document.createElement('style');
    style.id = 'dsob-styles';
    style.textContent = [

      /* Soft backdrop — dims without blocking */
      '#' + BACKDROP_ID + ' {',
      '  position: fixed;',
      '  inset: 0;',
      '  background: rgba(0, 0, 0, 0.45);',
      '  z-index: 8900;',
      '  pointer-events: none;',
      '  opacity: 0;',
      '  transition: opacity 0.25s ease;',
      '}',
      '#' + BACKDROP_ID + '.dsob-visible {',
      '  opacity: 1;',
      '}',

      /* Spotlight cut-out: a transparent "hole" revealing the target */
      '#' + BACKDROP_ID + ' .dsob-spotlight {',
      '  position: absolute;',
      '  border-radius: 12px;',
      '  box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.45);',
      '  pointer-events: none;',
      '  transition: top 0.3s ease, left 0.3s ease, width 0.3s ease, height 0.3s ease;',
      '}',

      /* Tooltip bubble */
      '#' + TOOLTIP_ID + ' {',
      '  position: fixed;',
      '  z-index: 9100;',
      '  background: var(--card-bg, #1a1a2e);',
      '  border: 1px solid var(--accent, #f95c5c);',
      '  border-radius: 14px;',
      '  padding: 16px 18px 14px;',
      '  width: 260px;',
      '  box-shadow: 0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.04);',
      '  opacity: 0;',
      '  transform: translateY(6px);',
      '  transition: opacity 0.22s ease, transform 0.22s ease;',
      '  pointer-events: none;',
      '}',
      '#' + TOOLTIP_ID + '.dsob-visible {',
      '  opacity: 1;',
      '  transform: translateY(0);',
      '  pointer-events: auto;',
      '}',

      /* Arrow (caret pointing from tooltip toward element) */
      '#' + TOOLTIP_ID + ' .dsob-arrow {',
      '  position: absolute;',
      '  width: 10px;',
      '  height: 10px;',
      '  background: var(--card-bg, #1a1a2e);',
      '  border: 1px solid var(--accent, #f95c5c);',
      '  transform: rotate(45deg);',
      '}',
      /* Arrow variants (positioned by JS class) */
      '#' + TOOLTIP_ID + ' .dsob-arrow.dsob-arrow-top {',
      '  top: -6px; left: 50%; margin-left: -5px;',
      '  border-bottom: none; border-right: none;',
      '}',
      '#' + TOOLTIP_ID + ' .dsob-arrow.dsob-arrow-bottom {',
      '  bottom: -6px; left: 50%; margin-left: -5px;',
      '  border-top: none; border-left: none;',
      '}',
      '#' + TOOLTIP_ID + ' .dsob-arrow.dsob-arrow-left {',
      '  left: -6px; top: 50%; margin-top: -5px;',
      '  border-top: none; border-right: none;',
      '}',
      '#' + TOOLTIP_ID + ' .dsob-arrow.dsob-arrow-right {',
      '  right: -6px; top: 50%; margin-top: -5px;',
      '  border-bottom: none; border-left: none;',
      '}',

      /* Step counter */
      '.dsob-counter {',
      '  font-size: 11px;',
      '  color: var(--text-dim2, #6b6f9e);',
      '  font-weight: 500;',
      '  letter-spacing: 0.04em;',
      '  margin-bottom: 8px;',
      '}',

      /* Heading */
      '.dsob-heading {',
      '  font-size: 14px;',
      '  font-weight: 700;',
      '  color: var(--text, #ffffff);',
      '  margin-bottom: 4px;',
      '  line-height: 1.3;',
      '}',

      /* Body text */
      '.dsob-body {',
      '  font-size: 13px;',
      '  color: var(--text-dim, #b0b3d6);',
      '  line-height: 1.5;',
      '  margin-bottom: 14px;',
      '}',

      /* Action row */
      '.dsob-actions {',
      '  display: flex;',
      '  align-items: center;',
      '  justify-content: space-between;',
      '  gap: 8px;',
      '}',

      /* Skip link — understated, never pressuring */
      '.dsob-skip {',
      '  font-size: 12px;',
      '  color: var(--text-dim2, #6b6f9e);',
      '  background: none;',
      '  border: none;',
      '  cursor: pointer;',
      '  padding: 4px 0;',
      '  transition: color 0.15s;',
      '}',
      '.dsob-skip:hover {',
      '  color: var(--text-dim, #b0b3d6);',
      '}',

      /* Next / Done button */
      '.dsob-next {',
      '  font-size: 13px;',
      '  font-weight: 600;',
      '  background: var(--accent, #f95c5c);',
      '  color: #fff;',
      '  border: none;',
      '  border-radius: 8px;',
      '  padding: 7px 18px;',
      '  cursor: pointer;',
      '  transition: background 0.15s, transform 0.1s;',
      '}',
      '.dsob-next:hover {',
      '  background: var(--accent-light, #ff7a7a);',
      '}',
      '.dsob-next:active {',
      '  transform: scale(0.96);',
      '}',

      /* Dot progress indicators */
      '.dsob-dots {',
      '  display: flex;',
      '  gap: 5px;',
      '  align-items: center;',
      '}',
      '.dsob-dot {',
      '  width: 5px;',
      '  height: 5px;',
      '  border-radius: 50%;',
      '  background: var(--text-dim2, #6b6f9e);',
      '  transition: background 0.2s, transform 0.2s;',
      '}',
      '.dsob-dot.dsob-dot-active {',
      '  background: var(--accent, #f95c5c);',
      '  transform: scale(1.3);',
      '}',

      /* Reduced-motion: skip transitions */
      '@media (prefers-reduced-motion: reduce) {',
      '  #' + BACKDROP_ID + ', #' + TOOLTIP_ID + ' {',
      '    transition: none !important;',
      '  }',
      '}',

    ].join('\n');

    document.head.appendChild(style);
  }

  // ── DOM builders ───────────────────────────────────────────────────────

  function buildBackdrop() {
    if (document.getElementById(BACKDROP_ID)) return;
    var bd = document.createElement('div');
    bd.id = BACKDROP_ID;

    var spotlight = document.createElement('div');
    spotlight.className = 'dsob-spotlight';
    spotlight.id = 'dsob-spotlight';
    bd.appendChild(spotlight);

    document.body.appendChild(bd);
  }

  function buildTooltip() {
    if (document.getElementById(TOOLTIP_ID)) return;

    var tip = document.createElement('div');
    tip.id = TOOLTIP_ID;
    tip.setAttribute('role', 'dialog');
    tip.setAttribute('aria-modal', 'true');
    tip.setAttribute('aria-label', 'Tour step');

    // Arrow caret (class set by positioner)
    var arrow = document.createElement('div');
    arrow.className = 'dsob-arrow';
    arrow.id = 'dsob-arrow';
    tip.appendChild(arrow);

    // Counter — "1 / 3"
    var counter = document.createElement('div');
    counter.className = 'dsob-counter';
    counter.id = 'dsob-counter';
    tip.appendChild(counter);

    // Heading
    var heading = document.createElement('div');
    heading.className = 'dsob-heading';
    heading.id = 'dsob-heading';
    tip.appendChild(heading);

    // Body
    var body = document.createElement('div');
    body.className = 'dsob-body';
    body.id = 'dsob-body';
    tip.appendChild(body);

    // Dot progress
    var dots = document.createElement('div');
    dots.className = 'dsob-dots';
    dots.id = 'dsob-dots';
    for (var i = 0; i < STEPS.length; i++) {
      var dot = document.createElement('div');
      dot.className = 'dsob-dot';
      dots.appendChild(dot);
    }
    tip.appendChild(dots);

    // Actions row
    var actions = document.createElement('div');
    actions.className = 'dsob-actions';

    var skip = document.createElement('button');
    skip.className = 'dsob-skip';
    skip.textContent = 'Skip tour';
    skip.addEventListener('click', finish);
    actions.appendChild(skip);

    var nextBtn = document.createElement('button');
    nextBtn.className = 'dsob-next';
    nextBtn.id = 'dsob-next';
    nextBtn.textContent = 'Next';
    nextBtn.addEventListener('click', advance);
    actions.appendChild(nextBtn);

    tip.appendChild(actions);
    document.body.appendChild(tip);
  }

  // ── Positioning ────────────────────────────────────────────────────────
  // Places the tooltip near the target element. Tries `prefer` side first,
  // flips if it would clip the viewport. Gap of 12px from element edge.

  var GAP = 14;

  function positionTooltip(targetEl) {
    var tip    = document.getElementById(TOOLTIP_ID);
    var arrow  = document.getElementById('dsob-arrow');
    var spot   = document.getElementById('dsob-spotlight');
    if (!tip || !targetEl) return;

    var rect = targetEl.getBoundingClientRect();
    var vw   = window.innerWidth;
    var vh   = window.innerHeight;
    var tw   = tip.offsetWidth  || 260;
    var th   = tip.offsetHeight || 160;

    // Update spotlight to reveal target
    var PADDING = 8;
    spot.style.top    = (rect.top    - PADDING) + 'px';
    spot.style.left   = (rect.left   - PADDING) + 'px';
    spot.style.width  = (rect.width  + PADDING * 2) + 'px';
    spot.style.height = (rect.height + PADDING * 2) + 'px';

    // Determine best placement side
    var sides = computeSideOrder(STEPS[currentStep].prefer, rect, tw, th, vw, vh);
    var placement = sides[0];

    var tipTop, tipLeft;

    if (placement === 'below') {
      tipTop  = rect.bottom + GAP;
      tipLeft = clamp(rect.left + rect.width / 2 - tw / 2, 8, vw - tw - 8);
    } else if (placement === 'above') {
      tipTop  = rect.top - th - GAP;
      tipLeft = clamp(rect.left + rect.width / 2 - tw / 2, 8, vw - tw - 8);
    } else if (placement === 'right') {
      tipTop  = clamp(rect.top + rect.height / 2 - th / 2, 8, vh - th - 8);
      tipLeft = rect.right + GAP;
    } else {
      // left
      tipTop  = clamp(rect.top + rect.height / 2 - th / 2, 8, vh - th - 8);
      tipLeft = rect.left - tw - GAP;
    }

    tip.style.top  = tipTop  + 'px';
    tip.style.left = tipLeft + 'px';

    // Arrow direction (points from tooltip toward element)
    arrow.className = 'dsob-arrow';
    if (placement === 'below') {
      arrow.classList.add('dsob-arrow-top');
      // Align arrow horizontally over the element center
      var arrowLeft = clamp(rect.left + rect.width / 2 - tipLeft - 5, 20, tw - 25);
      arrow.style.left       = arrowLeft + 'px';
      arrow.style.marginLeft = '0';
      arrow.style.top        = '';
      arrow.style.bottom     = '';
      arrow.style.right      = '';
    } else if (placement === 'above') {
      arrow.classList.add('dsob-arrow-bottom');
      var arrowLeft2 = clamp(rect.left + rect.width / 2 - tipLeft - 5, 20, tw - 25);
      arrow.style.left       = arrowLeft2 + 'px';
      arrow.style.marginLeft = '0';
      arrow.style.top        = '';
      arrow.style.right      = '';
    } else if (placement === 'right') {
      arrow.classList.add('dsob-arrow-left');
      arrow.style.left   = '';
      arrow.style.right  = '';
      arrow.style.top    = '';
      arrow.style.bottom = '';
    } else {
      arrow.classList.add('dsob-arrow-right');
      arrow.style.left   = '';
      arrow.style.right  = '';
      arrow.style.top    = '';
      arrow.style.bottom = '';
    }
  }

  function computeSideOrder(prefer, rect, tw, th, vw, vh) {
    // Space available on each side
    var space = {
      below: vh - rect.bottom - GAP,
      above: rect.top          - GAP,
      right: vw - rect.right   - GAP,
      left:  rect.left         - GAP,
    };
    var fits = {
      below: space.below >= th,
      above: space.above >= th,
      right: space.right >= tw,
      left:  space.left  >= tw,
    };

    // Start with preferred side, fallback in sensible order
    var order = [prefer];
    var fallbacks = { below: ['above', 'right', 'left'], above: ['below', 'right', 'left'],
                      right: ['left', 'below', 'above'], left:  ['right', 'below', 'above'] };
    fallbacks[prefer].forEach(function (s) { order.push(s); });

    for (var i = 0; i < order.length; i++) {
      if (fits[order[i]]) return order;
    }
    return order; // nothing fits — use preferred anyway, clip is acceptable
  }

  function clamp(val, min, max) {
    return Math.max(min, Math.min(max, val));
  }

  // ── Step rendering ─────────────────────────────────────────────────────

  function renderStep(index) {
    var step    = STEPS[index];
    var target  = step.find();

    // If target isn't in the DOM, quietly skip to next
    if (!target) {
      if (index < STEPS.length - 1) {
        currentStep = index + 1;
        renderStep(currentStep);
      } else {
        finish();
      }
      return;
    }

    var counter  = document.getElementById('dsob-counter');
    var heading  = document.getElementById('dsob-heading');
    var body     = document.getElementById('dsob-body');
    var nextBtn  = document.getElementById('dsob-next');
    var dotsEl   = document.getElementById('dsob-dots');

    counter.textContent  = (index + 1) + ' / ' + STEPS.length;
    heading.textContent  = step.heading;
    body.textContent     = step.body;
    nextBtn.textContent  = (index === STEPS.length - 1) ? 'Got it' : 'Next';

    // Dot progress
    var dotEls = dotsEl.querySelectorAll('.dsob-dot');
    dotEls.forEach(function (d, i) {
      d.classList.toggle('dsob-dot-active', i === index);
    });

    // Scroll target into view before positioning
    target.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });

    // Short delay lets scroll settle before we measure getBoundingClientRect
    setTimeout(function () {
      positionTooltip(target);

      // Show backdrop and tooltip on the first step
      var bd  = document.getElementById(BACKDROP_ID);
      var tip = document.getElementById(TOOLTIP_ID);
      if (bd)  bd.classList.add('dsob-visible');
      if (tip) tip.classList.add('dsob-visible');
    }, 150);
  }

  // ── Flow control ───────────────────────────────────────────────────────

  function advance() {
    if (currentStep < STEPS.length - 1) {
      // Hide tooltip briefly while repositioning (avoids visual jump)
      var tip = document.getElementById(TOOLTIP_ID);
      if (tip) {
        tip.classList.remove('dsob-visible');
        setTimeout(function () {
          currentStep++;
          renderStep(currentStep);
        }, 180);
      } else {
        currentStep++;
        renderStep(currentStep);
      }
    } else {
      finish();
    }
  }

  function finish() {
    running = false;
    try { localStorage.setItem(STORAGE_KEY, '1'); } catch (_) { /* quota or private browsing */ }

    var tip = document.getElementById(TOOLTIP_ID);
    var bd  = document.getElementById(BACKDROP_ID);

    if (tip) tip.classList.remove('dsob-visible');
    if (bd)  bd.classList.remove('dsob-visible');

    // Remove elements after transition completes — no DOM litter
    setTimeout(function () {
      if (tip) tip.remove();
      if (bd)  bd.remove();
    }, 300);

    // Release any z-index capture
    document.removeEventListener('keydown', onKeyDown);
  }

  // Keyboard: Escape = skip, Right arrow = next
  function onKeyDown(e) {
    if (!running) return;
    if (e.key === 'Escape')      finish();
    if (e.key === 'ArrowRight')  advance();
  }

  // Reposition on resize (debounced)
  var resizeTimer = null;
  function onResize() {
    if (!running) return;
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      var target = STEPS[currentStep].find();
      if (target) positionTooltip(target);
    }, 100);
  }

  // ── Public API ─────────────────────────────────────────────────────────

  function init() {
    // Already seen — respect permanently
    try { if (localStorage.getItem(STORAGE_KEY)) return; } catch (_) { /* private browsing — proceed as new user */ }

    // Already running
    if (running) return;

    // Wait for the DOM modules that inject our target elements
    // (scenario-cards.js and theme-switcher.js run on DOMContentLoaded)
    waitForTargets(function () {
      running     = true;
      currentStep = 0;

      injectStyles();
      buildBackdrop();
      buildTooltip();
      renderStep(0);

      document.addEventListener('keydown', onKeyDown);
      window.addEventListener('resize', onResize);
    });
  }

  // Polls until at least the first required target exists, then fires cb.
  // Gives up after 5 seconds — if the page is broken we don't want to spin.
  function waitForTargets(cb) {
    var attempts = 0;
    var MAX      = 50; // 50 × 100ms = 5s
    var timer    = setInterval(function () {
      attempts++;
      var firstTarget = STEPS[0].find();
      if (firstTarget || attempts >= MAX) {
        clearInterval(timer);
        if (firstTarget) cb();
      }
    }, 100);
  }

  function reset() {
    try { localStorage.removeItem(STORAGE_KEY); } catch (_) { /* private browsing */ }
    // Clean up any residual elements from a previous run
    var tip = document.getElementById(TOOLTIP_ID);
    var bd  = document.getElementById(BACKDROP_ID);
    if (tip) tip.remove();
    if (bd)  bd.remove();
    running     = false;
    currentStep = 0;
  }

  // ── Bootstrap ──────────────────────────────────────────────────────────
  // Defer until DOMContentLoaded so other modules have had a chance to run.

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    // Other DOMContentLoaded handlers (scenario-cards, theme-switcher)
    // may still be queued. A short timeout lets them settle first.
    setTimeout(init, 50);
  }

  // Expose
  window.DealSimOnboarding = {
    init:  init,
    reset: reset,
  };

})();
