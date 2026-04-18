const CONFIG = window.TAGCHECK_ADMIN_CONFIG;
const app = document.getElementById('app');
const openViewerButton = document.getElementById('openViewerButton');

const I18N = {
  pt: {
    brandTitle: 'TagCheck • Smart Asset Tracking',
    brandSubtitle: 'Powered by Just Engine™ ⚡',
    heroTitle: 'Admin novo V1',
    heroText: 'Cadastro e consulta de equipamentos usando o backend novo online.',
    apiOk: 'API online',
    apiFail: 'API indisponível',
    version: 'Versão',
    total: 'Total',
    withPhoto: 'Com foto',
    noPhoto: 'Sem foto',
    formTitle: 'Cadastrar equipamento',
    searchTitle: 'Buscar por TAG',
    searchPlaceholder: 'Ex.: TESTE-001',
    searchButton: 'Buscar',
    listTitle: 'Lista de equipamentos',
    refresh: 'Atualizar lista',
    create: 'Cadastrar',
    creating: 'Cadastrando...',
    tag: 'TAG',
    name: 'Nome',
    photo: 'Foto',
    noImage: 'Sem foto',
    qr: 'QR',
    actions: 'Ações',
    openViewer: 'Abrir Viewer',
    openSheet: 'Abrir ficha',
    status: 'Status',
    active: 'Ativo',
    onlineSearchDone: 'Consulta online concluída.',
    loading: 'Carregando Admin...',
    listLoading: 'Carregando equipamentos...',
    noItems: 'Nenhum equipamento cadastrado ainda.',
    typeTag: 'Digite uma TAG válida.',
    createSuccess: 'Equipamento cadastrado com sucesso.',
    createError: 'Falha ao cadastrar equipamento.',
    listError: 'Falha ao carregar a lista.',
    searchError: 'Nenhum equipamento encontrado para esta TAG.',
    apiCheck: 'Verificando API...',
    viewer: 'Viewer'
  },
  en: {
    brandTitle: 'TagCheck • Smart Asset Tracking',
    brandSubtitle: 'Powered by Just Engine™ ⚡',
    heroTitle: 'New Admin V1',
    heroText: 'Equipment registration and lookup using the new online backend.',
    apiOk: 'API online',
    apiFail: 'API unavailable',
    version: 'Version',
    total: 'Total',
    withPhoto: 'With photo',
    noPhoto: 'Without photo',
    formTitle: 'Register equipment',
    searchTitle: 'Search by TAG',
    searchPlaceholder: 'Ex.: TESTE-001',
    searchButton: 'Search',
    listTitle: 'Equipment list',
    refresh: 'Refresh list',
    create: 'Create',
    creating: 'Creating...',
    tag: 'TAG',
    name: 'Name',
    photo: 'Photo',
    noImage: 'No image',
    qr: 'QR',
    actions: 'Actions',
    openViewer: 'Open Viewer',
    openSheet: 'Open sheet',
    status: 'Status',
    active: 'Active',
    onlineSearchDone: 'Online lookup completed.',
    loading: 'Loading Admin...',
    listLoading: 'Loading equipment...',
    noItems: 'No equipment registered yet.',
    typeTag: 'Enter a valid TAG.',
    createSuccess: 'Equipment created successfully.',
    createError: 'Failed to create equipment.',
    listError: 'Failed to load list.',
    searchError: 'No equipment found for this TAG.',
    apiCheck: 'Checking API...',
    viewer: 'Viewer'
  }
};

const state = {
  language: localStorage.getItem(CONFIG.STORAGE_KEYS.language) || 'pt',
  items: [],
  apiReachable: null,
  searchResult: null
};

function t(key) {
  return I18N[state.language][key] || key;
}

function setLanguage(lang) {
  state.language = lang;
  localStorage.setItem(CONFIG.STORAGE_KEYS.language, lang);
  syncHeaderLanguage();
  renderApp();
}

function syncHeaderLanguage() {
  document.getElementById('brandTitle').textContent = t('brandTitle');
  document.getElementById('brandSubtitle').textContent = t('brandSubtitle');
  document.getElementById('langPt').classList.toggle('active', state.language === 'pt');
  document.getElementById('langPt').className = state.language === 'pt' ? 'secondary-button lang-button active' : 'outline-button lang-button';
  document.getElementById('langEn').classList.toggle('active', state.language === 'en');
  document.getElementById('langEn').className = state.language === 'en' ? 'secondary-button lang-button active' : 'outline-button lang-button';
  openViewerButton.textContent = t('viewer');
}

function escapeHtml(value) {
  return String(value ?? '-')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function normalizeText(value) {
  return String(value ?? '').trim();
}

function buildUrl(base, path) {
  return `${base.replace(/\/$/, '')}${path}`;
}

async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CONFIG.REQUEST_TIMEOUT_MS);
  try {
    return await fetch(url, { ...options, signal: controller.signal, cache: 'no-store' });
  } finally {
    clearTimeout(timer);
  }
}

async function pingApi() {
  try {
    const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, CONFIG.ENDPOINTS.health));
    state.apiReachable = response.ok;
    return response.ok;
  } catch {
    state.apiReachable = false;
    return false;
  }
}

function normalizeItem(raw) {
  return {
    id: raw.id ?? null,
    tag: raw.tag ?? '-',
    name: raw.name ?? 'Instrumento',
    photo: raw.photo ?? null,
    status: raw.status ?? t('active')
  };
}

async function loadItems() {
  const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, CONFIG.ENDPOINTS.list), {
    headers: { Accept: 'application/json' }
  });

  if (!response.ok) throw new Error(t('listError'));

  const data = await response.json();
  state.items = Array.isArray(data) ? data.map(normalizeItem) : [];
  return state.items;
}

async function searchByTag(tag) {
  const cleanTag = normalizeText(tag);
  if (!cleanTag) throw new Error(t('typeTag'));

  localStorage.setItem(CONFIG.STORAGE_KEYS.lastSearch, cleanTag);

  const url = buildUrl(
    CONFIG.API_BASE_URL,
    CONFIG.ENDPOINTS.byTag.replace(':tag', encodeURIComponent(cleanTag))
  );

  const response = await fetchWithTimeout(url, {
    headers: { Accept: 'application/json' }
  });

  if (!response.ok) throw new Error(t('searchError'));

  const data = await response.json();
  return normalizeItem(data);
}

async function createEquipment(formData) {
  const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, CONFIG.ENDPOINTS.create), {
    method: 'POST',
    body: formData
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || t('createError'));
  }

  const data = await response.json();
  return normalizeItem(data);
}

function viewerUrlForTag(tag) {
  const url = new URL(CONFIG.VIEWER_BASE_URL);
  url.searchParams.set('tag', tag);
  return url.toString();
}

function qrHtml(tag) {
  const qrId = `qr-${String(tag).replace(/[^a-zA-Z0-9_-]/g, '')}`;
  return `
    <div>
      <div class="qr-box"><canvas id="${qrId}"></canvas></div>
      <a class="qr-link" href="${viewerUrlForTag(tag)}" target="_blank" rel="noopener noreferrer">${t('openSheet')}</a>
    </div>
  `;
}

function statusPill(status) {
  return `<span class="status-pill status-ok">${escapeHtml(status || t('active'))}</span>`;
}

function photoHtml(item) {
  if (!item.photo) {
    return `<div class="thumb-fallback">${t('noImage')}</div>`;
  }

  return `<img class="thumb" src="${escapeHtml(item.photo)}" alt="${escapeHtml(item.name)}" />`;
}

function renderRows(items) {
  if (!items.length) {
    return `
      <tr>
        <td colspan="6">
          <div class="empty-state">${t('noItems')}</div>
        </td>
      </tr>
    `;
  }

  return items.map((item) => `
    <tr>
      <td class="code-soft">${escapeHtml(item.id)}</td>
      <td><strong>${escapeHtml(item.tag)}</strong></td>
      <td>${escapeHtml(item.name)}</td>
      <td>${photoHtml(item)}</td>
      <td>${statusPill(item.status)}</td>
      <td>${qrHtml(item.tag)}</td>
    </tr>
  `).join('');
}

function renderApp(notice = '') {
  const total = state.items.length;
  const withPhoto = state.items.filter((x) => !!x.photo).length;
  const noPhoto = total - withPhoto;
  const apiBadge = state.apiReachable
    ? `<span class="badge">${t('apiOk')}</span>`
    : `<span class="badge">${t('apiFail')}</span>`;

  app.innerHTML = `
    <section class="screen">
      <div class="card hero">
        <div>
          <h2>${t('heroTitle')}</h2>
          <p class="subtle">${t('heroText')}</p>
        </div>

        <div class="badge-row">
          <span class="badge">${t('version')} ${escapeHtml(CONFIG.APP_VERSION)}</span>
          ${apiBadge}
        </div>

        <div class="grid-3">
          <div class="kpi">
            <div class="kpi-label">${t('total')}</div>
            <strong>${total}</strong>
          </div>
          <div class="kpi">
            <div class="kpi-label">${t('withPhoto')}</div>
            <strong>${withPhoto}</strong>
          </div>
          <div class="kpi">
            <div class="kpi-label">${t('noPhoto')}</div>
            <strong>${noPhoto}</strong>
          </div>
        </div>
      </div>

      <div class="grid-2">
        <div class="card panel">
          <h3>${t('formTitle')}</h3>
          <input id="tagInput" class="input" placeholder="${t('tag')}" />
          <input id="nameInput" class="input" placeholder="${t('name')}" />
          <input id="photoInput" class="file-input" type="file" accept="image/*" />
          <div class="inline-actions">
            <button id="createButton" class="primary-button">${t('create')}</button>
          </div>
          <div id="createFeedback">${notice}</div>
        </div>

        <div class="card panel">
          <h3>${t('searchTitle')}</h3>
          <input id="searchTagInput" class="input" placeholder="${t('searchPlaceholder')}" value="${escapeHtml(localStorage.getItem(CONFIG.STORAGE_KEYS.lastSearch) || '')}" />
          <div class="inline-actions">
            <button id="searchButton" class="secondary-button">${t('searchButton')}</button>
            <button id="refreshButton" class="outline-button">${t('refresh')}</button>
          </div>
          <div id="searchFeedback"></div>
        </div>
      </div>

      <div class="card panel">
        <h3>${t('listTitle')}</h3>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>${t('tag')}</th>
                <th>${t('name')}</th>
                <th>${t('photo')}</th>
                <th>${t('status')}</th>
                <th>${t('qr')}</th>
              </tr>
            </thead>
            <tbody>
              ${renderRows(state.items)}
            </tbody>
          </table>
        </div>
      </div>

      <div class="footer-note">Admin novo V1 • backend único • pronto para evoluir</div>
    </section>
  `;

  bindEvents();
  renderQRCodes();
}

function bindEvents() {
  document.getElementById('createButton')?.addEventListener('click', async () => {
    const tag = document.getElementById('tagInput').value.trim();
    const name = document.getElementById('nameInput').value.trim();
    const photoFile = document.getElementById('photoInput').files[0];
    const feedback = document.getElementById('createFeedback');

    if (!tag || !name) {
      feedback.innerHTML = `<div class="notice error">${t('typeTag')}</div>`;
      return;
    }

    const formData = new FormData();
    formData.append('tag', tag);
    formData.append('name', name);
    if (photoFile) formData.append('photo', photoFile);

    feedback.innerHTML = `<div class="notice">${t('creating')}</div>`;

    try {
      await createEquipment(formData);
      await loadItems();
      renderApp(`<div class="notice success">${t('createSuccess')}</div>`);
    } catch (error) {
      feedback.innerHTML = `<div class="notice error">${escapeHtml(error.message || t('createError'))}</div>`;
    }
  });

  document.getElementById('searchButton')?.addEventListener('click', async () => {
    const tag = document.getElementById('searchTagInput').value.trim();
    const feedback = document.getElementById('searchFeedback');

    feedback.innerHTML = `<div class="notice">${t('apiCheck')}</div>`;

    try {
      const item = await searchByTag(tag);
      feedback.innerHTML = `
        <div class="notice success">
          <strong>${escapeHtml(item.name)}</strong><br>
          TAG: ${escapeHtml(item.tag)}<br>
          ${item.photo ? `<a href="${escapeHtml(item.photo)}" target="_blank" rel="noopener noreferrer">${t('photo')}</a>` : t('noImage')}
        </div>
      `;
    } catch (error) {
      feedback.innerHTML = `<div class="notice error">${escapeHtml(error.message || t('searchError'))}</div>`;
    }
  });

  document.getElementById('refreshButton')?.addEventListener('click', async () => {
    const feedback = document.getElementById('searchFeedback');
    feedback.innerHTML = `<div class="notice">${t('listLoading')}</div>`;

    try {
      await loadItems();
      renderApp();
    } catch (error) {
      feedback.innerHTML = `<div class="notice error">${escapeHtml(error.message || t('listError'))}</div>`;
    }
  });
}

function renderQRCodes() {
  state.items.forEach((item) => {
    const qrId = `qr-${String(item.tag).replace(/[^a-zA-Z0-9_-]/g, '')}`;
    const canvas = document.getElementById(qrId);
    if (!canvas || typeof QRCode === 'undefined') return;

    QRCode.toCanvas(canvas, viewerUrlForTag(item.tag), {
      width: 116,
      margin: 1
    }, () => {});
  });
}

async function boot() {
  syncHeaderLanguage();
  openViewerButton.href = CONFIG.VIEWER_BASE_URL;

  try {
    await pingApi();
    await loadItems();
    renderApp();
  } catch (error) {
    renderApp(`<div class="notice error">${escapeHtml(error.message || t('listError'))}</div>`);
  }
}

document.getElementById('langPt').addEventListener('click', () => setLanguage('pt'));
document.getElementById('langEn').addEventListener('click', () => setLanguage('en'));

boot();