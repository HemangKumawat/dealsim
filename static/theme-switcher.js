/**
 * DealSim Theme Switcher
 *
 * Quiet, integrated theme switching. Shows only the current theme icon
 * in the nav bar. Expands on click to reveal alternatives. No floating,
 * no animations that scream for attention. Just a tool that's there when
 * you want it.
 */
(function () {
  'use strict';

  // ── Theme palettes ──────────────────────────────────────────────────
  // Synced with themes.css — these MUST match the CSS custom property values
  const PALETTES = {
    arena: {
      navy:  { DEFAULT: '#0f0f23', light: '#1a1a2e', dark: '#0f0f23', card: '#1a1a2e' },
      coral: { DEFAULT: '#f95c5c', dark: '#e04444', light: '#ff7a7a' },
      slate: { chat: '#2a2d6b' },
    },
    coach: {
      navy:  { DEFAULT: '#1a1147', light: '#2d1b69', dark: '#1a1147', card: '#221758' },
      coral: { DEFAULT: '#f5a623', dark: '#d48f1a', light: '#ffc04d' },
      slate: { chat: '#2d1b69' },
    },
    lab: {
      navy:  { DEFAULT: '#0d1117', light: '#161b22', dark: '#0d1117', card: '#161b22' },
      coral: { DEFAULT: '#58a6ff', dark: '#388bfd', light: '#79c0ff' },
      slate: { chat: '#1c2128' },
    },
  };

  const THEME_META = {
    arena: { emoji: '⚔️', label: 'Arena' },
    coach: { emoji: '🧠', label: 'Coach' },
    lab:   { emoji: '🔬', label: 'Lab' },
  };

  const VALID_THEMES = Object.keys(PALETTES);
  const STORAGE_KEY  = 'dealsim_theme';

  // ── CSS custom properties fallback ──────────────────────────────────
  function applyCustomProperties(theme) {
    const p = PALETTES[theme];
    const root = document.documentElement.style;
    root.setProperty('--navy',       p.navy.DEFAULT);
    root.setProperty('--navy-light', p.navy.light);
    root.setProperty('--navy-dark',  p.navy.dark);
    root.setProperty('--navy-card',  p.navy.card);
    root.setProperty('--coral',       p.coral.DEFAULT);
    root.setProperty('--coral-dark',  p.coral.dark);
    root.setProperty('--coral-light', p.coral.light);
    root.setProperty('--slate-chat',  p.slate.chat);
  }

  // ── Tailwind CDN color override ─────────────────────────────────────
  function updateTailwindConfig(theme) {
    const p = PALETTES[theme];
    applyCustomProperties(theme);
    try {
      if (window.tailwind && window.tailwind.config) {
        window.tailwind.config.theme.extend.colors = {
          navy: p.navy,
          coral: p.coral,
          slate: p.slate,
        };
      }
    } catch (e) { /* Tailwind CDN may not support dynamic reconfig */ }
  }

  // ── Background effects ──────────────────────────────────────────────
  const EFFECTS_ID = 'dealsim-theme-effects';

  function clearEffects() {
    const el = document.getElementById(EFFECTS_ID);
    if (el) el.remove();
  }

  function createArenaEffects() {
    clearEffects();
    const container = document.createElement('div');
    container.id = EFFECTS_ID;
    container.setAttribute('aria-hidden', 'true');
    Object.assign(container.style, {
      position: 'fixed', inset: '0', pointerEvents: 'none', zIndex: '0', overflow: 'hidden',
    });

    // Subtle grid
    const grid = document.createElement('div');
    Object.assign(grid.style, {
      position: 'absolute', inset: '0', opacity: '0.03',
      backgroundImage:
        'linear-gradient(rgba(249,92,92,.3) 1px, transparent 1px),' +
        'linear-gradient(90deg, rgba(249,92,92,.3) 1px, transparent 1px)',
      backgroundSize: '60px 60px',
    });
    container.appendChild(grid);

    // Minimal particles (8 instead of 20 — enough atmosphere, not a rave)
    for (let i = 0; i < 8; i++) {
      const dot = document.createElement('div');
      const size = 2 + Math.random() * 2;
      Object.assign(dot.style, {
        position: 'absolute',
        width: size + 'px', height: size + 'px',
        borderRadius: '50%',
        background: 'rgba(249, 92, 92, 0.15)',
        left: Math.random() * 100 + '%',
        top:  Math.random() * 100 + '%',
        animation: `dealsim-float ${8 + Math.random() * 10}s ease-in-out ${Math.random() * 5}s infinite alternate`,
      });
      container.appendChild(dot);
    }

    document.body.appendChild(container);
    ensureKeyframes();
  }

  function createCoachEffects() {
    clearEffects();
    const container = document.createElement('div');
    container.id = EFFECTS_ID;
    container.setAttribute('aria-hidden', 'true');
    Object.assign(container.style, {
      position: 'fixed', inset: '0', pointerEvents: 'none', zIndex: '0',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    });

    container.innerHTML = `
      <svg viewBox="0 0 400 400" style="width:60vmin;height:60vmin;opacity:0.04">
        <defs>
          <filter id="dealsim-blob-goo"><feGaussianBlur in="SourceGraphic" stdDeviation="12" /></filter>
        </defs>
        <g filter="url(#dealsim-blob-goo)">
          <circle cx="200" cy="200" r="120" fill="#7c5cff">
            <animate attributeName="cx" values="200;220;180;200" dur="14s" repeatCount="indefinite" />
            <animate attributeName="cy" values="200;180;220;200" dur="16s" repeatCount="indefinite" />
            <animate attributeName="r"  values="120;140;110;120" dur="12s" repeatCount="indefinite" />
          </circle>
          <circle cx="240" cy="180" r="80" fill="#f5a623" opacity="0.6">
            <animate attributeName="cx" values="240;200;260;240" dur="15s" repeatCount="indefinite" />
            <animate attributeName="cy" values="180;220;170;180" dur="13s" repeatCount="indefinite" />
          </circle>
        </g>
      </svg>`;

    document.body.appendChild(container);
  }

  function createLabEffects() {
    clearEffects();
  }

  const effectsMap = { arena: createArenaEffects, coach: createCoachEffects, lab: createLabEffects };

  function ensureKeyframes() {
    if (document.getElementById('dealsim-keyframes')) return;
    const style = document.createElement('style');
    style.id = 'dealsim-keyframes';
    style.textContent = `
      @keyframes dealsim-float {
        0%   { transform: translateY(0) translateX(0); opacity: 0.15; }
        100% { transform: translateY(-30px) translateX(15px); opacity: 0.35; }
      }
    `;
    document.head.appendChild(style);
  }

  // ── Theme Switcher UI (nav-integrated, minimal) ─────────────────────
  function injectSwitcherStyles() {
    if (document.getElementById('dealsim-switcher-styles')) return;
    const style = document.createElement('style');
    style.id = 'dealsim-switcher-styles';
    style.textContent = `
      .theme-toggle {
        position: relative;
        display: inline-flex;
        align-items: center;
      }
      .theme-toggle-btn {
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 4px 10px;
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 8px;
        background: rgba(255,255,255,0.04);
        color: rgba(255,255,255,0.7);
        font-size: 13px;
        cursor: pointer;
        transition: border-color 0.2s, background 0.2s;
      }
      .theme-toggle-btn:hover {
        border-color: rgba(255,255,255,0.25);
        background: rgba(255,255,255,0.07);
      }
      .theme-toggle-btn .theme-emoji {
        font-size: 14px;
        line-height: 1;
      }
      .theme-toggle-btn .theme-label {
        font-size: 12px;
        font-weight: 500;
      }
      .theme-dropdown {
        position: absolute;
        top: calc(100% + 6px);
        right: 0;
        background: rgba(0,0,0,0.85);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 4px;
        min-width: 140px;
        opacity: 0;
        transform: translateY(-4px);
        pointer-events: none;
        transition: opacity 0.15s ease, transform 0.15s ease;
        z-index: 1000;
      }
      .theme-dropdown.open {
        opacity: 1;
        transform: translateY(0);
        pointer-events: auto;
      }
      .theme-dropdown button {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 100%;
        padding: 8px 12px;
        border: none;
        background: transparent;
        color: rgba(255,255,255,0.7);
        font-size: 13px;
        cursor: pointer;
        border-radius: 6px;
        transition: background 0.15s;
        text-align: left;
      }
      .theme-dropdown button:hover {
        background: rgba(255,255,255,0.08);
        color: #fff;
      }
      .theme-dropdown button.current {
        background: rgba(255,255,255,0.06);
        color: #fff;
      }
      .theme-dropdown button .check {
        margin-left: auto;
        opacity: 0;
        font-size: 12px;
      }
      .theme-dropdown button.current .check {
        opacity: 0.6;
      }
    `;
    document.head.appendChild(style);
  }

  function createSwitcherUI(activeTheme) {
    // Prevent duplicate switcher creation
    if (document.getElementById('theme-toggle')) return;

    injectSwitcherStyles();
    ensureKeyframes();

    const meta = THEME_META[activeTheme];

    // Find the nav bar and insert before the last element
    const navLinks = document.getElementById('nav-links');
    if (!navLinks) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'theme-toggle';
    wrapper.id = 'theme-toggle';

    // The button: shows current theme only
    const btn = document.createElement('button');
    btn.className = 'theme-toggle-btn';
    btn.id = 'theme-toggle-btn';
    btn.setAttribute('aria-label', 'Change theme');
    btn.setAttribute('aria-expanded', 'false');
    btn.innerHTML = `<span class="theme-emoji">${meta.emoji}</span><span class="theme-label">${meta.label}</span>`;
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const dropdown = document.getElementById('theme-dropdown');
      const isOpen = dropdown.classList.contains('open');
      dropdown.classList.toggle('open');
      btn.setAttribute('aria-expanded', !isOpen);
    });

    // Dropdown with all themes
    const dropdown = document.createElement('div');
    dropdown.className = 'theme-dropdown';
    dropdown.id = 'theme-dropdown';

    VALID_THEMES.forEach((theme) => {
      const opt = document.createElement('button');
      const m = THEME_META[theme];
      opt.dataset.theme = theme;
      if (theme === activeTheme) opt.classList.add('current');
      opt.innerHTML = `<span>${m.emoji}</span><span>${m.label}</span><span class="check">✓</span>`;
      opt.addEventListener('click', () => {
        switchTheme(theme);
        dropdown.classList.remove('open');
        btn.setAttribute('aria-expanded', 'false');
      });
      dropdown.appendChild(opt);
    });

    wrapper.appendChild(btn);
    wrapper.appendChild(dropdown);
    navLinks.appendChild(wrapper);

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
      if (!wrapper.contains(e.target)) {
        dropdown.classList.remove('open');
        btn.setAttribute('aria-expanded', 'false');
      }
    });
  }

  function updateSwitcherUI(theme) {
    const btn = document.getElementById('theme-toggle-btn');
    if (!btn) return;
    const meta = THEME_META[theme];
    btn.innerHTML = `<span class="theme-emoji">${meta.emoji}</span><span class="theme-label">${meta.label}</span>`;

    document.querySelectorAll('#theme-dropdown button').forEach((opt) => {
      opt.classList.toggle('current', opt.dataset.theme === theme);
    });
  }

  // ── Core: switchTheme ───────────────────────────────────────────────
  let currentTheme = 'arena';

  function switchTheme(themeName) {
    if (!VALID_THEMES.includes(themeName) || themeName === currentTheme) return;

    const scrollY = window.scrollY;

    // Enable smooth transitions during theme switch
    document.documentElement.classList.add('theme-transition');

    // Apply theme
    document.documentElement.dataset.theme = themeName;
    currentTheme = themeName;
    try { localStorage.setItem(STORAGE_KEY, themeName); } catch (_) { /* quota or private browsing */ }

    // Colors
    updateTailwindConfig(themeName);

    // Update the nav button to show new theme
    updateSwitcherUI(themeName);

    // Background effects
    effectsMap[themeName]();

    // Restore scroll position
    window.scrollTo(0, scrollY);

    // Remove transition class after animation completes to avoid interfering with other transitions
    setTimeout(() => {
      document.documentElement.classList.remove('theme-transition');
    }, 600);
  }

  // ── Core: initThemeSystem ───────────────────────────────────────────
  function initThemeSystem() {
    let saved; try { saved = localStorage.getItem(STORAGE_KEY); } catch (_) { saved = null; }
    currentTheme = VALID_THEMES.includes(saved) ? saved : 'arena';

    // Apply immediately (no transition on load)
    document.documentElement.dataset.theme = currentTheme;
    updateTailwindConfig(currentTheme);
    effectsMap[currentTheme]();
    createSwitcherUI(currentTheme);
  }

  // ── Bootstrap ───────────────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initThemeSystem);
  } else {
    initThemeSystem();
  }

  // Expose public API
  window.DealSimThemes = {
    init: initThemeSystem,
    switchTheme: switchTheme,
    get currentTheme() { return currentTheme; },
  };
})();
