/**
 * DealSim Achievements Display
 *
 * Renders an achievement grid and shows toast notifications on unlock.
 * Pulls data from DealSimGamification, styles itself with CSS variables
 * from themes.css. No dependencies beyond the gamification module.
 */
(function () {
  'use strict';

  const STYLES_ID = 'dealsim-achievements-styles';
  const TOAST_DURATION = 3000;
  let toastTimeout = null;

  // ── Inject styles ───────────────────────────────────────────────────
  function injectStyles() {
    if (document.getElementById(STYLES_ID)) return;
    const style = document.createElement('style');
    style.id = STYLES_ID;
    style.textContent = `
      .ds-achievements-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
      }
      @media (max-width: 640px) {
        .ds-achievements-grid {
          grid-template-columns: repeat(2, 1fr);
        }
      }
      @media (max-width: 360px) {
        .ds-achievements-grid {
          grid-template-columns: 1fr;
        }
      }

      .ds-achievement-card {
        display: flex;
        align-items: center;
        gap: 10px;
        height: 80px;
        padding: 12px 14px;
        border-radius: 10px;
        border: 1px solid var(--card-border);
        background: var(--card-bg);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        position: relative;
        overflow: hidden;
      }

      .ds-achievement-card--unlocked {
        border-left: 3px solid var(--accent);
        opacity: 1;
      }
      .ds-achievement-card--unlocked:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
      }

      .ds-achievement-card--locked {
        opacity: 0.3;
        border: 1px dashed var(--card-border);
      }
      .ds-achievement-card--locked .ds-achievement-emoji {
        filter: grayscale(1);
      }

      .ds-achievement-emoji {
        font-size: 26px;
        flex-shrink: 0;
        line-height: 1;
      }

      .ds-achievement-info {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
      }

      .ds-achievement-title {
        font-size: 13px;
        font-weight: 600;
        color: var(--text);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .ds-achievement-sub {
        font-size: 11px;
        color: var(--text-dim);
      }

      /* Tooltip on hover for unlocked cards */
      .ds-achievement-card--unlocked .ds-achievement-tooltip {
        position: absolute;
        bottom: calc(100% + 6px);
        left: 50%;
        transform: translateX(-50%) translateY(4px);
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        color: var(--text);
        font-size: 11px;
        padding: 6px 10px;
        border-radius: 6px;
        white-space: nowrap;
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.15s ease, transform 0.15s ease;
        z-index: 10;
      }
      .ds-achievement-card--unlocked:hover .ds-achievement-tooltip {
        opacity: 1;
        transform: translateX(-50%) translateY(0);
      }

      /* Toast notification */
      .ds-achievement-toast {
        position: fixed;
        top: -60px;
        left: 50%;
        transform: translateX(-50%);
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 12px 20px;
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-left: 3px solid var(--accent);
        border-radius: 10px;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
        font-size: 14px;
        color: var(--text);
        z-index: 10000;
        transition: top 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
        white-space: nowrap;
      }
      .ds-achievement-toast--visible {
        top: 20px;
      }
      .ds-achievement-toast .ds-toast-emoji {
        font-size: 22px;
        line-height: 1;
      }
      .ds-achievement-toast .ds-toast-text {
        font-weight: 600;
      }
    `;
    document.head.appendChild(style);
  }

  // ── Render grid ─────────────────────────────────────────────────────
  function renderGrid(containerId) {
    injectStyles();
    const container = document.getElementById(containerId);
    if (!container) return;

    const achievements = getAchievements();
    container.innerHTML = '';

    const grid = document.createElement('div');
    grid.className = 'ds-achievements-grid';

    achievements.forEach(function (a) {
      const unlocked = !!a.unlockedAt;
      const card = document.createElement('div');
      card.className = 'ds-achievement-card '
        + (unlocked ? 'ds-achievement-card--unlocked' : 'ds-achievement-card--locked');

      const emoji = document.createElement('span');
      emoji.className = 'ds-achievement-emoji';
      emoji.textContent = a.emoji || '';

      const info = document.createElement('div');
      info.className = 'ds-achievement-info';

      const title = document.createElement('span');
      title.className = 'ds-achievement-title';
      title.textContent = a.title || '';

      const sub = document.createElement('span');
      sub.className = 'ds-achievement-sub';
      sub.textContent = unlocked ? formatDate(a.unlockedAt) : '???';

      info.appendChild(title);
      info.appendChild(sub);
      card.appendChild(emoji);
      card.appendChild(info);

      if (unlocked && a.description) {
        const tooltip = document.createElement('span');
        tooltip.className = 'ds-achievement-tooltip';
        tooltip.textContent = a.description;
        card.appendChild(tooltip);
      }

      grid.appendChild(card);
    });

    container.appendChild(grid);
  }

  // ── Toast notification ──────────────────────────────────────────────
  function showUnlockToast(achievement) {
    injectStyles();
    removeExistingToast();

    const toast = document.createElement('div');
    toast.className = 'ds-achievement-toast';
    toast.id = 'ds-achievement-toast';

    const emoji = document.createElement('span');
    emoji.className = 'ds-toast-emoji';
    emoji.textContent = achievement.emoji || '';

    const text = document.createElement('span');
    text.className = 'ds-toast-text';
    text.textContent = 'Achievement Unlocked: ' + (achievement.title || '');

    toast.appendChild(emoji);
    toast.appendChild(text);
    document.body.appendChild(toast);

    // Trigger slide-in on next frame
    requestAnimationFrame(function () {
      toast.classList.add('ds-achievement-toast--visible');
    });

    toastTimeout = setTimeout(function () {
      toast.classList.remove('ds-achievement-toast--visible');
      setTimeout(function () { removeExistingToast(); }, 350);
    }, TOAST_DURATION);
  }

  function removeExistingToast() {
    if (toastTimeout) { clearTimeout(toastTimeout); toastTimeout = null; }
    var existing = document.getElementById('ds-achievement-toast');
    if (existing) existing.remove();
  }

  // ── Helpers ─────────────────────────────────────────────────────────
  function getAchievements() {
    // Prefer getAllAchievements (returns all 12 with lock status) over getAchievements (unlocked only)
    if (window.DealSimGamification && typeof window.DealSimGamification.getAllAchievements === 'function') {
      return window.DealSimGamification.getAllAchievements();
    }
    if (window.DealSimGamification && typeof window.DealSimGamification.getAchievements === 'function') {
      return window.DealSimGamification.getAchievements();
    }
    return [];
  }

  function formatDate(dateVal) {
    if (!dateVal) return '';
    var d = dateVal instanceof Date ? dateVal : new Date(dateVal);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  // ── Init ────────────────────────────────────────────────────────────
  var initialized = false;

  function init() {
    if (initialized) return;
    initialized = true;
    injectStyles();
    if (window.DealSimGamification && typeof window.DealSimGamification.onAchievement === 'function') {
      window.DealSimGamification.onAchievement(function (achievement) {
        showUnlockToast(achievement);
        document.querySelectorAll('[data-achievements-grid]').forEach(function (el) {
          renderGrid(el.id);
        });
      });
    }
  }

  // ── Public API ──────────────────────────────────────────────────────
  window.DealSimAchievements = {
    renderGrid: renderGrid,
    showUnlockToast: showUnlockToast,
    init: init,
  };
})();
