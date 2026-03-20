/**
 * DealSim Scenario Cards
 *
 * Replaces the plain <select> dropdown with a horizontally scrollable
 * row of visual cards — like choosing a game mode.
 *
 * Reads played-scenario data from DealSimGamification when available.
 * Keeps the original <select id="scenario-type"> as source of truth.
 *
 * Public API: window.DealSimScenarioCards { init(), getSelected() }
 */
(function () {
  'use strict';

  var SCENARIOS = [
    { id: 'salary',         name: 'Salary Negotiation', emoji: '\u{1F4BC}', tagline: 'Know your worth',  difficulty: 2 },
    { id: 'freelance',      name: 'Freelance Rate',     emoji: '\u{1F3A8}', tagline: 'Set your price',   difficulty: 2 },
    { id: 'rent',           name: 'Rent Negotiation',   emoji: '\u{1F3E0}', tagline: 'Lower the lease',  difficulty: 1 },
    { id: 'medical_bill',   name: 'Medical Bill',       emoji: '\u{1F3E5}', tagline: 'Reduce the bill',  difficulty: 3 },
    { id: 'car_buying',     name: 'Car Buying',         emoji: '\u{1F697}', tagline: 'Drive the deal',   difficulty: 2 },
    { id: 'scope_creep',    name: 'Scope Creep',        emoji: '\u{1F4CB}', tagline: 'Hold the line',    difficulty: 3 },
    { id: 'raise',          name: 'Raise Request',      emoji: '\u{1F4C8}', tagline: 'Make your case',   difficulty: 2 },
    { id: 'vendor',         name: 'Vendor Contract',    emoji: '\u{1F91D}', tagline: 'Seal the terms',   difficulty: 3 },
    { id: 'counter_offer',  name: 'Counter Offer',      emoji: '\u{1F504}', tagline: 'Flip the script',  difficulty: 2 },
    { id: 'budget_request', name: 'Budget Request',     emoji: '\u{1F4B0}', tagline: 'Fund the vision',  difficulty: 1 },
  ];

  var select = null;
  var cards = [];
  var container = null;

  // ── Helpers ──────────────────────────────────────────────────────────

  function getPlayedScenarios() {
    if (window.DealSimGamification) {
      var profile = window.DealSimGamification.getProfile();
      return (profile && profile.scenariosPlayed) ? profile.scenariosPlayed : {};
    }
    return {};
  }

  function difficultyDots(level) {
    var html = '';
    for (var i = 1; i <= 3; i++) {
      var filled = i <= level;
      html += '<span class="sc-dot' + (filled ? ' sc-dot--filled' : '') + '"></span>';
    }
    return html;
  }

  // ── Styles ───────────────────────────────────────────────────────────

  function injectStyles() {
    if (document.getElementById('sc-styles')) return;
    var style = document.createElement('style');
    style.id = 'sc-styles';
    style.textContent = [
      /* Container — horizontal scroll row */
      '.sc-row {',
      '  display: flex;',
      '  gap: 12px;',
      '  overflow-x: auto;',
      '  overflow-y: hidden;',
      '  padding: 8px 4px 12px;',
      '  scroll-behavior: smooth;',
      '  -webkit-overflow-scrolling: touch;',
      '}',

      /* Thin themed scrollbar */
      '.sc-row::-webkit-scrollbar { height: 4px; }',
      '.sc-row::-webkit-scrollbar-track { background: transparent; }',
      '.sc-row::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 2px; }',
      '.sc-row::-webkit-scrollbar-thumb:hover { background: var(--accent); }',
      /* Firefox */
      '.sc-row { scrollbar-width: thin; scrollbar-color: var(--scrollbar-thumb) transparent; }',

      /* Individual card */
      '.sc-card {',
      '  flex: 0 0 140px;',
      '  height: 160px;',
      '  display: flex;',
      '  flex-direction: column;',
      '  align-items: center;',
      '  justify-content: center;',
      '  gap: 6px;',
      '  background: var(--card-bg);',
      '  border: 1px solid var(--card-border);',
      '  border-radius: 12px;',
      '  cursor: pointer;',
      '  position: relative;',
      '  user-select: none;',
      '  touch-action: manipulation;',
      '  -webkit-tap-highlight-color: transparent;',
      '  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;',
      '}',

      '.sc-card:hover {',
      '  border-color: var(--accent-light);',
      '  transform: scale(1.02);',
      '}',

      /* Selected state */
      '.sc-card--selected {',
      '  border-color: var(--accent) !important;',
      '  transform: scale(1.03) !important;',
      '  box-shadow: 0 0 16px var(--accent-glow), 0 0 4px var(--accent-glow);',
      '}',

      /* Emoji */
      '.sc-emoji {',
      '  font-size: 36px;',
      '  line-height: 1;',
      '}',

      /* Name */
      '.sc-name {',
      '  font-size: 12px;',
      '  font-weight: 700;',
      '  color: var(--text);',
      '  text-align: center;',
      '  padding: 0 8px;',
      '  line-height: 1.2;',
      '}',

      /* Tagline */
      '.sc-tagline {',
      '  font-size: 11px;',
      '  color: var(--text-dim2);',
      '  text-align: center;',
      '  padding: 0 8px;',
      '}',

      /* Difficulty dots row */
      '.sc-dots {',
      '  display: flex;',
      '  gap: 4px;',
      '}',

      '.sc-dot {',
      '  width: 6px;',
      '  height: 6px;',
      '  border-radius: 50%;',
      '  background: var(--text-dim2);',
      '  opacity: 0.35;',
      '}',

      '.sc-dot--filled {',
      '  background: var(--accent);',
      '  opacity: 1;',
      '}',

      /* Played checkmark */
      '.sc-played {',
      '  position: absolute;',
      '  top: 6px;',
      '  right: 8px;',
      '  font-size: 12px;',
      '  color: var(--secondary);',
      '  opacity: 0.8;',
      '}',

      /* Mobile */
      '@media (max-width: 640px) {',
      '  .sc-card { flex: 0 0 120px; height: 140px; }',
      '  .sc-emoji { font-size: 30px; }',
      '  .sc-name { font-size: 11px; }',
      '}',

      /* Reduced motion */
      '@media (prefers-reduced-motion: reduce) {',
      '  .sc-card { transition: none !important; }',
      '}',
    ].join('\n');
    document.head.appendChild(style);
  }

  // ── Card Building ────────────────────────────────────────────────────

  function buildCards() {
    container = document.createElement('div');
    container.className = 'sc-row';

    var played = getPlayedScenarios();

    SCENARIOS.forEach(function (scenario) {
      var card = document.createElement('div');
      card.className = 'sc-card';
      card.setAttribute('data-scenario', scenario.id);
      card.setAttribute('role', 'option');
      card.setAttribute('tabindex', '0');

      var html =
        '<span class="sc-emoji">' + scenario.emoji + '</span>' +
        '<span class="sc-name">' + scenario.name + '</span>' +
        '<span class="sc-tagline">' + scenario.tagline + '</span>' +
        '<span class="sc-dots">' + difficultyDots(scenario.difficulty) + '</span>';

      if (played[scenario.id]) {
        html += '<span class="sc-played" title="Played before">\u2713</span>';
      }

      card.innerHTML = html;

      card.addEventListener('click', function () {
        selectScenario(scenario.id);
      });

      card.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          selectScenario(scenario.id);
        }
      });

      cards.push(card);
      container.appendChild(card);
    });
  }

  // ── Selection Logic ──────────────────────────────────────────────────

  function selectScenario(id) {
    // Update hidden select
    if (select && select.value !== id) {
      select.value = id;
      select.dispatchEvent(new Event('change', { bubbles: true }));
    }
    highlightCard(id);
  }

  function highlightCard(id) {
    cards.forEach(function (card) {
      var isMatch = card.getAttribute('data-scenario') === id;
      card.classList.toggle('sc-card--selected', isMatch);
      card.setAttribute('aria-selected', isMatch ? 'true' : 'false');
    });
  }

  function syncFromSelect() {
    if (select) highlightCard(select.value);
  }

  // ── Played-status refresh ────────────────────────────────────────────

  function refreshPlayedMarkers() {
    var played = getPlayedScenarios();
    cards.forEach(function (card) {
      var id = card.getAttribute('data-scenario');
      var existing = card.querySelector('.sc-played');
      if (played[id] && !existing) {
        var mark = document.createElement('span');
        mark.className = 'sc-played';
        mark.title = 'Played before';
        mark.textContent = '\u2713';
        card.appendChild(mark);
      }
    });
  }

  // ── Init ─────────────────────────────────────────────────────────────

  function init() {
    select = document.getElementById('scenario-type');
    if (!select) return;

    // Avoid double-init
    if (document.querySelector('.sc-row')) return;

    injectStyles();
    buildCards();

    // Insert card row before the select, then hide select
    select.parentNode.insertBefore(container, select);
    select.style.display = 'none';

    // Sync initial selection
    syncFromSelect();

    // Watch for programmatic changes to the select
    select.addEventListener('change', syncFromSelect);

    // Refresh played markers after any negotiation completes
    window.addEventListener('dealsim:sessionRecorded', refreshPlayedMarkers);
  }

  // ── Public API ───────────────────────────────────────────────────────

  window.DealSimScenarioCards = {
    init: init,
    getSelected: function () {
      return select ? select.value : null;
    },
  };
})();
