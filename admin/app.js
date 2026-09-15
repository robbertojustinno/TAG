const CONFIG = window.TAGCHECK_ADMIN_CONFIG;
const app = document.getElementById('app');
const openViewerButton = document.getElementById('openViewerButton');
const logoutButton = document.getElementById('logoutButton');

const I18N = {
  pt: {
    brandTitle: 'TagCheck • Smart Asset Tracking',
    brandSubtitle: 'Powered by Rovix Automation™ ⚡',
    heroTitle: 'Painel',
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
    username: 'E-mail',
    company: 'Empresa',
    selectCompany: 'Selecionar empresa',
    companySubtitle: 'Escolha a empresa para acessar o painel.',
    companyDenied: 'Acesso à empresa não autorizado.',
    backToLogin: 'Voltar ao login',
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
    brandSubtitle: 'Powered by Rovix Automation™ ⚡',
    heroTitle: 'Painel',
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
    username: 'Email or legacy username',
    company: 'Company',
    selectCompany: 'Select company',
    companySubtitle: 'Choose a company to access the panel.',
    companyDenied: 'Company access is not authorized.',
    backToLogin: 'Back to login',
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

// Discard the previous persistent login; require a fresh server-issued session.
localStorage.removeItem("tagcheck_admin_auth_token");
localStorage.removeItem('tagcheck_admin_auth_user');

const state = {
  language: localStorage.getItem(CONFIG.STORAGE_KEYS.language) || 'pt',
  authToken: sessionStorage.getItem(CONFIG.STORAGE_KEYS.authToken) || '',
  authUser: sessionStorage.getItem(CONFIG.STORAGE_KEYS.authUser) || '',
  companyName: '',
  isSuperadmin: false,
  role: '',
  apiSuccessVersion: 0,
  showSuperadmin: false,
  pendingPassword: sessionStorage.getItem(CONFIG.STORAGE_KEYS.authToken + '.password_change') || '',
  pendingSelection: null,
  items: [],
  units: [],
  selectedUnitId: '',
  categories: [],
  selectedCategoryId: '',
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
    notes: '',
    category_id: ''
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
  document.querySelector('.topbar-actions').classList.toggle('hidden', !!state.pendingPassword);
  document.getElementById('brandTitle').textContent = 'TAGCHECK';
  document.getElementById('brandSubtitle').textContent = state.authToken ? '' : t('brandSubtitle');
  document.getElementById('companyAdminButton').classList.toggle('hidden', !state.authToken || state.role !== 'company_admin' || state.isSuperadmin);
  document.querySelector('.footer-note')?.classList.toggle('hidden', !!state.authToken);
  document.getElementById('langPt').className = state.language === 'pt'
    ? 'secondary-button lang-button active'
    : 'outline-button lang-button';
  document.getElementById('langEn').className = state.language === 'en'
    ? 'secondary-button lang-button active'
    : 'outline-button lang-button';
  openViewerButton.textContent = t('viewer');
  logoutButton.textContent = t('logout');
  logoutButton.classList.toggle('hidden', !state.authToken);
  const company = document.getElementById('activeCompany');
  company.textContent = state.companyName ? `${t('company')}: ${state.companyName}` : '';
  company.classList.toggle('hidden', !state.authToken || !state.companyName);
  document.getElementById('superadminButton').classList.toggle('hidden', !state.authToken || !state.isSuperadmin);
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
    ,category_id: ''
  };
}

async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CONFIG.REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal, cache: 'no-store' });
    if (response.ok) {
      state.apiReachable = true;
      state.apiSuccessVersion += 1;
      const badge = document.getElementById('apiStatusBadge');
      if (badge) badge.textContent = t('apiOk');
    }
    if (response.status === 401 && options.headers?.Authorization && !url.endsWith('/auth/change-password')) {
      logoutAdmin();
    }
    return response;
  } finally {
    clearTimeout(timer);
  }
}

async function pingApi() {
  const successVersion = state.apiSuccessVersion;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, CONFIG.ENDPOINTS.health));
      if (response.ok) return true;
    } catch {
      // Render may still be starting; retry briefly.
    }
    if (attempt < 2) await new Promise(resolve => setTimeout(resolve, 400));
  }
  if (state.apiSuccessVersion === successVersion) state.apiReachable = false;
  return state.apiReachable === true;
}

function canWriteEquipment() {
  return state.isSuperadmin || ['company_admin', 'supervisor', 'operator'].includes(state.role);
}

function canDeleteEquipment() {
  return state.isSuperadmin || ['company_admin', 'supervisor'].includes(state.role);
}

function canManageUnits() {
  return state.isSuperadmin || state.role === 'company_admin';
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
    category_id: raw.category_id ?? '',
    category_path: Array.isArray(raw.category_path) ? raw.category_path : [],
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
    body: JSON.stringify(username.includes('@') ? { email: username, password } : { username, password })
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(t('loginError'));
  }

  return await response.json();
}

async function readIdentity(token = state.authToken) {
  const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, '/auth/me'), {
    headers: { Accept: 'application/json', Authorization: `Bearer ${token}` }
  });
  if (!response.ok) {
    logoutAdmin();
    throw new Error(t('loginError'));
  }
  const identity = await response.json();
  state.logoUrl = identity.logo_url;
  state.role = identity.role || '';
  return identity;
}

async function finishLogin(result) {
  if (result.must_change_password) return requirePasswordChange(result.token);
  if (result.requires_company_selection) {
    state.pendingSelection = result;
    return renderCompanySelection();
  }
  if (!result.token) throw new Error(t('loginError'));
  const identity = await readIdentity(result.token);
  if (identity.must_change_password) return requirePasswordChange(result.token);
  state.authToken = result.token;
  state.authUser = result.username || identity.email;
  state.companyName = identity.company_name;
  state.isSuperadmin = identity.is_superadmin === true;
  state.pendingSelection = null;
  sessionStorage.setItem(CONFIG.STORAGE_KEYS.authToken, state.authToken);
  sessionStorage.setItem(CONFIG.STORAGE_KEYS.authUser, state.authUser);
  syncHeaderLanguage();
  await refreshCompanyLogo();
  await loadUnits();
  await loadCategories();
  await loadItems();
  if (state.authToken) renderApp();
}

function requirePasswordChange(token) {
  logoutAdmin();
  state.pendingPassword = token;
  sessionStorage.setItem(CONFIG.STORAGE_KEYS.authToken + '.password_change', token);
  renderPasswordChange();
}

function renderPasswordChange() {
  syncHeaderLanguage();
  app.innerHTML = `<section class="login-shell"><form id="changePasswordForm" class="card login-card">
    <h2 class="login-title">Defina sua nova senha</h2>
    <p class="login-subtitle">Use uma senha própria com pelo menos 12 caracteres.</p>
    <div class="login-stack">
      <label>Senha atual<input name="current_password" class="input" type="password" autocomplete="current-password" maxlength="1024" required></label>
      <label>Nova senha<input name="new_password" class="input" type="password" autocomplete="new-password" minlength="12" maxlength="1024" required></label>
      <label>Confirmar nova senha<input name="confirm_password" class="input" type="password" autocomplete="new-password" minlength="12" maxlength="1024" required></label>
    </div>
    <div class="inline-actions"><button class="primary-button">Alterar senha</button>
      <button id="cancelPasswordChange" class="outline-button" type="button">Sair</button></div>
    <div id="passwordFeedback" role="alert"></div>
  </form></section>`;
  document.getElementById('cancelPasswordChange').addEventListener('click', logoutAdmin);
  document.getElementById('changePasswordForm').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const token = state.pendingPassword;
    const controls = [...form.querySelectorAll('button')];
    controls.forEach(button => button.disabled = true);
    try {
      const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, '/auth/change-password'), {
        method: 'POST', headers: {'Content-Type': 'application/json', Authorization: `Bearer ${token}`},
        body: JSON.stringify(Object.fromEntries(new FormData(form)))
      });
      const result = await response.json();
      if (token !== state.pendingPassword) return;
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Verifique as senhas. A nova senha deve ter pelo menos 12 caracteres.');
      state.pendingPassword = '';
      sessionStorage.removeItem(CONFIG.STORAGE_KEYS.authToken + '.password_change');
      syncHeaderLanguage();
      await finishLogin(result);
    } catch (error) {
      if (token === state.pendingPassword) document.getElementById('passwordFeedback').textContent = error.message;
      else renderCurrentView();
    } finally {
      form.reset();
      controls.forEach(button => button.disabled = false);
    }
  });
}

function renderCompanySelection(notice = '') {
  app.innerHTML = `
    <section class="login-shell">
      <form id="companyForm" class="card login-card">
        <div><h2 class="login-title">${t('selectCompany')}</h2>
          <p class="login-subtitle">${t('companySubtitle')}</p></div>
        <label for="companySelect">${t('company')}</label>
        <select id="companySelect" class="input" required>
          ${state.pendingSelection.companies.map(company =>
            `<option value="${escapeHtml(company.id)}">${escapeHtml(company.name)}</option>`).join('')}
        </select>
        <div class="inline-actions">
          <button id="selectCompanyButton" class="primary-button" type="submit">${t('loginButton')}</button>
          <button id="cancelCompanyButton" class="outline-button" type="button">${t('backToLogin')}</button>
        </div>
        <div role="alert">${notice}</div>
      </form>
    </section>`;
  document.getElementById('cancelCompanyButton').addEventListener('click', logoutAdmin);
  document.getElementById('companyForm').addEventListener('submit', async event => {
    event.preventDefault();
    const button = document.getElementById('selectCompanyButton');
    const cancel = document.getElementById('cancelCompanyButton');
    button.disabled = cancel.disabled = true;
    try {
      const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, '/auth/select-company'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${state.pendingSelection.selection_token}` },
        body: JSON.stringify({ company_id: Number(document.getElementById('companySelect').value) })
      });
      if (!response.ok) throw new Error(t(response.status === 403 ? 'companyDenied' : 'loginError'));
      await finishLogin(await response.json());
    } catch (error) {
      renderCurrentView(`<div class="notice error">${escapeHtml(error.message)}</div>`);
    }
  });
}

async function loadItems() {
  const params = [];
  if (state.selectedUnitId) params.push(`unit_id=${encodeURIComponent(state.selectedUnitId)}`);
  if (state.selectedCategoryId) params.push(`category_id=${encodeURIComponent(state.selectedCategoryId)}`, 'include_children=true');
  const path = params.length ? `${CONFIG.ENDPOINTS.list}?${params.join('&')}` : CONFIG.ENDPOINTS.list;
  const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, path), {
    headers: getAuthHeaders({ Accept: 'application/json' })
  });

  if (!response.ok) throw new Error(t('listError'));

  const data = await response.json();
  state.items = Array.isArray(data) ? data.map(normalizeItem) : [];
  return state.items;
}

async function loadCategories() {
  const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, '/asset-categories'), {
    headers: getAuthHeaders({ Accept: 'application/json' })
  });
  if (!response.ok) throw new Error(t('listError'));
  state.categories = await response.json();
  return state.categories;
}

function categoryOptions(selected = '') {
  const rows = [...state.categories].sort((a, b) => (a.parent_id || 0) - (b.parent_id || 0) || a.sort_order - b.sort_order || a.name.localeCompare(b.name));
  const byParent = new Map();
  rows.forEach(row => byParent.set(row.parent_id || 0, [...(byParent.get(row.parent_id || 0) || []), row]));
  const result = [];
  const walk = (parent, depth) => (byParent.get(parent) || []).forEach(row => {
    result.push(`<option value="${escapeHtml(row.id)}" ${String(row.id) === String(selected) ? 'selected' : ''}>${'&nbsp;'.repeat(depth * 4)}${escapeHtml(row.name)}${row.asset_count ? ` (${row.asset_count})` : ''}</option>`);
    walk(row.id, depth + 1);
  });
  walk(0, 0);
  return result.join('');
}

function categoryManagerHtml() {
  if (!state.categories.length && !canManageUnits()) return '';
  const byParent = new Map(); state.categories.forEach(c => byParent.set(c.parent_id || 0, [...(byParent.get(c.parent_id || 0) || []), c]));
  const node = (parent, depth = 0) => (byParent.get(parent) || []).map(c => `<div class="category-node" style="padding-left:${depth * 14}px"><button type="button" class="outline-button" data-category-id="${c.id}">${escapeHtml(c.name)} (${c.asset_count || 0})</button>${canManageUnits() ? `<button type="button" class="outline-button" data-category-edit="${c.id}">Editar</button><button type="button" class="outline-button" data-category-active="${c.id}" data-active="${!c.active}">${c.active ? 'Desativar' : 'Ativar'}</button>` : ''}${node(c.id, depth + 1)}</div>`).join('');
  return `<div class="card panel asset-manager"><div class="inline-actions" style="justify-content:space-between"><h3>Gerenciador de ativos</h3>${canManageUnits() ? '<button id="newCategoryButton" class="primary-button" type="button">+ Nova categoria</button>' : ''}</div>
    <div class="asset-manager-grid"><div><label>Categoria</label><select id="categoryFilter" class="input"><option value="">Todas as categorias</option>${categoryOptions(state.selectedCategoryId)}</select><div class="category-tree">${node(0)}</div></div>
    <div><p class="subtle">Selecione uma categoria para mostrar ativos do ramo. Categorias existentes sem vínculo mantêm os equipamentos em “Todas as categorias”.</p><div id="categoryFeedback"></div></div></div></div>`;
}

async function loadUnits() {
  const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, '/units'), {
    headers: getAuthHeaders({ Accept: 'application/json' })
  });
  if (!response.ok) throw new Error(t('listError'));
  const data = await response.json();
  state.units = Array.isArray(data) ? data : [];
  if (!state.units.some(unit => String(unit.id) === String(state.selectedUnitId))) state.selectedUnitId = '';
  return state.units;
}

async function searchByTag(tag) {
  const cleanTag = normalizeText(tag);
  if (!cleanTag) throw new Error(t('typeTag'));

  localStorage.setItem(CONFIG.STORAGE_KEYS.lastSearch, cleanTag);

  const searchPath = buildUrl(CONFIG.API_BASE_URL,
    CONFIG.ENDPOINTS.byTag.replace(':tag', encodeURIComponent(cleanTag)));
  const searchParams = [];
  if (state.selectedCategoryId) searchParams.push(`category_id=${encodeURIComponent(state.selectedCategoryId)}`, 'include_children=true');
  const url = `${searchPath}${searchParams.length ? `?${searchParams.join('&')}` : ''}`;

  const response = await fetchWithTimeout(url, {
    headers: getAuthHeaders({ Accept: 'application/json' })
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
      <label>Categoria<select id="${prefix}CategoryInput" class="input"><option value="">Sem categoria</option>${categoryOptions(values.category_id || '')}</select></label>
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
    category_id: item.category_id || '',
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
    if (canWriteEquipment() && state.editingId === item.id) {
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
          <div class="muted">${escapeHtml((item.category_path || []).join(' > ') || 'Sem categoria')}</div>
        </td>
        <td>${photoHtml(item)}</td>
        <td>${statusPill(item.status)}</td>
        <td>${qrHtml(item.tag)}</td>
        <td>
          <div class="inline-actions">
            ${canWriteEquipment() ? `<button class="secondary-button" onclick="startEditItem(${item.id})">${t('edit')}</button>` : ''}
            ${canDeleteEquipment() ? `<button class="danger-button" onclick="askDeleteItem(${item.id})">${t('delete')}</button>` : ''}
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function renderDeleteConfirm() {
  if (!canDeleteEquipment() || !state.deleteTargetId) return '';

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
      <form id="loginForm" class="card login-card">
        <div>
          <h2 class="login-title">${t('loginTitle')}</h2>
          <p class="login-subtitle">${t('loginSubtitle')}</p>
        </div>

        <div class="login-stack">
          <input id="loginUserInput" class="input" aria-label="${t('username')}" placeholder="${t('username')}" autocomplete="username" autocapitalize="none" required />
          <input id="loginPassInput" class="input" aria-label="${t('password')}" placeholder="${t('password')}" type="password" autocomplete="current-password" required />
        </div>

        <div class="inline-actions">
          <button id="loginButton" class="primary-button">${t('loginButton')}</button>
        </div>

        <div id="loginFeedback" role="alert">${notice}</div>
      </form>
    </section>
  `;

  bindLoginEvents();
}

function renderApp(notice = '') {
  if (state.pendingPassword) return renderPasswordChange();
  const total = state.items.length;
  const withPhoto = state.items.filter((x) => !!x.photo).length;
  const noPhoto = total - withPhoto;
  const apiBadge = state.apiReachable
    ? `<span id="apiStatusBadge" class="badge">${t('apiOk')}</span>`
    : `<span id="apiStatusBadge" class="badge">${t('apiFail')}</span>`;

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
        ${canWriteEquipment() ? `<div class="card panel">
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
        </div>` : ''}

        <div class="card panel">
          ${!canWriteEquipment() ? notice : ''}
          <h3>${t('searchTitle')}</h3>
          <input id="searchTagInput" class="input" placeholder="${t('searchPlaceholder')}" value="${escapeHtml(localStorage.getItem(CONFIG.STORAGE_KEYS.lastSearch) || '')}" />
          <div class="inline-actions">
            <button id="searchButton" class="secondary-button">${t('searchButton')}</button>
            <button id="refreshButton" class="outline-button">${t('refresh')}</button>
          </div>
          ${searchResultHtml()}
        </div>
      </div>

      <div class="card panel">
        <label for="unitFilter">Unidade</label>
        <select id="unitFilter" class="input">
          <option value="">Todas as unidades</option>
          ${state.units.map(unit => `<option value="${escapeHtml(unit.id)}" ${String(unit.id) === String(state.selectedUnitId) ? 'selected' : ''}>${escapeHtml(unit.name)}</option>`).join('')}
        </select>
        <small class="subtle">Equipamentos sem unidade aparecem em “Todas as unidades”.</small>
      </div>

      ${categoryManagerHtml()}

      ${canManageUnits() ? `<div class="card panel" id="unitManagement">
        <h3>Unidades</h3>
        <form id="unitCreateForm" class="inline-actions">
          <input id="unitName" class="input" aria-label="Nome da unidade" placeholder="Nome da unidade" required maxlength="200" />
          <input id="unitSlug" class="input" aria-label="Código da unidade" placeholder="Código da unidade" required maxlength="100" />
          <button class="primary-button" type="submit">Cadastrar unidade</button>
        </form>
        ${state.units.map(unit => `<div class="inline-actions"><span>${escapeHtml(unit.name)}</span>
          <button class="outline-button" data-unit-toggle="${escapeHtml(unit.id)}" data-active="${unit.active ? 'false' : 'true'}">${unit.active ? 'Desativar' : 'Ativar'}</button></div>`).join('')}
        <div id="unitFeedback" role="alert"></div>
      </div>` : ''}
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

      <div class="footer-note">Admin V7 • TagCheck • Smart Asset Tracking</div>
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
  state.createForm.category_id = document.getElementById('createCategoryInput')?.value || '';
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
    'createNotesInput',
    'createCategoryInput'
  ].forEach((id) => {
    document.getElementById(id)?.addEventListener('input', updateCreateFormState);
    document.getElementById(id)?.addEventListener('change', updateCreateFormState);
  });
}

function bindLoginEvents() {
  document.getElementById('loginForm')?.addEventListener('submit', async event => {
    event.preventDefault();
    const username = normalizeText(document.getElementById('loginUserInput')?.value);
    const password = document.getElementById('loginPassInput')?.value || '';
    const feedback = document.getElementById('loginFeedback');

    if (!username || !password) {
      feedback.innerHTML = `<div class="notice error">${t('loginError')}</div>`;
      return;
    }

    feedback.innerHTML = `<div class="notice">${t('loginLoading')}</div>`;
    document.getElementById('loginButton').disabled = true;

    try {
      const result = await loginAdmin(username, password);
      if (result.requires_company_selection) {
        state.pendingSelection = result;
        renderCompanySelection();
      } else {
        await finishLogin(result);
      }
    } catch (error) {
      renderCurrentView(`<div class="notice error">${escapeHtml(error.message || t('loginError'))}</div>`);
    }
  });
}

function bindEvents() {
  const changeUnit = async (path, method, data) => {
    if (!canManageUnits()) return;
    try {
      const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, path), {
        method, headers: getAuthHeaders({'Content-Type': 'application/json'}), body: JSON.stringify(data)
      });
      if (!response.ok) throw new Error('Não foi possível salvar a unidade. Verifique os dados e permissões.');
      await loadUnits();
      if (state.authToken) renderApp();
    } catch (error) {
      const feedback = document.getElementById('unitFeedback');
      if (feedback) feedback.textContent = error.message;
    }
  };
  document.getElementById('unitCreateForm')?.addEventListener('submit', event => {
    event.preventDefault();
    changeUnit('/units', 'POST', {name: document.getElementById('unitName').value, slug: document.getElementById('unitSlug').value});
  });
  document.querySelectorAll('[data-unit-toggle]').forEach(button => button.addEventListener('click', () => {
    changeUnit(`/units/${button.dataset.unitToggle}`, 'PATCH', {active: button.dataset.active === 'true'});
  }));
  bindCreateFormLiveState();

  document.getElementById('unitFilter')?.addEventListener('change', async event => {
    state.selectedUnitId = event.target.value;
    try {
      await loadItems();
      renderApp();
    } catch (error) {
      renderApp(`<div class="notice error">${escapeHtml(error.message || t('listError'))}</div>`);
    }
  });

  document.getElementById('categoryFilter')?.addEventListener('change', async event => {
    state.selectedCategoryId = event.target.value;
    try { await loadItems(); renderApp(); }
    catch (error) { renderApp(`<div class="notice error">${escapeHtml(error.message || t('listError'))}</div>`); }
  });
  document.querySelectorAll('[data-category-id]').forEach(button => button.addEventListener('click', async () => {
    state.selectedCategoryId = button.dataset.categoryId;
    await loadItems();
    renderApp();
  }));
  document.getElementById('newCategoryButton')?.addEventListener('click', async () => {
    const name = window.prompt('Nome da categoria');
    if (!name || !name.trim()) return;
    const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, '/asset-categories'), {
      method: 'POST', headers: getAuthHeaders({'Content-Type': 'application/json'}),
      body: JSON.stringify({name: name.trim()})
    });
    if (!response.ok) { const feedback = document.getElementById('categoryFeedback'); if (feedback) feedback.textContent = 'Não foi possível criar a categoria.'; return; }
    await loadCategories(); renderApp();
  });
  document.querySelectorAll('[data-category-edit]').forEach(button => button.addEventListener('click', async () => {
    const category = state.categories.find(item => String(item.id) === button.dataset.categoryEdit);
    const name = window.prompt('Nome da categoria', category?.name || '');
    if (!name || !name.trim()) return;
    const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, `/asset-categories/${button.dataset.categoryEdit}`), {
      method: 'PATCH', headers: getAuthHeaders({'Content-Type': 'application/json'}), body: JSON.stringify({name: name.trim()})
    });
    if (response.ok) { await loadCategories(); renderApp(); }
  }));
  document.querySelectorAll('[data-category-active]').forEach(button => button.addEventListener('click', async () => {
    const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, `/asset-categories/${button.dataset.categoryActive}`), {
      method: 'PATCH', headers: getAuthHeaders({'Content-Type': 'application/json'}), body: JSON.stringify({active: button.dataset.active === 'true'})
    });
    if (response.ok) { await loadCategories(); renderApp(); }
  }));

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
    formData.append('category_id', state.createForm.category_id || '');

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

  document.getElementById('pdfButton')?.addEventListener('click', openEquipmentPdf);


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
    ,'editCategoryInput'
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
        category_id: document.getElementById('editCategoryInput')?.value || '',
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
        category_id: document.getElementById('editCategoryInput')?.value || '',
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
    form.append('category_id', state.editDraft.category_id || '');

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
  if (!canWriteEquipment()) return;
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
    category_id: item.category_id || '',
    photoFile: null,
    previewUrl: item.photo || ''
  };
  renderApp();
};

window.askDeleteItem = function(id) {
  if (!canDeleteEquipment()) return;
  state.deleteTargetId = id;
  state.editingId = null;
  state.editDraft = null;
  renderApp();
};

function logoutAdmin() {
  state.pendingPassword = '';
  sessionStorage.removeItem(CONFIG.STORAGE_KEYS.authToken + '.password_change');
  state.showCompanyAdmin = false;
  state.logoUrl = null;
  clearCompanyLogo();
  state.authToken = '';
  state.authUser = '';
  state.role = '';
  state.companyName = '';
  state.isSuperadmin = false;
  state.showSuperadmin = false;
  state.pendingSelection = null;
  state.items = [];
  state.units = [];
  state.selectedUnitId = '';
  state.editingId = null;
  state.editDraft = null;
  state.deleteTargetId = null;
  sessionStorage.removeItem(CONFIG.STORAGE_KEYS.authToken);
  sessionStorage.removeItem(CONFIG.STORAGE_KEYS.authUser);
  syncHeaderLanguage();
  renderLogin();
}

function renderCurrentView(notice = '') {
  if (state.pendingPassword) return renderPasswordChange();
  syncHeaderLanguage();

  if (!state.authToken) {
    if (state.pendingSelection) renderCompanySelection(notice);
    else renderLogin(notice);
    return;
  }

  if (state.showCompanyAdmin && state.role === 'company_admin' && !state.isSuperadmin) {
    window.TAGCHECK_COMPANY.mount(app, companyRequest, escapeHtml, () => {
      state.showCompanyAdmin = false; renderCurrentView();
    }, refreshCompanyIdentity);
  } else if (state.showSuperadmin && state.isSuperadmin) {
    window.TAGCHECK_SUPERADMIN.mount(app, superadminRequest, escapeHtml, () => {
      state.showSuperadmin = false;
      renderCurrentView();
    }, refreshCompanyIdentity);
  } else renderApp(notice);
}

async function superadminRequest(path, method = 'GET', data, blob = false) {
  if (!state.authToken || !state.isSuperadmin || !state.showSuperadmin) throw new Error('Acesso não autorizado.');
  return companyRequest(path, method, data, blob);
}

async function companyRequest(path, method = 'GET', data, blob = false) {
  if (!state.authToken) throw new Error('Entre novamente.');
  const multipart = data instanceof FormData;
  const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, path), {
    method, headers: getAuthHeaders(multipart ? {} : { 'Content-Type': 'application/json' }),
    ...(data === undefined ? {} : { body: multipart ? data : JSON.stringify(data) })
  });
  if (response.status === 403) {
    state.isSuperadmin = false;
    state.showSuperadmin = false;
    state.showCompanyAdmin = false;
    state.role = '';
    renderCurrentView();
  }
  if (!response.ok) {
    const messages = {401: 'Sessão expirada. Entre novamente.', 403: 'Acesso não autorizado.',
      404: 'Registro não encontrado.', 409: 'Não foi possível salvar. Verifique os dados ou contate o suporte administrativo.',
      422: 'Verifique os campos informados, o domínio do e-mail e o formato da imagem.'};
    throw new Error(messages[response.status] || 'Não foi possível concluir a operação.');
  }
  return blob ? response.blob() : response.json();
}

async function boot() {
  syncHeaderLanguage();
  openViewerButton.href = CONFIG.VIEWER_BASE_URL;

  try {
    if (state.pendingPassword) {
      const identity = await readIdentity(state.pendingPassword);
      if (identity.must_change_password) return renderPasswordChange();
      return logoutAdmin();
    }
    await pingApi();
    if (state.authToken) {
      const identity = await readIdentity();
      if (identity.must_change_password) return requirePasswordChange(state.authToken);
      state.companyName = identity.company_name;
      state.isSuperadmin = identity.is_superadmin === true;
      syncHeaderLanguage();
      await refreshCompanyLogo();
      await loadUnits();
      await loadCategories();
      await loadItems();
      renderApp();
    } else {
      renderLogin();
    }
  } catch (error) {
    if (state.pendingPassword) {
      renderPasswordChange();
      document.getElementById('passwordFeedback').textContent = 'Não foi possível validar a sessão. Verifique sua conexão ou entre novamente.';
      return;
    }
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
document.getElementById('companyAdminButton').addEventListener('click', () => {
  if (!state.authToken || state.role !== 'company_admin' || state.isSuperadmin) return;
  state.showCompanyAdmin = true; renderCurrentView();
});

document.getElementById('superadminButton').addEventListener('click', () => {
  if (!state.authToken || !state.isSuperadmin) return;
  state.showSuperadmin = true;
  renderCurrentView();
});

boot();


async function openEquipmentPdf() {
  // Open synchronously to preserve the existing new-tab behavior under popup blockers.
  const target = `tagcheck_pdf_${crypto.randomUUID()}`;
  const tab = window.open('about:blank', target);
  if (!tab) return;
  tab.opener = null;
  try {
    const response = await fetchWithTimeout(`${CONFIG.API_BASE_URL}/equipment/pdf-access`, {
      method: 'POST', headers: getAuthHeaders({ Accept: 'application/json' })
    });
    if (!response.ok) throw new Error('Não foi possível gerar o PDF. Entre novamente e tente outra vez.');
    const result = await response.json();
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = `${CONFIG.API_BASE_URL}/equipment/pdf`;
    form.target = target;
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'pdf_token';
    input.value = result.token;
    form.appendChild(input);
    document.body.appendChild(form);
    form.submit();
    form.remove();
  } catch (error) {
    tab.close();
    const feedback = document.getElementById('searchFeedback');
    if (feedback) feedback.textContent = error.message;
  }
}

let companyLogoObjectUrl = null;
function clearCompanyLogo() {
  if (companyLogoObjectUrl) URL.revokeObjectURL(companyLogoObjectUrl);
  companyLogoObjectUrl = null;
  document.querySelector('.brand-logo').src = './public/logo.png';
}
async function refreshCompanyLogo() {
  clearCompanyLogo();
  const token = state.authToken, url = state.logoUrl;
  if (!token || !url) return;
  try {
    const response = await fetchWithTimeout(buildUrl(CONFIG.API_BASE_URL, url), {headers: getAuthHeaders()});
    if (!response.ok) return;
    const blob = await response.blob();
    if (state.authToken !== token || state.logoUrl !== url) return;
    companyLogoObjectUrl = URL.createObjectURL(blob);
    document.querySelector('.brand-logo').src = companyLogoObjectUrl;
  } catch (_) { /* Keep the standard identity if the image is unavailable. */ }
}
async function refreshCompanyIdentity() {
  const identity = await readIdentity();
  state.companyName = identity.company_name;
  syncHeaderLanguage();
  await refreshCompanyLogo();
}
