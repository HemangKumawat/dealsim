/**
 * DealSim Stats Bar
 * Compact sticky bar showing streak, level/XP, win rate, and session count.
 * Reads from DealSimGamification.getProfile() and updates on session-complete events.
 *
 * Exposes: window.DealSimStatsBar = { init, update }
 * Depends: DealSimGamification must be loaded first.
 */
(function () {
  'use strict';

  // ── Guard ──────────────────────────────────────────────────────
  if (typeof window.DealSimGamification === 'undefined') {
    console.warn('[stats-bar] DealSimGamification not found. Load gamification.js before stats-bar.js.');
    return;
  }

  var G = window.DealSimGamification;
  var bar = null;
  var els = {};

  // ── Styles ─────────────────────────────────────────────────────
  function injectStyles() {
    var s = document.createElement('style');
    s.textContent =
      '#stats-bar { display:flex; align-items:center; justify-content:center; gap:2rem;' +
      ' height:36px; padding:0 1.25rem; background:var(--nav-bg);' +
      ' border-bottom:1px solid var(--nav-border); backdrop-filter:blur(12px);' +
      ' font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;' +
      ' position:sticky; top:0; z-index:49; }' +
      '#stats-bar .sb-stat { display:flex; align-items:center; gap:0.35rem;' +
      ' font-size:12px; color:var(--text-dim); white-space:nowrap; }' +
      '#stats-bar .sb-val { font-size:14px; font-weight:600; color:var(--text); }' +
      '#stats-bar .sb-level-wrap { display:flex; flex-direction:column;' +
      ' align-items:center; gap:0; position:relative; }' +
      '#stats-bar .sb-xp-track { width:48px; height:2px; background:var(--card-border);' +
      ' border-radius:1px; overflow:hidden; }' +
      '#stats-bar .sb-xp-fill { height:100%; background:var(--accent);' +
      ' border-radius:1px; transition:width 0.4s ease; }' +
      '#stats-bar .sb-levelup { animation:sb-flash 0.5s ease-out; }' +
      '@keyframes sb-flash { 0%{background-color:var(--accent)} 100%{background-color:transparent} }' +
      '#stats-bar .sb-wr-green { color:#00c853; }' +
      '#stats-bar .sb-wr-yellow { color:#ffd600; }' +
      '#stats-bar .sb-wr-red { color:var(--accent, #f95c5c); }' +
      '@media(max-width:640px){ #stats-bar{gap:1.25rem} #stats-bar .sb-hide-mobile{display:none} }';
    document.head.appendChild(s);
  }

  // ── Win-rate color ─────────────────────────────────────────────
  function wrClass(rate) {
    if (rate >= 60) return 'sb-wr-green';
    if (rate >= 40) return 'sb-wr-yellow';
    return 'sb-wr-red';
  }

  // ── Build DOM ──────────────────────────────────────────────────
  function buildBar() {
    bar = document.createElement('div');
    bar.id = 'stats-bar';

    // Streak
    var streak = document.createElement('div');
    streak.className = 'sb-stat';
    streak.innerHTML = '<span>\u{1F525}</span> <span class="sb-val" data-sb="streak"></span>';
    bar.appendChild(streak);

    // Level + XP track
    var level = document.createElement('div');
    level.className = 'sb-stat';
    level.innerHTML =
      '<div class="sb-level-wrap">' +
        '<span class="sb-val" data-sb="level"></span>' +
        '<div class="sb-xp-track"><div class="sb-xp-fill" data-sb="xp"></div></div>' +
      '</div>';
    bar.appendChild(level);

    // Win Rate (hidden on mobile)
    var wr = document.createElement('div');
    wr.className = 'sb-stat sb-hide-mobile';
    wr.innerHTML = '<span class="sb-val" data-sb="wr"></span> <span>win rate</span>';
    bar.appendChild(wr);

    // Sessions (hidden on mobile)
    var sess = document.createElement('div');
    sess.className = 'sb-stat sb-hide-mobile';
    sess.innerHTML = '<span class="sb-val" data-sb="sessions"></span> <span>negotiations</span>';
    bar.appendChild(sess);

    // Cache references
    els.streak   = bar.querySelector('[data-sb="streak"]');
    els.level    = bar.querySelector('[data-sb="level"]');
    els.xp       = bar.querySelector('[data-sb="xp"]');
    els.wr       = bar.querySelector('[data-sb="wr"]');
    els.sessions = bar.querySelector('[data-sb="sessions"]');
    els.levelWrap = bar.querySelector('.sb-level-wrap');
  }

  // ── Render data ────────────────────────────────────────────────
  function render(profile) {
    if (!profile || !bar) return;

    var sessions = profile.totalSessions || 0;
    if (sessions < 1) {
      bar.style.display = 'none';
      return;
    }
    bar.style.display = '';

    // Streak
    var streakVal = profile.streak || 0;
    els.streak.textContent = streakVal > 0 ? streakVal + ' days' : '0';

    // Level — derive from XP using same formula as gamification.js
    var xpCurrent = profile.xp || 0;
    var lvl = Math.floor(Math.sqrt(xpCurrent / 100)) + 1;
    els.level.textContent = 'Lv ' + lvl;

    // XP progress — compute xpToNext from level formula
    var xpForCurrentLevel = (lvl - 1) * (lvl - 1) * 100;
    var xpForNextLevel = lvl * lvl * 100;
    var xpInLevel = xpCurrent - xpForCurrentLevel;
    var xpNeeded = xpForNextLevel - xpForCurrentLevel;
    var pct = xpNeeded > 0 ? Math.min(100, Math.round((xpInLevel / xpNeeded) * 100)) : 0;
    els.xp.style.width = pct + '%';

    // Win rate — compute from wins/totalSessions
    var rate = sessions > 0 ? Math.round((( profile.wins || 0) / sessions) * 100) : 0;
    els.wr.textContent = rate + '%';
    els.wr.className = 'sb-val ' + wrClass(rate);

    // Sessions
    els.sessions.textContent = sessions;
  }

  // ── Level-up highlight ─────────────────────────────────────────
  function flashLevel() {
    if (!els.levelWrap) return;
    els.levelWrap.classList.remove('sb-levelup');
    // Force reflow so re-adding the class restarts the animation
    void els.levelWrap.offsetWidth;
    els.levelWrap.classList.add('sb-levelup');
  }

  // ── Public: update ─────────────────────────────────────────────
  function update() {
    if (!bar) return;
    var profile = G.getProfile();
    render(profile);
  }

  // ── Public: init ───────────────────────────────────────────────
  function init() {
    if (bar) return; // Prevent duplicate init / listener leaks
    injectStyles();
    buildBar();

    // Insert after the first <nav>, or as the first child of <body>
    var nav = document.querySelector('nav');
    if (nav && nav.parentNode) {
      nav.parentNode.insertBefore(bar, nav.nextSibling);
    } else {
      document.body.insertBefore(bar, document.body.firstChild);
    }

    // Initial render
    update();

    // Listen for session-complete events
    document.addEventListener('dealsim:session-complete', update);

    // Listen for level-up events
    if (typeof G.onLevelUp === 'function') {
      G.onLevelUp(function () {
        update();
        flashLevel();
      });
    }
  }

  // ── Expose ─────────────────────────────────────────────────────
  window.DealSimStatsBar = { init: init, update: update };
})();
