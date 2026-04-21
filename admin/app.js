const CONFIG = window.TAGCHECK_ADMIN_CONFIG;
const app = document.getElementById('app');
const openViewerButton = document.getElementById('openViewerButton');
const logoutButton = document.getElementById('logoutButton');

const I18N = {
  pt: {
    brandTitle: 'TagCheck • Smart Asset Tracking',
    brandSubtitle: 'Powered by Just Engine™ ⚡',
    heroTitle: 'Admin V3',
    heroText: 'Cadastro, consulta e gestão completa de equipamentos e instrumentos.',
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
    loading: 'Carregando Admin...',
    listLoading: 'Carregando equipamentos...',
    noItems: 'Nenhum equipamento cadastrado ainda.',
    typeTag: 'Digite TAG, nome e selecione uma foto.',
    createSuccess: 'Equipamento cadastrado com sucesso.',
    createError: 'Falha ao cadastrar equipamento.',
    listError: 'Falha ao carregar a lista.',
    searchError: 'Nenhum equipamento encontrado para esta TAG.',
    apiCheck: 'Verificando API...',
    viewer: 'Viewer',
    logout: 'Sair',
    loginTitle: 'Login do Admin',
    loginSubtitle: 'Acesso protegido ao painel de gestão.',
    username: 'Usuário',
    password: 'Senha',
    loginButton: 'Entrar',
    loginLoading: 'Entrando...',
    loginError: 'Falha ao entrar.',
    loginSuccess: 'Login realizado com sucesso.',
    edit: 'Editar',
    delete: 'Excluir',
    save: 'Salvar',
    cancel: 'Cancelar',
    editMode: 'Modo de edição',
    updateSuccess: 'Equipamento atualizado com sucesso.',
    updateError: 'Falha ao atualizar equipamento.',
    deleteConfirmTitle: 'Confirmar exclusão',
    deleteConfirmText: 'Deseja excluir este equipamento?',
    deleteSuccess: 'Equipamento excluído com sucesso.',
    deleteError: 'Falha ao excluir equipamento.',
    preview: 'Pré-visualização',
    selectedPhoto: 'Foto selecionada',
    clearPhoto: 'Limpar foto',
    searchResult: 'Resultado da busca',
    equipmentType: 'Tipo',
    sector: 'Setor',
    location: 'Localização',
    manufacturer: 'Fabricante',
    model: 'Modelo',
    serialNumber: 'Nº de série',
    calibrationDate: 'Data da calibração',
    nextCalibrationDate: 'Próxima calibração',
    notes: 'Observações',
    chooseStatus: 'Status',
  },
  en: {
    brandTitle: 'TagCheck • Smart Asset Tracking',
    brandSubtitle: 'Powered by Just Engine™ ⚡',
    heroTitle: 'Admin V3',
    heroText: 'Complete registration, lookup and management for equipment and instruments.',
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
    loading: 'Loading Admin...',
    listLoading: 'Loading equipment...',
    noItems: 'No equipment registered yet.',
    typeTag: 'Enter TAG, name and select a photo.',
    createSuccess: 'Equipment created successfully.',
    createError: 'Failed to create equipment.',
    listError: 'Failed to load list.',
    searchError: 'No equipment found for this TAG.',
    apiCheck: 'Checking API...',
    viewer: 'Viewer',
    logout: 'Logout',
    loginTitle: 'Admin Login',
    loginSubtitle: 'Protected access to the management panel.',
    username: 'Username',
    password: 'Password',
    loginButton: 'Sign in',
    loginLoading: 'Signing in...',
    loginError: 'Failed to sign in.',
    loginSuccess: 'Signed in successfully.',
    edit: 'Edit',
    delete: 'Delete',
    save: 'Save',
    cancel: 'Cancel',
    editMode: 'Edit mode',
    updateSuccess: 'Equipment updated successfully.',
    updateError: 'Failed to update equipment.',
    deleteConfirmTitle: 'Confirm deletion',
    deleteConfirmText: 'Do you want to delete this equipment?',
    deleteSuccess: 'Equipment deleted successfully.',
    deleteError: 'Failed to delete equipment.',
    preview: 'Preview',
    selectedPhoto: 'Selected photo',
    clearPhoto: 'Clear photo',
    searchResult: 'Search result',
    equipmentType: 'Type',
    sector: 'Sector',
    location: 'Location',
    manufacturer: 'Manufacturer',
    model: 'Model',
    serialNumber: 'Serial number',
    calibrationDate: 'Calibration date',
    nextCalibrationDate: 'Next calibration',
    notes: 'Notes',
    chooseStatus: 'Status',
  }
};

const state = {
  language: localStorage.getItem(CONFIG.STORAGE_KEYS.language) || 'pt',
  authToken: localStorage.getItem(CONFIG.STORAGE_KEYS.authToken) || '',
  authUser: localStorage.getItem(CONFIG.STORAGE_KEYS.authUser) || '',
  items: [],
  apiReachable: null,
  createPreviewUrl: '',
  createPhotoFile: null,
  createForm: {
    tag: '',
    name: '',
    equipment_type: '',
    sector: '',
    location: '',
    manufacturer: '',
    model: '',
    serial_number: '',
    calibration_date: '',
    next_calibration_date: '',
    status: 'Ativo',
    notes: ''
  },
  editingId: null,
  editDraft: null,
  deleteTargetId: null
};

function t(key) {
  return I18N[state.language][key] || key;
}

function setLanguage(lang) {
  state.language = lang;
  localStorage.setItem(CONFIG.STORAGE_KEYS.language, lang);
  syncHeaderLanguage();
  renderCurrentView();
}

function syncHeaderLanguage() {
  document.getElementById('brandTitle').textContent = t('brandTitle');
  document.getElementById('brandSubtitle').textContent = t('brandSubtitle');
  document.getElementById('langPt').className = state.language === 'pt'
    ? 'secondary-button lang-button active'
    : 'outline-button lang-button';
  document.getElementById('langEn').className = state.language === 'en'
    ? 'secondary-button lang-button active'
    : 'outline-button lang-button';
  openViewerButton.textContent = t('viewer');
  logoutButton.textContent = t('logout');
  logoutButton.classList.toggle('hidden', !state.authToken);
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

function getAuthHeaders(extra = {}) {
  if (!state.authToken) return extra;
  return {
    ...extra,
    Authorization: `Bearer ${state.authToken}`
  };
}

function resetCreateForm() {
  state.createPreviewUrl = '';
  state.createPhotoFile = null;
  state.createForm = {
    tag: '',
    name: '',
    equipment_type: '',
    sector: '',
    location: '',
    manufacturer: '',
    model: '',
    serial_number: '',
    calibration_date: '',
    next_calibration_date: '',
    status: 'Ativo',
    notes: ''
  };
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
    equipment_type: raw.equipment_type ?? '',
    sector: raw.sector ?? '',
    location: raw.location ?? '',
    manufacturer: raw.manufacturer ?? '',
    model: raw.model ?? '',
    serial_number: raw.serial_number ?? '',
    calibration_date: raw.calibration_date ?? '',
    next_calibration_date: raw.next_calibration_date ?? '',
    status: raw.status ?? t('active'),
    notes: raw.notes ?? '',
    qr_payload: raw.qr_payload ?? ''
  };
}

async function loginAdmin(username, password) {
  const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, CONFIG.ENDPOINTS.login), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json'
    },
    body: JSON.stringify({ username, password })
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || t('loginError'));
  }

  return await response.json();
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
    headers: getAuthHeaders(),
    body: formData
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || t('createError'));
  }

  const data = await response.json();
  return normalizeItem(data);
}

async function updateEquipment(id, formData) {
  const response = await fetchWithTimeout(`${CONFIG.API_BASE_URL}/equipment/${id}`, {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: formData
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || t('updateError'));
  }

  return await response.json().catch(() => ({ ok: true }));
}

async function deleteEquipment(id) {
  const response = await fetchWithTimeout(`${CONFIG.API_BASE_URL}/equipment/${id}`, {
    method: 'DELETE',
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || t('deleteError'));
  }

  return await response.json().catch(() => ({ ok: true }));
}

function viewerUrlForTag(tag) {
  const url = new URL(CONFIG.VIEWER_BASE_URL);
  url.searchParams.set('tag', tag);
  return url.toString();
}

function buildQrPayload(item) {
  if (item.qr_payload && String(item.qr_payload).trim()) {
    return String(item.qr_payload).trim();
  }

  return `TAGCHECK | MODO HIBRIDO
TAG: ${item.tag}
NOME: ${item.name}
TIPO: ${item.equipment_type || '-'}
CALIBRACAO: ${item.next_calibration_date || item.calibration_date || '-'}
DADOS MINIMOS PORQUE TA OFFLINE`;
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

function getItemById(id) {
  return state.items.find((item) => item.id === id) || null;
}

function createPreviewBlock() {
  if (!state.createPreviewUrl) {
    return `
      <div class="image-upload-box empty">
        <div class="image-upload-placeholder">${t('preview')}</div>
      </div>
    `;
  }

  return `
    <div class="image-upload-box">
      <img class="image-preview" src="${escapeHtml(state.createPreviewUrl)}" alt="${t('selectedPhoto')}" />
    </div>
    <div class="inline-actions">
      <button type="button" id="clearCreatePhoto" class="outline-button">${t('clearPhoto')}</button>
    </div>
  `;
}

function searchResultHtml() {
  return `<div id="searchFeedback"></div>`;
}

function createAdditionalFields(prefix, values) {
  const calibrationType = 'date';
  const nextCalibrationType = 'date';

  return `
    <div class="grid-2">
      <input id="${prefix}TypeInput" class="input" placeholder="${t('equipmentType')}" value="${escapeHtml(values.equipment_type || '')}" />
      <input id="${prefix}SectorInput" class="input" placeholder="${t('sector')}" value="${escapeHtml(values.sector || '')}" />
      <input id="${prefix}LocationInput" class="input" placeholder="${t('location')}" value="${escapeHtml(values.location || '')}" />
      <input id="${prefix}ManufacturerInput" class="input" placeholder="${t('manufacturer')}" value="${escapeHtml(values.manufacturer || '')}" />
      <input id="${prefix}ModelInput" class="input" placeholder="${t('model')}" value="${escapeHtml(values.model || '')}" />
      <input id="${prefix}SerialInput" class="input" placeholder="${t('serialNumber')}" value="${escapeHtml(values.serial_number || '')}" />
      <input id="${prefix}CalibrationDateInput" class="input" type="${calibrationType}" placeholder="${t('calibrationDate')}" value="${escapeHtml(values.calibration_date || '')}" />
      <input id="${prefix}NextCalibrationDateInput" class="input" type="${nextCalibrationType}" placeholder="${t('nextCalibrationDate')}" value="${escapeHtml(values.next_calibration_date || '')}" />
      <input id="${prefix}StatusInput" class="input" placeholder="${t('chooseStatus')}" value="${escapeHtml(values.status || 'Ativo')}" />
      <input id="${prefix}NotesInput" class="input" placeholder="${t('notes')}" value="${escapeHtml(values.notes || '')}" />
    </div>
  `;
}

function renderEditableRow(item) {
  const draft = state.editDraft || {
    tag: item.tag,
    name: item.name,
    equipment_type: item.equipment_type || '',
    sector: item.sector || '',
    location: item.location || '',
    manufacturer: item.manufacturer || '',
    model: item.model || '',
    serial_number: item.serial_number || '',
    calibration_date: item.calibration_date || '',
    next_calibration_date: item.next_calibration_date || '',
    status: item.status || 'Ativo',
    notes: item.notes || '',
    photoFile: null,
    previewUrl: item.photo || ''
  };

  return `
    <tr class="edit-row">
      <td class="code-soft">${escapeHtml(item.id)}</td>
      <td colspan="6">
        <div class="panel edit-panel">
          <div class="grid-2">
            <input id="editTagInput" class="input table-input" value="${escapeHtml(draft.tag)}" placeholder="${t('tag')}" />
            <input id="editNameInput" class="input table-input" value="${escapeHtml(draft.name)}" placeholder="${t('name')}" />
          </div>

          ${createAdditionalFields('edit', draft)}

          <div class="edit-photo-stack">
            ${draft.previewUrl
              ? `<img class="thumb thumb-large" src="${escapeHtml(draft.previewUrl)}" alt="${escapeHtml(draft.name)}" />`
              : `<div class="thumb-fallback thumb-large">${t('noImage')}</div>`}
            <input id="editPhotoInput" class="file-input compact-file" type="file" accept="image/*" />
          </div>

          <div class="inline-actions">
            <button class="primary-button" id="saveEditButton">${t('save')}</button>
            <button class="outline-button" id="cancelEditButton">${t('cancel')}</button>
          </div>
        </div>
      </td>
    </tr>
  `;
}

function renderRows(items) {
  if (!items.length) {
    return `
      <tr>
        <td colspan="7">
          <div class="empty-state">${t('noItems')}</div>
        </td>
      </tr>
    `;
  }

  return items.map((item) => {
    if (state.editingId === item.id) {
      return renderEditableRow(item);
    }

    return `
      <tr>
        <td class="code-soft">${escapeHtml(item.id)}</td>
        <td><strong>${escapeHtml(item.tag)}</strong></td>
        <td>
          <strong>${escapeHtml(item.name)}</strong>
          <div class="muted">${escapeHtml(item.equipment_type || '')}</div>
          <div class="muted">${escapeHtml(item.model || '')}</div>
          <div class="muted">${escapeHtml(item.serial_number || '')}</div>
        </td>
        <td>${photoHtml(item)}</td>
        <td>${statusPill(item.status)}</td>
        <td>${qrHtml(item.tag)}</td>
        <td>
          <div class="inline-actions">
            <button class="secondary-button" onclick="startEditItem(${item.id})">${t('edit')}</button>
            <button class="danger-button" onclick="askDeleteItem(${item.id})">${t('delete')}</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function renderDeleteConfirm() {
  if (!state.deleteTargetId) return '';

  const item = getItemById(state.deleteTargetId);
  if (!item) return '';

  return `
    <div class="card panel danger-panel">
      <h3>${t('deleteConfirmTitle')}</h3>
      <div class="notice error">
        ${t('deleteConfirmText')}<br>
        <strong>${escapeHtml(item.tag)} • ${escapeHtml(item.name)}</strong>
      </div>
      <div class="inline-actions">
        <button class="danger-button" id="confirmDeleteButton">${t('delete')}</button>
        <button class="outline-button" id="cancelDeleteButton">${t('cancel')}</button>
      </div>
    </div>
  `;
}

function renderLogin(notice = '') {
  app.innerHTML = `
    <section class="login-shell">
      <div class="card login-card">
        <div>
          <h2 class="login-title">${t('loginTitle')}</h2>
          <p class="login-subtitle">${t('loginSubtitle')}</p>
        </div>

        <div class="login-stack">
          <input id="loginUserInput" class="input" placeholder="${t('username')}" autocomplete="username" />
          <input id="loginPassInput" class="input" placeholder="${t('password')}" type="password" autocomplete="current-password" />
        </div>

        <div class="inline-actions">
          <button id="loginButton" class="primary-button">${t('loginButton')}</button>
        </div>

        <div id="loginFeedback">${notice}</div>
      </div>
    </section>
  `;

  bindLoginEvents();
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
          ${state.editingId ? `<span class="badge">${t('editMode')}</span>` : ''}
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
          <input id="tagInput" class="input" placeholder="${t('tag')}" value="${escapeHtml(state.createForm.tag)}" />
          <input id="nameInput" class="input" placeholder="${t('name')}" value="${escapeHtml(state.createForm.name)}" />

          ${createAdditionalFields('create', state.createForm)}

          <input id="photoInput" class="file-input" type="file" accept="image/*" />
          ${createPreviewBlock()}
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
          ${searchResultHtml()}
        </div>
      </div>

      ${renderDeleteConfirm()}

      <div class="card panel">
        <div class="inline-actions" style="justify-content: space-between; align-items: center;">
  <h3>${t('listTitle')}</h3>
  <button id="pdfButton" class="primary-button" type="button">Gerar PDF QR</button>
</div>
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
                <th>${t('actions')}</th>
              </tr>
            </thead>
            <tbody>
              ${renderRows(state.items)}
            </tbody>
          </table>
        </div>
      </div>

      <div class="footer-note">Admin V3 • login + QR + calibração + campos completos</div>
    </section>
  `;

  bindEvents();
  renderQRCodes();
}

function updateCreateFormState() {
  state.createForm.tag = normalizeText(document.getElementById('tagInput')?.value);
  state.createForm.name = normalizeText(document.getElementById('nameInput')?.value);
  state.createForm.equipment_type = normalizeText(document.getElementById('createTypeInput')?.value);
  state.createForm.sector = normalizeText(document.getElementById('createSectorInput')?.value);
  state.createForm.location = normalizeText(document.getElementById('createLocationInput')?.value);
  state.createForm.manufacturer = normalizeText(document.getElementById('createManufacturerInput')?.value);
  state.createForm.model = normalizeText(document.getElementById('createModelInput')?.value);
  state.createForm.serial_number = normalizeText(document.getElementById('createSerialInput')?.value);
  state.createForm.calibration_date = normalizeText(document.getElementById('createCalibrationDateInput')?.value);
  state.createForm.next_calibration_date = normalizeText(document.getElementById('createNextCalibrationDateInput')?.value);
  state.createForm.status = normalizeText(document.getElementById('createStatusInput')?.value) || 'Ativo';
  state.createForm.notes = normalizeText(document.getElementById('createNotesInput')?.value);
}

function bindCreateFormLiveState() {
  [
    'tagInput',
    'nameInput',
    'createTypeInput',
    'createSectorInput',
    'createLocationInput',
    'createManufacturerInput',
    'createModelInput',
    'createSerialInput',
    'createCalibrationDateInput',
    'createNextCalibrationDateInput',
    'createStatusInput',
    'createNotesInput'
  ].forEach((id) => {
    document.getElementById(id)?.addEventListener('input', updateCreateFormState);
    document.getElementById(id)?.addEventListener('change', updateCreateFormState);
  });
}

function bindLoginEvents() {
  document.getElementById('loginButton')?.addEventListener('click', async () => {
    const username = normalizeText(document.getElementById('loginUserInput')?.value);
    const password = document.getElementById('loginPassInput')?.value || '';
    const feedback = document.getElementById('loginFeedback');

    if (!username || !password) {
      feedback.innerHTML = `<div class="notice error">${t('loginError')}</div>`;
      return;
    }

    feedback.innerHTML = `<div class="notice">${t('loginLoading')}</div>`;

    try {
      const result = await loginAdmin(username, password);
      state.authToken = result.token;
      state.authUser = result.username || username;
      localStorage.setItem(CONFIG.STORAGE_KEYS.authToken, state.authToken);
      localStorage.setItem(CONFIG.STORAGE_KEYS.authUser, state.authUser);
      syncHeaderLanguage();
      await loadItems();
      renderApp(`<div class="notice success">${t('loginSuccess')}</div>`);
    } catch (error) {
      feedback.innerHTML = `<div class="notice error">${escapeHtml(error.message || t('loginError'))}</div>`;
    }
  });
}

function bindEvents() {
  bindCreateFormLiveState();

  document.getElementById('photoInput')?.addEventListener('change', (event) => {
    updateCreateFormState();
    const file = event.target.files?.[0];

    state.createPhotoFile = file || null;
    state.createPreviewUrl = file ? URL.createObjectURL(file) : '';

    renderApp();
  });

  document.getElementById('clearCreatePhoto')?.addEventListener('click', () => {
    state.createPreviewUrl = '';
    state.createPhotoFile = null;
    const input = document.getElementById('photoInput');
    if (input) input.value = '';
    renderApp();
  });

  document.getElementById('createButton')?.addEventListener('click', async () => {
    updateCreateFormState();

    const tag = state.createForm.tag;
    const name = state.createForm.name;
    const photoFile = state.createPhotoFile;
    const feedback = document.getElementById('createFeedback');

    if (!tag || !name || !photoFile) {
      feedback.innerHTML = `<div class="notice error">${t('typeTag')}</div>`;
      return;
    }

    const formData = new FormData();
    formData.append('tag', tag);
    formData.append('name', name);
    formData.append('photo', photoFile);
    formData.append('equipment_type', state.createForm.equipment_type);
    formData.append('sector', state.createForm.sector);
    formData.append('location', state.createForm.location);
    formData.append('manufacturer', state.createForm.manufacturer);
    formData.append('model', state.createForm.model);
    formData.append('serial_number', state.createForm.serial_number);
    formData.append('calibration_date', state.createForm.calibration_date);
    formData.append('next_calibration_date', state.createForm.next_calibration_date);
    formData.append('status', state.createForm.status);
    formData.append('notes', state.createForm.notes);

    feedback.innerHTML = `<div class="notice">${t('creating')}</div>`;

    try {
      await createEquipment(formData);
      resetCreateForm();
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
        <div class="search-result-card">
          <div class="search-result-media">
            ${item.photo
              ? `<img class="search-result-thumb" src="${escapeHtml(item.photo)}" alt="${escapeHtml(item.name)}" />`
              : `<div class="thumb-fallback thumb-large">${t('noImage')}</div>`}
          </div>
          <div class="search-result-body">
            <div class="search-result-label">${t('searchResult')}</div>
            <strong>${escapeHtml(item.name)}</strong>
            <div class="muted">TAG: ${escapeHtml(item.tag)}</div>
            <div class="muted">${escapeHtml(item.equipment_type || '')}</div>
            <div class="muted">${escapeHtml(item.calibration_date || '')} → ${escapeHtml(item.next_calibration_date || '')}</div>
            <div class="inline-actions">
              <a class="secondary-button" href="${viewerUrlForTag(item.tag)}" target="_blank" rel="noopener noreferrer">${t('openViewer')}</a>
              ${item.photo ? `<a class="outline-button" href="${escapeHtml(item.photo)}" target="_blank" rel="noopener noreferrer">${t('photo')}</a>` : ''}
            </div>
          </div>
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

  document.getElementById('pdfButton')?.addEventListener('click', () => {
    window.open(`${CONFIG.API_BASE_URL}/pdf/equipment/pdf-labels`, '_blank', 'noopener,noreferrer');
  });


  document.getElementById('editPhotoInput')?.addEventListener('change', (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    state.editDraft = {
      ...state.editDraft,
      photoFile: file,
      previewUrl: URL.createObjectURL(file)
    };
    renderApp();
  });

  [
    'editTagInput',
    'editNameInput',
    'editTypeInput',
    'editSectorInput',
    'editLocationInput',
    'editManufacturerInput',
    'editModelInput',
    'editSerialInput',
    'editCalibrationDateInput',
    'editNextCalibrationDateInput',
    'editStatusInput',
    'editNotesInput'
  ].forEach((id) => {
    document.getElementById(id)?.addEventListener('input', () => {
      state.editDraft = {
        ...state.editDraft,
        tag: normalizeText(document.getElementById('editTagInput')?.value),
        name: normalizeText(document.getElementById('editNameInput')?.value),
        equipment_type: normalizeText(document.getElementById('editTypeInput')?.value),
        sector: normalizeText(document.getElementById('editSectorInput')?.value),
        location: normalizeText(document.getElementById('editLocationInput')?.value),
        manufacturer: normalizeText(document.getElementById('editManufacturerInput')?.value),
        model: normalizeText(document.getElementById('editModelInput')?.value),
        serial_number: normalizeText(document.getElementById('editSerialInput')?.value),
        calibration_date: normalizeText(document.getElementById('editCalibrationDateInput')?.value),
        next_calibration_date: normalizeText(document.getElementById('editNextCalibrationDateInput')?.value),
        status: normalizeText(document.getElementById('editStatusInput')?.value),
        notes: normalizeText(document.getElementById('editNotesInput')?.value),
      };
    });
    document.getElementById(id)?.addEventListener('change', () => {
      state.editDraft = {
        ...state.editDraft,
        tag: normalizeText(document.getElementById('editTagInput')?.value),
        name: normalizeText(document.getElementById('editNameInput')?.value),
        equipment_type: normalizeText(document.getElementById('editTypeInput')?.value),
        sector: normalizeText(document.getElementById('editSectorInput')?.value),
        location: normalizeText(document.getElementById('editLocationInput')?.value),
        manufacturer: normalizeText(document.getElementById('editManufacturerInput')?.value),
        model: normalizeText(document.getElementById('editModelInput')?.value),
        serial_number: normalizeText(document.getElementById('editSerialInput')?.value),
        calibration_date: normalizeText(document.getElementById('editCalibrationDateInput')?.value),
        next_calibration_date: normalizeText(document.getElementById('editNextCalibrationDateInput')?.value),
        status: normalizeText(document.getElementById('editStatusInput')?.value),
        notes: normalizeText(document.getElementById('editNotesInput')?.value),
      };
    });
  });

  document.getElementById('saveEditButton')?.addEventListener('click', async () => {
    if (!state.editingId || !state.editDraft) return;

    const form = new FormData();
    form.append('tag', state.editDraft.tag || '');
    form.append('name', state.editDraft.name || '');
    form.append('equipment_type', state.editDraft.equipment_type || '');
    form.append('sector', state.editDraft.sector || '');
    form.append('location', state.editDraft.location || '');
    form.append('manufacturer', state.editDraft.manufacturer || '');
    form.append('model', state.editDraft.model || '');
    form.append('serial_number', state.editDraft.serial_number || '');
    form.append('calibration_date', state.editDraft.calibration_date || '');
    form.append('next_calibration_date', state.editDraft.next_calibration_date || '');
    form.append('status', state.editDraft.status || 'Ativo');
    form.append('notes', state.editDraft.notes || '');

    if (state.editDraft.photoFile) {
      form.append('photo', state.editDraft.photoFile);
    }

    try {
      await updateEquipment(state.editingId, form);
      state.editingId = null;
      state.editDraft = null;
      await loadItems();
      renderApp(`<div class="notice success">${t('updateSuccess')}</div>`);
    } catch (error) {
      renderApp(`<div class="notice error">${escapeHtml(error.message || t('updateError'))}</div>`);
    }
  });

  document.getElementById('cancelEditButton')?.addEventListener('click', () => {
    state.editingId = null;
    state.editDraft = null;
    renderApp();
  });

  document.getElementById('confirmDeleteButton')?.addEventListener('click', async () => {
    if (!state.deleteTargetId) return;

    try {
      await deleteEquipment(state.deleteTargetId);
      state.deleteTargetId = null;
      await loadItems();
      renderApp(`<div class="notice success">${t('deleteSuccess')}</div>`);
    } catch (error) {
      renderApp(`<div class="notice error">${escapeHtml(error.message || t('deleteError'))}</div>`);
    }
  });

  document.getElementById('cancelDeleteButton')?.addEventListener('click', () => {
    state.deleteTargetId = null;
    renderApp();
  });
}

function renderQRCodes() {
  state.items.forEach((item) => {
    const qrId = `qr-${String(item.tag).replace(/[^a-zA-Z0-9_-]/g, '')}`;
    const canvas = document.getElementById(qrId);
    if (!canvas || typeof QRCode === 'undefined') return;

    const payload = buildQrPayload(item);

    QRCode.toCanvas(canvas, payload, {
      width: 140,
      margin: 2,
      color: {
        dark: "#000000",
        light: "#ffffff"
      }
    }, () => {});
  });
}

window.startEditItem = function(id) {
  const item = getItemById(id);
  if (!item) return;

  state.editingId = id;
  state.deleteTargetId = null;
  state.editDraft = {
    tag: item.tag,
    name: item.name,
    equipment_type: item.equipment_type || '',
    sector: item.sector || '',
    location: item.location || '',
    manufacturer: item.manufacturer || '',
    model: item.model || '',
    serial_number: item.serial_number || '',
    calibration_date: item.calibration_date || '',
    next_calibration_date: item.next_calibration_date || '',
    status: item.status || 'Ativo',
    notes: item.notes || '',
    photoFile: null,
    previewUrl: item.photo || ''
  };
  renderApp();
};

window.askDeleteItem = function(id) {
  state.deleteTargetId = id;
  state.editingId = null;
  state.editDraft = null;
  renderApp();
};

function logoutAdmin() {
  state.authToken = '';
  state.authUser = '';
  state.items = [];
  state.editingId = null;
  state.editDraft = null;
  state.deleteTargetId = null;
  localStorage.removeItem(CONFIG.STORAGE_KEYS.authToken);
  localStorage.removeItem(CONFIG.STORAGE_KEYS.authUser);
  syncHeaderLanguage();
  renderLogin();
}

function renderCurrentView(notice = '') {
  syncHeaderLanguage();

  if (!state.authToken) {
    renderLogin(notice);
    return;
  }

  renderApp(notice);
}

async function boot() {
  syncHeaderLanguage();
  openViewerButton.href = CONFIG.VIEWER_BASE_URL;

  try {
    await pingApi();
    if (state.authToken) {
      await loadItems();
      renderApp();
    } else {
      renderLogin();
    }
  } catch (error) {
    if (state.authToken) {
      renderApp(`<div class="notice error">${escapeHtml(error.message || t('listError'))}</div>`);
    } else {
      renderLogin(`<div class="notice error">${escapeHtml(error.message || t('apiFail'))}</div>`);
    }
  }
}

document.getElementById('langPt').addEventListener('click', () => setLanguage('pt'));
document.getElementById('langEn').addEventListener('click', () => setLanguage('en'));
logoutButton.addEventListener('click', logoutAdmin);

boot();