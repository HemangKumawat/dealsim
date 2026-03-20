/**
 * DealSim Analytics — Privacy-First Event Tracking
 *
 * Design principles:
 * - No cookies, no fingerprinting, no PII collection
 * - All data aggregated server-side, no individual tracking
 * - GDPR/ePrivacy compliant by architecture (not by consent banner)
 * - Graceful degradation: if analytics fail, app is unaffected
 *
 * Backend: sends events to /api/analytics (simple append-only log)
 * Alternative: swap sendEvent() body for Plausible/Umami/PostHog
 *
 * Units: durations in seconds, scores 0-100, counts integer
 */
(function () {
  'use strict';

  // ── Configuration ───────────────────────────────────────────────────
  const ENDPOINT   = '/api/analytics';
  const BATCH_SIZE = 5;           // flush after N events
  const FLUSH_MS   = 10000;       // or after 10s, whichever comes first
  const SESSION_KEY = 'dealsim_analytics_sid';

  // ── Session ID (ephemeral, not a tracking cookie) ──────────────────
  // Random ID per browser tab. Not persisted across tabs or visits.
  // Purpose: group events within a single visit for funnel analysis.
  const sessionId = crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2) + Date.now().toString(36);

  // ── Event Queue & Batching ─────────────────────────────────────────
  let queue = [];
  let flushTimer = null;

  function enqueue(event) {
    queue.push(event);
    if (queue.length >= BATCH_SIZE) {
      flush();
    } else if (!flushTimer) {
      flushTimer = setTimeout(flush, FLUSH_MS);
    }
  }

  function flush() {
    if (flushTimer) { clearTimeout(flushTimer); flushTimer = null; }
    if (queue.length === 0) return;

    const batch = queue.splice(0);
    const payload = JSON.stringify({ events: batch });

    // Use sendBeacon for reliability on page unload; fall back to fetch
    if (navigator.sendBeacon) {
      navigator.sendBeacon(ENDPOINT, new Blob([payload], { type: 'application/json' }));
    } else {
      fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
        keepalive: true,
      }).catch(function () { /* silent — analytics must never break the app */ });
    }
  }

  // Flush on page unload
  window.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') flush();
  });
  window.addEventListener('pagehide', flush);

  // ── Core: trackEvent ──────────────────────────────────────────────
  /**
   * @param {string} name   - Event name (snake_case)
   * @param {Object} props  - Event properties (no PII allowed)
   */
  function trackEvent(name, props) {
    try {
      enqueue({
        event: name,
        props: props || {},
        sid: sessionId,
        ts: new Date().toISOString(),
        // Minimal context — no IP, no UA string, no screen size
        path: window.location.pathname,
        referrer: document.referrer ? new URL(document.referrer).hostname : null,
        theme: document.documentElement.dataset.theme || 'arena',
      });
    } catch (_) { /* never throw from analytics */ }
  }

  // ── Timing Helpers ────────────────────────────────────────────────
  const timers = {};

  function startTimer(name) {
    timers[name] = performance.now();
  }

  function endTimer(name) {
    if (!timers[name]) return null;
    const elapsed = Math.round((performance.now() - timers[name]) / 1000);
    delete timers[name];
    return elapsed;
  }

  // ── Funnel Events ─────────────────────────────────────────────────
  // Each function below maps to one step in the conversion funnel:
  //
  //   page_view → scenario_configured → negotiation_started →
  //   message_sent (repeated) → negotiation_completed →
  //   score_viewed → feedback_submitted → negotiation_repeated

  const Analytics = {

    /** Step 0: Page loaded */
    pageView: function () {
      trackEvent('page_view', {
        landing: true,
      });
    },

    /** Step 1: User selects/configures a scenario */
    scenarioConfigured: function (opts) {
      // opts: { scenario, difficulty, customContext }
      trackEvent('scenario_configured', {
        scenario: opts.scenario || 'unknown',
        difficulty: opts.difficulty || 'medium',
        has_custom_context: !!opts.customContext,
      });
    },

    /** Step 2: Negotiation session created (API returned sessionId) */
    negotiationStarted: function (opts) {
      // opts: { scenario, difficulty, sessionId }
      startTimer('negotiation');
      trackEvent('negotiation_started', {
        scenario: opts.scenario || 'unknown',
        difficulty: opts.difficulty || 'medium',
      });
    },

    /** Step 3: Each message sent (sampled — track count, not content) */
    messageSent: function (roundNumber) {
      trackEvent('message_sent', {
        round: roundNumber,
      });
    },

    /** Step 4: Negotiation scored / completed */
    negotiationCompleted: function (opts) {
      // opts: { scenario, overallScore, outcome, dimensions, roundCount }
      var duration = endTimer('negotiation');
      trackEvent('negotiation_completed', {
        scenario: opts.scenario || 'unknown',
        overall_score: opts.overallScore || 0,
        outcome: opts.outcome || 'unknown', // deal_reached | no_deal
        round_count: opts.roundCount || 0,
        duration_seconds: duration,
        // Dimension scores (aggregated, no PII)
        dim_scores: opts.dimensions || {},
      });
    },

    /** Step 5: Scorecard viewed (auto-fires on render) */
    scoreViewed: function (score) {
      trackEvent('score_viewed', {
        overall_score: score,
      });
    },

    /** Step 6: Feedback submitted */
    feedbackSubmitted: function (opts) {
      // opts: { rating, hasComment }
      // Note: comment TEXT is never sent to analytics — only boolean
      trackEvent('feedback_submitted', {
        rating: opts.rating || 0,
        has_comment: !!opts.hasComment,
      });
    },

    /** Step 7: User clicks "Try Again" or starts another scenario */
    negotiationRepeated: function (opts) {
      trackEvent('negotiation_repeated', {
        same_scenario: !!opts.sameScenario,
      });
    },

    // ── Feature-Specific Events ───────────────────────────────────

    /** Theme switched */
    themeSwitched: function (fromTheme, toTheme) {
      trackEvent('theme_switched', {
        from: fromTheme,
        to: toTheme,
      });
    },

    /** Achievement unlocked */
    achievementUnlocked: function (achievementId) {
      trackEvent('achievement_unlocked', {
        achievement: achievementId,
      });
    },

    /** Level up */
    levelUp: function (oldLevel, newLevel) {
      trackEvent('level_up', {
        from_level: oldLevel,
        to_level: newLevel,
      });
    },

    /** Demo mode started */
    demoStarted: function () {
      trackEvent('demo_started', {});
    },

    /** Demo completed */
    demoCompleted: function (score) {
      trackEvent('demo_completed', {
        overall_score: score || 0,
      });
    },

    /** Playbook generated */
    playbookGenerated: function () {
      trackEvent('playbook_generated', {});
    },

    /** Debrief viewed */
    debriefViewed: function () {
      trackEvent('debrief_viewed', {});
    },

    /** Offer analyzer used */
    offerAnalyzerUsed: function () {
      trackEvent('offer_analyzer_used', {});
    },

    /** Negotiation audit used */
    auditUsed: function () {
      trackEvent('audit_used', {});
    },

    /** Daily challenge started */
    dailyChallengeStarted: function () {
      trackEvent('daily_challenge_started', {});
    },

    /** Score shared (social) */
    scoreShared: function (method) {
      trackEvent('score_shared', {
        method: method || 'clipboard', // clipboard | native_share
      });
    },

    /** Navigation: section viewed */
    sectionViewed: function (sectionId) {
      trackEvent('section_viewed', {
        section: sectionId,
      });
    },

    /** Error encountered (for reliability monitoring) */
    errorOccurred: function (context, message) {
      trackEvent('error_occurred', {
        context: context,
        // Sanitize: only first 100 chars, no stack traces
        message: (message || '').slice(0, 100),
      });
    },

    // ── Utility ───────────────────────────────────────────────────

    /** Force flush (call on page unload or critical events) */
    flush: flush,

    /** Raw trackEvent for custom one-offs */
    track: trackEvent,
  };

  // ── Auto-wire: Gamification Events ────────────────────────────────
  // Hook into DealSimGamification if present
  function wireGamification() {
    if (!window.DealSimGamification) return;

    window.DealSimGamification.onAchievement(function (achievement) {
      Analytics.achievementUnlocked(achievement.id);
    });

    window.DealSimGamification.onLevelUp(function (data) {
      Analytics.levelUp(data.oldLevel, data.newLevel);
    });
  }

  // Wire up after DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      wireGamification();
      Analytics.pageView();
    });
  } else {
    wireGamification();
    Analytics.pageView();
  }

  // ── Expose ────────────────────────────────────────────────────────
  window.DealSimAnalytics = Analytics;

})();
