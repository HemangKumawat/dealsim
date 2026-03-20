/**
 * DealSim Engine Peek — "Under The Hood"
 *
 * Collapsible section showing how the negotiation engine works.
 * Educational transparency: engine flow, opponent styles, scoring dimensions.
 * Adapts to all 3 themes via CSS variables.
 *
 * Public API: window.DealSimEnginePeek { init(), toggle() }
 */
(function () {
  'use strict';

  /* ── Data ──────────────────────────────────────────────────────── */

  var FLOW_STEPS = [
    { icon: '\u{1F4AC}', label: 'Your Message' },
    { icon: '\u{1F50D}', label: 'Style Detection' },
    { icon: '\u{2699}\uFE0F', label: 'Strategy Engine' },
    { icon: '\u{1F4CA}', label: 'Scoring' },
    { icon: '\u{1F4A1}', label: 'Response' },
  ];

  var STYLES = [
    {
      id: 'competitive',
      name: 'Competitive',
      desc: 'Pushes hard for maximum individual gain. Treats negotiation as a zero-sum contest where concessions signal weakness.',
      traits: ['Anchors aggressively', 'Resists concessions', 'Uses pressure tactics', 'Claims value first'],
    },
    {
      id: 'collaborative',
      name: 'Collaborative',
      desc: 'Seeks outcomes that satisfy both parties. Invests time exploring interests to find solutions neither side imagined alone.',
      traits: ['Shares information', 'Asks open questions', 'Explores trade-offs', 'Builds on proposals'],
    },
    {
      id: 'compromising',
      name: 'Compromising',
      desc: 'Meets in the middle efficiently. Values speed and fairness over maximizing any single outcome.',
      traits: ['Splits differences', 'Makes quick offers', 'Values fairness', 'Trades evenly'],
    },
    {
      id: 'accommodating',
      name: 'Accommodating',
      desc: 'Prioritizes the relationship over the deal terms. Yields on substance to preserve goodwill and long-term connection.',
      traits: ['Yields early', 'Preserves harmony', 'Accepts first offers', 'Avoids confrontation'],
    },
    {
      id: 'avoiding',
      name: 'Avoiding',
      desc: 'Deflects and delays engagement. Sidesteps direct confrontation and leaves issues unresolved when possible.',
      traits: ['Delays responses', 'Changes subject', 'Defers decisions', 'Minimizes stakes'],
    },
  ];

  var DIMENSIONS = [
    { name: 'Opening Strategy', desc: 'How effectively you frame the initial position' },
    { name: 'Information Gathering', desc: 'How well you uncover the other side\'s interests' },
    { name: 'Concession Pattern', desc: 'Strategic give-and-take timing' },
    { name: 'BATNA Usage', desc: 'Leveraging your alternatives' },
    { name: 'Emotional Control', desc: 'Managing pressure and staying composed' },
    { name: 'Value Creation', desc: 'Finding win-win opportunities' },
  ];

  /* ── State ─────────────────────────────────────────────────────── */

  var expanded = false;
  var activeStyle = 0;
  var root = null;

  /* ── CSS (injected once) ───────────────────────────────────────── */

  var CSS = [
    '.ep-wrap { max-width: 36rem; width: 100%; margin: 2rem auto 0; }',

    /* Toggle button */
    '.ep-toggle {',
    '  display: flex; align-items: center; justify-content: center; gap: 0.5rem;',
    '  width: 100%; padding: 0.75rem 1.25rem;',
    '  background: var(--card-bg); color: var(--text-dim);',
    '  border: 1px solid var(--card-border); border-radius: 12px;',
    '  font-size: 0.875rem; font-weight: 500; cursor: pointer;',
    '  transition: color 0.2s, border-color 0.2s;',
    '}',
    '.ep-toggle:hover { color: var(--text); border-color: var(--accent); }',
    '.ep-toggle svg { width: 16px; height: 16px; transition: transform 0.3s ease; }',
    '.ep-toggle[aria-expanded="true"] svg { transform: rotate(180deg); }',

    /* Collapsible body */
    '.ep-body {',
    '  max-height: 0; overflow: hidden; opacity: 0;',
    '  transition: max-height 0.5s cubic-bezier(0.4,0,0.2,1), opacity 0.35s ease;',
    '}',
    '.ep-body--open { max-height: 2000px; opacity: 1; }',

    /* Inner content */
    '.ep-inner { padding: 1.25rem 0 0; }',

    /* Section titles */
    '.ep-title {',
    '  font-size: 0.7rem; font-weight: 600; letter-spacing: 0.08em;',
    '  text-transform: uppercase; color: var(--text-dim2);',
    '  margin: 0 0 0.75rem; font-family: "JetBrains Mono", "Fira Code", monospace;',
    '}',

    /* ── Flow diagram ── */
    '.ep-flow {',
    '  display: flex; align-items: center; gap: 0;',
    '  overflow-x: auto; padding: 0.5rem 0 1rem;',
    '  -webkit-overflow-scrolling: touch;',
    '}',
    '.ep-flow-step {',
    '  flex: 0 0 auto; display: flex; flex-direction: column; align-items: center;',
    '  gap: 0.35rem; min-width: 5.5rem;',
    '}',
    '.ep-flow-box {',
    '  display: flex; flex-direction: column; align-items: center; justify-content: center;',
    '  width: 4.5rem; height: 3.5rem;',
    '  background: var(--card-bg); border: 1px solid var(--card-border);',
    '  border-radius: 8px;',
    '}',
    '.ep-flow-icon { font-size: 1.1rem; line-height: 1; }',
    '.ep-flow-label {',
    '  font-size: 0.65rem; color: var(--text-dim); text-align: center;',
    '  line-height: 1.2; max-width: 5.5rem;',
    '  font-family: "JetBrains Mono", "Fira Code", monospace;',
    '}',
    '.ep-flow-arrow {',
    '  flex: 0 0 auto; color: var(--accent); font-size: 1rem;',
    '  margin: 0 0.15rem; padding-bottom: 1.1rem;',
    '}',

    /* ── Opponent styles ── */
    '.ep-styles { margin-top: 1.25rem; }',
    '.ep-tabs {',
    '  display: flex; gap: 0.25rem; overflow-x: auto;',
    '  padding-bottom: 0.5rem; -webkit-overflow-scrolling: touch;',
    '}',
    '.ep-tab {',
    '  flex: 0 0 auto; padding: 0.4rem 0.75rem;',
    '  font-size: 0.7rem; font-weight: 500;',
    '  background: transparent; color: var(--text-dim);',
    '  border: 1px solid var(--card-border); border-radius: 6px;',
    '  cursor: pointer; transition: all 0.2s; white-space: nowrap;',
    '}',
    '.ep-tab:hover { color: var(--text); border-color: var(--accent); }',
    '.ep-tab--active {',
    '  background: var(--accent); color: #fff;',
    '  border-color: var(--accent);',
    '}',
    '.ep-tab--active:hover { color: #fff; }',
    '.ep-panel {',
    '  background: var(--card-bg); border: 1px solid var(--card-border);',
    '  border-radius: 8px; padding: 1rem; margin-top: 0.35rem;',
    '}',
    '.ep-panel-desc {',
    '  font-size: 0.8rem; color: var(--text-dim); line-height: 1.5;',
    '  margin: 0 0 0.65rem;',
    '}',
    '.ep-pills { display: flex; flex-wrap: wrap; gap: 0.35rem; }',
    '.ep-pill {',
    '  font-size: 0.65rem; padding: 0.2rem 0.55rem;',
    '  background: rgba(255,255,255,0.05); color: var(--text-dim);',
    '  border: 1px solid var(--card-border); border-radius: 999px;',
    '  font-family: "JetBrains Mono", "Fira Code", monospace;',
    '}',

    /* ── Scoring dimensions ── */
    '.ep-dims { margin-top: 1.25rem; }',
    '.ep-dim-list { list-style: none; margin: 0; padding: 0; }',
    '.ep-dim-item {',
    '  display: flex; align-items: baseline; gap: 0.5rem;',
    '  padding: 0.45rem 0; border-bottom: 1px solid var(--card-border);',
    '}',
    '.ep-dim-item:last-child { border-bottom: none; }',
    '.ep-dim-name {',
    '  font-size: 0.78rem; font-weight: 600; color: var(--text);',
    '  white-space: nowrap; flex: 0 0 auto;',
    '}',
    '.ep-dim-dot {',
    '  flex: 0 0 4px; width: 4px; height: 4px;',
    '  background: var(--accent); border-radius: 50%;',
    '  position: relative; top: -1px;',
    '}',
    '.ep-dim-desc {',
    '  font-size: 0.75rem; color: var(--text-dim); line-height: 1.4;',
    '}',

    /* Responsive */
    '@media (max-width: 480px) {',
    '  .ep-flow-box { width: 3.8rem; height: 3rem; }',
    '  .ep-flow-label { font-size: 0.58rem; max-width: 4.5rem; }',
    '  .ep-flow-arrow { font-size: 0.85rem; }',
    '  .ep-tab { font-size: 0.63rem; padding: 0.35rem 0.6rem; }',
    '}',
  ].join('\n');

  /* ── Helpers ───────────────────────────────────────────────────── */

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === 'className') node.className = attrs[k];
        else if (k === 'html') node.innerHTML = attrs[k];
        else if (k.slice(0, 2) === 'on') node.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
        else node.setAttribute(k, attrs[k]);
      });
    }
    if (typeof children === 'string') node.textContent = children;
    else if (Array.isArray(children)) children.forEach(function (c) { if (c) node.appendChild(c); });
    return node;
  }

  /* ── Build: Flow Diagram ──────────────────────────────────────── */

  function buildFlow() {
    var wrap = el('div', { className: 'ep-flow', role: 'img', 'aria-label': 'Engine processing flow: Your Message, Style Detection, Strategy Engine, Scoring, Response' });
    FLOW_STEPS.forEach(function (step, i) {
      wrap.appendChild(
        el('div', { className: 'ep-flow-step' }, [
          el('div', { className: 'ep-flow-box' }, [
            el('span', { className: 'ep-flow-icon', 'aria-hidden': 'true' }, step.icon),
          ]),
          el('span', { className: 'ep-flow-label' }, step.label),
        ])
      );
      if (i < FLOW_STEPS.length - 1) {
        wrap.appendChild(el('span', { className: 'ep-flow-arrow', 'aria-hidden': 'true', html: '&#x2192;' }));
      }
    });
    return el('div', null, [
      el('div', { className: 'ep-title' }, 'Engine Flow'),
      wrap,
    ]);
  }

  /* ── Build: Opponent Styles ───────────────────────────────────── */

  function buildStylePanel(idx) {
    var s = STYLES[idx];
    var pills = el('div', { className: 'ep-pills' });
    s.traits.forEach(function (t) { pills.appendChild(el('span', { className: 'ep-pill' }, t)); });
    return el('div', { className: 'ep-panel', role: 'tabpanel', id: 'ep-panel-' + s.id, 'aria-labelledby': 'ep-tab-' + s.id }, [
      el('p', { className: 'ep-panel-desc' }, s.desc),
      pills,
    ]);
  }

  function setActiveStyle(idx) {
    activeStyle = idx;
    var tabs = root.querySelectorAll('.ep-tab');
    tabs.forEach(function (t, i) {
      var isActive = i === idx;
      t.classList.toggle('ep-tab--active', isActive);
      t.setAttribute('aria-selected', isActive ? 'true' : 'false');
      t.setAttribute('tabindex', isActive ? '0' : '-1');
    });
    var panelContainer = root.querySelector('.ep-panel-container');
    if (panelContainer) {
      panelContainer.innerHTML = '';
      panelContainer.appendChild(buildStylePanel(idx));
    }
  }

  function buildStyles() {
    var tabs = el('div', { className: 'ep-tabs', role: 'tablist', 'aria-label': 'Negotiation styles' });
    STYLES.forEach(function (s, i) {
      var tab = el('button', {
        className: 'ep-tab' + (i === 0 ? ' ep-tab--active' : ''),
        role: 'tab',
        id: 'ep-tab-' + s.id,
        'aria-selected': i === 0 ? 'true' : 'false',
        'aria-controls': 'ep-panel-' + s.id,
        tabindex: i === 0 ? '0' : '-1',
        onClick: function () { setActiveStyle(i); },
      }, s.name);
      tabs.appendChild(tab);
    });

    /* Keyboard navigation for tabs */
    tabs.addEventListener('keydown', function (e) {
      var dir = 0;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') dir = 1;
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') dir = -1;
      if (dir) {
        e.preventDefault();
        var next = (activeStyle + dir + STYLES.length) % STYLES.length;
        setActiveStyle(next);
        root.querySelector('#ep-tab-' + STYLES[next].id).focus();
      }
    });

    var panelContainer = el('div', { className: 'ep-panel-container' }, [buildStylePanel(0)]);

    return el('div', { className: 'ep-styles' }, [
      el('div', { className: 'ep-title' }, '5 Opponent Styles'),
      tabs,
      panelContainer,
    ]);
  }

  /* ── Build: Scoring Dimensions ────────────────────────────────── */

  function buildDimensions() {
    var list = el('ul', { className: 'ep-dim-list' });
    DIMENSIONS.forEach(function (d) {
      list.appendChild(
        el('li', { className: 'ep-dim-item' }, [
          el('span', { className: 'ep-dim-name' }, d.name),
          el('span', { className: 'ep-dim-dot', 'aria-hidden': 'true' }),
          el('span', { className: 'ep-dim-desc' }, d.desc),
        ])
      );
    });
    return el('div', { className: 'ep-dims' }, [
      el('div', { className: 'ep-title' }, '6 Scoring Dimensions'),
      list,
    ]);
  }

  /* ── Toggle ────────────────────────────────────────────────────── */

  function toggle() {
    if (!root) return;
    expanded = !expanded;
    var btn = root.querySelector('.ep-toggle');
    var body = root.querySelector('.ep-body');
    btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    body.classList.toggle('ep-body--open', expanded);
  }

  /* ── Init ──────────────────────────────────────────────────────── */

  function init() {
    /* Inject CSS once */
    if (!document.getElementById('ep-styles')) {
      var style = document.createElement('style');
      style.id = 'ep-styles';
      style.textContent = CSS;
      document.head.appendChild(style);
    }

    /* Find injection point: after the form card that contains #landing-form */
    var form = document.getElementById('landing-form');
    if (!form) return;
    var formCard = form.closest('.form-card') || form.closest('.bg-navy-card') || form.parentElement;

    /* Don't double-init */
    if (document.getElementById('engine-peek')) return;

    /* Build the component */
    root = el('div', { className: 'ep-wrap', id: 'engine-peek' });

    var toggleBtn = el('button', {
      className: 'ep-toggle',
      'aria-expanded': 'false',
      'aria-controls': 'ep-body',
      onClick: toggle,
    }, [
      el('span', null, 'How does it work?'),
      el('span', { html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>' }),
    ]);

    var body = el('div', { className: 'ep-body', id: 'ep-body', role: 'region', 'aria-labelledby': 'ep-toggle-label' });
    var inner = el('div', { className: 'ep-inner' }, [
      buildFlow(),
      buildStyles(),
      buildDimensions(),
    ]);
    body.appendChild(inner);

    root.appendChild(toggleBtn);
    root.appendChild(body);

    /* Inject after the form card */
    formCard.parentNode.insertBefore(root, formCard.nextSibling);
  }

  /* ── Public API ────────────────────────────────────────────────── */

  window.DealSimEnginePeek = {
    init: init,
    toggle: toggle,
  };
})();
