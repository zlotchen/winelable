'use strict';

// ---------------------------------------------------------------------------
// API endpoints
// ---------------------------------------------------------------------------
const API = {
  submissions: '/api/submissions',
  application: '/api/application',
  statuses:    '/api/statuses',
  save:        '/api/save',
};

// ---------------------------------------------------------------------------
// App state
// ---------------------------------------------------------------------------
let currentFolderType  = 'input';
let currentSubmissions = [];
let selectedPaths      = new Set();
let currentApp         = null;   // full loaded application detail
let statusConfig       = [];     // [{value, label, count}, ...]

// ---------------------------------------------------------------------------
// Metadata fields shown in the comparison table
// ---------------------------------------------------------------------------
const META_FIELDS = [
  { key: 'TTB_ID',                label: 'TTB ID',                    editable: false },
  { key: 'vendor_code',           label: 'Vendor Code',               editable: true  },
  { key: 'product_class_type',    label: 'Product Class Type',        editable: true  },
  { key: 'date_submission',       label: 'Date Submitted',            editable: false },
  { key: 'date_reviewed',         label: 'Date Reviewed',             editable: false },
  { key: 'date_processed',        label: 'Date Processed',            editable: false },
  { key: 'Wine_Name',             label: 'Wine / Fanciful Name',      editable: true  },
  { key: 'Brand_Name',            label: 'Brand Name',                editable: true  },
  { key: 'Vintage',               label: 'Vintage Year',              editable: true  },
  { key: 'Grape_Variety',         label: 'Grape Variety',             editable: true  },
  { key: 'Alcohol_concentration', label: 'Alcohol Content',           editable: true  },
  { key: 'Volume',                label: 'Volume (mL)',               editable: true  },
  { key: 'Vendor_Name',           label: 'Vendor / Distributor',      editable: true  },
  { key: 'Country_of_Origin',     label: 'Country of Origin',         editable: true  },
  { key: 'GOVERNMENT_WARNING',    label: 'Government Warning',        editable: true  },
];

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
  bindTabEvents();
  bindFilterEvents();
  bindBatchEvents();
  bindLightbox();
  await loadStatuses();
  await loadSubmissions();
});

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------
function bindTabEvents() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      currentFolderType = tab.dataset.folder;
      selectedPaths.clear();
      updateSelectedCount();
      hideDetail();
      loadSubmissions();
    });
  });
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------
function bindFilterEvents() {
  document.getElementById('btn-apply-filter').addEventListener('click', loadSubmissions);
  document.getElementById('btn-clear-filter').addEventListener('click', () => {
    document.getElementById('filter-date-from').value = '';
    document.getElementById('filter-date-to').value   = '';
    document.getElementById('filter-vendor').value    = '';
    document.getElementById('filter-status').value    = '';
    loadSubmissions();
  });
}

function filterParams() {
  const p = new URLSearchParams({ folder_type: currentFolderType });
  const from   = document.getElementById('filter-date-from').value;
  const to     = document.getElementById('filter-date-to').value;
  const vendor = document.getElementById('filter-vendor').value.trim();
  const status = document.getElementById('filter-status').value;
  if (from)   p.set('date_from', from.replace(/-/g, ''));
  if (to)     p.set('date_to',   to.replace(/-/g, ''));
  if (vendor) p.set('vendor', vendor);
  if (status) p.set('status', status);
  return p;
}

// ---------------------------------------------------------------------------
// Statuses
// ---------------------------------------------------------------------------
async function loadStatuses() {
  try {
    const data = await apiFetch(API.statuses);
    statusConfig = data.statuses || [];
    populateStatusDropdowns();
    updateTabCounts(statusConfig);
  } catch (e) {
    console.error('loadStatuses:', e);
  }
}

function populateStatusDropdowns() {
  // Filter dropdown — only statuses with non-zero counts are selectable
  const filterSel = document.getElementById('filter-status');
  filterSel.innerHTML = '<option value="">All Statuses</option>';
  statusConfig.forEach(s => {
    const opt = new Option(
      `${s.label}${s.count !== undefined ? ` (${s.count})` : ''}`,
      s.value
    );
    opt.disabled = (s.count === 0);
    filterSel.appendChild(opt);
  });

  // Batch & detail dropdowns — all statuses
  ['batch-status-select', 'detail-status-select'].forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = '<option value="">— Select —</option>';
    statusConfig.forEach(s => sel.appendChild(new Option(s.label, s.value)));
  });
}

function updateTabCounts(statuses) {
  // Map status counts to folder type (rough association for tab badge)
  const folderStatus = {
    input:       ['new', 'reviewed'],
    processed:   ['processed'],
    quaranteen:  ['quarantine', 'error'],
  };
  Object.entries(folderStatus).forEach(([ft, keys]) => {
    const total = statuses
      .filter(s => keys.includes(s.value))
      .reduce((sum, s) => sum + (s.count || 0), 0);
    const el = document.getElementById(`count-${ft}`);
    if (el) el.textContent = total || '0';
  });
}

// ---------------------------------------------------------------------------
// Submissions list
// ---------------------------------------------------------------------------
async function loadSubmissions() {
  const listEl = document.getElementById('submissions-list');
  listEl.innerHTML = '<div class="loading-msg">Loading…</div>';

  try {
    currentSubmissions = await apiFetch(`${API.submissions}?${filterParams()}`);
    renderSubmissions(currentSubmissions);
  } catch (e) {
    listEl.innerHTML = `<div class="empty-state">Error loading submissions.<br>${e.message}</div>`;
  }
}

function renderSubmissions(submissions) {
  const listEl = document.getElementById('submissions-list');
  listEl.innerHTML = '';
  document.getElementById('select-all').checked = false;
  selectedPaths.clear();
  updateSelectedCount();

  if (!submissions.length) {
    listEl.innerHTML = '<div class="empty-state">No submissions found.</div>';
    return;
  }

  submissions.forEach(sub => {
    const fp = sub._folder_path;
    const card = document.createElement('div');
    card.className = 'submission-card';
    card.dataset.folderPath = fp;

    const badgeClass = `badge-${sub.status || 'unknown'}`;

    card.innerHTML = `
      <div class="card-cb">
        <input type="checkbox" class="submission-checkbox" data-folder-path="${escAttr(fp)}">
      </div>
      <div class="card-body">
        <div class="card-row">
          <span class="label">TTB ID</span>
          <span class="value">${esc(sub.TTB_ID || '—')}</span>
        </div>
        <div class="card-row">
          <span class="label">Vendor</span>
          <span class="value">${esc(sub.vendor_code || '—')}</span>
        </div>
        <div class="card-row">
          <span class="label">Type</span>
          <span class="value">${esc(sub.product_class_type || '—')}</span>
        </div>
        <div class="card-row">
          <span class="label">Submitted</span>
          <span class="value">${esc(fmtDate(sub.date_submission))}</span>
        </div>
        <span class="status-badge ${badgeClass}">${esc(sub.status || 'unknown')}</span>
      </div>
    `;

    // Checkbox selection
    card.querySelector('.submission-checkbox').addEventListener('change', e => {
      e.stopPropagation();
      if (e.target.checked) selectedPaths.add(fp);
      else selectedPaths.delete(fp);
      updateSelectedCount();
    });

    // Click card body → open detail
    card.querySelector('.card-body').addEventListener('click', () => openApplication(sub));

    listEl.appendChild(card);
  });
}

function updateSelectedCount() {
  document.getElementById('selected-count').textContent = `${selectedPaths.size} selected`;
}

// Select all / deselect all
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('select-all').addEventListener('change', e => {
    const checked = e.target.checked;
    document.querySelectorAll('.submission-checkbox').forEach(cb => {
      cb.checked = checked;
      const fp = cb.dataset.folderPath;
      if (checked) selectedPaths.add(fp);
      else selectedPaths.delete(fp);
    });
    updateSelectedCount();
  });
});

// ---------------------------------------------------------------------------
// Open application detail
// ---------------------------------------------------------------------------
async function openApplication(sub) {
  // Highlight selected card
  document.querySelectorAll('.submission-card').forEach(c => c.classList.remove('selected'));
  const card = document.querySelector(`.submission-card[data-folder-path="${escAttr(sub._folder_path)}"]`);
  if (card) card.classList.add('selected');

  showDetailLoading();

  try {
    const data = await apiFetch(`${API.application}?folder=${encodeURIComponent(sub._folder_path)}`);
    currentApp = data;
    renderDetail(data);
  } catch (e) {
    document.getElementById('detail-content').innerHTML =
      `<div class="empty-state" style="padding:2rem">Failed to load application: ${e.message}</div>`;
    document.getElementById('detail-content').classList.remove('hidden');
    document.getElementById('detail-placeholder').classList.add('hidden');
  }
}

function showDetailLoading() {
  document.getElementById('detail-placeholder').classList.add('hidden');
  const content = document.getElementById('detail-content');
  content.classList.remove('hidden');
  content.innerHTML = '<div class="loading-msg" style="padding:2rem">Loading application data…</div>';
}

function hideDetail() {
  document.getElementById('detail-placeholder').classList.remove('hidden');
  document.getElementById('detail-content').classList.add('hidden');
  currentApp = null;
}

// ---------------------------------------------------------------------------
// Render detail panel
// ---------------------------------------------------------------------------
function renderDetail(data) {
  const { submitted_metadata: sub, extracted_metadata: ext, image_urls, folder_path } = data;
  const content = document.getElementById('detail-content');

  const statusOpts = statusConfig.map(s =>
    `<option value="${escAttr(s.value)}"${s.value === sub.status ? ' selected' : ''}>${esc(s.label)}</option>`
  ).join('');

  content.innerHTML = `
    <section id="image-viewer">
      <h2 class="section-title">Label Images</h2>
      <div id="image-strip"></div>
    </section>

    <section id="metadata-section">
      <h2 class="section-title">
        Metadata Comparison
        <span id="extract-status" class="extract-badge ${ext && !ext.error ? 'done' : 'error'}">
          ${ext && !ext.error ? 'Extracted' : ext && ext.error ? 'Extraction error' : 'No extraction'}
        </span>
      </h2>
      <div class="table-scroll">
        <table id="metadata-table">
          <thead>
            <tr>
              <th class="col-field">Field</th>
              <th class="col-submitted">Submitted Metadata</th>
              <th class="col-extracted">Extracted Metadata</th>
            </tr>
          </thead>
          <tbody id="metadata-tbody"></tbody>
        </table>
      </div>
    </section>

    <section id="detail-actions">
      <label class="action-label">Status:
        <select id="detail-status-select">${statusOpts}</select>
      </label>
      <div class="action-buttons">
        <button id="btn-detail-save" class="btn btn-primary">Save</button>
        <button id="btn-detail-process" class="btn btn-success">Mark Processed</button>
        <button id="btn-detail-quarantine" class="btn btn-danger">Quarantine</button>
      </div>
    </section>
  `;

  // Images
  const strip = document.getElementById('image-strip');
  if (image_urls && image_urls.length) {
    image_urls.forEach(url => {
      const img = document.createElement('img');
      img.src = url;
      img.alt = url.split('/').pop();
      img.title = 'Click to enlarge';
      img.addEventListener('click', () => openLightbox(url));
      strip.appendChild(img);
    });
  } else {
    strip.innerHTML = '<span class="muted">No images available.</span>';
  }

  // Metadata table
  buildMetadataTable(sub, flattenObj(ext || {}));

  // Action buttons
  document.getElementById('btn-detail-save').addEventListener('click',       () => detailSave('reviewed'));
  document.getElementById('btn-detail-process').addEventListener('click',    () => detailSave('processed'));
  document.getElementById('btn-detail-quarantine').addEventListener('click', () => detailSave('quarantine'));
}

// ---------------------------------------------------------------------------
// Metadata table
// ---------------------------------------------------------------------------
function buildMetadataTable(submitted, extracted) {
  const tbody = document.getElementById('metadata-tbody');
  tbody.innerHTML = '';

  META_FIELDS.forEach(field => {
    const subVal = findVal(submitted, field.key) ?? '';
    const extVal = findVal(extracted, field.key) ?? '';
    const ro     = field.editable ? '' : 'readonly';

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="field-name">${esc(field.label)}</td>
      <td><input type="text" class="meta-input sub-input" data-field="${escAttr(field.key)}"
           value="${escAttr(stringify(subVal))}" ${ro}></td>
      <td><input type="text" class="meta-input ext-input" data-field="${escAttr(field.key)}"
           value="${escAttr(stringify(extVal))}" ${ro}></td>
    `;
    tbody.appendChild(tr);
  });
}

// Collect edited metadata from table
function collectMetadata() {
  const meta = {};
  document.querySelectorAll('.sub-input').forEach(el => {
    meta[el.dataset.field] = el.value;
  });
  const extracted_updates = {};
  document.querySelectorAll('.ext-input').forEach(el => {
    extracted_updates[el.dataset.field] = el.value;
  });
  meta.extracted_updates = extracted_updates;
  return meta;
}

// ---------------------------------------------------------------------------
// Save actions
// ---------------------------------------------------------------------------
async function detailSave(statusOverride) {
  if (!currentApp) return;
  const status = statusOverride === 'reviewed'
    ? (document.getElementById('detail-status-select')?.value || 'reviewed')
    : statusOverride;

  await saveSubmission(currentApp.folder_path, status, collectMetadata());
}

async function saveSubmission(folderPath, status, metadata) {
  try {
    const result = await apiFetch(API.save, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_path: folderPath, status, metadata }),
    });

    if (result.success) {
      toast(`Saved — status: ${result.status}`, 'success');
      if (currentApp && currentApp.folder_path === folderPath) {
        currentApp.folder_path = result.new_folder_path;
      }
      await loadStatuses();
      await loadSubmissions();
    } else {
      toast(`Error: ${result.error}`, 'error');
    }
  } catch (e) {
    toast(`Failed: ${e.message}`, 'error');
  }
}

// ---------------------------------------------------------------------------
// Batch actions
// ---------------------------------------------------------------------------
function bindBatchEvents() {
  document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('btn-batch-process').addEventListener('click',
      () => batchAction('processed'));
    document.getElementById('btn-batch-quarantine').addEventListener('click',
      () => batchAction('quarantine'));
    document.getElementById('btn-batch-save').addEventListener('click',
      () => batchAction('reviewed'));
    document.getElementById('btn-batch-change-status').addEventListener('click', () => {
      const sel = document.getElementById('batch-status-select');
      if (sel && sel.value) batchAction(sel.value);
      else toast('Select a status first.', 'info');
    });
  });
}

async function batchAction(status) {
  if (!selectedPaths.size) {
    toast('No submissions selected.', 'info');
    return;
  }
  const promises = [...selectedPaths].map(fp => saveSubmission(fp, status, {}));
  await Promise.all(promises);
}

// ---------------------------------------------------------------------------
// Lightbox
// ---------------------------------------------------------------------------
function bindLightbox() {
  document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('lightbox').addEventListener('click', e => {
      if (e.target === e.currentTarget || e.target.id === 'lightbox-close') {
        closeLightbox();
      }
    });
  });
}
function openLightbox(src) {
  document.getElementById('lightbox-img').src = src;
  document.getElementById('lightbox').classList.remove('hidden');
}
function closeLightbox() {
  document.getElementById('lightbox').classList.add('hidden');
  document.getElementById('lightbox-img').src = '';
}
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeLightbox();
});

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
async function apiFetch(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

function flattenObj(obj, result = {}) {
  if (!obj || typeof obj !== 'object') return result;
  for (const [k, v] of Object.entries(obj)) {
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      flattenObj(v, result);
    }
    result[k] = v;
    result[k.toLowerCase()] = v;
    result[k.toLowerCase().replace(/[^a-z0-9]/g, '_')] = v;
  }
  return result;
}

function findVal(obj, key) {
  if (!obj) return undefined;
  if (obj[key] !== undefined) return obj[key];
  const kl = key.toLowerCase();
  for (const [k, v] of Object.entries(obj)) {
    if (k.toLowerCase() === kl || k.toLowerCase().replace(/[^a-z0-9]/g, '_') === kl.replace(/[^a-z0-9]/g, '_')) {
      return v;
    }
  }
  return undefined;
}

function stringify(v) {
  if (v === null || v === undefined) return '';
  if (Array.isArray(v)) return v.join(', ');
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

function fmtDate(iso) {
  if (!iso) return '—';
  return iso.replace('T', ' ').substring(0, 16);
}

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function escAttr(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 3500);
}
