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

/* ── Metric metadata (populated dynamically from DynamoDB metadata) ── */
const METRIC_META = {};

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
  setupChartModal();

  const isLocal = DATA_BASE_URL === 'output' || DATA_BASE_URL.startsWith('.');
  els.dataSourceLabel.textContent = isLocal ? 'Local' : 'S3 / CDN';

  // Fetch global metadata.json registry if present
  try {
    const metaResp = await fetch(`${DATA_BASE_URL}/metadata.json`);
    if (metaResp.ok) {
      const metaData = await metaResp.json();
      if (metaData && metaData.metrics) {
        Object.entries(metaData.metrics).forEach(([id, m]) => {
          METRIC_META[id] = {
            name: m.name,
            unit: m.unit || '',
            icon: m.icon || '📊',
            minYRange: m.minYRange
          };
        });
      }
    }
  } catch (ignored) {}

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

/* ════════════════════════════════════════════════════════════════
   JSON DATA SIDECAR FETCH & CACHE
════════════════════════════════════════════════════════════════ */
const jsonCache = new Map();

async function fetchChartJson(url) {
  if (jsonCache.has(url)) return jsonCache.get(url);
  try {
    const resp = await fetch(url);
    if (!resp.ok) return null;
    const data = await resp.json();
    jsonCache.set(url, data);

    if (data && data.metricId && data.metricName) {
      if (!METRIC_META[data.metricId] || !METRIC_META[data.metricId].icon || METRIC_META[data.metricId].icon === '📊') {
        METRIC_META[data.metricId] = {
          name: data.metricName,
          unit: data.unit || '',
          icon: data.icon || (METRIC_META[data.metricId]?.icon) || '📊'
        };
      }
    }

    return data;
  } catch (err) {
    return null;
  }
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
  const tilesList = [];

  metricIds.forEach(metId => {
    const meta = METRIC_META[metId] || { name: `Metric ${metId}`, unit: '', icon: '📊' };
    const imgUrl = `${DATA_BASE_URL}/${deviceId}/${metId}/${y}/${m}/${metId}-${y}${m}${d}.png`;
    const jsonUrl = `${DATA_BASE_URL}/${deviceId}/${metId}/${y}/${m}/${metId}-${y}${m}${d}.json`;

    const tile = document.createElement('div');
    tile.className = 'chart-tile';
    tile.dataset.metId = metId;

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
         <div class="crosshair-line"></div>
         <div class="crosshair-dot"></div>
         <div class="chart-tooltip"></div>
       </div>`;

    tilesGrid.appendChild(tile);
    tilesList.push({ tile, metId, meta, imgUrl, jsonUrl });

    // Click tile to enlarge/expand chart to browser window size
    tile.addEventListener('click', () => {
      const imgEl = tile.querySelector('.tile-img');
      if (imgEl.src && !imgEl.classList.contains('loading')) {
        const titleText = `Device ${deviceId} · ${meta.name} — ${formatDate(dateStr)}`;
        openChartModal(imgUrl, jsonUrl, titleText, meta);
      }
    });

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

    // Fetch JSON sidecar
    fetchChartJson(jsonUrl).then(data => {
      if (data) tile.chartData = data;
    });
  });

  // Attach synchronized mouse tracking across tiles in day card
  const handlePointerMove = e => {
    const hoveredTile = e.target.closest('.chart-tile');
    if (!hoveredTile || !hoveredTile.chartData) return;

    const data = hoveredTile.chartData;
    const points = data.points;
    const plotArea = data.plotArea;
    if (!points || points.length === 0 || !plotArea) return;

    const imgEl = hoveredTile.querySelector('.tile-img');
    if (!imgEl || imgEl.classList.contains('loading')) return;

    const imgRect = imgEl.getBoundingClientRect();
    const plotLeftPx = imgRect.left + imgRect.width * (plotArea.x / plotArea.imageWidth);
    const plotWidthPx = imgRect.width * (plotArea.width / plotArea.imageWidth);

    if (plotWidthPx <= 0) return;

    let relX = (e.clientX - plotLeftPx) / plotWidthPx;
    relX = Math.max(0, Math.min(1, relX));

    const minTimeMs = points[0].epochMs;
    const maxTimeMs = points[points.length - 1].epochMs;
    const targetTimeMs = minTimeMs + relX * (maxTimeMs - minTimeMs);

    tilesList.forEach(({ tile, meta }) => {
      updateTileCrosshair(tile, targetTimeMs, meta);
    });
  };

  const handlePointerLeave = () => {
    tilesList.forEach(({ tile }) => {
      hideTileCrosshair(tile);
    });
  };

  card.addEventListener('mousemove', handlePointerMove);
  card.addEventListener('mouseleave', handlePointerLeave);

  card.appendChild(tilesGrid);
  return card;
}

function updateTileCrosshair(tile, targetTimeMs, meta) {
  const data = tile.chartData;
  if (!data || !data.points || data.points.length === 0 || !data.plotArea) {
    hideTileCrosshair(tile);
    return;
  }

  const wrapper = tile.querySelector('.tile-img-wrapper');
  const imgEl = tile.querySelector('.tile-img');
  const lineEl = tile.querySelector('.crosshair-line');
  const dotEl = tile.querySelector('.crosshair-dot');
  const ttEl = tile.querySelector('.chart-tooltip');

  if (!wrapper || !imgEl || imgEl.classList.contains('loading')) {
    hideTileCrosshair(tile);
    return;
  }

  const points = data.points;
  const plotArea = data.plotArea;
  const N = points.length;

  let bestPt = points[0];
  let bestIdx = 0;
  let minDiff = Math.abs(bestPt.epochMs - targetTimeMs);
  for (let i = 1; i < points.length; i++) {
    const diff = Math.abs(points[i].epochMs - targetTimeMs);
    if (diff < minDiff) {
      minDiff = diff;
      bestPt = points[i];
      bestIdx = i;
    }
  }

  const ptIndex = (bestPt.index !== undefined && bestPt.index !== null) ? bestPt.index : bestIdx;
  const ptFractionX = N > 1 ? (ptIndex / (N - 1)) : 0.5;

  const wrapperRect = wrapper.getBoundingClientRect();
  const imgRect = imgEl.getBoundingClientRect();

  const plotLeftPx = imgRect.left + imgRect.width * (plotArea.x / plotArea.imageWidth);
  const plotWidthPx = imgRect.width * (plotArea.width / plotArea.imageWidth);
  const plotTopPx = imgRect.top + imgRect.height * (plotArea.y / plotArea.imageHeight);
  const plotHeightPx = imgRect.height * (plotArea.height / plotArea.imageHeight);

  const lineX = (plotLeftPx - wrapperRect.left) + ptFractionX * plotWidthPx;

  let valRatio = 0.5;
  if (plotArea.yLowerBound !== undefined && plotArea.yUpperBound !== undefined && plotArea.yUpperBound > plotArea.yLowerBound) {
    valRatio = (bestPt.value - plotArea.yLowerBound) / (plotArea.yUpperBound - plotArea.yLowerBound);
  } else {
    let minVal = points[0].value;
    let maxVal = points[0].value;
    points.forEach(p => {
      if (p.value < minVal) minVal = p.value;
      if (p.value > maxVal) maxVal = p.value;
    });
    const valSpan = maxVal - minVal;
    valRatio = valSpan > 0 ? (bestPt.value - minVal) / valSpan : 0.5;
  }
  valRatio = Math.max(0, Math.min(1, valRatio));
  const dotY = (plotTopPx - wrapperRect.top) + (1 - valRatio) * plotHeightPx;

  if (lineEl) {
    lineEl.style.left = `${lineX}px`;
    lineEl.classList.add('active');
  }

  if (dotEl) {
    dotEl.style.left = `${lineX}px`;
    dotEl.style.top = `${dotY}px`;
    dotEl.classList.add('active');
  }

  if (ttEl) {
    const icon = meta.icon || '📊';
    const unit = data.unit || meta.unit || '';
    ttEl.innerHTML = `<div class="tt-time">${bestPt.time}</div><div class="tt-val"><span>${icon}</span><span>${bestPt.value} ${unit}</span></div>`;
    ttEl.style.left = `${lineX}px`;
    ttEl.style.top = `${dotY}px`;

    const wrapperWidth = wrapperRect.width;
    let transformX = '-50%';
    if (lineX > wrapperWidth - 95) {
      transformX = '-100%';
    } else if (lineX < 95) {
      transformX = '0%';
    }
    ttEl.style.transform = `translate(${transformX}, -125%)`;
    ttEl.classList.add('active');
  }
}

function hideTileCrosshair(tile) {
  tile.querySelector('.crosshair-line')?.classList.remove('active');
  tile.querySelector('.crosshair-dot')?.classList.remove('active');
  tile.querySelector('.chart-tooltip')?.classList.remove('active');
}

/* ════════════════════════════════════════════════════════════════
   CHART ENLARGE LIGHTBOX MODAL
════════════════════════════════════════════════════════════════ */
function setupChartModal() {
  const modal = $('chart-modal');
  const closeBtn = $('chart-modal-close');

  if (!modal) return;

  // Click anywhere on the modal or enlarged chart to collapse back to normal size
  modal.addEventListener('click', closeChartModal);
  if (closeBtn) {
    closeBtn.addEventListener('click', e => {
      e.stopPropagation();
      closeChartModal();
    });
  }

  // Keyboard Esc key to collapse
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && modal.classList.contains('active')) {
      closeChartModal();
    }
  });
}

function openChartModal(imgSrc, jsonUrl, titleText, meta) {
  const modal = $('chart-modal');
  const modalImg = $('chart-modal-img');
  const modalTitle = $('chart-modal-title');
  const wrapper = $('modal-img-wrapper');

  if (!modal || !modalImg || !wrapper) return;

  modalImg.src = imgSrc;
  if (modalTitle) modalTitle.textContent = titleText || '';

  // Clean previous crosshair elements
  wrapper.querySelectorAll('.crosshair-line, .crosshair-dot, .chart-tooltip').forEach(el => el.remove());

  const lineEl = document.createElement('div');
  lineEl.className = 'crosshair-line';
  const dotEl = document.createElement('div');
  dotEl.className = 'crosshair-dot';
  const ttEl = document.createElement('div');
  ttEl.className = 'chart-tooltip';

  wrapper.appendChild(lineEl);
  wrapper.appendChild(dotEl);
  wrapper.appendChild(ttEl);

  modal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';

  // Force reflow for smooth CSS opacity transition
  void modal.offsetWidth;
  modal.classList.add('active');
  modal.setAttribute('aria-hidden', 'false');

  if (jsonUrl) {
    fetchChartJson(jsonUrl).then(data => {
      if (!data || !data.points || data.points.length === 0 || !data.plotArea) return;

      const handleModalMove = e => {
        e.stopPropagation();
        const imgRect = modalImg.getBoundingClientRect();
        const wrapperRect = wrapper.getBoundingClientRect();
        const plotArea = data.plotArea;
        const points = data.points;
        const N = points.length;

        const plotLeftPx = imgRect.left + imgRect.width * (plotArea.x / plotArea.imageWidth);
        const plotWidthPx = imgRect.width * (plotArea.width / plotArea.imageWidth);
        const plotTopPx = imgRect.top + imgRect.height * (plotArea.y / plotArea.imageHeight);
        const plotHeightPx = imgRect.height * (plotArea.height / plotArea.imageHeight);

        if (plotWidthPx <= 0) return;

        let relX = (e.clientX - plotLeftPx) / plotWidthPx;
        relX = Math.max(0, Math.min(1, relX));

        const minTimeMs = points[0].epochMs;
        const maxTimeMs = points[points.length - 1].epochMs;
        const targetTimeMs = minTimeMs + relX * (maxTimeMs - minTimeMs);

        let bestPt = points[0];
        let bestIdx = 0;
        let minDiff = Math.abs(bestPt.epochMs - targetTimeMs);
        for (let i = 1; i < points.length; i++) {
          const diff = Math.abs(points[i].epochMs - targetTimeMs);
          if (diff < minDiff) {
            minDiff = diff;
            bestPt = points[i];
            bestIdx = i;
          }
        }

        const ptIndex = (bestPt.index !== undefined && bestPt.index !== null) ? bestPt.index : bestIdx;
        const ptFractionX = N > 1 ? (ptIndex / (N - 1)) : 0.5;
        const lineX = (plotLeftPx - wrapperRect.left) + ptFractionX * plotWidthPx;

        let valRatio = 0.5;
        if (plotArea.yLowerBound !== undefined && plotArea.yUpperBound !== undefined && plotArea.yUpperBound > plotArea.yLowerBound) {
          valRatio = (bestPt.value - plotArea.yLowerBound) / (plotArea.yUpperBound - plotArea.yLowerBound);
        } else {
          let minVal = points[0].value;
          let maxVal = points[0].value;
          points.forEach(p => {
            if (p.value < minVal) minVal = p.value;
            if (p.value > maxVal) maxVal = p.value;
          });
          const valSpan = maxVal - minVal;
          valRatio = valSpan > 0 ? (bestPt.value - minVal) / valSpan : 0.5;
        }
        valRatio = Math.max(0, Math.min(1, valRatio));
        const dotY = (plotTopPx - wrapperRect.top) + (1 - valRatio) * plotHeightPx;

        lineEl.style.left = `${lineX}px`;
        lineEl.classList.add('active');

        dotEl.style.left = `${lineX}px`;
        dotEl.style.top = `${dotY}px`;
        dotEl.classList.add('active');

        const icon = (meta && meta.icon) ? meta.icon : '📊';
        const unit = data.unit || (meta && meta.unit) || '';
        ttEl.innerHTML = `<div class="tt-time">${bestPt.time}</div><div class="tt-val"><span>${icon}</span><span>${bestPt.value} ${unit}</span></div>`;
        ttEl.style.left = `${lineX}px`;
        ttEl.style.top = `${dotY}px`;

        const wrapperWidth = wrapperRect.width;
        let transformX = '-50%';
        if (lineX > wrapperWidth - 110) {
          transformX = '-100%';
        } else if (lineX < 110) {
          transformX = '0%';
        }
        ttEl.style.transform = `translate(${transformX}, -125%)`;
        ttEl.classList.add('active');
      };

      const handleModalLeave = () => {
        lineEl.classList.remove('active');
        dotEl.classList.remove('active');
        ttEl.classList.remove('active');
      };

      wrapper.onmousemove = handleModalMove;
      wrapper.onmouseleave = handleModalLeave;
    });
  }
}

function closeChartModal() {
  const modal = $('chart-modal');
  if (!modal || !modal.classList.contains('active')) return;

  modal.classList.remove('active');
  modal.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';

  setTimeout(() => {
    if (!modal.classList.contains('active')) {
      modal.classList.add('hidden');
    }
  }, 260);
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
