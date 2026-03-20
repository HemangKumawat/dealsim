/**
 * DealSimRadar — Pure SVG radar chart for Negotiation DNA display.
 * Renders 6 dimensions onto a hexagonal grid. No dependencies.
 */
(function () {
  'use strict';

  var SVG_NS = 'http://www.w3.org/2000/svg';
  var SIZE = 280;
  var CX = SIZE / 2;
  var CY = SIZE / 2;
  var RADIUS = 105;
  var RINGS = [0.33, 0.66, 1.0];
  var DOT_R = 4;
  var LABEL_OFFSET = 18;
  var AXES = 6;
  var ANGLE_OFFSET = -Math.PI / 2; // start from top

  function svgEl(tag) {
    return document.createElementNS(SVG_NS, tag);
  }

  function css(prop) {
    return getComputedStyle(document.documentElement).getPropertyValue(prop).trim();
  }

  function vertexXY(index, scale) {
    var angle = ANGLE_OFFSET + (2 * Math.PI * index) / AXES;
    return [CX + Math.cos(angle) * RADIUS * scale, CY + Math.sin(angle) * RADIUS * scale];
  }

  function hexPoints(scale) {
    var pts = [];
    for (var i = 0; i < AXES; i++) {
      var v = vertexXY(i, scale);
      pts.push(v[0] + ',' + v[1]);
    }
    return pts.join(' ');
  }

  function buildGrid(svg) {
    var gridColor = css('--text-dim2') || '#6b6f9e';

    // concentric hexagons
    RINGS.forEach(function (r) {
      var poly = svgEl('polygon');
      poly.setAttribute('points', hexPoints(r));
      poly.setAttribute('fill', 'none');
      poly.setAttribute('stroke', gridColor);
      poly.setAttribute('stroke-opacity', '0.15');
      poly.setAttribute('stroke-width', '1');
      svg.appendChild(poly);
    });

    // axis lines from center to each vertex
    for (var i = 0; i < AXES; i++) {
      var v = vertexXY(i, 1);
      var line = svgEl('line');
      line.setAttribute('x1', CX);
      line.setAttribute('y1', CY);
      line.setAttribute('x2', v[0]);
      line.setAttribute('y2', v[1]);
      line.setAttribute('stroke', gridColor);
      line.setAttribute('stroke-opacity', '0.15');
      line.setAttribute('stroke-width', '1');
      svg.appendChild(line);
    }
  }

  function buildLabels(svg, labels) {
    var labelColor = css('--text-dim') || '#b0b3d6';

    labels.forEach(function (label, i) {
      var v = vertexXY(i, 1);
      var angle = ANGLE_OFFSET + (2 * Math.PI * i) / AXES;
      var dx = Math.cos(angle) * LABEL_OFFSET;
      var dy = Math.sin(angle) * LABEL_OFFSET;

      var text = svgEl('text');
      text.setAttribute('x', v[0] + dx);
      text.setAttribute('y', v[1] + dy);
      text.setAttribute('fill', labelColor);
      text.setAttribute('font-size', '11');
      text.setAttribute('font-family', 'inherit');
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('dominant-baseline', 'central');
      text.textContent = label;
      svg.appendChild(text);
    });
  }

  function buildDataLayer(svg, values, animate) {
    var accent = css('--accent') || '#f95c5c';
    var group = svgEl('g');
    group.setAttribute('class', 'radar-data');

    // data polygon
    var pts = [];
    values.forEach(function (val, i) {
      var scale = Math.max(0, Math.min(val, 100)) / 100;
      var v = vertexXY(i, scale);
      pts.push(v[0] + ',' + v[1]);
    });

    var poly = svgEl('polygon');
    poly.setAttribute('points', pts.join(' '));
    poly.setAttribute('fill', accent);
    poly.setAttribute('fill-opacity', '0.2');
    poly.setAttribute('stroke', accent);
    poly.setAttribute('stroke-opacity', '0.8');
    poly.setAttribute('stroke-width', '2');
    poly.setAttribute('stroke-linejoin', 'round');

    if (animate) {
      poly.style.opacity = '0';
      poly.style.transition = 'opacity 0.4s ease';
      setTimeout(function () { poly.style.opacity = '1'; }, 30);
    }

    group.appendChild(poly);

    // vertex dots
    values.forEach(function (val, i) {
      var scale = Math.max(0, Math.min(val, 100)) / 100;
      var v = vertexXY(i, scale);
      var dot = svgEl('circle');
      dot.setAttribute('cx', v[0]);
      dot.setAttribute('cy', v[1]);
      dot.setAttribute('r', DOT_R);
      dot.setAttribute('fill', accent);
      group.appendChild(dot);
    });

    svg.appendChild(group);
  }

  function buildEmptyMessage(svg) {
    var dimColor = css('--text-dim') || '#b0b3d6';
    var text = svgEl('text');
    text.setAttribute('x', CX);
    text.setAttribute('y', CY);
    text.setAttribute('fill', dimColor);
    text.setAttribute('font-size', '11');
    text.setAttribute('font-family', 'inherit');
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('dominant-baseline', 'central');
    text.setAttribute('opacity', '0.6');

    var line1 = svgEl('tspan');
    line1.setAttribute('x', CX);
    line1.setAttribute('dy', '-6');
    line1.textContent = 'Your negotiation DNA will';

    var line2 = svgEl('tspan');
    line2.setAttribute('x', CX);
    line2.setAttribute('dy', '16');
    line2.textContent = 'appear here after your first session';

    text.appendChild(line1);
    text.appendChild(line2);
    svg.appendChild(text);
  }

  function createSVG() {
    var svg = svgEl('svg');
    svg.setAttribute('viewBox', '0 0 ' + SIZE + ' ' + SIZE);
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', '100%');
    svg.style.maxWidth = SIZE + 'px';
    svg.style.display = 'block';
    return svg;
  }

  function renderInto(container, data, animate) {
    container.innerHTML = '';
    var svg = createSVG();
    var labels = data && data.labels ? data.labels : [
      'Opening Strategy', 'Information Gathering', 'Concession Pattern',
      'BATNA Usage', 'Emotional Control', 'Value Creation'
    ];
    var values = data && data.values ? data.values : null;

    buildGrid(svg);
    buildLabels(svg, labels);

    if (values && values.length > 0) {
      // Pad to AXES dimensions with zeros if fewer than 6
      var padded = values.slice();
      while (padded.length < AXES) padded.push(0);
      buildDataLayer(svg, padded.slice(0, AXES), animate);
    } else {
      buildEmptyMessage(svg);
    }

    container.appendChild(svg);
  }

  window.DealSimRadar = {
    render: function (containerId, data) {
      var el = document.getElementById(containerId);
      if (!el) return;
      renderInto(el, data, false);
    },

    update: function (containerId, data) {
      var el = document.getElementById(containerId);
      if (!el) return;
      renderInto(el, data, true);
    }
  };
})();
