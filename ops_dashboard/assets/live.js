'use strict';
// Live mode only. This script is not part of the snapshot file, so the snapshot never makes a request.
(function () {
  var POLL_MS = 30000;
  var TIMEOUT_MS = 10000;
  var STALE_AFTER_S = 180;

  var version = document.body.getAttribute('data-version') || '';
  var status = null;
  var contacted = false;
  var reachable = true;
  var inflight = false;
  var pending = null;

  function nowS() { return Date.now() / 1000; }

  function age(seconds) {
    var s = Math.max(0, Math.round(seconds));
    if (s < 60) return s + ' s';
    if (s < 3600) return Math.floor(s / 60) + ' min';
    return Math.floor(s / 3600) + ' h ' + Math.floor((s % 3600) / 60) + ' min';
  }

  function paint() {
    var pill = document.getElementById('live-pill');
    if (!pill) return;
    var state = 'connecting';
    var text = 'Connecting';
    var title = '';
    if (contacted && status && status.refreshed_at) {
      var since = nowS() - status.refreshed_at;
      var tail = ' · updated ' + age(since) + ' ago';
      if (!reachable) {
        state = 'offline';
        text = 'Server unreachable' + tail;
        title = 'The page could not reach the local server. It keeps trying.';
      } else if (!status.ok || since > STALE_AFTER_S) {
        state = 'stale';
        text = 'Stale' + tail;
        title = status.error ? 'Last refresh failed: ' + status.error : 'No recent refresh from Azure.';
      } else {
        state = 'live';
        text = 'Live' + tail;
        if (status.query_errors) {
          text += ' · ' + status.query_errors + ' query error' + (status.query_errors === 1 ? '' : 's');
          title = 'Some Azure queries failed in the last refresh. See Data quality at the bottom of the page.';
        }
      }
    } else if (contacted && !reachable) {
      state = 'offline';
      text = 'Server unreachable';
    } else if (contacted) {
      text = 'Waiting for first Azure query';
      if (status && status.error) {
        state = 'stale';
        text = 'Azure query failed';
        title = status.error;
      }
    }
    if (pending) text += ' · new data on hold';
    pill.setAttribute('data-state', state);
    pill.textContent = text;
    if (title) pill.setAttribute('title', title);
    else pill.removeAttribute('title');
  }

  function swap(data) {
    var scroll = window.scrollY;
    var focused = document.activeElement && document.activeElement.id ? document.activeElement.id : '';
    document.getElementById('app').innerHTML = data.body;
    document.getElementById('report-data').textContent = JSON.stringify(data.payload);
    document.title = data.title;
    version = data.version;
    document.body.setAttribute('data-version', version);
    window.OpsDashboard.mount();
    window.scrollTo(0, scroll);
    if (focused) {
      var again = document.getElementById(focused);
      if (again && again.focus) again.focus({ preventScroll: true });
    }
  }

  function apply(data) {
    if (window.OpsDashboard.isBusy()) {
      pending = data;
      return;
    }
    pending = null;
    swap(data);
  }

  function flush() {
    if (pending && !window.OpsDashboard.isBusy()) {
      var data = pending;
      pending = null;
      swap(data);
    }
  }

  function poll() {
    if (document.hidden || inflight) return;
    inflight = true;
    var control = new AbortController();
    var timer = window.setTimeout(function () { control.abort(); }, TIMEOUT_MS);
    var known = pending ? pending.version : version;
    fetch('/api/report?version=' + encodeURIComponent(known), { signal: control.signal, cache: 'no-store' })
      .then(function (response) {
        if (response.status === 503) return response.json();
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return response.json();
      })
      .then(function (data) {
        contacted = true;
        reachable = true;
        status = data.status;
        if (data.changed) apply(data);
      })
      .catch(function () {
        contacted = true;
        reachable = false;
      })
      .then(function () {
        window.clearTimeout(timer);
        inflight = false;
        paint();
      });
  }

  window.setInterval(poll, POLL_MS);
  window.setInterval(function () { flush(); paint(); }, 1000);
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) poll();
  });
  poll();
})();
