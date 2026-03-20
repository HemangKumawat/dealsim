/**
 * DealSim Celebrations
 *
 * Subtle, warm micro-celebrations for key moments.
 * Provides tasteful acknowledgments — no confetti, no fireworks.
 * All animations use transform + opacity only (GPU-accelerated).
 * Respects prefers-reduced-motion. Max 1 celebration per session.
 *
 * Public API exposed via window.DealSimCelebrations.
 */
(function () {
  'use strict';

  var STYLES_ID = 'dealsim-celebrations-styles';
  var shownThisSession = false;
  var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Priority: levelUp > firstSession > highScore > personalBest
  var PRIORITY = { levelUp: 4, firstSession: 3, highScore: 2, personalBest: 1 };
  var highestShown = 0;

  function canShow(type) {
    if (shownThisSession && PRIORITY[type] <= highestShown) return false;
    return true;
  }

  function markShown(type) {
    shownThisSession = true;
    highestShown = Math.max(highestShown, PRIORITY[type]);
  }

  // ── Inject styles ───────────────────────────────────────────────────

  function injectStyles() {
    if (document.getElementById(STYLES_ID)) return;
    var style = document.createElement('style');
    style.id = STYLES_ID;
    style.textContent = [
      '.ds-level-card {',
      '  position: fixed; bottom: 32px; left: 50%; z-index: 9000;',
      '  transform: translateX(-50%) translateY(40px); opacity: 0;',
      '  background: var(--card-bg); border: 1px solid var(--card-border);',
      '  border-top: 3px solid var(--accent); border-radius: 12px;',
      '  padding: 18px 28px; text-align: center; cursor: pointer;',
      '  font-family: inherit; color: var(--text);',
      '  transition: transform 0.4s ease, opacity 0.4s ease;',
      '}',
      '.ds-level-card.ds-visible {',
      '  transform: translateX(-50%) translateY(0); opacity: 1;',
      '}',
      '.ds-level-card .ds-level-num {',
      '  font-size: 2rem; font-weight: 700; color: var(--accent);',
      '  line-height: 1.1;',
      '}',
      '.ds-level-card .ds-level-label {',
      '  font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em;',
      '  color: var(--text-dim); margin-bottom: 4px;',
      '}',
      '.ds-level-card .ds-level-xp {',
      '  font-size: 0.8rem; color: var(--text-dim2); margin-top: 4px;',
      '}',
      '@keyframes ds-shimmer {',
      '  0%   { opacity: 0; }',
      '  30%  { opacity: 1; }',
      '  70%  { opacity: 1; }',
      '  100% { opacity: 0; }',
      '}',
      '.ds-personal-best {',
      '  color: var(--secondary); font-size: 0.8rem; font-weight: 600;',
      '  animation: ds-shimmer 2s ease forwards;',
      '}',
      '@keyframes ds-glow-pulse {',
      '  0%, 100% { box-shadow: 0 0 0 0 transparent; }',
      '  50%      { box-shadow: 0 0 18px 4px var(--accent-glow); }',
      '}',
      '.ds-high-score-glow {',
      '  animation: ds-glow-pulse 0.8s ease 2;',
      '}',
      '.ds-first-session {',
      '  font-style: italic; color: var(--text-dim2); font-size: 0.85rem;',
      '  margin-top: 8px; opacity: 0;',
      '  transition: opacity 0.6s ease;',
      '}',
      '.ds-first-session.ds-visible { opacity: 1; }',
      '@media (prefers-reduced-motion: reduce) {',
      '  .ds-level-card { transition: none; }',
      '  .ds-personal-best { animation: none; opacity: 1; }',
      '  .ds-high-score-glow { animation: none; }',
      '  .ds-first-session { transition: none; }',
      '}',
    ].join('\n');
    document.head.appendChild(style);
  }

  // ── Level Up Card ───────────────────────────────────────────────────

  function showLevelUp(level, xp) {
    if (!canShow('levelUp')) return;
    markShown('levelUp');
    injectStyles();

    var card = document.createElement('div');
    card.className = 'ds-level-card';
    card.innerHTML =
      '<div class="ds-level-label">Level</div>' +
      '<div class="ds-level-num">' + level + '</div>' +
      '<div class="ds-level-xp">You\u2019ve earned ' + xp.toLocaleString() + ' XP</div>';

    card.addEventListener('click', function () { dismiss(card); });
    document.body.appendChild(card);

    if (prefersReducedMotion) {
      card.classList.add('ds-visible');
    } else {
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { card.classList.add('ds-visible'); });
      });
    }

    setTimeout(function () { dismiss(card); }, 3000);
  }

  function dismiss(card) {
    if (!card || !card.parentNode) return;
    card.classList.remove('ds-visible');
    setTimeout(function () {
      if (card.parentNode) card.parentNode.removeChild(card);
    }, prefersReducedMotion ? 0 : 400);
  }

  // ── Personal Best Shimmer ──────────────────────────────────────────

  function showPersonalBest(scoreEl) {
    if (!canShow('personalBest')) return;
    markShown('personalBest');
    injectStyles();

    var target = scoreEl || document.querySelector('.score-value, .ds-score-value, [data-score]');
    if (!target) return;

    var msg = document.createElement('div');
    msg.className = 'ds-personal-best';
    msg.textContent = 'New personal best!';
    target.parentNode.insertBefore(msg, target.nextSibling);

    setTimeout(function () {
      if (msg.parentNode) msg.parentNode.removeChild(msg);
    }, 2500);
  }

  // ── High Score Glow (80+) ──────────────────────────────────────────

  function showHighScore(scoreEl) {
    if (!canShow('highScore')) return;
    markShown('highScore');
    injectStyles();

    var target = scoreEl || document.querySelector('.score-circle, .ds-score-circle, [data-score-circle]');
    if (!target) return;

    target.classList.add('ds-high-score-glow');
    target.addEventListener('animationend', function handler() {
      target.classList.remove('ds-high-score-glow');
      target.removeEventListener('animationend', handler);
    });
  }

  // ── First Session Message ──────────────────────────────────────────

  function showFirstSession() {
    if (!canShow('firstSession')) return;
    markShown('firstSession');
    injectStyles();

    var anchor = document.querySelector('.score-value, .ds-score-value, [data-score]');
    if (!anchor) return;

    var msg = document.createElement('div');
    msg.className = 'ds-first-session';
    msg.textContent = 'Your first negotiation is done. You\u2019re already ahead of most people who never practice.';
    anchor.parentNode.insertBefore(msg, anchor.nextSibling);

    if (prefersReducedMotion) {
      msg.classList.add('ds-visible');
    } else {
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { msg.classList.add('ds-visible'); });
      });
    }

    setTimeout(function () {
      msg.classList.remove('ds-visible');
      setTimeout(function () {
        if (msg.parentNode) msg.parentNode.removeChild(msg);
      }, prefersReducedMotion ? 0 : 600);
    }, 3000);
  }

  // ── Init ────────────────────────────────────────────────────────────

  function init() {
    injectStyles();
    shownThisSession = false;
    highestShown = 0;
  }

  // ── Public API ──────────────────────────────────────────────────────

  window.DealSimCelebrations = {
    init: init,
    showLevelUp: showLevelUp,
    showPersonalBest: showPersonalBest,
    showHighScore: showHighScore,
    showFirstSession: showFirstSession,
  };
})();
