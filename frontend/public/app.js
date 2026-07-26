/**
 * PiLambdaChart Dashboard — app.js v2
 *
 * Layout: Device selector + Year/Month navigator in sidebar.
 * Main content: month view — all days descending, each day shows
 * all available metric charts as a tile grid.
 *
 * On first load: auto-selects the first device with data and the
 * most recent month, so charts appear immediately.
 *
 * Configuration:
 *   DATA_BASE_URL  — base URL of the output folder.
 *     • Local:          'output'   (relative to index.html)
 *     • S3/CloudFront:  set via <meta name="data-base-url" content="...">
 *                       or window.PILAMBDACHART_BASE_URL
 */

/* ── Configuration ──────────────────────────────────────────────── */
const DATA_BASE_URL = (() => {
  if (typeof window.PILAMBDACHART_BASE_URL === 'string') return window.PILAMBDACHART_BASE_URL;
  const meta = document.querySelector('meta[name="data-base-url"]');
  if (meta) return meta.content.replace(/\/$/, '');
  return 'output';
})();

/* ── Metric metadata ────────────────────────────────────────────── */
const METRIC_META = {
  1: { name: 'Temperature',   unit: '°C',           icon: '🌡️' },
  2: { name: 'Humidity',      unit: '%',             icon: '💧' },
  3: { name: 'Ambient Light', unit: 'Lux',           icon: '☀️' },
  4: { name: 'Motion Count',  unit: 'triggers/min',  icon: '🔍' },
  5: { name: 'Water Level',   unit: 'cm',            icon: '📏' },
};

/* ── State ──────────────────────────────────────────────────────── */
const state = {
  fileTree:       null,   // parsed file-list.json
  deviceId:       null,   // currently selected device ID string
  selectedYearMo: null,   // currently selected "YYYY/MM"
};

/* ── DOM refs ───────────────────────────────────────────────────── */
const $ = id => document.getElementById(id);
const els = {
  sidebar:        $('sidebar'),
  sidebarToggle:  $('sidebar-toggle'),
  mobileToggle:   $('mobile-toggle'),
  sidebarOverlay: $('sidebar-overlay'),
  deviceList:     $('device-list'),
  historyLabel:   $('history-label'),
  monthList:      $('month-list'),
  dataSourceLabel:$('data-source-label'),
  monthBadge:     $('month-badge'),
  mainLoading:    $('main-loading'),
  monthView:      $('month-view'),
  contentFooter:  $('content-footer'),
};

/* ════════════════════════════════════════════════════════════════
   BOOTSTRAP
════════════════════════════════════════════════════════════════ */
async function init() {
  setupSidebar();

  const isLocal = DATA_BASE_URL === 'output' || DATA_BASE_URL.startsWith('.');
  els.dataSourceLabel.textContent = isLocal ? 'Local' : 'S3 / CDN';

  try {
    const resp = await fetch(`${DATA_BASE_URL}/file-list.json`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    state.fileTree = await resp.json();
    buildDeviceList();
    autoSelectFirst();
  } catch (err) {
    els.deviceList.innerHTML =
      `<div class="sidebar-loading" style="color:hsl(38,90%,58%)">
         <span>⚠️</span>
         <span style="white-space:normal;font-size:0.78rem">
           Could not load file-list.json<br>
           <span style="color:var(--text-muted)">${err.message}</span>
         </span>
       </div>`;
    showFooter();
    console.error('file-list.json error:', err);
  }
}

/* ════════════════════════════════════════════════════════════════
   SIDEBAR — DEVICE LIST
════════════════════════════════════════════════════════════════ */
function buildDeviceList() {
  const deviceIds = Object.keys(state.fileTree).sort((a, b) => +a - +b);

  if (deviceIds.length === 0) {
    els.deviceList.innerHTML =
      '<div class="sidebar-loading"><span>No devices found.</span></div>';
    return;
  }

  els.deviceList.innerHTML = '';
  deviceIds.forEach(devId => {
    const btn = document.createElement('button');
    btn.className = 'device-btn';
    btn.id = `dev-btn-${devId}`;
    btn.dataset.deviceId = devId;
    btn.innerHTML =
      `<span class="device-btn-icon">🖥️</span>
       <span class="device-btn-label">Device ${devId}</span>`;
    btn.addEventListener('click', () => selectDevice(devId));
    els.deviceList.appendChild(btn);
  });
}

/* ════════════════════════════════════════════════════════════════
   AUTO-SELECT: first device + most recent month on page load
════════════════════════════════════════════════════════════════ */
function autoSelectFirst() {
  const deviceIds = Object.keys(state.fileTree).sort((a, b) => +a - +b);
  if (deviceIds.length === 0) { showFooter(); return; }
  selectDevice(deviceIds[0], /* initial */ true);
}

/* ════════════════════════════════════════════════════════════════
   SELECT DEVICE
════════════════════════════════════════════════════════════════ */
function selectDevice(devId, initial = false) {
  state.deviceId = devId;

  // Update active state
  document.querySelectorAll('.device-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`dev-btn-${devId}`)?.classList.add('active');

  // Build year/month navigator for this device
  const months = getDeviceMonths(devId); // descending ["2026/07", "2026/06", ...]

  els.historyLabel.style.display = '';
  els.monthList.innerHTML = '';

  if (months.length === 0) {
    els.monthList.innerHTML =
      '<div class="sidebar-loading"><span style="font-size:0.78rem">No data for this device.</span></div>';
    showFooter();
    return;
  }

  months.forEach((ym, idx) => {
    const [yr, mo] = ym.split('/');
    const label = formatYearMonth(yr, mo);
    const btn = document.createElement('button');
    btn.className = 'month-btn';
    btn.id = `month-btn-${ym.replace('/', '-')}`;
    btn.dataset.yearmo = ym;
    btn.innerHTML =
      `<span class="month-btn-dot"></span>
       <span class="month-btn-label">${label}</span>`;
    btn.addEventListener('click', () => selectYearMonth(ym));
    els.monthList.appendChild(btn);
  });

  // Auto-select most recent month
  const mostRecent = months[0];
  selectYearMonth(mostRecent);

  if (window.innerWidth <= 860 && !initial) closeMobileSidebar();
}

/* ════════════════════════════════════════════════════════════════
   SELECT YEAR/MONTH
════════════════════════════════════════════════════════════════ */
function selectYearMonth(ym) {
  state.selectedYearMo = ym;
  const [yr, mo] = ym.split('/');

  // Update active state in month list
  document.querySelectorAll('.month-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`month-btn-${ym.replace('/', '-')}`)?.classList.add('active');

  // Update topbar badge
  els.monthBadge.textContent = formatYearMonth(yr, mo);

  // Hide footer, show loading
  hideFooter();
  els.mainLoading.classList.remove('hidden');
  els.monthView.innerHTML = '';

  // Small delay so the spinner is visible before heavy DOM work
  requestAnimationFrame(() => renderMonthView(yr, mo));
}

/* ════════════════════════════════════════════════════════════════
   RENDER MONTH VIEW
════════════════════════════════════════════════════════════════ */
function renderMonthView(year, month) {
  const { deviceId, fileTree } = state;
  const dates = getDatesInMonth(deviceId, year, month); // descending

  els.mainLoading.classList.add('hidden');

  if (dates.length === 0) {
    els.monthView.innerHTML =
      `<div style="text-align:center;padding:60px 0;color:var(--text-muted);font-size:0.88rem">
         No charts for ${formatYearMonth(year, month)} yet.
       </div>`;
    return;
  }

  els.monthView.innerHTML = '';

  // Today string for "Today" / "Yesterday" tags
  const todayStr = toLocalDateStr(new Date());
  const yesterdayStr = toLocalDateStr(new Date(Date.now() - 86400000));

  dates.forEach(dateStr => {
    const metricIds = getMetricsForDate(deviceId, dateStr, year, month);
    if (metricIds.length === 0) return;

    const card = buildDayCard(deviceId, dateStr, metricIds, todayStr, yesterdayStr);
    els.monthView.appendChild(card);
  });
}

/* ── Build one day card ─────────────────────────────────────────── */
function buildDayCard(deviceId, dateStr, metricIds, todayStr, yesterdayStr) {
  const card = document.createElement('div');
  card.className = 'day-card';

  // Header row
  const header = document.createElement('div');
  header.className = 'day-header';

  const dateLabel = document.createElement('span');
  dateLabel.className = 'day-date';
  dateLabel.textContent = formatDate(dateStr);

  header.appendChild(dateLabel);

  // Today / Yesterday tag
  if (dateStr === todayStr) {
    const tag = document.createElement('span');
    tag.className = 'day-tag';
    tag.textContent = 'Today';
    header.appendChild(tag);
  } else if (dateStr === yesterdayStr) {
    const tag = document.createElement('span');
    tag.className = 'day-tag';
    tag.textContent = 'Yesterday';
    header.appendChild(tag);
  }

  const divider = document.createElement('div');
  divider.className = 'day-divider';
  header.appendChild(divider);

  card.appendChild(header);

  // Tile grid
  const cols = metricIds.length === 1 ? 1 : 2;
  const tilesGrid = document.createElement('div');
  tilesGrid.className = 'chart-tiles';
  tilesGrid.style.setProperty('--tile-cols', cols);

  const [y, m, d] = dateStr.split('-');

  metricIds.forEach(metId => {
    const meta = METRIC_META[metId] || { name: `Metric ${metId}`, unit: '', icon: '📊' };
    const imgUrl = `${DATA_BASE_URL}/${deviceId}/${metId}/${y}/${m}/${metId}-${y}${m}${d}.png`;

    const tile = document.createElement('div');
    tile.className = 'chart-tile';

    tile.innerHTML =
      `<div class="tile-header">
         <span>${meta.icon}</span>
         <span class="tile-metric-name">${meta.name}</span>
       </div>
       <div class="tile-img-wrapper" id="tile-wrap-${deviceId}-${metId}-${y}${m}${d}">
         <div class="tile-placeholder">
           <div class="spinner spinner-sm"></div>
         </div>
         <img class="tile-img loading"
              alt="${meta.name} chart for ${dateStr}"
              loading="lazy" />
       </div>`;

    tilesGrid.appendChild(tile);

    // Load the image using a detached Image() to avoid caching issues
    const imgEl = tile.querySelector('.tile-img');
    const placeholder = tile.querySelector('.tile-placeholder');
    const loader = new Image();
    loader.onload = () => {
      imgEl.src = imgUrl;
      imgEl.classList.remove('loading');
      placeholder.style.display = 'none';
    };
    loader.onerror = () => {
      placeholder.innerHTML =
        `<span class="tile-error">Chart not available</span>`;
    };
    loader.src = imgUrl;
  });

  card.appendChild(tilesGrid);
  return card;
}

/* ════════════════════════════════════════════════════════════════
   DATA HELPERS
════════════════════════════════════════════════════════════════ */

/** All year/months with data for a device, sorted descending. */
function getDeviceMonths(deviceId) {
  const metricsMap = state.fileTree[deviceId] || {};
  const monthSet = new Set();
  Object.values(metricsMap).forEach(yearsMap => {
    Object.keys(yearsMap).forEach(yr => {
      Object.keys(yearsMap[yr]).forEach(mo => {
        if ((yearsMap[yr][mo] || []).length > 0) monthSet.add(`${yr}/${mo}`);
      });
    });
  });
  return Array.from(monthSet).sort().reverse(); // e.g. ["2026/07", "2026/06"]
}

/** All dates in a given month for a device (across all metrics), sorted descending. */
function getDatesInMonth(deviceId, year, month) {
  const metricsMap = state.fileTree[deviceId] || {};
  const dateSet = new Set();
  Object.values(metricsMap).forEach(yearsMap => {
    const keys = (yearsMap[year] || {})[month] || [];
    keys.forEach(key => {
      const m = key.match(/(\d{8})\.png$/);
      if (m) {
        const raw = m[1];
        dateSet.add(`${raw.slice(0,4)}-${raw.slice(4,6)}-${raw.slice(6,8)}`);
      }
    });
  });
  return Array.from(dateSet).sort().reverse(); // descending
}

/** Metric IDs available for a specific device + date combination. */
function getMetricsForDate(deviceId, dateStr, year, month) {
  const metricsMap = state.fileTree[deviceId] || {};
  const dateCode = dateStr.replace(/-/g, '');
  return Object.keys(metricsMap)
    .filter(metId => {
      const keys = (metricsMap[metId][year] || {})[month] || [];
      return keys.some(k => k.includes(dateCode));
    })
    .sort((a, b) => +a - +b);
}

/* ════════════════════════════════════════════════════════════════
   FOOTER VISIBILITY
════════════════════════════════════════════════════════════════ */
function showFooter() { els.contentFooter.classList.remove('hidden'); }
function hideFooter() { els.contentFooter.classList.add('hidden'); }

/* ════════════════════════════════════════════════════════════════
   SIDEBAR COLLAPSE / MOBILE
════════════════════════════════════════════════════════════════ */
function setupSidebar() {
  els.sidebarToggle.addEventListener('click', () => {
    const c = els.sidebar.classList.toggle('collapsed');
    document.body.classList.toggle('sidebar-collapsed', c);
    els.sidebarToggle.setAttribute('aria-label', c ? 'Expand sidebar' : 'Collapse sidebar');
  });
  els.mobileToggle.addEventListener('click', () => {
    els.sidebar.classList.add('mobile-open');
    els.sidebarOverlay.classList.add('visible');
  });
  els.sidebarOverlay.addEventListener('click', closeMobileSidebar);
}

function closeMobileSidebar() {
  els.sidebar.classList.remove('mobile-open');
  els.sidebarOverlay.classList.remove('visible');
}

/* ════════════════════════════════════════════════════════════════
   FORMATTING HELPERS
════════════════════════════════════════════════════════════════ */
function formatDate(dateStr) {
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-US',
    { year: 'numeric', month: 'long', day: 'numeric' });
}

function formatYearMonth(year, month) {
  return new Date(+year, +month - 1, 1).toLocaleDateString('en-US',
    { year: 'numeric', month: 'long' });
}

/** Returns YYYY-MM-DD for a local Date object (no UTC shift). */
function toLocalDateStr(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/* ════════════════════════════════════════════════════════════════
   START
════════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', init);
