const DB_NAME = 'tagcheck_campo_offline_v1';
const STORE = 'pending_equipment';
const CONFIG_KEY = 'tagcheck_campo_config';
const DEFAULT_API = 'https://tag-1-xfzk.onrender.com';
let db;
let deferredPrompt;

const $ = (id) => document.getElementById(id);

function toast(msg, type='') {
  const el = $('toast');
  el.textContent = msg;
  el.className = `toast ${type}`;
  setTimeout(() => el.classList.add('hidden'), 3500);
}

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const database = req.result;
      if (!database.objectStoreNames.contains(STORE)) {
        const store = database.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
        store.createIndex('tag', 'tag', { unique: false });
        store.createIndex('created_at', 'created_at', { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function tx(mode='readonly') { return db.transaction(STORE, mode).objectStore(STORE); }

function getAllPending() {
  return new Promise((resolve, reject) => {
    const req = tx().getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

function addPending(item) {
  return new Promise((resolve, reject) => {
    const req = tx('readwrite').add(item);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function deletePending(id) {
  return new Promise((resolve, reject) => {
    const req = tx('readwrite').delete(Number(id));
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

function clearStore() {
  return new Promise((resolve, reject) => {
    const req = tx('readwrite').clear();
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

function loadConfig() {
  const config = JSON.parse(localStorage.getItem(CONFIG_KEY) || '{}');
  $('apiBase').value = config.apiBase || DEFAULT_API;
  $('token').value = config.token || '';
  $('loginUser').value = config.username || 'admin';
}

function saveConfig() {
  localStorage.setItem(CONFIG_KEY, JSON.stringify({
    apiBase: $('apiBase').value.trim() || DEFAULT_API,
    token: $('token').value.trim(),
    username: $('loginUser').value.trim() || 'admin'
  }));
}

function config() {
  const data = JSON.parse(localStorage.getItem(CONFIG_KEY) || '{}');
  return { apiBase: data.apiBase || DEFAULT_API, token: data.token || '' };
}

function updateNetworkStatus() {
  const el = $('netStatus');
  if (navigator.onLine) {
    el.textContent = 'Online';
    el.className = 'status-pill ok';
  } else {
    el.textContent = 'Offline';
    el.className = 'status-pill off';
  }
}

async function renderPending() {
  const list = await getAllPending();
  $('countBadge').textContent = `${list.length} pendente${list.length === 1 ? '' : 's'}`;
  const box = $('pendingList');
  if (!list.length) {
    box.innerHTML = '<p class="small">Nenhum cadastro pendente. Você pode cadastrar mesmo sem internet.</p>';
    return;
  }
  box.innerHTML = '';
  for (const item of list.sort((a,b)=>(b.created_at||'').localeCompare(a.created_at||''))) {
    const url = URL.createObjectURL(item.photo_blob);
    const div = document.createElement('div');
    div.className = 'pending-item';
    div.innerHTML = `
      <img src="${url}" alt="Foto">
      <div>
        <h4>${escapeHtml(item.tag)} — ${escapeHtml(item.name)}</h4>
        <p>${escapeHtml(item.sector || '-')} • ${escapeHtml(item.location || '-')}</p>
        <p>Salvo: ${new Date(item.created_at).toLocaleString('pt-BR')}</p>
      </div>
      <div class="mini-actions">
        <button class="secondary" data-sync="${item.id}">Enviar</button>
        <button class="outline" data-del="${item.id}">Excluir</button>
      </div>`;
    box.appendChild(div);
  }
  box.querySelectorAll('[data-del]').forEach(btn => btn.onclick = async () => {
    if (confirm('Excluir este cadastro pendente?')) { await deletePending(btn.dataset.del); await renderPending(); toast('Cadastro pendente excluído.'); }
  });
  box.querySelectorAll('[data-sync]').forEach(btn => btn.onclick = async () => syncOne(Number(btn.dataset.sync)));
}

function escapeHtml(v) { return String(v ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])); }

function clearForm() {
  $('equipmentForm').reset();
  $('preview').src = '';
  $('preview').classList.add('hidden');
}

async function fileToBlob(file) {
  return new Blob([await file.arrayBuffer()], { type: file.type || 'image/jpeg' });
}

function isoDateBRToInput(value) { return value || ''; }

async function saveOffline(event) {
  event.preventDefault();
  const photo = $('photo').files[0];
  if (!photo) { toast('Selecione ou tire uma foto.', 'error'); return; }
  const tag = $('tag').value.trim().toUpperCase();
  const name = $('name').value.trim();
  if (!tag || !name) { toast('TAG e Nome são obrigatórios.', 'error'); return; }

  const item = {
    tag,
    name,
    equipment_type: $('equipment_type').value.trim(),
    sector: $('sector').value.trim(),
    location: $('location').value.trim(),
    manufacturer: $('manufacturer').value.trim(),
    model: $('model').value.trim(),
    serial_number: $('serial_number').value.trim(),
    calibration_date: isoDateBRToInput($('calibration_date').value),
    next_calibration_date: isoDateBRToInput($('next_calibration_date').value),
    status: $('status').value.trim() || 'Ativo',
    notes: $('notes').value.trim(),
    photo_name: `${tag}.jpg`,
    photo_type: photo.type || 'image/jpeg',
    photo_blob: await fileToBlob(photo),
    created_at: new Date().toISOString(),
    synced_at: ''
  };
  await addPending(item);
  clearForm();
  await renderPending();
  toast('Salvo offline. Tire a próxima foto/cadastre o próximo instrumento.', 'ok');
}

function buildFormData(item) {
  const fd = new FormData();
  ['tag','name','equipment_type','sector','location','manufacturer','model','serial_number','calibration_date','next_calibration_date','status','notes'].forEach(k => fd.append(k, item[k] || ''));
  fd.append('photo', item.photo_blob, item.photo_name || `${item.tag}.jpg`);
  return fd;
}

async function apiFetch(path, options={}) {
  const { apiBase, token } = config();
  const headers = options.headers || {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${apiBase.replace(/\/$/, '')}${path}`, { ...options, headers });
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const msg = data?.detail || `Erro HTTP ${res.status}`;
    const err = new Error(msg);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

async function syncItem(item) {
  try {
    await apiFetch('/equipment', { method: 'POST', body: buildFormData(item) });
    return 'created';
  } catch (err) {
    const msg = String(err.message || '').toLowerCase();
    if (err.status === 400 && msg.includes('tag')) {
      const existing = await apiFetch(`/equipment/tag/${encodeURIComponent(item.tag)}`);
      await apiFetch(`/equipment/${existing.id}`, { method: 'PUT', body: buildFormData(item) });
      return 'updated';
    }
    throw err;
  }
}

async function syncOne(id) {
  if (!navigator.onLine) { toast('Sem internet para sincronizar.', 'error'); return; }
  if (!config().token) { toast('Faça login/salve o token antes de sincronizar.', 'error'); return; }
  const all = await getAllPending();
  const item = all.find(x => x.id === Number(id));
  if (!item) return;
  try {
    const action = await syncItem(item);
    await deletePending(id);
    await renderPending();
    toast(action === 'created' ? 'Cadastro enviado.' : 'TAG já existia: cadastro atualizado.', 'ok');
  } catch (err) {
    toast(`Falha ao enviar ${item.tag}: ${err.message}`, 'error');
  }
}

async function syncAll() {
  if (!navigator.onLine) { toast('Sem internet para sincronizar.', 'error'); return; }
  if (!config().token) { toast('Faça login/salve o token antes de sincronizar.', 'error'); return; }
  const all = await getAllPending();
  if (!all.length) { toast('Não há pendentes.', 'ok'); return; }
  let ok = 0, fail = 0;
  for (const item of all) {
    try { await syncItem(item); await deletePending(item.id); ok++; }
    catch (err) { console.error(item.tag, err); fail++; }
  }
  await renderPending();
  toast(`Sincronização concluída. Enviados: ${ok}. Falhas: ${fail}.`, fail ? 'error' : 'ok');
}

async function login() {
  const apiBase = $('apiBase').value.trim() || DEFAULT_API;
  const username = $('loginUser').value.trim();
  const password = $('loginPass').value;
  if (!username || !password) { toast('Informe usuário e senha.', 'error'); return; }
  try {
    const res = await fetch(`${apiBase.replace(/\/$/, '')}/auth/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Falha no login');
    $('token').value = data.token;
    saveConfig();
    toast('Login salvo. Agora pode sincronizar.', 'ok');
  } catch (err) { toast(err.message, 'error'); }
}

async function exportJson() {
  const all = await getAllPending();
  const serializable = [];
  for (const item of all) {
    const base64 = await blobToBase64(item.photo_blob);
    serializable.push({ ...item, photo_blob: base64 });
  }
  const blob = new Blob([JSON.stringify(serializable, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `tagcheck_pendentes_${new Date().toISOString().slice(0,10)}.json`;
  a.click();
}

function blobToBase64(blob) { return new Promise(resolve => { const r = new FileReader(); r.onload = () => resolve(r.result); r.readAsDataURL(blob); }); }
function base64ToBlob(dataUrl) { const [head, b64] = dataUrl.split(','); const mime = (head.match(/data:(.*);base64/)||[])[1] || 'image/jpeg'; const bin = atob(b64); const arr = new Uint8Array(bin.length); for(let i=0;i<bin.length;i++) arr[i]=bin.charCodeAt(i); return new Blob([arr], {type:mime}); }

async function importJson(file) {
  const text = await file.text();
  const data = JSON.parse(text);
  if (!Array.isArray(data)) throw new Error('JSON inválido.');
  for (const item of data) {
    item.photo_blob = typeof item.photo_blob === 'string' ? base64ToBlob(item.photo_blob) : item.photo_blob;
    delete item.id;
    await addPending(item);
  }
  await renderPending();
  toast('Backup importado.', 'ok');
}

async function init() {
  db = await openDb();
  loadConfig();
  updateNetworkStatus();
  await renderPending();

  $('equipmentForm').addEventListener('submit', saveOffline);
  $('clearBtn').onclick = clearForm;
  $('syncBtn').onclick = syncAll;
  $('loginBtn').onclick = login;
  $('saveConfigBtn').onclick = () => { saveConfig(); toast('Configuração salva.', 'ok'); };
  $('exportBtn').onclick = exportJson;
  $('importFile').onchange = (e) => e.target.files[0] && importJson(e.target.files[0]).catch(err => toast(err.message, 'error'));
  $('photo').onchange = () => {
    const file = $('photo').files[0];
    if (!file) return;
    $('preview').src = URL.createObjectURL(file);
    $('preview').classList.remove('hidden');
  };

  window.addEventListener('online', updateNetworkStatus);
  window.addEventListener('offline', updateNetworkStatus);
  window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferredPrompt = e; $('installBtn').classList.remove('hidden'); });
  $('installBtn').onclick = async () => { if (deferredPrompt) { deferredPrompt.prompt(); await deferredPrompt.userChoice; deferredPrompt = null; $('installBtn').classList.add('hidden'); } };
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(console.warn);
}
init().catch(err => toast(`Erro inicial: ${err.message}`, 'error'));
