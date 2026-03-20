/**
 * DealSimScoreTrends — Score history visualization module.
 * Adds a trend line chart, summary stats card, and per-dimension sparklines
 * to the Score History section (sec-history). Pure SVG, no dependencies.
 *
 * Exposes: window.DealSimScoreTrends = { init(containerId), update() }
 *
 * Data source: localStorage 'dealsim_scores'
 * Expected entry shape:
 *   { date: ISO string, score: 0-100, outcome: string, scenario: string,
 *     dims?: { 'Opening Strategy': 0-100, 'Information Gathering': 0-100,
 *              'Concession Pattern': 0-100, 'BATNA Usage': 0-100,
 *              'Emotional Control': 0-100, 'Value Creation': 0-100 } }
 *
 * NOTE: 'dims' is written by saveScoreToHistory() in index.html.
 * It is built from data.dimensions in renderScorecard and stored as:
 *   dims: { 'Opening Strategy': 0-100, ... }  (present on every scored session)
 */
(function () {
  'use strict';

  /* ── Constants ─────────────────────────────────────────────────────── */
  var SVG_NS = 'http://www.w3.org/2000/svg';
  var STORAGE_KEY = 'dealsim_scores';
  var MAX_POINTS = 10;
  var CHART_W = 520;
  var CHART_H = 160;
  var PAD = { top: 16, right: 20, bottom: 32, left: 42 };
  var DOT_R = 4;
  var SPARK_W = 72;
  var SPARK_H = 28;

  var DIM_KEYS = [
    'Opening Strategy',
    'Information Gathering',
    'Concession Pattern',
    'BATNA Usage',
    'Emotional Control',
    'Value Creation'
  ];

  /* ── State ──────────────────────────────────────────────────────────── */
  var _containerId = null;
  var _tooltip = null;
  var _mounted = false;

  /* ── Utilities ──────────────────────────────────────────────────────── */
  function svgEl(tag) {
    return document.createElementNS(SVG_NS, tag);
  }

  function css(prop) {
    return getComputedStyle(document.documentElement).getPropertyValue(prop).trim();
  }

  function accent() { return css('--accent') || '#f95c5c'; }
  function textDim() { return css('--text-dim') || '#b0b3d6'; }
  function textDim2() { return css('--text-dim2') || '#6b6f9e'; }
  function cardBg() { return css('--card-bg') || '#1a1a2e'; }

  function getHistory() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); } catch (e) { return []; }
  }

  /* Take the last MAX_POINTS entries from the full history */
  function sliceRecent(history) {
    return history.slice(-MAX_POINTS);
  }

  /* ── Tooltip ────────────────────────────────────────────────────────── */
  function ensureTooltip() {
    if (_tooltip) return _tooltip;
    _tooltip = document.createElement('div');
    _tooltip.id = 'dst-tooltip';
    _tooltip.style.cssText = [
      'position:fixed',
      'pointer-events:none',
      'z-index:9999',
      'padding:6px 10px',
      'border-radius:8px',
      'font-size:12px',
      'line-height:1.4',
      'white-space:nowrap',
      'opacity:0',
      'transition:opacity 0.12s ease',
      'background:' + (css('--card-bg') || '#1a1a2e'),
      'border:1px solid ' + (css('--card-border') || 'rgba(249,92,92,0.25)'),
      'color:' + (css('--text') || '#fff'),
      'box-shadow:0 4px 16px rgba(0,0,0,0.4)',
    ].join(';');
    document.body.appendChild(_tooltip);
    return _tooltip;
  }

  function showTooltip(html, x, y) {
    var t = ensureTooltip();
    t.innerHTML = html;
    t.style.opacity = '1';
    var tw = t.offsetWidth;
    var th = t.offsetHeight;
    var vw = window.innerWidth;
    var vh = window.innerHeight;
    var left = x + 12;
    var top = y - th / 2;
    if (left + tw > vw - 8) left = x - tw - 12;
    if (top < 8) top = 8;
    if (top + th > vh - 8) top = vh - th - 8;
    t.style.left = left + 'px';
    t.style.top = top + 'px';
  }

  function hideTooltip() {
    var t = ensureTooltip();
    t.style.opacity = '0';
  }

  /* ── Score color helper ─────────────────────────────────────────────── */
  function scoreColor(s) {
    if (s >= 70) return '#34d399';
    if (s >= 40) return '#facc15';
    return accent();
  }

  /* ── Summary stats ──────────────────────────────────────────────────── */
  function computeStats(history) {
    var n = history.length;
    if (n === 0) return null;

    var scores = history.map(function (h) { return h.score || 0; });
    var avg = Math.round(scores.reduce(function (a, b) { return a + b; }, 0) / n);
    var best = Math.max.apply(null, scores);

    // Streak: consecutive sessions from most-recent going backward (score >= 1 = valid)
    var streak = 0;
    for (var i = n - 1; i >= 0; i--) {
      if (scores[i] > 0) streak++; else break;
    }

    // Trend: compare average of last 3 vs previous 3
    var trend = 'flat';
    if (n >= 6) {
      var last3 = scores.slice(-3).reduce(function (a, b) { return a + b; }, 0) / 3;
      var prev3 = scores.slice(-6, -3).reduce(function (a, b) { return a + b; }, 0) / 3;
      var delta = last3 - prev3;
      if (delta > 3) trend = 'up';
      else if (delta < -3) trend = 'down';
    } else if (n >= 2) {
      var delta2 = scores[n - 1] - scores[n - 2];
      if (delta2 > 3) trend = 'up';
      else if (delta2 < -3) trend = 'down';
    }

    return { avg: avg, best: best, total: n, streak: streak, trend: trend };
  }

  /* ── Stats card DOM ─────────────────────────────────────────────────── */
  function buildStatsCard(stats) {
    var card = document.createElement('div');
    card.id = 'dst-stats-card';
    card.style.cssText = [
      'display:grid',
      'grid-template-columns:repeat(4,1fr)',
      'gap:12px',
      'margin-bottom:20px',
    ].join(';');

    var trendIcon = { up: '&#x2191;', down: '&#x2193;', flat: '&#x2192;' }[stats.trend];
    var trendColor = { up: '#34d399', down: accent(), flat: textDim() }[stats.trend];

    var cells = [
      { label: 'Average', value: stats.avg + '/100', color: scoreColor(stats.avg) },
      { label: 'Best', value: stats.best + '/100', color: scoreColor(stats.best) },
      { label: 'Sessions', value: stats.total, color: textDim() },
      { label: 'Trend', value: trendIcon, color: trendColor, raw: true },
    ];

    cells.forEach(function (c) {
      var cell = document.createElement('div');
      cell.style.cssText = [
        'background:rgba(255,255,255,0.04)',
        'border:1px solid rgba(255,255,255,0.08)',
        'border-radius:12px',
        'padding:12px 10px',
        'text-align:center',
      ].join(';');

      var val = document.createElement('div');
      val.style.cssText = 'font-size:20px;font-weight:700;color:' + c.color + ';line-height:1.2;margin-bottom:4px;';
      if (c.raw) { val.innerHTML = c.value; } else { val.textContent = c.value; }

      var lbl = document.createElement('div');
      lbl.style.cssText = 'font-size:10px;text-transform:uppercase;letter-spacing:0.06em;color:' + textDim2() + ';';
      lbl.textContent = c.label;

      cell.appendChild(val);
      cell.appendChild(lbl);
      card.appendChild(cell);
    });

    return card;
  }

  /* ── Main trend chart (SVG) ─────────────────────────────────────────── */
  function buildTrendChart(recent) {
    var wrap = document.createElement('div');
    wrap.id = 'dst-chart-wrap';
    wrap.style.cssText = 'position:relative;width:100%;overflow:hidden;';

    var svg = svgEl('svg');
    svg.setAttribute('viewBox', '0 0 ' + CHART_W + ' ' + CHART_H);
    svg.setAttribute('width', '100%');
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.style.display = 'block';
    svg.style.overflow = 'visible';

    var plotW = CHART_W - PAD.left - PAD.right;
    var plotH = CHART_H - PAD.top - PAD.bottom;
    var n = recent.length;

    /* Grid lines + Y labels */
    var gridLevels = [0, 25, 50, 75, 100];
    gridLevels.forEach(function (val) {
      var y = PAD.top + plotH * (1 - val / 100);

      var line = svgEl('line');
      line.setAttribute('x1', PAD.left);
      line.setAttribute('y1', y);
      line.setAttribute('x2', CHART_W - PAD.right);
      line.setAttribute('y2', y);
      line.setAttribute('stroke', 'rgba(255,255,255,0.07)');
      line.setAttribute('stroke-width', '1');
      svg.appendChild(line);

      var label = svgEl('text');
      label.setAttribute('x', PAD.left - 6);
      label.setAttribute('y', y);
      label.setAttribute('text-anchor', 'end');
      label.setAttribute('dominant-baseline', 'central');
      label.setAttribute('font-size', '9');
      label.setAttribute('font-family', 'inherit');
      label.setAttribute('fill', textDim2());
      label.textContent = val;
      svg.appendChild(label);
    });

    if (n === 0) {
      var emptyText = svgEl('text');
      emptyText.setAttribute('x', CHART_W / 2);
      emptyText.setAttribute('y', CHART_H / 2);
      emptyText.setAttribute('text-anchor', 'middle');
      emptyText.setAttribute('dominant-baseline', 'central');
      emptyText.setAttribute('font-size', '11');
      emptyText.setAttribute('font-family', 'inherit');
      emptyText.setAttribute('fill', textDim2());
      emptyText.setAttribute('opacity', '0.6');
      emptyText.textContent = 'Complete a session to see your trend';
      svg.appendChild(emptyText);
      wrap.appendChild(svg);
      return wrap;
    }

    /* X position helper */
    function xFor(i) {
      return n === 1
        ? PAD.left + plotW / 2
        : PAD.left + (plotW / (n - 1)) * i;
    }

    function yFor(score) {
      return PAD.top + plotH * (1 - Math.max(0, Math.min(score, 100)) / 100);
    }

    /* Area fill under the line */
    var areaA = accent();
    var areaPoints = '';
    recent.forEach(function (item, i) {
      areaPoints += xFor(i) + ',' + yFor(item.score || 0) + ' ';
    });
    areaPoints += (PAD.left + (n === 1 ? plotW / 2 : plotW)) + ',' + (PAD.top + plotH) + ' ';
    areaPoints += PAD.left + ',' + (PAD.top + plotH);

    var area = svgEl('polygon');
    area.setAttribute('points', areaPoints);
    area.setAttribute('fill', areaA);
    area.setAttribute('fill-opacity', '0.06');
    svg.appendChild(area);

    /* Line path */
    if (n >= 2) {
      var pathD = '';
      recent.forEach(function (item, i) {
        var x = xFor(i);
        var y = yFor(item.score || 0);
        pathD += (i === 0 ? 'M' : 'L') + x + ' ' + y + ' ';
      });

      var path = svgEl('path');
      path.setAttribute('d', pathD.trim());
      path.setAttribute('fill', 'none');
      path.setAttribute('stroke', areaA);
      path.setAttribute('stroke-width', '2');
      path.setAttribute('stroke-linejoin', 'round');
      path.setAttribute('stroke-linecap', 'round');
      svg.appendChild(path);
    }

    /* X axis session labels */
    recent.forEach(function (item, i) {
      var x = xFor(i);

      /* Only label first, last, and every other in between to avoid clutter */
      var showLabel = (n <= 5) || (i === 0) || (i === n - 1) || (i % 2 === 0);

      if (showLabel) {
        var xLbl = svgEl('text');
        xLbl.setAttribute('x', x);
        xLbl.setAttribute('y', PAD.top + plotH + 14);
        xLbl.setAttribute('text-anchor', 'middle');
        xLbl.setAttribute('font-size', '9');
        xLbl.setAttribute('font-family', 'inherit');
        xLbl.setAttribute('fill', textDim2());
        xLbl.textContent = '#' + (i + 1);
        svg.appendChild(xLbl);
      }
    });

    /* Dots with hover hit areas */
    recent.forEach(function (item, i) {
      var x = xFor(i);
      var y = yFor(item.score || 0);
      var s = item.score || 0;
      var col = scoreColor(s);

      /* Invisible larger hit target */
      var hit = svgEl('circle');
      hit.setAttribute('cx', x);
      hit.setAttribute('cy', y);
      hit.setAttribute('r', '12');
      hit.setAttribute('fill', 'transparent');
      hit.style.cursor = 'pointer';

      /* Visible dot */
      var dot = svgEl('circle');
      dot.setAttribute('cx', x);
      dot.setAttribute('cy', y);
      dot.setAttribute('r', DOT_R);
      dot.setAttribute('fill', col);
      dot.setAttribute('stroke', cardBg());
      dot.setAttribute('stroke-width', '1.5');
      dot.style.pointerEvents = 'none';

      var dateStr = '';
      try {
        var d = new Date(item.date);
        dateStr = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      } catch (e) { dateStr = 'Session ' + (i + 1); }

      var tipHtml = '<span style="color:' + col + ';font-weight:700;">' + s + '</span>'
        + '<span style="color:rgba(255,255,255,0.5);"> / 100</span>'
        + '<br><span style="color:rgba(255,255,255,0.4);font-size:11px;">' + dateStr + '</span>';

      hit.addEventListener('mouseenter', function (e) {
        dot.setAttribute('r', DOT_R + 2);
        showTooltip(tipHtml, e.clientX, e.clientY);
      });
      hit.addEventListener('mousemove', function (e) {
        showTooltip(tipHtml, e.clientX, e.clientY);
      });
      hit.addEventListener('mouseleave', function () {
        dot.setAttribute('r', DOT_R);
        hideTooltip();
      });

      svg.appendChild(hit);
      svg.appendChild(dot);
    });

    wrap.appendChild(svg);
    return wrap;
  }

  /* ── Sparklines section ─────────────────────────────────────────────── */
  function buildSparkline(values) {
    var svg = svgEl('svg');
    svg.setAttribute('viewBox', '0 0 ' + SPARK_W + ' ' + SPARK_H);
    svg.setAttribute('width', SPARK_W);
    svg.setAttribute('height', SPARK_H);
    svg.style.display = 'block';
    svg.style.overflow = 'visible';

    var n = values.length;
    var col = accent();

    if (n === 0) {
      var line = svgEl('line');
      line.setAttribute('x1', '0');
      line.setAttribute('y1', SPARK_H / 2);
      line.setAttribute('x2', SPARK_W);
      line.setAttribute('y2', SPARK_H / 2);
      line.setAttribute('stroke', 'rgba(255,255,255,0.10)');
      line.setAttribute('stroke-width', '1');
      line.setAttribute('stroke-dasharray', '3,3');
      svg.appendChild(line);
      return svg;
    }

    function xSpark(i) {
      return n === 1 ? SPARK_W / 2 : (SPARK_W / (n - 1)) * i;
    }
    function ySpark(v) {
      var pad = 3;
      return SPARK_H - pad - ((SPARK_H - pad * 2) * Math.max(0, Math.min(v, 100)) / 100);
    }

    /* Area */
    if (n >= 2) {
      var aPoints = '';
      values.forEach(function (v, i) { aPoints += xSpark(i) + ',' + ySpark(v) + ' '; });
      aPoints += SPARK_W + ',' + SPARK_H + ' 0,' + SPARK_H;
      var area = svgEl('polygon');
      area.setAttribute('points', aPoints);
      area.setAttribute('fill', col);
      area.setAttribute('fill-opacity', '0.10');
      svg.appendChild(area);

      var pathD = '';
      values.forEach(function (v, i) {
        pathD += (i === 0 ? 'M' : 'L') + xSpark(i) + ' ' + ySpark(v) + ' ';
      });
      var path = svgEl('path');
      path.setAttribute('d', pathD.trim());
      path.setAttribute('fill', 'none');
      path.setAttribute('stroke', col);
      path.setAttribute('stroke-width', '1.5');
      path.setAttribute('stroke-linejoin', 'round');
      path.setAttribute('stroke-linecap', 'round');
      svg.appendChild(path);
    }

    /* End dot */
    var lastX = xSpark(n - 1);
    var lastY = ySpark(values[n - 1]);
    var dot = svgEl('circle');
    dot.setAttribute('cx', lastX);
    dot.setAttribute('cy', lastY);
    dot.setAttribute('r', '2.5');
    dot.setAttribute('fill', scoreColor(values[n - 1]));
    svg.appendChild(dot);

    return svg;
  }

  function buildSparkSection(history) {
    /* Extract dim values per dimension key */
    var dimSeries = {};
    DIM_KEYS.forEach(function (k) { dimSeries[k] = []; });

    history.forEach(function (item) {
      if (item.dims) {
        DIM_KEYS.forEach(function (k) {
          if (typeof item.dims[k] === 'number') {
            dimSeries[k].push(item.dims[k]);
          }
        });
      }
    });

    var hasDimData = DIM_KEYS.some(function (k) { return dimSeries[k].length > 0; });

    var section = document.createElement('div');
    section.id = 'dst-sparks';
    section.style.cssText = 'margin-top:24px;';

    var heading = document.createElement('div');
    heading.style.cssText = [
      'font-size:10px',
      'text-transform:uppercase',
      'letter-spacing:0.07em',
      'color:' + textDim2(),
      'margin-bottom:12px',
    ].join(';');
    heading.textContent = 'Dimension Trends';
    section.appendChild(heading);

    if (!hasDimData) {
      var note = document.createElement('p');
      note.style.cssText = 'font-size:11px;color:' + textDim2() + ';opacity:0.7;';
      note.textContent = 'Dimension trends appear after sessions scored with per-skill data.';
      section.appendChild(note);
      return section;
    }

    var grid = document.createElement('div');
    grid.style.cssText = [
      'display:grid',
      'grid-template-columns:repeat(3,1fr)',
      'gap:12px',
    ].join(';');

    DIM_KEYS.forEach(function (k) {
      var values = dimSeries[k];

      var cell = document.createElement('div');
      cell.style.cssText = [
        'background:rgba(255,255,255,0.03)',
        'border:1px solid rgba(255,255,255,0.07)',
        'border-radius:10px',
        'padding:10px 10px 6px',
      ].join(';');

      var lbl = document.createElement('div');
      lbl.style.cssText = 'font-size:10px;color:' + textDim() + ';margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
      lbl.title = k;
      lbl.textContent = k;

      var sparkRow = document.createElement('div');
      sparkRow.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:6px;';

      var lastVal = values.length > 0 ? values[values.length - 1] : null;
      var valLabel = document.createElement('span');
      valLabel.style.cssText = 'font-size:13px;font-weight:700;color:' + (lastVal !== null ? scoreColor(lastVal) : textDim2()) + ';min-width:24px;';
      valLabel.textContent = lastVal !== null ? lastVal : '--';

      var sparkWrap = document.createElement('div');
      sparkWrap.style.cssText = 'flex:1;display:flex;justify-content:flex-end;';
      sparkWrap.appendChild(buildSparkline(values.slice(-MAX_POINTS)));

      sparkRow.appendChild(valLabel);
      sparkRow.appendChild(sparkWrap);

      cell.appendChild(lbl);
      cell.appendChild(sparkRow);
      grid.appendChild(cell);
    });

    section.appendChild(grid);
    return section;
  }

  /* ── Mount / render ─────────────────────────────────────────────────── */
  function mount(containerId) {
    _containerId = containerId;
    var container = document.getElementById(containerId);
    if (!container) return;

    /* The container is the card div holding #history-chart.
       Inject our panel above the existing canvas, then hide the canvas. */
    var canvas = container.querySelector('#history-chart');

    var panel = document.createElement('div');
    panel.id = 'dst-panel';

    if (canvas) {
      container.insertBefore(panel, canvas);
      canvas.style.display = 'none';
    } else {
      container.appendChild(panel);
    }

    _mounted = true;
    render();
  }

  function render() {
    if (!_mounted || !_containerId) return;

    var panel = document.getElementById('dst-panel');
    if (!panel) return;
    panel.innerHTML = '';

    var history = getHistory();
    var stats = computeStats(history);
    var recent = sliceRecent(history);

    /* Empty state handled by existing #history-empty — nothing to render */
    if (!stats) return;

    /* Stats card */
    panel.appendChild(buildStatsCard(stats));

    /* Trend chart */
    var chartSection = document.createElement('div');
    chartSection.style.cssText = 'margin-bottom:4px;';
    var chartLabel = document.createElement('div');
    chartLabel.style.cssText = [
      'font-size:10px',
      'text-transform:uppercase',
      'letter-spacing:0.07em',
      'color:' + textDim2(),
      'margin-bottom:10px',
    ].join(';');
    chartLabel.textContent = 'Last ' + recent.length + ' Sessions';
    chartSection.appendChild(chartLabel);
    chartSection.appendChild(buildTrendChart(recent));
    panel.appendChild(chartSection);

    /* Sparklines */
    panel.appendChild(buildSparkSection(history));
  }

  /* ── Public API ─────────────────────────────────────────────────────── */
  window.DealSimScoreTrends = {
    /**
     * init — call once when the history section becomes visible.
     * @param {string} containerId  ID of the card element wrapping #history-chart
     */
    init: function (containerId) {
      if (_mounted) { render(); return; }
      mount(containerId);
    },

    /**
     * update — re-render after new data is written to localStorage.
     * Call this from saveScoreToHistory() if you want live refresh.
     */
    update: function () {
      render();
    },
  };

})();
