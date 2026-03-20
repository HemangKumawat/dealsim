/**
 * DealSim Daily Challenge Card
 * Compact landing-page card for today's challenge.
 * Fetches /api/challenges/today, tracks completion via localStorage,
 * awards +50 XP bonus on completion.
 * API: window.DealSimDailyChallenge = { init(), refresh() }
 */
(function () {
  'use strict';
  var KEY = 'dealsim_last_challenge';
  var SCORE_KEY = 'dealsim_last_challenge_score';
  var DIFF_MAP = {
    'Anchoring': 1, 'Information Extraction': 2, 'Concession Trading': 2,
    'BATNA Leverage': 3, 'Emotional Control': 2, 'Value Creation': 3,
  };
  var challenge = null, cardEl = null;

  function today() { return new Date().toISOString().slice(0, 10); }
  function done() { try { return localStorage.getItem(KEY) === today(); } catch (_) { return false; } }

  function storedScore() {
    try {
      var p = JSON.parse(localStorage.getItem(SCORE_KEY));
      if (p && p.date === today()) return p.score;
    } catch (_) { /* corrupted data */ }
    return null;
  }

  function resetTimer() {
    var now = new Date();
    var ms = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1)) - now;
    return Math.floor(ms / 3600000) + 'h ' + Math.floor((ms % 3600000) / 60000) + 'm';
  }

  function dots(n) { return '\u25CF'.repeat(n) + '\u25CB'.repeat(3 - n); }

  function esc(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

  function trunc(s, n) {
    if (!s || s.length <= n) return s || '';
    return s.slice(0, n).replace(/\s+\S*$/, '') + '\u2026';
  }

  function label(diff) {
    return '<div style="display:flex;align-items:center;gap:8px;margin-bottom:2px">'
      + '<span style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--text-dim,#b0b3d6)">Daily Challenge</span>'
      + '<span style="font-size:11px;color:var(--text-dim2,#6b6f9e)">' + dots(diff) + '</span></div>';
  }

  function titleLine(t) {
    return '<div style="font-weight:700;color:var(--text,#fff);font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + esc(t) + '</div>';
  }

  function renderInner() {
    var completed = done(), score = storedScore();
    var diff = challenge ? (DIFF_MAP[challenge.category] || 2) : 2;
    var title = challenge ? challenge.title : 'Loading\u2026';

    if (completed) {
      var scoreText = score != null ? ' \u2014 ' + score + ' pts' : '';
      return '<div style="font-size:28px;line-height:1;flex-shrink:0;margin-top:2px">\u2705</div>'
        + '<div style="flex:1;min-width:0">' + label(diff) + titleLine(title)
        + '<div style="display:flex;align-items:center;gap:12px;margin-top:4px">'
        + '<span style="font-size:13px;color:var(--secondary,#ffd700);font-weight:600">Completed today' + scoreText + '</span>'
        + '<span style="font-size:11px;color:var(--text-dim2,#6b6f9e)">Resets in ' + resetTimer() + '</span>'
        + '</div></div>';
    }

    var desc = challenge ? trunc(challenge.description, 90) : '';
    return '<div style="font-size:28px;line-height:1;flex-shrink:0;margin-top:2px">\uD83C\uDFAF</div>'
      + '<div style="flex:1;min-width:0">' + label(diff) + titleLine(title)
      + '<div style="font-size:13px;color:var(--text-dim,#b0b3d6);margin-top:2px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">' + esc(desc) + '</div></div>'
      + '<button onclick="DealSimDailyChallenge._start()" style="'
      + 'flex-shrink:0;align-self:center;background:transparent;'
      + 'border:1px solid var(--accent,#f95c5c);color:var(--accent,#f95c5c);'
      + 'font-size:13px;font-weight:600;padding:8px 16px;border-radius:8px;'
      + 'cursor:pointer;white-space:nowrap;transition:background .2s,color .2s'
      + '" onmouseover="this.style.background=\'var(--accent,#f95c5c)\';this.style.color=\'#fff\'"'
      + ' onmouseout="this.style.background=\'transparent\';this.style.color=\'var(--accent,#f95c5c)\'"'
      + '>Start Challenge</button>';
  }

  function buildCard() {
    var el = document.createElement('div');
    el.id = 'daily-challenge-card';
    el.setAttribute('role', 'region');
    el.setAttribute('aria-label', 'Daily Challenge');
    el.style.cssText = 'background:var(--card-bg,#1a1a2e);border:1px solid var(--card-border,rgba(249,92,92,.25));'
      + 'border-left:3px solid var(--accent,#f95c5c);border-radius:12px;padding:16px 20px;'
      + 'display:flex;align-items:flex-start;gap:14px;max-height:120px;overflow:hidden;'
      + 'transition:opacity .3s ease;cursor:default';
    el.innerHTML = renderInner();
    return el;
  }

  function inject() {
    var landing = document.getElementById('sec-landing');
    if (!landing) return;
    var grid = landing.querySelector('.grid.grid-cols-2');
    if (!grid) return;
    var old = document.getElementById('daily-challenge-card');
    if (old) old.parentElement.remove();
    cardEl = buildCard();
    var wrap = document.createElement('div');
    wrap.style.marginBottom = '24px';
    wrap.appendChild(cardEl);
    grid.parentNode.insertBefore(wrap, grid.nextSibling);
  }

  function refreshCard() {
    if (!cardEl) return;
    cardEl.innerHTML = renderInner();
    cardEl.style.opacity = done() ? '0.7' : '1';
  }

  function startChallenge() {
    if (!challenge) return;
    var sel = document.getElementById('scenario-type');
    if (sel) sel.value = challenge.scenario || 'salary';
    var tgt = document.getElementById('target-value');
    if (tgt) tgt.value = '';
    var ctx = document.getElementById('context');
    if (ctx) ctx.value = 'Daily Challenge: ' + challenge.title + ' \u2014 ' + (challenge.scenario_prompt || challenge.description);
    if (typeof window.selectDiff === 'function') {
      var btn = document.querySelector('.diff-btn[data-diff="medium"]');
      if (btn) window.selectDiff(btn);
    }
    // Mark challenge as started — XP bonus is awarded after session completion
    // via the dealsim:session-complete listener, not here
    try { localStorage.setItem(KEY, today()); } catch (_) { /* quota or private browsing */ }
    var form = document.getElementById('landing-form');
    if (form) {
      form.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setTimeout(function () { if (ctx) ctx.focus(); }, 400);
    }
    refreshCard();
  }

  // Award +50 XP when the daily challenge session completes.
  // Listens for 'dealsim:sessionRecorded' which renderScorecard dispatches.
  var BONUS_KEY = 'dealsim_challenge_xp_awarded';

  function challengeBonusAlreadyAwarded() {
    try { return localStorage.getItem(BONUS_KEY) === today(); } catch (_) { return true; }
  }

  function markChallengeBonusAwarded() {
    try { localStorage.setItem(BONUS_KEY, today()); } catch (_) { /* quota */ }
  }

  function showToastIfAvailable(msg) {
    // Prefer the shared toast system if present; fall back to console.
    if (typeof window.showToast === 'function') {
      window.showToast(msg, 3500);
    } else {
      var t = document.getElementById('toast');
      if (t) {
        t.textContent = msg;
        t.classList.add('show');
        setTimeout(function () { t.classList.remove('show'); }, 3500);
      }
    }
  }

  function awardChallengeXP() {
    if (!done()) return;                         // Challenge not started today
    if (challengeBonusAlreadyAwarded()) return;  // Already awarded this calendar day

    var gam = window.DealSimGamification;
    if (!gam) return;

    // Load profile directly and add +50 XP so we don't double-count the session.
    var profile = gam.getProfile();
    var oldLevel = profile.level;

    // Patch XP directly: DealSimGamification exposes no addXP, so we reach
    // in via recordSession with score=0 + bonusXP flag. Instead, we recalculate
    // via a tiny internal adjustment using the public profile + a scored bonus call
    // that contributes only the bonus delta.
    // recordSession(score=25) gives 50 XP base and is the cleanest supported path.
    // We use score=0 to avoid polluting session stats — only XP matters here.
    // Implementation: call recordSession with xpBonus workaround.
    // Gamification doesn't expose addXP, so we use the profile save pattern via
    // a read-modify-write through localStorage directly (mirrors gamification internals).
    try {
      var raw = localStorage.getItem('dealsim_profile');
      if (raw) {
        var p = JSON.parse(raw);
        if (typeof p.xp === 'number') {
          var prevLevel = Math.floor(Math.sqrt(p.xp / 100)) + 1;
          p.xp += 50;
          var newLevel = Math.floor(Math.sqrt(p.xp / 100)) + 1;
          localStorage.setItem('dealsim_profile', JSON.stringify(p));
          markChallengeBonusAwarded();

          // Refresh the stats bar if present
          if (window.DealSimStatsBar) window.DealSimStatsBar.update();

          // Show level-up celebration if level changed
          if (newLevel > prevLevel && window.DealSimCelebrations) {
            window.DealSimCelebrations.showLevelUp(newLevel, p.xp);
          }

          showToastIfAvailable('\uD83C\uDFAF Daily Challenge bonus: +50 XP');
        }
      }
    } catch (_) { /* corrupted profile — skip bonus silently */ }
  }

  window.addEventListener('dealsim:sessionRecorded', awardChallengeXP);

  window.DealSimDailyChallenge = {
    init: function () {
      fetch('/api/challenges/today').then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      }).then(function (data) {
        challenge = data;
        inject();
        setInterval(function () {
          if (done() && cardEl) refreshCard();
        }, 60000);
      }).catch(function () { /* API down — no card shown */ });
    },
    refresh: refreshCard,
    _start: startChallenge,
  };
})();
