/* ============================================================
   DealSim — Session Export & Sharing Module
   IIFE — exposes window.DealSimExport
   ============================================================ */

(function () {
  'use strict';

  // ------------------------------------------------------------------
  // Internal helpers
  // ------------------------------------------------------------------

  /** Resolve a CSS variable value from the document root. */
  function cssVar(name, fallback) {
    var val = getComputedStyle(document.documentElement)
      .getPropertyValue(name).trim();
    return val || fallback;
  }

  /** Detect the active theme name. */
  function activeTheme() {
    return document.documentElement.dataset.theme || 'arena';
  }

  /** Per-theme palette resolved at call-time (reads CSS vars). */
  function themePalette() {
    var theme = activeTheme();
    return {
      bg:          cssVar('--bg',          '#0f0f23'),
      cardBg:      cssVar('--card-bg',     '#1a1a2e'),
      accent:      cssVar('--accent',      '#f95c5c'),
      accentLight: cssVar('--accent-light','#ff7a7a'),
      text:        cssVar('--text',        '#ffffff'),
      textDim:     cssVar('--text-dim',    '#b0b3d6'),
      secondary:   cssVar('--secondary',   '#ffd700'),
      cardBorder:  cssVar('--card-border', 'rgba(249,92,92,0.25)'),
      theme:       theme,
    };
  }

  /** Sanitise strings going into canvas/text. */
  function safe(s) {
    return (s == null) ? '' : String(s);
  }

  /** Format a date as YYYY-MM-DD. */
  function dateStamp() {
    var d = new Date();
    return d.getFullYear() + '-' +
      String(d.getMonth() + 1).padStart(2, '0') + '-' +
      String(d.getDate()).padStart(2, '0');
  }

  /** Trigger a file download from a data URL or Blob URL. */
  function triggerDownload(url, filename) {
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  /** Show a brief toast notification. Reuses showToast if available. */
  function toast(msg) {
    if (typeof showToast === 'function') {
      showToast(msg);
      return;
    }
    // Fallback toast
    var el = document.createElement('div');
    el.textContent = msg;
    el.style.cssText = [
      'position:fixed',
      'bottom:90px',
      'left:50%',
      'transform:translateX(-50%)',
      'background:' + cssVar('--card-bg', '#1a1a2e'),
      'color:' + cssVar('--text', '#fff'),
      'border:1px solid ' + cssVar('--accent', '#f95c5c'),
      'padding:10px 20px',
      'border-radius:12px',
      'font-size:14px',
      'z-index:99999',
      'pointer-events:none',
      'white-space:nowrap',
      'box-shadow:0 4px 24px rgba(0,0,0,0.5)',
    ].join(';');
    document.body.appendChild(el);
    setTimeout(function () { el.remove(); }, 2800);
  }

  // ------------------------------------------------------------------
  // Data extraction
  // ------------------------------------------------------------------

  /** Pull the current session data from the page's global state. */
  function collectSessionData() {
    var scoreData = (typeof lastScoreData !== 'undefined') ? lastScoreData : null;
    if (!scoreData) {
      return null;
    }

    var score = scoreData.overall_score || 0;

    // Dimensions — normalise from array to ordered pairs
    var rawDims = scoreData.dimensions || [];
    var dimOrder = [
      'Opening Strategy', 'Information Gathering', 'Concession Pattern',
      'BATNA Usage', 'Emotional Control', 'Value Creation',
    ];
    var dimsMap = {};
    rawDims.forEach(function (d) { dimsMap[d.name] = d.score; });
    var dims = dimOrder
      .filter(function (k) { return k in dimsMap; })
      .map(function (k) { return { name: k, score: dimsMap[k] }; });
    // Append any extra dimensions not in the canonical order
    rawDims.forEach(function (d) {
      if (!dimOrder.includes(d.name)) dims.push({ name: d.name, score: d.score });
    });

    var tips = scoreData.top_tips || [];

    // Scenario + difficulty from DOM (most reliable source)
    var scenarioEl = document.getElementById('scenario-type');
    var scenarioVal = scenarioEl ? scenarioEl.value : '';
    var scenarioLabel = scenarioEl && scenarioEl.selectedOptions[0]
      ? scenarioEl.selectedOptions[0].text
      : (scenarioVal || 'Negotiation');

    var stateObj = (typeof state !== 'undefined') ? state : {};
    var difficulty = stateObj.selectedDiff || 'unknown';
    var diffLabel  = difficulty.charAt(0).toUpperCase() + difficulty.slice(1);

    // Score label
    var label;
    if (score >= 85) label = 'Outstanding';
    else if (score >= 70) label = 'Strong Performer';
    else if (score >= 40) label = 'Developing';
    else label = 'Building Foundations';

    // Outcome
    var outcome = scoreData.outcome === 'deal_reached'
      ? 'Deal reached at $' + (scoreData.agreed_value || 0).toLocaleString()
      : 'No deal reached';

    // Collect chat messages from DOM
    var messages = [];
    var chatContainer = document.getElementById('chat-messages');
    if (chatContainer) {
      chatContainer.querySelectorAll('.bubble').forEach(function (wrapper) {
        var isUser = wrapper.classList.contains('justify-end');
        var bubble = wrapper.querySelector('div');
        if (bubble && bubble.textContent.trim()) {
          messages.push({
            role: isUser ? 'You' : 'Counterpart',
            text: bubble.textContent.trim(),
          });
        }
      });
    }

    return {
      score: score,
      label: label,
      outcome: outcome,
      scenarioLabel: scenarioLabel,
      difficulty: diffLabel,
      dims: dims,
      tips: tips,
      messages: messages,
      date: new Date().toLocaleDateString('en-GB', {
        day: 'numeric', month: 'long', year: 'numeric',
      }),
    };
  }

  // ------------------------------------------------------------------
  // 1. IMAGE EXPORT — Canvas API, 1200x630
  // ------------------------------------------------------------------

  function exportImage() {
    var data = collectSessionData();
    if (!data) { toast('Complete a negotiation first.'); return; }

    var W = 1200, H = 630;
    var canvas = document.createElement('canvas');
    canvas.width  = W * 2; // 2x for retina-quality PNG
    canvas.height = H * 2;
    var ctx = canvas.getContext('2d');
    ctx.scale(2, 2);

    var p = themePalette();

    // ── Background ──
    var bgGrad = ctx.createLinearGradient(0, 0, 0, H);
    var theme = activeTheme();
    if (theme === 'coach') {
      bgGrad.addColorStop(0, '#1a1147');
      bgGrad.addColorStop(1, '#2d1b69');
    } else if (theme === 'lab') {
      bgGrad.addColorStop(0, '#0d1117');
      bgGrad.addColorStop(1, '#0d1117');
    } else {
      bgGrad.addColorStop(0, '#0f0f23');
      bgGrad.addColorStop(1, '#1a1a2e');
    }
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, W, H);

    // Subtle grid pattern (arena theme only)
    if (theme === 'arena') {
      ctx.save();
      ctx.strokeStyle = 'rgba(249,92,92,0.05)';
      ctx.lineWidth = 1;
      for (var gx = 0; gx < W; gx += 60) {
        ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, H); ctx.stroke();
      }
      for (var gy = 0; gy < H; gy += 60) {
        ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(W, gy); ctx.stroke();
      }
      ctx.restore();
    }

    // ── Brand accent strip (top) ──
    ctx.fillStyle = p.accent;
    ctx.fillRect(0, 0, W, 4);

    // ── Left column: branding + score ring (x: 60 … 380) ──
    var cx = 200, cy = 290, r = 115;

    // Outer glow ring
    var glowGrad = ctx.createRadialGradient(cx, cy, r - 10, cx, cy, r + 30);
    glowGrad.addColorStop(0, hexToRgba(p.accent, 0.35));
    glowGrad.addColorStop(1, 'transparent');
    ctx.fillStyle = glowGrad;
    ctx.beginPath();
    ctx.arc(cx, cy, r + 30, 0, Math.PI * 2);
    ctx.fill();

    // Card behind ring
    roundRect(ctx, cx - r - 20, cy - r - 20, (r + 20) * 2, (r + 20) * 2, 20);
    ctx.fillStyle = p.cardBg;
    ctx.fill();

    // Score ring background
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineWidth = 12;
    ctx.stroke();

    // Score ring progress
    var pct = Math.min(data.score / 100, 1);
    var scoreColor = data.score >= 70 ? '#34d399' : data.score >= 40 ? '#fbbf24' : p.accent;
    ctx.beginPath();
    ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + pct * 2 * Math.PI);
    ctx.strokeStyle = scoreColor;
    ctx.lineWidth = 12;
    ctx.lineCap = 'round';
    ctx.stroke();

    // Score number
    ctx.fillStyle = scoreColor;
    ctx.font = 'bold 72px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(String(data.score), cx, cy - 8);

    // "/100" sub-label
    ctx.fillStyle = 'rgba(255,255,255,0.45)';
    ctx.font = '22px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    ctx.fillText('/ 100', cx, cy + 44);

    // Label beneath ring
    ctx.fillStyle = scoreColor;
    ctx.font = 'bold 18px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(safe(data.label), cx, cy + r + 28);

    // ── Middle column: dimensions (x: 400 … 800) ──
    var barX = 400, barY = 80, barW = 340, barH = 12, barGap = 58;

    ctx.textAlign = 'left';
    ctx.fillStyle = 'rgba(255,255,255,0.45)';
    ctx.font = 'bold 11px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    ctx.fillText('BREAKDOWN', barX, barY - 12);

    data.dims.slice(0, 6).forEach(function (dim, i) {
      var y = barY + i * barGap;
      var val = Math.min(Math.max(dim.score, 0), 100);
      var barColor = val >= 70 ? '#34d399' : val >= 40 ? '#fbbf24' : p.accent;

      // Dimension label
      ctx.fillStyle = 'rgba(255,255,255,0.80)';
      ctx.font = '13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(safe(dim.name), barX, y + 3);

      // Score value (right-aligned)
      ctx.fillStyle = barColor;
      ctx.font = 'bold 13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(String(val), barX + barW, y + 3);

      // Track
      roundRect(ctx, barX, y + 14, barW, barH, 6);
      ctx.fillStyle = 'rgba(255,255,255,0.08)';
      ctx.fill();

      // Fill
      if (val > 0) {
        roundRect(ctx, barX, y + 14, barW * (val / 100), barH, 6);
        ctx.fillStyle = barColor;
        ctx.fill();
      }
    });

    // ── Right column: tips + metadata (x: 770 … 1150) ──
    var tipX = 780, tipY = 80, tipW = 370;

    ctx.textAlign = 'left';
    ctx.fillStyle = 'rgba(255,255,255,0.45)';
    ctx.font = 'bold 11px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    ctx.fillText('COACHING TIPS', tipX, tipY - 12);

    var visibleTips = data.tips.slice(0, 3);
    visibleTips.forEach(function (tip, i) {
      var ty = tipY + i * 80;

      // Bullet dot
      ctx.beginPath();
      ctx.arc(tipX + 7, ty + 8, 4, 0, Math.PI * 2);
      ctx.fillStyle = p.accent;
      ctx.fill();

      // Tip text (word-wrapped)
      ctx.fillStyle = 'rgba(255,255,255,0.75)';
      ctx.font = '13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
      wrapText(ctx, safe(tip), tipX + 20, ty, tipW - 20, 18, 3);
    });

    // ── Bottom bar: metadata ──
    var metaY = H - 64;
    ctx.fillStyle = 'rgba(255,255,255,0.06)';
    ctx.fillRect(0, metaY - 12, W, 1);

    // Logo/brand
    ctx.fillStyle = p.accent;
    ctx.font = 'bold 22px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('\uD83D\uDE80 DealSim', 60, metaY + 20);

    // Scenario + difficulty
    ctx.fillStyle = 'rgba(255,255,255,0.55)';
    ctx.font = '14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(safe(data.scenarioLabel) + ' \u00B7 ' + safe(data.difficulty) + ' difficulty', W / 2, metaY + 20);

    // Date + URL
    ctx.fillStyle = 'rgba(255,255,255,0.35)';
    ctx.font = '13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(data.date + ' \u00B7 dealsim.app', W - 60, metaY + 20);

    // Outcome
    ctx.fillStyle = 'rgba(255,255,255,0.40)';
    ctx.font = '12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(safe(data.outcome), 60, H - 24);

    // ── Export ──
    var filename = 'dealsim-score-' + dateStamp() + '.png';
    canvas.toBlob(function (blob) {
      var url = URL.createObjectURL(blob);
      triggerDownload(url, filename);
      setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
      toast('Image saved — ' + filename);
    }, 'image/png');
  }

  // ------------------------------------------------------------------
  // 2. TRANSCRIPT EXPORT — Markdown file
  // ------------------------------------------------------------------

  function exportTranscript() {
    var data = collectSessionData();
    if (!data) { toast('Complete a negotiation first.'); return; }

    var lines = [];

    lines.push('# DealSim Session Transcript');
    lines.push('');
    lines.push('**Date:** ' + data.date);
    lines.push('**Scenario:** ' + data.scenarioLabel);
    lines.push('**Difficulty:** ' + data.difficulty);
    lines.push('**Outcome:** ' + data.outcome);
    lines.push('');
    lines.push('---');
    lines.push('');
    lines.push('## Overall Score');
    lines.push('');
    lines.push('**' + data.score + '/100** — ' + data.label);
    lines.push('');

    if (data.dims.length > 0) {
      lines.push('## Dimension Breakdown');
      lines.push('');
      lines.push('| Dimension | Score |');
      lines.push('|-----------|-------|');
      data.dims.forEach(function (d) {
        lines.push('| ' + d.name + ' | ' + d.score + '/100 |');
      });
      lines.push('');
    }

    if (data.tips.length > 0) {
      lines.push('## Coaching Tips');
      lines.push('');
      data.tips.forEach(function (tip) {
        lines.push('- ' + tip);
      });
      lines.push('');
    }

    if (data.messages.length > 0) {
      lines.push('## Negotiation Transcript');
      lines.push('');
      data.messages.forEach(function (msg, i) {
        lines.push('**' + msg.role + ':** ' + msg.text);
        if (i < data.messages.length - 1) lines.push('');
      });
      lines.push('');
    }

    lines.push('---');
    lines.push('');
    lines.push('*Generated by [DealSim](https://dealsim.app) — Negotiation Simulator*');

    var content = lines.join('\n');
    var blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var filename = 'dealsim-transcript-' + dateStamp() + '.md';
    triggerDownload(url, filename);
    setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
    toast('Transcript downloaded.');
  }

  // ------------------------------------------------------------------
  // 3. COPY SCORE SUMMARY TO CLIPBOARD
  // ------------------------------------------------------------------

  function copySummary() {
    var data = collectSessionData();
    if (!data) { toast('Complete a negotiation first.'); return; }

    var text = 'I scored ' + data.score + '/100 on a ' +
      data.scenarioLabel + ' (' + data.difficulty + ') in DealSim! \uD83C\uDFAF ' +
      data.outcome + '. Try it: https://dealsim.app';

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        toast('\u2713 Score summary copied to clipboard!');
      }).catch(function () {
        fallbackCopy(text);
      });
    } else {
      fallbackCopy(text);
    }
  }

  function fallbackCopy(text) {
    var el = document.createElement('textarea');
    el.value = text;
    el.style.cssText = 'position:fixed;top:-9999px;left:-9999px;opacity:0';
    document.body.appendChild(el);
    el.focus();
    el.select();
    try {
      document.execCommand('copy');
      toast('\u2713 Score summary copied!');
    } catch (e) {
      toast('Could not copy. Score: ' + text.split('!')[0] + '!');
    }
    document.body.removeChild(el);
  }

  // ------------------------------------------------------------------
  // 4. UI INJECTION — "Export" dropdown next to "Share Your Score"
  // ------------------------------------------------------------------

  function buildDropdown() {
    // Find the share button as the anchor
    var shareBtn = null;
    document.querySelectorAll('button').forEach(function (btn) {
      if (btn.getAttribute('onclick') === 'shareScore()') shareBtn = btn;
    });
    if (!shareBtn) return; // Not yet in DOM — will retry

    // Wrap share button + new export button in a flex row
    var parent = shareBtn.parentNode;
    var wrapper = document.createElement('div');
    wrapper.id  = 'ds-export-wrapper';
    wrapper.className = 'flex gap-2 mb-3';
    wrapper.style.cssText = 'position:relative;';

    // Clone/move the share button into the wrapper (keep its classes/onclick)
    parent.insertBefore(wrapper, shareBtn);
    wrapper.appendChild(shareBtn);

    // Remove the original mb-3 from the share button since wrapper has it
    shareBtn.classList.remove('mb-3');
    shareBtn.style.flex = '1';

    // Export button
    var exportBtn = document.createElement('button');
    exportBtn.id        = 'ds-export-btn';
    exportBtn.type      = 'button';
    exportBtn.className = 'bg-white/10 hover:bg-white/15 text-white/90 font-medium py-3 rounded-xl transition-all text-sm border border-white/10 inline-flex items-center justify-center gap-2';
    exportBtn.style.cssText = 'flex:0 0 auto;padding-left:16px;padding-right:16px;position:relative;';
    exportBtn.setAttribute('aria-haspopup', 'true');
    exportBtn.setAttribute('aria-expanded', 'false');
    exportBtn.setAttribute('aria-label', 'Export options');
    exportBtn.innerHTML =
      '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" ' +
          'd="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>' +
      '</svg>' +
      '<span>Export</span>' +
      '<svg class="w-3 h-3 opacity-60" id="ds-export-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>' +
      '</svg>';
    wrapper.appendChild(exportBtn);

    // Dropdown menu
    var menu = document.createElement('div');
    menu.id = 'ds-export-menu';
    menu.setAttribute('role', 'menu');
    menu.style.cssText = [
      'display:none',
      'position:absolute',
      'bottom:calc(100% + 8px)',
      'right:0',
      'min-width:200px',
      'background:' + cssVar('--card-bg', '#1a1a2e'),
      'border:1px solid ' + cssVar('--card-border', 'rgba(249,92,92,0.25)'),
      'border-radius:12px',
      'padding:6px',
      'box-shadow:0 8px 32px rgba(0,0,0,0.5)',
      'z-index:9998',
    ].join(';');

    var menuItems = [
      { icon: '\uD83D\uDDBC\uFE0F', label: 'Save as Image',        action: exportImage },
      { icon: '\uD83D\uDCCB', label: 'Download Transcript',  action: exportTranscript },
      { icon: '\uD83D\uDCCB', label: 'Copy Summary',          action: copySummary },
    ];
    // Override icon for Copy Summary
    menuItems[2].icon = '\uD83D\uDCCB';

    menuItems.forEach(function (item, idx) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.setAttribute('role', 'menuitem');
      btn.style.cssText = [
        'display:flex',
        'align-items:center',
        'gap:10px',
        'width:100%',
        'padding:10px 14px',
        'border:none',
        'border-radius:8px',
        'background:transparent',
        'color:' + cssVar('--text', '#ffffff'),
        'font-size:14px',
        'cursor:pointer',
        'text-align:left',
        'transition:background 0.15s ease',
      ].join(';');

      // Correct icons
      var icons = [
        // Save as Image
        '<svg style="width:16px;height:16px;flex-shrink:0;opacity:0.7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>',
        // Download Transcript
        '<svg style="width:16px;height:16px;flex-shrink:0;opacity:0.7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>',
        // Copy Summary
        '<svg style="width:16px;height:16px;flex-shrink:0;opacity:0.7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"/></svg>',
      ];
      var labels = ['Save as Image', 'Download Transcript', 'Copy Summary'];

      btn.innerHTML = icons[idx] + '<span>' + labels[idx] + '</span>';

      btn.addEventListener('mouseover', function () {
        btn.style.background = 'rgba(255,255,255,0.08)';
      });
      btn.addEventListener('mouseout', function () {
        btn.style.background = 'transparent';
      });

      btn.addEventListener('click', function () {
        closeMenu();
        item.action();
      });

      menu.appendChild(btn);
    });

    wrapper.appendChild(menu);

    // Toggle logic
    var isOpen = false;

    function openMenu() {
      isOpen = true;
      menu.style.display = 'block';
      exportBtn.setAttribute('aria-expanded', 'true');
      // Re-read CSS vars in case theme changed
      menu.style.background = cssVar('--card-bg', '#1a1a2e');
      menu.style.borderColor = cssVar('--card-border', 'rgba(249,92,92,0.25)');
      menu.querySelectorAll('button').forEach(function (b) {
        b.style.color = cssVar('--text', '#ffffff');
      });
    }

    function closeMenu() {
      isOpen = false;
      menu.style.display = 'none';
      exportBtn.setAttribute('aria-expanded', 'false');
    }

    exportBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      isOpen ? closeMenu() : openMenu();
    });

    // Close on outside click
    document.addEventListener('click', function (e) {
      if (isOpen && !wrapper.contains(e.target)) closeMenu();
    });

    // Close on Escape
    document.addEventListener('keydown', function (e) {
      if (isOpen && e.key === 'Escape') closeMenu();
    });
  }

  // ------------------------------------------------------------------
  // Canvas utility helpers
  // ------------------------------------------------------------------

  /** Draw a rounded rectangle path. */
  function roundRect(ctx, x, y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }

  /** Wrap text within maxWidth, drawing at most maxLines. */
  function wrapText(ctx, text, x, y, maxWidth, lineHeight, maxLines) {
    var words = text.split(' ');
    var line  = '';
    var drawn = 0;
    for (var i = 0; i < words.length; i++) {
      var test = line + (line ? ' ' : '') + words[i];
      if (ctx.measureText(test).width > maxWidth && line) {
        if (drawn < maxLines - 1 || i === words.length - 1) {
          ctx.fillText(line, x, y + drawn * lineHeight);
          drawn++;
          line = words[i];
        } else {
          // Last allowed line — truncate with ellipsis
          while (ctx.measureText(line + '\u2026').width > maxWidth && line.length > 0) {
            line = line.slice(0, -1);
          }
          ctx.fillText(line + '\u2026', x, y + drawn * lineHeight);
          return;
        }
      } else {
        line = test;
      }
    }
    if (line && drawn < maxLines) {
      ctx.fillText(line, x, y + drawn * lineHeight);
    }
  }

  /** Convert a hex colour string to rgba(). */
  function hexToRgba(hex, alpha) {
    var clean = hex.replace('#', '');
    if (clean.length === 3) {
      clean = clean.split('').map(function (c) { return c + c; }).join('');
    }
    var r = parseInt(clean.substring(0, 2), 16);
    var g = parseInt(clean.substring(2, 4), 16);
    var b = parseInt(clean.substring(4, 6), 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
  }

  // ------------------------------------------------------------------
  // Public init — waits for DOM + scorecard section
  // ------------------------------------------------------------------

  function init() {
    // If scorecard is already rendered, inject immediately
    if (document.getElementById('ds-export-wrapper')) return; // Already done

    // Attempt injection now
    buildDropdown();

    // Also observe for the scorecard section becoming active (SPA routing)
    var scorecardSection = document.getElementById('sec-scorecard');
    if (scorecardSection && window.MutationObserver) {
      var obs = new MutationObserver(function () {
        if (!document.getElementById('ds-export-wrapper')) {
          buildDropdown();
        }
      });
      obs.observe(scorecardSection, { attributes: true, attributeFilter: ['class'] });
    }
  }

  // ------------------------------------------------------------------
  // Boot
  // ------------------------------------------------------------------

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // ------------------------------------------------------------------
  // Public API
  // ------------------------------------------------------------------

  window.DealSimExport = {
    init:             init,
    exportImage:      exportImage,
    exportTranscript: exportTranscript,
    copySummary:      copySummary,
  };

}());
