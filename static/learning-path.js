/**
 * DealSim Learning Path
 * Visual skill-tree showing negotiation milestones as a horizontal progress path.
 * Reads completion state from DealSimGamification and renders pure DOM.
 *
 * Exposes: window.DealSimLearningPath = { init, update }
 * Depends: DealSimGamification must be loaded first.
 */
(function () {
  'use strict';

  if (typeof window.DealSimGamification === 'undefined') {
    console.warn('[learning-path] DealSimGamification not found. Load gamification.js first.');
    return;
  }

  var G = window.DealSimGamification;
  var container = null;
  var tooltipEl = null;

  // ── Milestone Definitions ──────────────────────────────────────

  var MILESTONES = [
    { id: 'first-steps',     emoji: '\uD83C\uDFAF', label: 'First Steps',       req: 'Complete 1 negotiation',                check: function (p)    { return p.totalSessions >= 1; } },
    { id: 'finding-voice',   emoji: '\uD83D\uDCAC', label: 'Finding Your Voice', req: 'Try 3 different scenarios',              check: function (p)    { return Object.keys(p.scenariosPlayed).length >= 3; } },
    { id: 'reading-room',    emoji: '\uD83D\uDCCA', label: 'Reading the Room',   req: 'Score 50+ on Information Gathering',     check: function (p, r) { return dimAvg(r, 'Information Gathering') >= 50; } },
    { id: 'give-take',       emoji: '\uD83E\uDD1D', label: 'Give and Take',      req: 'Score 50+ on Concession Pattern',       check: function (p, r) { return dimAvg(r, 'Concession Pattern') >= 50; } },
    { id: 'standing-ground', emoji: '\uD83D\uDEE1\uFE0F', label: 'Standing Ground',   req: 'Score 60+ on BATNA Usage',              check: function (p, r) { return dimAvg(r, 'BATNA Usage') >= 60; } },
    { id: 'staying-cool',    emoji: '\uD83D\uDE0C', label: 'Staying Cool',       req: 'Score 60+ on Emotional Control',        check: function (p, r) { return dimAvg(r, 'Emotional Control') >= 60; } },
    { id: 'creating-value',  emoji: '\u2728',        label: 'Creating Value',     req: 'Score 60+ on Value Creation',           check: function (p, r) { return dimAvg(r, 'Value Creation') >= 60; } },
    { id: 'master',          emoji: '\uD83C\uDFC6', label: 'Negotiation Master', req: 'Score 80+ overall average',             check: function (p)    { return p.totalSessions > 0 && p.bestScore >= 80; } },
  ];

  function dimAvg(radar, name) {
    var idx = radar.labels.indexOf(name);
    return idx >= 0 ? radar.values[idx] : 0;
  }

  // ── Styles ─────────────────────────────────────────────────────

  function injectStyles() {
    if (document.getElementById('lp-styles')) return;
    var s = document.createElement('style');
    s.id = 'lp-styles';
    s.textContent = [
      '.lp-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:thin;padding:12px 0;}',
      '.lp-track{display:flex;align-items:flex-start;gap:0;min-width:max-content;padding:0 16px;}',
      '.lp-node{display:flex;flex-direction:column;align-items:center;position:relative;flex-shrink:0;cursor:pointer;}',
      '.lp-circle{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;',
      '  font-size:15px;line-height:1;border:2px solid var(--accent);transition:all .3s ease;}',
      '.lp-node.completed .lp-circle{background:var(--accent);border-color:var(--accent);opacity:1;}',
      '.lp-node.current .lp-circle{border-color:var(--accent);animation:lp-pulse 2s ease-in-out infinite;}',
      '.lp-node.future .lp-circle{border-color:var(--text-dim2);opacity:.3;}',
      '.lp-label{font-size:10px;color:var(--text-dim);margin-top:4px;white-space:nowrap;max-width:72px;',
      '  text-align:center;overflow:hidden;text-overflow:ellipsis;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;}',
      '.lp-node.future .lp-label{opacity:.3;}',
      '.lp-connector{width:28px;height:2px;margin-top:16px;flex-shrink:0;}',
      '.lp-connector.solid{background:var(--accent);}',
      '.lp-connector.dashed{background:repeating-linear-gradient(90deg,var(--text-dim2) 0 4px,transparent 4px 8px);opacity:.35;}',
      '@keyframes lp-pulse{0%,100%{opacity:.6}50%{opacity:1}}',
      '.lp-tooltip{position:fixed;padding:6px 10px;background:var(--card-bg);border:1px solid var(--card-border);',
      '  border-radius:6px;font-size:11px;color:var(--text);pointer-events:none;z-index:200;',
      '  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;',
      '  box-shadow:0 4px 12px rgba(0,0,0,.4);opacity:0;transition:opacity .15s ease;}',
      '.lp-tooltip.visible{opacity:1;}',
    ].join('\n');
    document.head.appendChild(s);
  }

  // ── Tooltip ────────────────────────────────────────────────────

  function showTooltip(e, text) {
    if (!tooltipEl) {
      tooltipEl = document.createElement('div');
      tooltipEl.className = 'lp-tooltip';
      document.body.appendChild(tooltipEl);
    }
    tooltipEl.textContent = text;
    var rect = e.currentTarget.getBoundingClientRect();
    var rawLeft = rect.left + rect.width / 2 - 60;
    tooltipEl.style.left = Math.max(4, Math.min(rawLeft, window.innerWidth - 130)) + 'px';
    tooltipEl.style.top = rect.bottom + 6 + 'px';
    tooltipEl.classList.add('visible');
  }

  function hideTooltip() {
    if (tooltipEl) tooltipEl.classList.remove('visible');
  }

  // ── Completion State ───────────────────────────────────────────

  function computeStates() {
    var profile = G.getProfile();
    var radar = G.getRadarData();
    var foundCurrent = false;
    return MILESTONES.map(function (m) {
      if (foundCurrent) return 'future';
      var done = m.check(profile, radar);
      if (done) return 'completed';
      foundCurrent = true;
      return 'current';
    });
  }

  // ── Render ─────────────────────────────────────────────────────

  function render() {
    if (!container) return;

    var profile = G.getProfile();
    if (profile.totalSessions < 1) {
      container.style.display = 'none';
      return;
    }
    container.style.display = '';

    var states = computeStates();

    // Clear previous content
    while (container.firstChild) container.removeChild(container.firstChild);

    var wrap = document.createElement('div');
    wrap.className = 'lp-wrap';

    var track = document.createElement('div');
    track.className = 'lp-track';

    MILESTONES.forEach(function (m, i) {
      // Connector before node (skip first)
      if (i > 0) {
        var conn = document.createElement('div');
        conn.className = 'lp-connector ' + (states[i - 1] === 'completed' && states[i] !== 'future' ? 'solid' : 'dashed');
        track.appendChild(conn);
      }

      var node = document.createElement('div');
      node.className = 'lp-node ' + states[i];

      var circle = document.createElement('div');
      circle.className = 'lp-circle';
      circle.textContent = m.emoji;

      var label = document.createElement('div');
      label.className = 'lp-label';
      label.textContent = m.label;

      node.appendChild(circle);
      node.appendChild(label);

      // Tooltip on click/hover
      var reqText = states[i] === 'completed' ? m.label + ' (done!)' : m.req;
      node.addEventListener('mouseenter', function (e) { showTooltip(e, reqText); });
      node.addEventListener('mouseleave', hideTooltip);
      node.addEventListener('click', function (e) { showTooltip(e, reqText); });

      track.appendChild(node);
    });

    wrap.appendChild(track);
    container.appendChild(wrap);
  }

  // ── Public API ─────────────────────────────────────────────────

  window.DealSimLearningPath = {
    init: function (containerId) {
      injectStyles();
      container = document.getElementById(containerId);
      if (!container) {
        console.warn('[learning-path] Container #' + containerId + ' not found.');
        return;
      }
      render();
    },
    update: function () {
      render();
    },
  };

})();
