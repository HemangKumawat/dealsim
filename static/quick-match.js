/* ==================================================================
   DealSim — Quick Match
   One-click random negotiation start. Injects a two-card hero
   above the existing form in #sec-landing.
   ================================================================== */
(function () {
  'use strict';

  var SCENARIOS = [
    { value: 'salary',        label: 'Salary Negotiation',       ctx: 'You received a job offer and want to negotiate a higher starting salary based on your experience and market research.' },
    { value: 'freelance',     label: 'Freelance Rate',           ctx: 'A new client wants to hire you for a project but is pushing back on your hourly rate.' },
    { value: 'rent',          label: 'Rent Negotiation',         ctx: 'Your lease is up for renewal and the landlord proposed a rent increase you want to negotiate down.' },
    { value: 'medical_bill',  label: 'Medical Bill Negotiation', ctx: 'You received a large medical bill and want to negotiate a reduced payment or payment plan.' },
    { value: 'car_buying',    label: 'Car Buying',               ctx: 'You are at a dealership negotiating the price of a used car listed above your budget.' },
    { value: 'scope_creep',   label: 'Scope Creep',              ctx: 'Your client keeps adding features outside the original agreement and you need to renegotiate terms.' },
    { value: 'raise',         label: 'Raise Request',            ctx: 'You have been in your role for over a year and want to ask your manager for a raise.' },
    { value: 'vendor',        label: 'Vendor Contract',          ctx: 'You are reviewing a vendor contract renewal and want better pricing or terms.' },
    { value: 'counter_offer', label: 'Counter Offer',            ctx: 'You received a counter offer from your current employer after getting an outside offer.' },
    { value: 'budget_request',label: 'Budget Request',           ctx: 'You need to convince leadership to approve additional budget for your team or project.' },
  ];

  var TARGET_DEFAULTS = {
    salary: 95000, freelance: 120, rent: 1200, medical_bill: 500,
    car_buying: 18000, scope_creep: 5000, raise: 10, vendor: 50000,
    counter_offer: 105000, budget_request: 25000,
  };

  function pickRandom() {
    return SCENARIOS[Math.floor(Math.random() * SCENARIOS.length)];
  }

  function buildCards() {
    var wrapper = document.createElement('div');
    wrapper.id = 'qm-cards';
    wrapper.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px;';

    // Quick Match card
    var qm = document.createElement('button');
    qm.type = 'button';
    qm.id = 'qm-start';
    qm.className = 'coral-glow';
    qm.className = 'quick-action-card coral-glow';
    qm.style.cssText = [
      'border-width:2px',
      'border-color:var(--accent)',
      'padding:24px 16px',
      'text-align:center',
      'cursor:pointer',
      'color:var(--text)',
      'position:relative',
      'overflow:hidden',
    ].join(';');
    qm.innerHTML =
      '<div style="font-size:2.5rem;margin-bottom:8px">&#x26A1;</div>' +
      '<div style="font-size:1.1rem;font-weight:700;margin-bottom:4px">Quick Match</div>' +
      '<div style="font-size:0.85rem;opacity:0.65;margin-bottom:16px">Jump into a random negotiation</div>' +
      '<div style="display:inline-block;background:var(--accent);color:#fff;padding:8px 28px;border-radius:10px;font-weight:600;font-size:0.9rem">Start</div>';
    // Only apply hover transforms on non-touch devices to avoid sticky states on mobile
    if (window.matchMedia && !window.matchMedia('(hover: none)').matches) {
      qm.onmouseenter = function () { qm.style.borderColor = 'var(--accent-light)'; qm.style.transform = 'translateY(-2px)'; };
      qm.onmouseleave = function () { qm.style.borderColor = 'var(--accent)'; qm.style.transform = 'none'; };
    }
    qm.onclick = function () { startQuickMatch(); };

    // Full Setup card
    var fs = document.createElement('button');
    fs.type = 'button';
    fs.className = 'quick-action-card';
    fs.style.cssText = [
      'padding:24px 16px',
      'text-align:center',
      'cursor:pointer',
      'color:var(--text)',
    ].join(';');
    fs.innerHTML =
      '<div style="font-size:2.5rem;margin-bottom:8px">&#x1F527;</div>' +
      '<div style="font-size:1.1rem;font-weight:700;margin-bottom:4px">Full Setup</div>' +
      '<div style="font-size:0.85rem;opacity:0.65;margin-bottom:16px">Choose scenario, difficulty, and context</div>' +
      '<div style="display:inline-block;border:1px solid var(--card-border);color:var(--text);padding:8px 28px;border-radius:10px;font-weight:600;font-size:0.9rem">Customize</div>';
    if (window.matchMedia && !window.matchMedia('(hover: none)').matches) {
      fs.onmouseenter = function () { fs.style.borderColor = 'var(--accent)'; fs.style.transform = 'translateY(-2px)'; };
      fs.onmouseleave = function () { fs.style.borderColor = 'var(--card-border)'; fs.style.transform = 'none'; };
    }
    fs.onclick = function () {
      var form = document.getElementById('landing-form');
      if (form) form.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    wrapper.appendChild(qm);
    wrapper.appendChild(fs);
    return wrapper;
  }

  function buildMatchingOverlay() {
    var overlay = document.createElement('div');
    overlay.id = 'qm-overlay';
    overlay.className = 'modal-overlay';
    overlay.style.cssText = [
      'display:none',
      'position:fixed',
      'inset:0',
      'z-index:9000',
      'align-items:center',
      'justify-content:center',
      'flex-direction:column',
      'gap:16px',
      'color:var(--text)',
      'font-family:inherit',
    ].join(';');
    overlay.innerHTML =
      '<div style="font-size:3rem" id="qm-overlay-emoji">&#x26A1;</div>' +
      '<div style="font-size:1.3rem;font-weight:700" id="qm-overlay-text">Matching you with...</div>' +
      '<div style="font-size:1rem;color:var(--accent);font-weight:600" id="qm-overlay-scenario"></div>';
    document.body.appendChild(overlay);
    return overlay;
  }

  function showOverlay(scenarioLabel) {
    var overlay = document.getElementById('qm-overlay') || buildMatchingOverlay();
    document.getElementById('qm-overlay-scenario').textContent = scenarioLabel;
    overlay.style.display = 'flex';
  }

  function hideOverlay() {
    var overlay = document.getElementById('qm-overlay');
    if (overlay) overlay.style.display = 'none';
  }

  function startQuickMatch() {
    var pick = pickRandom();

    // Fill the form fields
    var scenarioSelect = document.getElementById('scenario-type');
    var targetInput = document.getElementById('target-value');
    var contextArea = document.getElementById('context');

    if (!scenarioSelect || !targetInput || !contextArea) return;

    scenarioSelect.value = pick.value;
    targetInput.value = TARGET_DEFAULTS[pick.value] || 50000;
    contextArea.value = pick.ctx;

    // Set difficulty to medium
    // selectDiff is a global defined in index.html
    var mediumBtn = document.querySelector('.diff-btn[data-diff="medium"]');
    if (mediumBtn && typeof window.selectDiff === 'function') {
      window.selectDiff(mediumBtn);
    }

    // Show the matching overlay
    showOverlay(pick.label);

    // Submit after a brief delay
    setTimeout(function () {
      hideOverlay();
      var form = document.getElementById('landing-form');
      if (form) {
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      }
    }, 1000);
  }

  function init() {
    // Inject cards before the form card
    var landing = document.getElementById('sec-landing');
    if (!landing) return;

    var formCard = landing.querySelector('.form-card') || landing.querySelector('.bg-navy-card');
    if (!formCard) return;

    var cards = buildCards();
    formCard.parentNode.insertBefore(cards, formCard);

    // Build overlay ahead of time
    buildMatchingOverlay();

    // Responsive: stack on mobile
    var style = document.createElement('style');
    style.textContent =
      '@media(max-width:640px){#qm-cards{grid-template-columns:1fr !important;}}';
    document.head.appendChild(style);
  }

  // Auto-init when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Public API
  window.DealSimQuickMatch = {
    init: init,
    startQuickMatch: startQuickMatch,
  };
})();
