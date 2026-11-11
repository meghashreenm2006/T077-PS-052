/**
 * Cold-Chain Compliance Dashboard — app.js
 * Team T077 / PS-052
 *
 * Fetches live data from the FastAPI backend (/api/*) and renders:
 * - KPI summary cards
 * - Decision breakdown doughnut chart
 * - Shipment status bar chart
 * - Per-shipment status cards with click-to-detail
 * - Temperature graphs via Chart.js
 * - Excursion report table
 * - Claims & Penalties dashboard
 * - Release certificates
 * - Quarantine deviation report
 */

'use strict';

// ─── State ────────────────────────────────────────────────────────
let _dashboardData   = null;
let _excursionData   = [];
let _penaltyData     = [];
let _claimData       = [];
let _certData        = [];
let _quarantineData  = [];
let _decisionChart   = null;
let _statusBarChart  = null;
let _penaltyChart    = null;
let _claimsChart     = null;
let _tempChart       = null;
let _selectedShipment= null;

// ─── Navigation ───────────────────────────────────────────────────
function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  document.querySelectorAll('.nav-btn').forEach(b => {
    if (b.textContent.trim().toLowerCase().includes(name.replace('-', ' ')) ||
        b.getAttribute('onclick') === `showPage('${name}')`) {
      b.classList.add('active');
    }
  });
  // Load page data on first visit
  if (name === 'shipments') loadShipmentList();
  if (name === 'excursions') loadExcursions();
  if (name === 'claims')     loadClaimsPenalties();
  if (name === 'certificates') loadCertificates();
  if (name === 'quarantine') loadQuarantine();
}

function showTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + tabId).classList.add('active');
  event.target.classList.add('active');
}

// ─── Helpers ──────────────────────────────────────────────────────
const fmt = (n, dec = 0) =>
  typeof n === 'number' ? n.toLocaleString('en-IN', { maximumFractionDigits: dec }) : n;

function badge(text, cls) {
  return `<span class="badge badge-${cls}">${text}</span>`;
}

function statusBadge(s) {
  const map = { RELEASE: 'RELEASE2', QUARANTINE: 'QUAR', REJECT: 'REJ' };
  return badge(s, map[s] || s);
}

function typeBadge(t) {
  return badge(t, t);   // class matches badge-HIGH, badge-LOW, badge-DATA_GAP
}

function decBadge(d) {
  if (d === 'true')  return badge('YES', 'true');
  if (d === 'false') return badge('NO', 'false');
  return d;
}

async function apiFetch(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

// ─── OVERVIEW PAGE ────────────────────────────────────────────────
async function loadOverview() {
  try {
    _dashboardData = await apiFetch('/api/dashboard');
    renderKPIs();
    renderDecisionChart();
    renderStatusBarChart();
    renderShipmentCards();
  } catch (e) {
    console.error('Overview load failed:', e);
    document.getElementById('kpi-grid').innerHTML =
      `<div class="loading">⚠️ Failed to load data: ${e.message}</div>`;
  }
}

function renderKPIs() {
  const d = _dashboardData;
  document.getElementById('kpi-shipments').textContent   = d.total_shipments;
  document.getElementById('kpi-released').textContent    = d.decision_counts.RELEASE  || 0;
  document.getElementById('kpi-quarantine').textContent  = d.decision_counts.QUARANTINE|| 0;
  document.getElementById('kpi-rejected').textContent    = d.decision_counts.REJECT   || 0;
  document.getElementById('kpi-excursion-min').textContent = fmt(d.total_excursions, 1);
  document.getElementById('kpi-penalty').textContent     = '₹ ' + fmt(d.total_penalty_rs);
  document.getElementById('kpi-claims').textContent      = '₹ ' + fmt(d.total_claim_rs);
  document.getElementById('kpi-certs').textContent       = d.total_certificates;
}

function renderDecisionChart() {
  const d = _dashboardData.decision_counts;
  const ctx = document.getElementById('decisionChart').getContext('2d');
  if (_decisionChart) _decisionChart.destroy();
  _decisionChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Released', 'Quarantined', 'Rejected'],
      datasets: [{
        data: [d.RELEASE || 0, d.QUARANTINE || 0, d.REJECT || 0],
        backgroundColor: ['#22c55e', '#f59e0b', '#ef4444'],
        borderWidth: 0,
        hoverOffset: 6,
      }],
    },
    options: {
      plugins: {
        legend: { position: 'right', labels: { color: '#8892a4', font: { size: 12 } } },
      },
      cutout: '65%',
    },
  });
}

function renderStatusBarChart() {
  const cards = _dashboardData.shipment_cards;
  const ctx = document.getElementById('statusBarChart').getContext('2d');
  if (_statusBarChart) _statusBarChart.destroy();
  _statusBarChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: cards.map(c => c.shipment_id),
      datasets: [{
        label: 'Excursion Events',
        data: cards.map(c => c.excursion_count),
        backgroundColor: cards.map(c =>
          c.status === 'REJECT'     ? '#ef4444' :
          c.status === 'QUARANTINE' ? '#f59e0b' : '#22c55e'
        ),
        borderRadius: 4,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#8892a4', font: { size: 10 } }, grid: { color: '#2e3250' } },
        y: { ticks: { color: '#8892a4' }, grid: { color: '#2e3250' }, beginAtZero: true },
      },
    },
  });
}

function renderShipmentCards() {
  const grid = document.getElementById('card-grid');
  grid.innerHTML = '';
  for (const c of _dashboardData.shipment_cards) {
    const div = document.createElement('div');
    div.className = 'shp-card';
    div.onclick = () => { showPage('shipments'); selectShipment(c.shipment_id); };
    div.innerHTML = `
      <div class="shp-id">${c.shipment_id}</div>
      <div class="shp-route">🗺 ${c.origin} → ${c.destination}</div>
      <span class="shp-badge badge-${c.status}">${c.status}</span>
      <div class="shp-stats">
        <div class="shp-stat"><strong>${c.excursion_count}</strong> excursions</div>
        <div class="shp-stat"><strong>₹ ${fmt(c.penalty_total)}</strong> penalty</div>
      </div>`;
    grid.appendChild(div);
  }
}

// ─── SHIPMENTS PAGE ───────────────────────────────────────────────
function loadShipmentList() {
  if (!_dashboardData) {
    loadOverview().then(() => loadShipmentList());
    return;
  }
  const list = document.getElementById('shipment-list');
  list.innerHTML = '';
  for (const c of _dashboardData.shipment_cards) {
    const div = document.createElement('div');
    div.className = 'shp-list-item';
    div.id = 'li-' + c.shipment_id;
    div.onclick = () => selectShipment(c.shipment_id);
    div.innerHTML = `
      <span class="shp-badge badge-${c.status}" style="min-width:70px;text-align:center">${c.status}</span>
      <div>
        <div class="shp-list-id">${c.shipment_id}</div>
        <div class="shp-list-route">${c.origin} → ${c.destination}</div>
      </div>`;
    list.appendChild(div);
  }
}

async function selectShipment(id) {
  _selectedShipment = id;
  document.querySelectorAll('.shp-list-item').forEach(el => el.classList.remove('active'));
  const li = document.getElementById('li-' + id);
  if (li) li.classList.add('active');

  const detail = document.getElementById('shipment-detail');
  detail.innerHTML = '<div class="loading">Loading…</div>';

  try {
    const [shp, rdg] = await Promise.all([
      apiFetch(`/api/shipments/${id}/detail`),
      apiFetch(`/api/shipments/${id}/readings`).catch(() => null),
    ]);
    renderShipmentDetail(shp, rdg);
  } catch (e) {
    detail.innerHTML = `<div class="loading">⚠️ ${e.message}</div>`;
  }
}

function renderShipmentDetail(shp, rdg) {
  const detail = document.getElementById('shipment-detail');

  const worstDecision = shp.status;
  const totalPenalty  = shp.penalties.reduce((s, p) => s + (p.penalty_total || 0), 0);
  const totalExcMin   = shp.excursions
    .filter(e => e.type !== 'DATA_GAP')
    .reduce((s, e) => s + (e.duration_minutes || 0), 0);

  // Build table rows
  const decRows = shp.decisions.map(d => `
    <tr>
      <td>${d.consignment_id}</td>
      <td>${d.profile_id}</td>
      <td>${statusBadge(d.decision)}</td>
      <td>${d.reason_codes}</td>
      <td>${fmt(d.cumulative_minutes, 1)}</td>
      <td>${d.mkt_c}</td>
    </tr>`).join('');

  const excRows = shp.excursions.map(e => `
    <tr>
      <td>${typeBadge(e.type)}</td>
      <td>${e.start_ts}</td>
      <td>${fmt(e.duration_minutes, 1)} min</td>
      <td>${e.max_temp_c}</td>
      <td>Leg ${e.leg_no} / ${e.party}</td>
    </tr>`).join('');

  const penRows = shp.penalties.map(p => `
    <tr>
      <td>Leg ${p.leg_no}</td>
      <td>${p.carrier_id}</td>
      <td>${fmt(p.attributed_minutes, 1)}</td>
      <td>₹ ${fmt(p.minute_penalty)}</td>
      <td>${decBadge(p.cap_applied)}</td>
      <td>₹ ${fmt(p.penalty_total)}</td>
    </tr>`).join('');

  detail.innerHTML = `
    <div class="detail-header">
      <h2>${shp.shipment_id}</h2>
      ${statusBadge(worstDecision)}
    </div>

    <div class="detail-meta">
      <div class="meta-item"><div class="meta-label">Route</div>
        <div class="meta-value">${shp.origin_city} → ${shp.destination_city}</div></div>
      <div class="meta-item"><div class="meta-label">Departure</div>
        <div class="meta-value">${shp.planned_departure}</div></div>
      <div class="meta-item"><div class="meta-label">Insured Value</div>
        <div class="meta-value">₹ ${fmt(shp.insured_value)}</div></div>
      <div class="meta-item"><div class="meta-label">Logger Owner</div>
        <div class="meta-value">${shp.logger_owner}</div></div>
      <div class="meta-item"><div class="meta-label">Excursion Min</div>
        <div class="meta-value">${fmt(totalExcMin, 1)}</div></div>
      <div class="meta-item"><div class="meta-label">Total Penalty</div>
        <div class="meta-value">₹ ${fmt(totalPenalty)}</div></div>
    </div>

    ${rdg ? `
    <div class="detail-chart">
      <h3>🌡 Temperature Profile</h3>
      <canvas id="tempChart-${shp.shipment_id}" height="150"></canvas>
    </div>` : ''}

    <div class="detail-section">
      <h3>Compliance Decisions</h3>
      <div class="table-wrap"><table>
        <thead><tr><th>Consignment</th><th>Profile</th><th>Decision</th><th>Reason</th><th>Exc Min</th><th>MKT °C</th></tr></thead>
        <tbody>${decRows || '<tr><td colspan="6">—</td></tr>'}</tbody>
      </table></div>
    </div>

    <div class="detail-section">
      <h3>Excursion Events</h3>
      <div class="table-wrap"><table>
        <thead><tr><th>Type</th><th>Start</th><th>Duration</th><th>Peak Temp</th><th>Party</th></tr></thead>
        <tbody>${excRows || '<tr><td colspan="5">No excursions</td></tr>'}</tbody>
      </table></div>
    </div>

    <div class="detail-section">
      <h3>Carrier Penalties</h3>
      <div class="table-wrap"><table>
        <thead><tr><th>Leg</th><th>Carrier</th><th>Attributed Min</th><th>Minute Penalty</th><th>Cap</th><th>Total</th></tr></thead>
        <tbody>${penRows || '<tr><td colspan="6">No penalties</td></tr>'}</tbody>
      </table></div>
    </div>
  `;

  // Render temperature chart
  if (rdg) {
    setTimeout(() => {
      const ctx = document.getElementById(`tempChart-${shp.shipment_id}`);
      if (!ctx) return;
      if (_tempChart) _tempChart.destroy();

      // Sample every N points so the chart stays readable
      const maxPoints = 200;
      const step = Math.max(1, Math.floor(rdg.labels.length / maxPoints));
      const labels = rdg.labels.filter((_, i) => i % step === 0);
      const temps  = rdg.temperatures.filter((_, i) => i % step === 0);

      _tempChart = new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: 'Temperature (°C)',
            data: temps,
            borderColor: '#4f8ef7',
            backgroundColor: 'rgba(79,142,247,0.08)',
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.3,
            fill: true,
          }],
        },
        options: {
          plugins: { legend: { display: false } },
          scales: {
            x: {
              ticks: { color: '#8892a4', maxTicksLimit: 8, maxRotation: 0, font: { size: 10 } },
              grid: { color: '#2e3250' },
            },
            y: {
              ticks: { color: '#8892a4', callback: v => v + '°C' },
              grid: { color: '#2e3250' },
            },
          },
          interaction: { intersect: false, mode: 'index' },
          animation: { duration: 400 },
        },
      });
    }, 50);
  }
}

// ─── EXCURSIONS PAGE ──────────────────────────────────────────────
async function loadExcursions() {
  if (_excursionData.length) { renderExcursionTable(); return; }
  try {
    _excursionData = await apiFetch('/api/reports/excursions');
    renderExcursionTable();
  } catch (e) {
    document.getElementById('excursion-tbody').innerHTML =
      `<tr><td colspan="10">⚠️ ${e.message}</td></tr>`;
  }
}

function filterExcursions() {
  const val = document.getElementById('exc-filter').value;
  renderExcursionTable(val === 'ALL' ? _excursionData : _excursionData.filter(e => e.type === val));
}

function renderExcursionTable(data) {
  if (!data) data = _excursionData;
  const tbody = document.getElementById('excursion-tbody');
  tbody.innerHTML = data.map(e => `
    <tr>
      <td>${e.shipment_id}</td>
      <td>${e.excursion_no}</td>
      <td>${typeBadge(e.type)}</td>
      <td>${e.start_ts}</td>
      <td>${e.end_ts}</td>
      <td>${fmt(e.duration_minutes, 1)}</td>
      <td>${e.max_temp_c}</td>
      <td>Leg ${e.leg_no}</td>
      <td>${e.party}</td>
      <td>${decBadge(e.counts_toward_limit)}</td>
    </tr>`).join('') || '<tr><td colspan="10">No data</td></tr>';
}

// ─── CLAIMS & PENALTIES PAGE ──────────────────────────────────────
async function loadClaimsPenalties() {
  try {
    if (!_penaltyData.length) _penaltyData = await apiFetch('/api/reports/penalties');
    if (!_claimData.length)   _claimData   = await apiFetch('/api/reports/claims');
    renderPenaltiesTable();
    renderClaimsTable();
    renderPenaltyChart();
    renderClaimsChart();
  } catch (e) {
    console.error(e);
  }
}

function renderPenaltiesTable() {
  document.getElementById('penalties-tbody').innerHTML =
    _penaltyData.map(p => `
      <tr>
        <td>${p.shipment_id}</td>
        <td>Leg ${p.leg_no}</td>
        <td>${p.carrier_id}</td>
        <td>${fmt(p.attributed_minutes, 1)}</td>
        <td>₹ ${fmt(p.minute_penalty)}</td>
        <td>₹ ${fmt(p.precool_penalty)}</td>
        <td>${decBadge(p.cap_applied)}</td>
        <td><strong>₹ ${fmt(p.penalty_total)}</strong></td>
      </tr>`).join('') || '<tr><td colspan="8">No penalties</td></tr>';
}

function renderClaimsTable() {
  document.getElementById('claims-tbody').innerHTML =
    _claimData.map(c => `
      <tr>
        <td>${c.shipment_id}</td>
        <td>${c.consignment_id}</td>
        <td>₹ ${fmt(c.claim_value)}</td>
        <td>${c.party}</td>
        <td>${fmt(c.attributed_minutes, 1)}</td>
        <td>₹ ${fmt(c.share_before_cap)}</td>
        <td><strong>₹ ${fmt(c.share_after_cap)}</strong></td>
      </tr>`).join('') || '<tr><td colspan="7">No claims</td></tr>';
}

function renderPenaltyChart() {
  // Aggregate by carrier
  const byCarrier = {};
  for (const p of _penaltyData) {
    byCarrier[p.carrier_id] = (byCarrier[p.carrier_id] || 0) + p.penalty_total;
  }
  const labels = Object.keys(byCarrier).sort();
  const values = labels.map(l => byCarrier[l]);
  const ctx = document.getElementById('penaltyChart').getContext('2d');
  if (_penaltyChart) _penaltyChart.destroy();
  _penaltyChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{ label: 'Penalty (₹)', data: values, backgroundColor: '#f97316', borderRadius: 4 }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#8892a4' }, grid: { color: '#2e3250' } },
        y: { ticks: { color: '#8892a4', callback: v => '₹' + fmt(v) }, grid: { color: '#2e3250' } },
      },
    },
  });
}

function renderClaimsChart() {
  const byParty = {};
  for (const c of _claimData) {
    byParty[c.party] = (byParty[c.party] || 0) + c.share_after_cap;
  }
  const labels = Object.keys(byParty).sort();
  const values = labels.map(l => byParty[l]);
  const ctx = document.getElementById('claimsChart').getContext('2d');
  if (_claimsChart) _claimsChart.destroy();
  _claimsChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{ label: 'Claims (₹)', data: values, backgroundColor: '#a855f7', borderRadius: 4 }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#8892a4' }, grid: { color: '#2e3250' } },
        y: { ticks: { color: '#8892a4', callback: v => '₹' + fmt(v) }, grid: { color: '#2e3250' } },
      },
    },
  });
}

// ─── CERTIFICATES PAGE ────────────────────────────────────────────
async function loadCertificates() {
  if (_certData.length) { renderCertificates(); return; }
  try {
    _certData = await apiFetch('/api/reports/certificates');
    renderCertificates();
  } catch (e) {
    document.getElementById('cert-grid').innerHTML = `<div class="loading">⚠️ ${e.message}</div>`;
  }
}

function renderCertificates() {
  const grid = document.getElementById('cert-grid');
  if (!_certData.length) { grid.innerHTML = '<div class="loading">No certificates issued.</div>'; return; }
  grid.innerHTML = _certData.map(c => `
    <div class="cert-card">
      <div class="cert-title">✅ Release Certificate</div>
      <div class="cert-id">${c.shipment_id}</div>
      <div class="cert-cons">${c.consignment_id}</div>
      <div class="cert-stats">
        <div class="cert-stat">
          <div class="label">MKT</div>
          <div class="value">${c.mkt_c} °C</div>
        </div>
        <div class="cert-stat">
          <div class="label">Excursion Min</div>
          <div class="value">${fmt(c.cumulative_minutes, 1)}</div>
        </div>
      </div>
      <div class="cert-text">${c.certificate_text}</div>
      <div class="cert-text" style="margin-top:4px">Released: ${c.released_at}</div>
    </div>`).join('');
}

// ─── QUARANTINE PAGE ──────────────────────────────────────────────
async function loadQuarantine() {
  if (_quarantineData.length) { renderQuarantineTable(); return; }
  try {
    _quarantineData = await apiFetch('/api/reports/quarantine');
    renderQuarantineTable();
  } catch (e) {
    document.getElementById('quarantine-tbody').innerHTML =
      `<tr><td colspan="9">⚠️ ${e.message}</td></tr>`;
  }
}

function renderQuarantineTable() {
  document.getElementById('quarantine-tbody').innerHTML =
    _quarantineData.map(r => `
      <tr>
        <td>${r.shipment_id}</td>
        <td>${r.origin} → ${r.destination}</td>
        <td>${r.consignment_id}</td>
        <td>${r.profile_id}</td>
        <td>${statusBadge(r.decision)}</td>
        <td>${r.reason_codes}</td>
        <td>${fmt(r.cumulative_excursion_minutes, 1)}</td>
        <td>${r.excursion_events}</td>
        <td>${r.mkt_c}</td>
      </tr>`).join('') || '<tr><td colspan="9">No quarantine/reject decisions.</td></tr>';
}

// ─── MODAL ────────────────────────────────────────────────────────
function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
}

// ─── BOOT ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadOverview();
});
