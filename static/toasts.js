/**
 * DealSim Toast / Notification System
 * ====================================
 * IIFE — attaches window.DealSimToasts with four typed methods.
 *
 * API
 *   DealSimToasts.success(message, options?)
 *   DealSimToasts.error(message, options?)
 *   DealSimToasts.info(message, options?)
 *   DealSimToasts.warning(message, options?)
 *
 * options {
 *   duration  : number   — ms until auto-dismiss (default 4000)
 *   persistent: boolean  — skip auto-dismiss entirely
 *   action    : { label: string, onClick: fn }
 * }
 *
 * Behaviour
 *   - Stack from bottom-right, newest on top, max 3 visible (4th queued)
 *   - Slide in from right on enter, fade+shrink on exit
 *   - Progress bar drains over duration
 *   - Pause timer on hover
 *   - Accessible: role="alert" + aria-live="polite" on each toast
 *   - Respects prefers-reduced-motion
 *   - Theming: chrome uses CSS vars; type colors are semantic constants
 */

;(function (global) {
  'use strict';

  /* ------------------------------------------------------------------
     Constants
  ------------------------------------------------------------------ */

  var DEFAULT_DURATION = 4000;
  var MAX_VISIBLE      = 3;
  var CONTAINER_ID     = 'ds-toast-container';

  /**
   * Type definitions — icon SVG paths and fixed semantic colors.
   * Colors are intentionally NOT CSS-var-driven because success/error/
   * warning carry universal meaning that should not shift with a theme
   * accent color. The chrome (background, border, text) still uses vars.
   */
  var TYPES = {
    success: {
      color:     '#22c55e',        /* green-500  */
      colorDim:  'rgba(34,197,94,0.18)',
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>',
    },
    error: {
      color:     '#f87171',        /* red-400 — "coral" per DealSim palette */
      colorDim:  'rgba(248,113,113,0.18)',
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    },
    info: {
      color:     '#60a5fa',        /* blue-400  */
      colorDim:  'rgba(96,165,250,0.18)',
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
    },
    warning: {
      color:     '#fbbf24',        /* amber-400 */
      colorDim:  'rgba(251,191,36,0.18)',
      icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    },
  };

  /* ------------------------------------------------------------------
     Inject styles — done once on first call
  ------------------------------------------------------------------ */

  var stylesInjected = false;

  function injectStyles() {
    if (stylesInjected) return;
    stylesInjected = true;

    var style = document.createElement('style');
    style.id  = 'ds-toast-styles';
    style.textContent = [

      /* Container — anchored above the theme-switcher pill (bottom-right) */
      '#ds-toast-container {',
      '  position: fixed;',
      '  bottom: 80px;',            /* sits above the 64px theme-switcher pill */
      '  right: 20px;',
      '  z-index: 10000;',          /* above theme-switcher z-9999 */
      '  display: flex;',
      '  flex-direction: column-reverse;', /* newest on top visually */
      '  gap: 10px;',
      '  pointer-events: none;',
      '  width: 340px;',
      '  max-width: calc(100vw - 40px);',
      '}',

      /* Individual toast */
      '.ds-toast {',
      '  position: relative;',
      '  display: flex;',
      '  align-items: flex-start;',
      '  gap: 12px;',
      '  padding: 14px 14px 14px 14px;',
      '  border-radius: 12px;',
      '  background: var(--card-bg, #1a1a2e);',
      '  border: 1px solid var(--card-border, rgba(255,255,255,0.15));',
      '  box-shadow: 0 8px 32px rgba(0,0,0,0.45);',
      '  color: var(--text, #fff);',
      '  font-size: 14px;',
      '  line-height: 1.45;',
      '  pointer-events: all;',
      '  overflow: hidden;',
      '  transform: translateX(calc(100% + 24px));',
      '  opacity: 0;',
      '  transition:',
      '    transform 0.32s cubic-bezier(0.22, 1, 0.36, 1),',
      '    opacity   0.25s ease;',
      '  will-change: transform, opacity;',
      '}',

      /* Entrance state */
      '.ds-toast--visible {',
      '  transform: translateX(0);',
      '  opacity: 1;',
      '}',

      /* Exit state — fade + shrink in place */
      '.ds-toast--exiting {',
      '  transform: translateX(calc(100% + 24px));',
      '  opacity: 0;',
      '  transition:',
      '    transform 0.28s cubic-bezier(0.55, 0, 1, 0.45),',
      '    opacity   0.22s ease,',
      '    max-height 0.28s ease 0.1s,',  /* collapse gap after slide-out */
      '    padding    0.28s ease 0.1s,',
      '    margin     0.28s ease 0.1s;',
      '  max-height: 0 !important;',
      '  padding-top: 0 !important;',
      '  padding-bottom: 0 !important;',
      '  margin: 0 !important;',
      '}',

      /* Colored left-border strip */
      '.ds-toast__stripe {',
      '  position: absolute;',
      '  left: 0;',
      '  top: 0;',
      '  bottom: 0;',
      '  width: 4px;',
      '  border-radius: 12px 0 0 12px;',
      '}',

      /* Icon wrapper */
      '.ds-toast__icon {',
      '  flex-shrink: 0;',
      '  width: 32px;',
      '  height: 32px;',
      '  border-radius: 8px;',
      '  display: flex;',
      '  align-items: center;',
      '  justify-content: center;',
      '  margin-left: 8px;',        /* clear the stripe */
      '}',

      /* Body */
      '.ds-toast__body {',
      '  flex: 1;',
      '  min-width: 0;',
      '}',

      '.ds-toast__message {',
      '  margin: 0;',
      '  word-break: break-word;',
      '}',

      /* Optional action button */
      '.ds-toast__action {',
      '  margin-top: 8px;',
      '  background: none;',
      '  border: 1px solid currentColor;',
      '  border-radius: 6px;',
      '  padding: 3px 10px;',
      '  font-size: 12px;',
      '  font-weight: 600;',
      '  cursor: pointer;',
      '  opacity: 0.9;',
      '  transition: opacity 0.15s ease, background 0.15s ease;',
      '}',

      '.ds-toast__action:hover {',
      '  opacity: 1;',
      '  background: rgba(255,255,255,0.08);',
      '}',

      '.ds-toast__action:focus-visible {',
      '  outline: 2px solid var(--focus-ring, rgba(255,255,255,0.4));',
      '  outline-offset: 2px;',
      '}',

      /* Dismiss button */
      '.ds-toast__dismiss {',
      '  flex-shrink: 0;',
      '  background: none;',
      '  border: none;',
      '  padding: 4px;',
      '  cursor: pointer;',
      '  color: var(--text-dim, #b0b3d6);',
      '  border-radius: 6px;',
      '  line-height: 0;',
      '  transition: color 0.15s ease, background 0.15s ease;',
      '  align-self: flex-start;',
      '}',

      '.ds-toast__dismiss:hover {',
      '  color: var(--text, #fff);',
      '  background: rgba(255,255,255,0.08);',
      '}',

      '.ds-toast__dismiss:focus-visible {',
      '  outline: 2px solid var(--focus-ring, rgba(255,255,255,0.4));',
      '  outline-offset: 2px;',
      '}',

      /* Progress bar track */
      '.ds-toast__progress {',
      '  position: absolute;',
      '  bottom: 0;',
      '  left: 0;',
      '  right: 0;',
      '  height: 3px;',
      '  background: rgba(255,255,255,0.08);',
      '  border-radius: 0 0 12px 12px;',
      '  overflow: hidden;',
      '}',

      /* Progress bar fill — width animated via CSS custom property */
      '.ds-toast__progress-fill {',
      '  height: 100%;',
      '  width: 100%;',
      '  border-radius: inherit;',
      '  transform-origin: left;',
      '  transition: transform linear;', /* duration set inline per toast */
      '}',

      /* Pause progress on hover */
      '.ds-toast:hover .ds-toast__progress-fill {',
      '  transition-duration: 0s !important;',
      '}',

      /* Reduced-motion: kill all transitions */
      '@media (prefers-reduced-motion: reduce) {',
      '  .ds-toast, .ds-toast--exiting, .ds-toast__progress-fill {',
      '    transition: none !important;',
      '    animation: none !important;',
      '  }',
      '}',

      /* Mobile: full-width, bottom-anchored */
      '@media (max-width: 480px) {',
      '  #ds-toast-container {',
      '    bottom: 72px;',
      '    right: 0;',
      '    left: 0;',
      '    width: 100%;',
      '    max-width: 100%;',
      '    padding: 0 12px;',
      '    box-sizing: border-box;',
      '  }',
      '}',

    ].join('\n');

    document.head.appendChild(style);
  }

  /* ------------------------------------------------------------------
     State
  ------------------------------------------------------------------ */

  /** @type {HTMLElement|null} */
  var container = null;

  /** Active toast records — each is { el, timerId, pausedAt, remaining } */
  var activeToasts = [];

  /** Queued when MAX_VISIBLE is reached */
  var queue = [];

  /* ------------------------------------------------------------------
     Container bootstrap
  ------------------------------------------------------------------ */

  function getContainer() {
    if (container) return container;
    injectStyles();
    container = document.getElementById(CONTAINER_ID);
    if (!container) {
      container = document.createElement('div');
      container.id = CONTAINER_ID;
      /* aria-live on the container lets screen readers announce new items */
      container.setAttribute('aria-live', 'polite');
      container.setAttribute('aria-relevant', 'additions');
      document.body.appendChild(container);
    }
    return container;
  }

  /* ------------------------------------------------------------------
     Core — show one toast
  ------------------------------------------------------------------ */

  /**
   * @param {'success'|'error'|'info'|'warning'} type
   * @param {string} message
   * @param {{ duration?: number, persistent?: boolean, action?: { label: string, onClick: fn } }} opts
   */
  function show(type, message, opts) {
    opts = opts || {};

    var typeConf   = TYPES[type] || TYPES.info;
    var duration   = opts.persistent ? 0 : (opts.duration != null ? opts.duration : DEFAULT_DURATION);
    var persistent = opts.persistent || duration === 0;

    /* Queue overflow guard */
    if (activeToasts.length >= MAX_VISIBLE) {
      queue.push({ type: type, message: message, opts: opts });
      return;
    }

    var el = buildElement(type, typeConf, message, opts, persistent);
    var c  = getContainer();
    c.appendChild(el);

    /* Record before timer so dismiss callback has the reference */
    var record = {
      el:        el,
      timerId:   null,
      remaining: duration,
      startedAt: null,
    };
    activeToasts.push(record);

    /* Trigger entrance — must be in a separate frame to allow CSS pickup */
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        el.classList.add('ds-toast--visible');

        if (!persistent) {
          startTimer(record, duration);
          attachHoverPause(record, el);
        }

        /* Kick off progress bar animation (needs el in DOM + visible) */
        if (!persistent) {
          var fill = el.querySelector('.ds-toast__progress-fill');
          if (fill) {
            /* Set the transition duration first, then collapse the scaleX */
            fill.style.transitionDuration = duration + 'ms';
            requestAnimationFrame(function () {
              fill.style.transform = 'scaleX(0)';
            });
          }
        }
      });
    });
  }

  /* ------------------------------------------------------------------
     Build DOM element
  ------------------------------------------------------------------ */

  function buildElement(type, typeConf, message, opts, persistent) {
    var el = document.createElement('div');
    el.className = 'ds-toast';
    /* Each toast is its own alert region for AT */
    el.setAttribute('role', 'alert');
    el.setAttribute('aria-atomic', 'true');

    /* Pre-set max-height for collapse animation */
    el.style.maxHeight = '200px';

    /* Colored stripe */
    var stripe = document.createElement('div');
    stripe.className = 'ds-toast__stripe';
    stripe.style.background = typeConf.color;
    stripe.setAttribute('aria-hidden', 'true');
    el.appendChild(stripe);

    /* Icon */
    var iconWrap = document.createElement('div');
    iconWrap.className = 'ds-toast__icon';
    iconWrap.style.background = typeConf.colorDim;
    iconWrap.style.color       = typeConf.color;
    iconWrap.innerHTML         = typeConf.icon;
    el.appendChild(iconWrap);

    /* Body */
    var body = document.createElement('div');
    body.className = 'ds-toast__body';

    var msgEl = document.createElement('p');
    msgEl.className = 'ds-toast__message';
    msgEl.textContent = message;
    body.appendChild(msgEl);

    /* Optional action button */
    if (opts.action && opts.action.label) {
      var actionBtn = document.createElement('button');
      actionBtn.className = 'ds-toast__action';
      actionBtn.textContent = opts.action.label;
      actionBtn.style.color = typeConf.color;
      actionBtn.setAttribute('type', 'button');
      actionBtn.addEventListener('click', function () {
        if (typeof opts.action.onClick === 'function') {
          opts.action.onClick();
        }
        dismiss(el);
      });
      body.appendChild(actionBtn);
    }

    el.appendChild(body);

    /* Dismiss button */
    var dismissBtn = document.createElement('button');
    dismissBtn.className = 'ds-toast__dismiss';
    dismissBtn.setAttribute('type', 'button');
    dismissBtn.setAttribute('aria-label', 'Dismiss notification');
    dismissBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    dismissBtn.addEventListener('click', function () { dismiss(el); });
    el.appendChild(dismissBtn);

    /* Progress bar (only for timed toasts) */
    if (!persistent) {
      var progress = document.createElement('div');
      progress.className = 'ds-toast__progress';
      progress.setAttribute('aria-hidden', 'true');

      var fill = document.createElement('div');
      fill.className = 'ds-toast__progress-fill';
      fill.style.background = typeConf.color;
      /* Start at full width — animation collapses to 0 via scaleX */
      fill.style.transform  = 'scaleX(1)';
      /* transitionDuration set after mount in show() */

      progress.appendChild(fill);
      el.appendChild(progress);
    }

    return el;
  }

  /* ------------------------------------------------------------------
     Timer management
  ------------------------------------------------------------------ */

  function startTimer(record, duration) {
    record.startedAt = Date.now();
    record.remaining = duration;
    record.timerId   = setTimeout(function () {
      dismiss(record.el);
    }, duration);
  }

  function attachHoverPause(record, el) {
    el.addEventListener('mouseenter', function () {
      if (record.timerId == null) return;
      clearTimeout(record.timerId);
      record.timerId   = null;
      record.remaining = record.remaining - (Date.now() - record.startedAt);
    });

    el.addEventListener('mouseleave', function () {
      if (record.remaining == null || record.remaining <= 0) return;
      /* Resume progress bar */
      var fill = el.querySelector('.ds-toast__progress-fill');
      if (fill) {
        /* Read current scaleX so we can resume from here visually */
        var currentScale = getCurrentScale(fill);
        fill.style.transitionDuration = '0ms';
        fill.style.transform = 'scaleX(' + currentScale + ')';
        requestAnimationFrame(function () {
          fill.style.transitionDuration = record.remaining + 'ms';
          fill.style.transform = 'scaleX(0)';
        });
      }
      record.startedAt = Date.now();
      record.timerId   = setTimeout(function () {
        dismiss(record.el);
      }, record.remaining);
    });
  }

  function getCurrentScale(fillEl) {
    try {
      var matrix = getComputedStyle(fillEl).transform;
      if (!matrix || matrix === 'none') return 1;
      /* matrix(a, b, c, d, tx, ty) — scaleX is 'a' */
      var match = matrix.match(/matrix\(([^,]+)/);
      if (match) return parseFloat(match[1]);
    } catch (e) { /* ignore */ }
    return 1;
  }

  /* ------------------------------------------------------------------
     Dismiss
  ------------------------------------------------------------------ */

  function dismiss(el) {
    /* Find record */
    var idx = -1;
    for (var i = 0; i < activeToasts.length; i++) {
      if (activeToasts[i].el === el) { idx = i; break; }
    }
    if (idx === -1) return; /* already dismissed */

    var record = activeToasts[idx];
    if (record.timerId != null) {
      clearTimeout(record.timerId);
      record.timerId = null;
    }

    /* Remove from active list immediately so queue can fill the slot */
    activeToasts.splice(idx, 1);

    /* Animate out */
    el.classList.remove('ds-toast--visible');
    el.classList.add('ds-toast--exiting');

    var removeEl = function () {
      if (el.parentNode) el.parentNode.removeChild(el);
      drainQueue();
    };

    /* Transition end — fallback timeout in case event never fires */
    var removed = false;
    el.addEventListener('transitionend', function handler() {
      if (removed) return;
      removed = true;
      el.removeEventListener('transitionend', handler);
      removeEl();
    });
    setTimeout(function () {
      if (!removed) { removed = true; removeEl(); }
    }, 600);
  }

  /* ------------------------------------------------------------------
     Queue drain
  ------------------------------------------------------------------ */

  function drainQueue() {
    if (queue.length === 0) return;
    if (activeToasts.length >= MAX_VISIBLE) return;
    var next = queue.shift();
    show(next.type, next.message, next.opts);
  }

  /* ------------------------------------------------------------------
     Public API
  ------------------------------------------------------------------ */

  var DealSimToasts = {
    success: function (message, opts) { show('success', message, opts); },
    error:   function (message, opts) { show('error',   message, opts); },
    info:    function (message, opts) { show('info',    message, opts); },
    warning: function (message, opts) { show('warning', message, opts); },

    /**
     * Dismiss all currently visible toasts and clear the queue.
     * Useful on page navigation or major state resets.
     */
    clear: function () {
      queue = [];
      var snapshot = activeToasts.slice();
      for (var i = 0; i < snapshot.length; i++) {
        dismiss(snapshot[i].el);
      }
    },
  };

  global.DealSimToasts = DealSimToasts;

}(window));
