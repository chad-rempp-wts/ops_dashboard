'use strict';
var REPORT = JSON.parse(document.getElementById('report-data').textContent);

const PT_FMT = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Los_Angeles',
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23'
});
function ptParts(epoch) {
  const bag = { weekday: '', month: '', day: '', hour: '', minute: '' };
  const parts = PT_FMT.formatToParts(new Date(epoch * 1000));
  for (let i = 0; i < parts.length; i++) {
    if (Object.prototype.hasOwnProperty.call(bag, parts[i].type)) bag[parts[i].type] = parts[i].value;
  }
  return bag;
}
function formatWhen(epoch) {
  const p = ptParts(epoch);
  return p.weekday + ' ' + p.month + ' ' + Number(p.day) + ', ' + p.hour + ':' + p.minute + ' PT';
}
function formatValue(v, format) {
  if (v == null) return 'No sample';
  if (format === 'pct1') return v.toFixed(1) + '%';
  if (format === 'pct2') return v.toFixed(2) + '%';
  if (format === 'pct3') return v.toFixed(3) + '%';
  if (format === 'ms') return Math.round(v).toLocaleString('en-US') + ' ms';
  if (format === 'int') return Math.round(v).toLocaleString('en-US');
  return String(v);
}
function formatTick(v, format) {
  if (format === 'int' || format === 'ms') return Math.round(v).toLocaleString('en-US');
  const digits = format === 'pct3' ? 3 : format === 'pct2' ? 2 : 1;
  let s = Number(v).toFixed(digits);
  s = s.replace(/\.0+$/, '').replace(/(\.[0-9]*?)0+$/, '$1');
  return s + '%';
}
function pathFrom(values, xOf, yOf) {
  let d = '';
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (v == null) continue;
    const x = xOf(i);
    const y = yOf(v);
    const prev = i > 0 && values[i - 1] != null;
    const next = i + 1 < values.length && values[i + 1] != null;
    if (!prev && !next) {
      d += 'M' + (x - 1.5).toFixed(1) + ',' + y.toFixed(1) + 'L' + (x + 1.5).toFixed(1) + ',' + y.toFixed(1);
    } else if (!prev) {
      d += 'M' + x.toFixed(1) + ',' + y.toFixed(1);
    } else {
      d += 'L' + x.toFixed(1) + ',' + y.toFixed(1);
    }
  }
  return d;
}
function bandNote(epoch, bands) {
  if (!bands) return '';
  for (let i = 0; i < bands.length; i++) {
    if (epoch >= bands[i].start && epoch <= bands[i].end) return bands[i].label;
  }
  return '';
}
function formatReadout(chart, index) {
  const epoch = REPORT.start + index * REPORT.step;
  const when = formatWhen(epoch);
  const bits = [];
  let allMissing = true;
  let total = 0;
  for (let s = 0; s < chart.series.length; s++) {
    const spec = chart.series[s];
    const v = REPORT.series[spec.key][index];
    if (v != null) allMissing = false;
    else total = null;
    if (total != null && v != null) total += v;
    bits.push(spec.name + ': ' + formatValue(v, chart.format));
  }
  if (chart.sum && total != null) bits.push('total: ' + formatValue(total, 'int'));
  if (chart.volume) {
    const v = REPORT.series[chart.volume][index];
    bits.push(v == null ? 'requests: No sample' : formatValue(v, 'int') + ' requests');
  }
  let extra = '';
  if (allMissing) {
    const note = bandNote(epoch, chart.bands);
    extra = note ? ' Gap (' + note + '), not zero.' : ' Gap, not zero.';
  }
  return when + ' — ' + bits.join(' · ') + '.' + extra;
}

var WIDTH = 1000;
var HEIGHT = 236;
var LEFT = 58;
var RIGHT = 14;
var TOP = 14;
var BOTTOM = 28;
var PLOT_W = WIDTH - LEFT - RIGHT;
var PLOT_H = HEIGHT - TOP - BOTTOM;
var hoverId = '';
var pinnedId = '';

function yOf(v, yMax) {
  if (!yMax) return TOP + PLOT_H;
  return TOP + (1 - v / yMax) * PLOT_H;
}
function xOf(i, n) {
  return LEFT + (i / (n - 1)) * PLOT_W;
}
function xml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
}
function mountChart(plot) {
  var id = plot.getAttribute('data-chart');
  var chart = REPORT.charts[id];
  var n = REPORT.count;
  var readout = plot.parentNode.querySelector('.readout');
  var markup = '';
  if (chart.bands) {
    for (var b = 0; b < chart.bands.length; b++) {
      var band = chart.bands[b];
      var i0 = Math.round((band.start - REPORT.start) / REPORT.step);
      var i1 = Math.round((band.end - REPORT.start) / REPORT.step);
      var x0 = xOf(i0, n);
      var x1 = xOf(i1, n);
      markup += '<rect class="band" x="' + x0.toFixed(1) + '" y="' + TOP + '" width="' + Math.max(1, x1 - x0).toFixed(1) + '" height="' + PLOT_H + '"></rect>';
    }
  }
  for (var t = 0; t < chart.ticks.length; t++) {
    var tick = chart.ticks[t];
    var y = yOf(tick, chart.yMax);
    markup += '<line class="grid" x1="' + LEFT + '" x2="' + (LEFT + PLOT_W) + '" y1="' + y.toFixed(1) + '" y2="' + y.toFixed(1) + '"></line>';
    markup += '<text x="' + (LEFT - 8) + '" y="' + (y + 4).toFixed(1) + '" text-anchor="end">' + xml(formatTick(tick, chart.format)) + '</text>';
  }
  for (var s = 0; s < chart.series.length; s++) {
    var key = chart.series[s].key;
    var d = pathFrom(REPORT.series[key], function (i) { return xOf(i, n); }, function (v) { return yOf(v, chart.yMax); });
    markup += '<path class="series-' + (s === 0 ? 'a' : 'b') + '" d="' + d + '"></path>';
  }
  for (var k = 0; k < chart.thresholds.length; k++) {
    var thr = chart.thresholds[k];
    var ty = yOf(thr.y, chart.yMax);
    markup += '<line class="thr-' + thr.kind + '" x1="' + LEFT + '" x2="' + (LEFT + PLOT_W) + '" y1="' + ty.toFixed(1) + '" y2="' + ty.toFixed(1) + '"></line>';
  }
  var epoch0 = REPORT.start;
  for (var i = 0; i < n; i++) {
    var p = ptParts(epoch0 + i * REPORT.step);
    if (p.hour === '00' && p.minute === '00') {
      markup += '<text class="xlab" x="' + xOf(i, n).toFixed(1) + '" y="' + (HEIGHT - 8) + '" text-anchor="middle">' + xml(p.month + ' ' + Number(p.day)) + '</text>';
    }
  }
  markup += '<line class="probe" x1="0" x2="0" y1="' + TOP + '" y2="' + (TOP + PLOT_H) + '"></line>';
  markup += '<circle class="dot-a" r="3.5" cx="0" cy="0"></circle>';
  markup += '<circle class="dot-b" r="3.5" cx="0" cy="0" visibility="hidden"></circle>';
  plot.innerHTML = '<svg viewBox="0 0 ' + WIDTH + ' ' + HEIGHT + '" aria-hidden="true">' + markup + '</svg>';
  var svg = plot.querySelector('svg');
  var probe = svg.querySelector('.probe');
  var dots = [svg.querySelector('.dot-a'), svg.querySelector('.dot-b')];
  var idx = n - 1;
  function show(index) {
    idx = index;
    var x = xOf(index, n);
    probe.setAttribute('x1', x.toFixed(1));
    probe.setAttribute('x2', x.toFixed(1));
    for (var si = 0; si < dots.length; si++) {
      if (!chart.series[si]) {
        dots[si].setAttribute('visibility', 'hidden');
        continue;
      }
      var value = REPORT.series[chart.series[si].key][index];
      if (value == null) dots[si].setAttribute('visibility', 'hidden');
      else {
        dots[si].removeAttribute('visibility');
        dots[si].setAttribute('cx', x.toFixed(1));
        dots[si].setAttribute('cy', yOf(value, chart.yMax).toFixed(1));
      }
    }
    readout.textContent = formatReadout(chart, index);
  }
  function indexAt(x) {
    var i = Math.round(((x - LEFT) / PLOT_W) * (n - 1));
    if (i < 0) i = 0;
    if (i > n - 1) i = n - 1;
    return i;
  }
  svg.addEventListener('pointermove', function (event) {
    var rect = svg.getBoundingClientRect();
    if (!rect.width) return;
    var x = ((event.clientX - rect.left) / rect.width) * WIDTH;
    show(indexAt(x));
  });
  plot.addEventListener('keydown', function (event) {
    var step = event.shiftKey ? 12 : 1;
    var next = idx;
    if (event.key === 'ArrowRight') next = Math.min(n - 1, idx + step);
    else if (event.key === 'ArrowLeft') next = Math.max(0, idx - step);
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = n - 1;
    else return;
    event.preventDefault();
    show(next);
  });
  show(n - 1);
}
function drawLinks() {
  var root = document.querySelector('.board');
  var svg = document.getElementById('links');
  var spine = document.querySelector('.spine');
  if (!root || !svg || !spine) return;
  if (window.matchMedia('(max-width: 1100px)').matches || root.getBoundingClientRect().width < 40) {
    svg.textContent = '';
    return;
  }
  var rb = root.getBoundingClientRect();
  svg.setAttribute('viewBox', '0 0 ' + root.clientWidth + ' ' + root.clientHeight);
  svg.setAttribute('width', String(root.clientWidth));
  svg.setAttribute('height', String(root.clientHeight));
  var sr = spine.getBoundingClientRect();
  var channelX = (sr.left - rb.left) + sr.width / 2;
  var active = hoverId || pinnedId;
  var markup = '';
  for (var i = 0; i < REPORT.links.length; i++) {
    var from = REPORT.links[i][0];
    var to = REPORT.links[i][1];
    var host = REPORT.links[i][2] === 1;
    var a = root.querySelector('[data-id="' + from + '"]');
    var b = root.querySelector('[data-id="' + to + '"]');
    if (!a || !b) continue;
    var ar = a.getBoundingClientRect();
    var br = b.getBoundingClientRect();
    var x1 = ar.left - rb.left + ar.width / 2;
    var y1 = ar.bottom - rb.top;
    var x2 = br.left - rb.left + br.width / 2;
    var y2 = br.top - rb.top;
    if (y2 <= y1 + 8) continue;
    var same = REPORT.stacks[from] === REPORT.stacks[to];
    var adjacent = same && Math.abs(REPORT.layers[from] - REPORT.layers[to]) === 1;
    var pts;
    if (adjacent) {
      var mid = y1 + (y2 - y1) * 0.55;
      pts = [[x1, y1], [x1, mid], [x2, mid], [x2, y2]];
    } else {
      var yA = y1 + 10;
      var yB = y2 - 10;
      if (yB <= yA) yB = yA + 4;
      pts = [[x1, y1], [x1, yA], [channelX, yA], [channelX, yB], [x2, yB], [x2, y2]];
    }
    var d = 'M' + pts[0][0].toFixed(1) + ' ' + pts[0][1].toFixed(1);
    for (var p = 1; p < pts.length; p++) d += ' L' + pts[p][0].toFixed(1) + ' ' + pts[p][1].toFixed(1);
    d += ' M' + (x2 - 4.5).toFixed(1) + ' ' + (y2 - 7).toFixed(1) + ' L' + x2.toFixed(1) + ' ' + y2.toFixed(1) + ' L' + (x2 + 4.5).toFixed(1) + ' ' + (y2 - 7).toFixed(1);
    var hot = active && (active === from || active === to);
    var dim = active && !hot;
    var cls = 'link';
    if (host) cls += ' host';
    if (hot) cls += ' hot';
    if (dim) cls += ' dim';
    markup += '<path class="' + cls + '" d="' + d + '"></path>';
  }
  svg.innerHTML = markup;
}
function syncSelection() {
  var id = location.hash.replace('#', '');
  if (!/^[a-z0-9-]+$/.test(id)) id = '';
  pinnedId = id;
  var prev = document.querySelectorAll('.is-selected');
  for (var i = 0; i < prev.length; i++) prev[i].classList.remove('is-selected');
  if (id) {
    var detail = document.getElementById(id);
    if (detail) detail.classList.add('is-selected');
    var node = document.querySelector('.board [data-id="' + id + '"]');
    if (node) node.classList.add('is-selected');
  }
  drawLinks();
}
function setView(view) {
  document.body.setAttribute('data-view', view);
  document.getElementById('show-map').setAttribute('aria-pressed', view === 'map' ? 'true' : 'false');
  document.getElementById('show-list').setAttribute('aria-pressed', view === 'list' ? 'true' : 'false');
  window.requestAnimationFrame(drawLinks);
}
document.getElementById('show-map').addEventListener('click', function () { setView('map'); });
document.getElementById('show-list').addEventListener('click', function () { setView('list'); });
document.getElementById('theme').addEventListener('click', function () {
  var root = document.documentElement;
  var light = root.getAttribute('data-theme') !== 'light';
  root.setAttribute('data-theme', light ? 'light' : 'dark');
  var btn = document.getElementById('theme');
  btn.setAttribute('aria-pressed', light ? 'true' : 'false');
  btn.textContent = light ? 'Switch to dark mode' : 'Switch to light mode';
});
var plots = document.querySelectorAll('.plot');
for (var pi = 0; pi < plots.length; pi++) mountChart(plots[pi]);
var board = document.querySelector('.board');
board.addEventListener('mouseover', function (event) {
  var node = event.target.closest('[data-id]');
  var id = node ? node.getAttribute('data-id') : '';
  if (id !== hoverId) { hoverId = id; drawLinks(); }
});
board.addEventListener('mouseout', function (event) {
  var node = event.target.closest('[data-id]');
  if (!node) return;
  var next = event.relatedTarget && event.relatedTarget.closest ? event.relatedTarget.closest('[data-id]') : null;
  if (next === node) return;
  hoverId = next ? next.getAttribute('data-id') : '';
  drawLinks();
});
window.addEventListener('hashchange', syncSelection);
window.addEventListener('resize', drawLinks);
if (window.ResizeObserver) new ResizeObserver(drawLinks).observe(board);
window.matchMedia('(max-width: 1100px)').addEventListener('change', drawLinks);
syncSelection();
document.body.addEventListener('click', function (event) {
  var link = event.target.closest('a[href^="#"]');
  if (!link) return;
  window.setTimeout(syncSelection, 0);
});
