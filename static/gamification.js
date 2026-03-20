/**
 * DealSim Gamification Engine
 *
 * Tracks user progress, XP, levels, streaks, and achievements.
 * All data persisted in localStorage under key "dealsim_profile".
 *
 * Public API exposed via window.DealSimGamification.
 */
(function () {
  'use strict';

  const STORAGE_KEY = 'dealsim_profile';
  const TOTAL_SCENARIOS = 10;

  // ── Achievement Definitions ──────────────────────────────────────────

  const ACHIEVEMENT_DEFS = {
    first_blood:          { title: 'First Blood',          emoji: '🎯', description: 'Complete your first negotiation' },
    streak_3:             { title: '3-Day Streak',         emoji: '🔥', description: 'Negotiate 3 days in a row' },
    streak_7:             { title: 'Weekly Warrior',       emoji: '⚡', description: 'Negotiate 7 days in a row' },
    streak_30:            { title: 'Iron Will',            emoji: '🏆', description: '30-day negotiation streak' },
    high_roller:          { title: 'High Roller',          emoji: '💎', description: 'Score 90 or above in a session' },
    perfect_game:         { title: 'Flawless Victory',     emoji: '👑', description: 'Score a perfect 100' },
    diversified:          { title: 'Diversified',          emoji: '🌍', description: 'Play 5 different scenarios' },
    all_scenarios:        { title: 'Renaissance Negotiator', emoji: '🎓', description: 'Play all 10 scenarios' },
    level_5:              { title: 'Rising Star',          emoji: '⭐', description: 'Reach Level 5' },
    level_10:             { title: 'Master Class',         emoji: '🌟', description: 'Reach Level 10' },
    comeback_kid:         { title: 'Comeback Kid',         emoji: '🔄', description: 'Score 70+ right after scoring below 30' },
    negotiation_veteran:  { title: 'Negotiation Veteran',  emoji: '🎖️', description: 'Complete 50 negotiations' },
  };

  // ── Event System ─────────────────────────────────────────────────────

  const listeners = { levelUp: [], achievement: [] };
  let newlyUnlocked = []; // Achievements unlocked during the current recordSession call

  function emit(event, data) {
    (listeners[event] || []).forEach(function (cb) { cb(data); });
  }

  // ── Profile Helpers ──────────────────────────────────────────────────

  function defaultProfile() {
    return {
      xp: 0,
      level: 1,
      streak: 0,
      lastPlayDate: null,
      totalSessions: 0,
      wins: 0,
      losses: 0,
      bestScore: 0,
      scenariosPlayed: {},
      dimensionTotals: {},
      achievements: [],
      createdAt: null,
    };
  }

  function loadProfile() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        var parsed = JSON.parse(raw);
        // Reject prototype pollution keys
        delete parsed.__proto__;
        delete parsed.constructor;
        delete parsed.prototype;
        // Merge with defaults so new fields are always present
        var profile = Object.assign(defaultProfile(), parsed);
        // Type-validate critical fields
        if (typeof profile.xp !== 'number') profile.xp = 0;
        if (typeof profile.level !== 'number') profile.level = 1;
        if (typeof profile.totalSessions !== 'number') profile.totalSessions = 0;
        if (typeof profile.wins !== 'number') profile.wins = 0;
        if (typeof profile.streak !== 'number') profile.streak = 0;
        if (!Array.isArray(profile.achievements)) profile.achievements = [];
        return profile;
      }
    } catch (_) { /* corrupted data — start fresh */ }
    return defaultProfile();
  }

  function saveProfile(profile) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(profile)); } catch (_) { /* quota or private browsing */ }
  }

  // ── Leveling Math ────────────────────────────────────────────────────
  // Level = floor(sqrt(totalXP / 100)) + 1
  // XP thresholds: L2 = 100, L3 = 400, L5 = 1600, L10 = 8100

  function levelFromXP(xp) {
    return Math.floor(Math.sqrt(xp / 100)) + 1;
  }

  function xpForLevel(level) {
    // XP required to first reach this level: (level - 1)^2 * 100
    return (level - 1) * (level - 1) * 100;
  }

  function xpToNextLevel(xp) {
    var currentLevel = levelFromXP(xp);
    var nextThreshold = xpForLevel(currentLevel + 1);
    return nextThreshold - xp;
  }

  function xpProgress(xp) {
    var currentLevel = levelFromXP(xp);
    var currentThreshold = xpForLevel(currentLevel);
    var nextThreshold = xpForLevel(currentLevel + 1);
    var range = nextThreshold - currentThreshold;
    if (range <= 0) return 1;
    return (xp - currentThreshold) / range;
  }

  // ── Streak Logic ─────────────────────────────────────────────────────

  function todayISO() {
    return new Date().toISOString().slice(0, 10);
  }

  function updateStreak(profile) {
    var today = todayISO();
    if (profile.lastPlayDate === today) {
      // Already played today — no change
      return;
    }
    if (profile.lastPlayDate) {
      var last = new Date(profile.lastPlayDate);
      var now = new Date(today);
      var diffDays = Math.round((now - last) / (1000 * 60 * 60 * 24));
      if (diffDays === 1) {
        profile.streak += 1;
      } else {
        // Gap of 2+ days — reset to 1 (today counts as day 1)
        profile.streak = 1;
      }
    } else {
      // First ever session
      profile.streak = 1;
    }
    profile.lastPlayDate = today;
  }

  // ── Dimension Tracking ───────────────────────────────────────────────

  function recordDimensions(profile, dimensions) {
    // dimensions: { "Opening Strategy": 80, "Anchoring": 65, ... }
    if (!dimensions || typeof dimensions !== 'object') return;
    Object.keys(dimensions).forEach(function (key) {
      if (!profile.dimensionTotals[key]) {
        profile.dimensionTotals[key] = [];
      }
      profile.dimensionTotals[key].push(dimensions[key]);
    });
  }

  // ── Achievement Checker ──────────────────────────────────────────────

  function hasAchievement(profile, id) {
    return profile.achievements.some(function (a) { return a.id === id; });
  }

  function unlock(profile, id) {
    if (hasAchievement(profile, id)) return;
    var def = ACHIEVEMENT_DEFS[id];
    if (!def) return;
    var entry = {
      id: id,
      title: def.title,
      description: def.description,
      emoji: def.emoji,
      unlockedAt: new Date().toISOString(),
    };
    profile.achievements.push(entry);
    newlyUnlocked.push(entry);
    emit('achievement', entry);
  }

  function checkAchievements(profile, score, previousScore) {
    // first_blood — first negotiation
    if (profile.totalSessions >= 1) unlock(profile, 'first_blood');

    // Streak achievements
    if (profile.streak >= 3) unlock(profile, 'streak_3');
    if (profile.streak >= 7) unlock(profile, 'streak_7');
    if (profile.streak >= 30) unlock(profile, 'streak_30');

    // Score-based
    if (score >= 90) unlock(profile, 'high_roller');
    if (score >= 100) unlock(profile, 'perfect_game');

    // Scenario diversity
    var scenarioCount = Object.keys(profile.scenariosPlayed).length;
    if (scenarioCount >= 5) unlock(profile, 'diversified');
    if (scenarioCount >= TOTAL_SCENARIOS) unlock(profile, 'all_scenarios');

    // Level-based
    if (profile.level >= 5) unlock(profile, 'level_5');
    if (profile.level >= 10) unlock(profile, 'level_10');

    // Comeback kid — 70+ after a sub-30 score
    if (previousScore !== null && previousScore < 30 && score >= 70) {
      unlock(profile, 'comeback_kid');
    }

    // Veteran
    if (profile.totalSessions >= 50) unlock(profile, 'negotiation_veteran');
  }

  // ── Core: Record Session ─────────────────────────────────────────────

  function recordSession(scoreData) {
    // scoreData = { score: Number, scenario: String, dimensions: Object }
    if (!scoreData || typeof scoreData.score !== 'number') return;

    var profile = loadProfile();
    var score = scoreData.score;
    var previousScore = profile.lastScore != null ? profile.lastScore : null;
    newlyUnlocked = [];

    // First session timestamp
    if (!profile.createdAt) {
      profile.createdAt = new Date().toISOString();
    }

    // Update streak before anything else
    updateStreak(profile);

    // Session counting
    profile.totalSessions += 1;
    if (score >= 60) {
      profile.wins += 1;
    } else {
      profile.losses += 1;
    }

    // Scenario tracking
    if (scoreData.scenario) {
      var key = scoreData.scenario;
      profile.scenariosPlayed[key] = (profile.scenariosPlayed[key] || 0) + 1;
    }

    // Dimension tracking
    recordDimensions(profile, scoreData.dimensions);

    // ── XP Calculation ───────────────────────────────────────────────
    var earnedXP = score * 2;

    // Bonus: new personal best
    var isNewBest = score > profile.bestScore;
    if (isNewBest) {
      earnedXP += 100;
      profile.bestScore = score;
    }

    // Bonus: streak day (streak >= 2 means this is a consecutive day)
    if (profile.streak >= 2) {
      earnedXP += 25;
    }

    // Note: daily challenge bonus (+50) is not applied here automatically.
    // The caller can add it by adjusting scoreData.score or via a separate mechanism.

    var oldLevel = profile.level;
    profile.xp += earnedXP;
    profile.level = levelFromXP(profile.xp);

    // Level-up event
    if (profile.level > oldLevel) {
      emit('levelUp', { oldLevel: oldLevel, newLevel: profile.level, totalXP: profile.xp });
    }

    // Check achievements
    checkAchievements(profile, score, previousScore);

    // Persist last score for cross-session comeback_kid detection
    profile.lastScore = score;
    saveProfile(profile);

    return {
      earnedXP: earnedXP,
      newLevel: profile.level > oldLevel ? profile.level : null,
      isNewBest: isNewBest,
      newAchievements: newlyUnlocked.slice(),
    };
  }

  // ── Public API ───────────────────────────────────────────────────────

  window.DealSimGamification = {

    /** Returns the full profile object (a copy). */
    getProfile: function () {
      return loadProfile();
    },

    /**
     * Record a completed negotiation session.
     * @param {Object} scoreData - { score: Number, scenario: String, dimensions: { dimName: score, ... } }
     * @returns {Object} Summary: { earnedXP, newLevel, isNewBest, newAchievements }
     */
    recordSession: recordSession,

    /** Level info: { level, xp, xpToNext, xpProgress } */
    getLevel: function () {
      var p = loadProfile();
      return {
        level: p.level,
        xp: p.xp,
        xpToNext: xpToNextLevel(p.xp),
        xpProgress: xpProgress(p.xp),
      };
    },

    /** Streak info: { current, isActive } — active means played today or yesterday */
    getStreak: function () {
      var p = loadProfile();
      var today = todayISO();
      var isActive = false;
      if (p.lastPlayDate) {
        var diff = Math.round((new Date(today) - new Date(p.lastPlayDate)) / (1000 * 60 * 60 * 24));
        isActive = diff <= 1;
      }
      return { current: p.streak, isActive: isActive };
    },

    /** Win rate as a number 0-100 (or 0 if no sessions). */
    getWinRate: function () {
      var p = loadProfile();
      if (p.totalSessions === 0) return 0;
      return Math.round((p.wins / p.totalSessions) * 100);
    },

    /** Averaged dimension scores for radar chart: { labels, values } */
    getRadarData: function () {
      var p = loadProfile();
      var labels = [];
      var values = [];
      Object.keys(p.dimensionTotals).forEach(function (dim) {
        var scores = p.dimensionTotals[dim];
        if (scores.length === 0) return;
        var avg = scores.reduce(function (a, b) { return a + b; }, 0) / scores.length;
        labels.push(dim);
        values.push(Math.round(avg * 10) / 10);
      });
      return { labels: labels, values: values };
    },

    /** All unlocked achievements with metadata. */
    getAchievements: function () {
      var p = loadProfile();
      return p.achievements.slice();
    },

    /**
     * Returns ALL 12 achievement definitions merged with unlock status.
     * Each entry: { id, title, emoji, description, unlockedAt: Date|null }
     * Locked achievements have unlockedAt = null.
     */
    getAllAchievements: function () {
      var p = loadProfile();
      var unlockMap = {};
      p.achievements.forEach(function (a) { unlockMap[a.id] = a.unlockedAt; });
      return Object.keys(ACHIEVEMENT_DEFS).map(function (id) {
        var def = ACHIEVEMENT_DEFS[id];
        return {
          id: id,
          title: def.title,
          emoji: def.emoji,
          description: def.description,
          unlockedAt: unlockMap[id] || null,
        };
      });
    },

    /** Returns achievements unlocked in the most recent recordSession call, then clears the buffer. */
    getNewAchievements: function () {
      var result = newlyUnlocked.slice();
      newlyUnlocked = [];
      return result;
    },

    /** Register a callback for level-up events. Callback receives { oldLevel, newLevel, totalXP }. */
    onLevelUp: function (callback) {
      if (typeof callback === 'function') listeners.levelUp.push(callback);
    },

    /** Register a callback for achievement unlocks. Callback receives the achievement object. */
    onAchievement: function (callback) {
      if (typeof callback === 'function') listeners.achievement.push(callback);
    },
  };

})();
