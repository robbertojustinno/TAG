(() => {
  const DB_VERSION = 1;
  const STORE_SNAPSHOTS = 'snapshots';
  const STORE_QUEUE = 'queue';
  const CONTEXT_KEY = 'tagcheck_offline_context_v1';

  function requireCompanyId(companyId) {
    const id = Number(companyId);
    if (!Number.isInteger(id) || id <= 0) throw new Error('Empresa offline inválida.');
    return id;
  }

  function dbName(companyId) {
    return `tagcheck_offline_company_${requireCompanyId(companyId)}`;
  }

  function openDb(companyId) {
    const name = dbName(companyId);
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(name, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(STORE_SNAPSHOTS)) db.createObjectStore(STORE_SNAPSHOTS, { keyPath: 'key' });
        if (!db.objectStoreNames.contains(STORE_QUEUE)) {
          const store = db.createObjectStore(STORE_QUEUE, { keyPath: 'local_id' });
          store.createIndex('status', 'status', { unique: false });
          store.createIndex('created_at', 'created_at', { unique: false });
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error('Falha ao abrir armazenamento offline.'));
    });
  }

  function txRequest(request) {
    return new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error('Falha no armazenamento offline.'));
    });
  }

  async function withStore(companyId, storeName, mode, callback) {
    const db = await openDb(companyId);
    try {
      const tx = db.transaction(storeName, mode);
      const store = tx.objectStore(storeName);
      const result = await callback(store);
      await new Promise((resolve, reject) => {
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error || new Error('Falha na transação offline.'));
        tx.onabort = () => reject(tx.error || new Error('Transação offline cancelada.'));
      });
      return result;
    } finally {
      db.close();
    }
  }

  async function putSnapshot(companyId, key, value) {
    const id = requireCompanyId(companyId);
    return withStore(id, STORE_SNAPSHOTS, 'readwrite', store =>
      txRequest(store.put({ key: String(key), company_id: id, value, updated_at: new Date().toISOString() }))
    );
  }

  async function getSnapshot(companyId, key, fallback = null) {
    const id = requireCompanyId(companyId);
    const row = await withStore(id, STORE_SNAPSHOTS, 'readonly', store => txRequest(store.get(String(key))));
    if (!row || Number(row.company_id) !== id) return fallback;
    return row.value;
  }

  async function enqueueCreate(companyId, userId, payload, photoFile) {
    const id = requireCompanyId(companyId);
    const localId = `offline-${crypto.randomUUID()}`;
    const row = {
      local_id: localId,
      company_id: id,
      user_id: userId == null ? null : Number(userId),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      status: 'pending_sync',
      last_error: '',
      operation: 'create_equipment',
      payload: structuredClone(payload),
      photo: photoFile || null
    };
    await withStore(id, STORE_QUEUE, 'readwrite', store => txRequest(store.add(row)));
    return row;
  }

  async function listQueue(companyId) {
    const id = requireCompanyId(companyId);
    const rows = await withStore(id, STORE_QUEUE, 'readonly', store => txRequest(store.getAll()));
    return (rows || [])
      .filter(row => Number(row.company_id) === id)
      .sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
  }

  async function deleteQueueItem(companyId, localId) {
    const id = requireCompanyId(companyId);
    return withStore(id, STORE_QUEUE, 'readwrite', store => txRequest(store.delete(String(localId))));
  }

  async function markQueueItem(companyId, localId, status, error = '') {
    const id = requireCompanyId(companyId);
    return withStore(id, STORE_QUEUE, 'readwrite', async store => {
      const row = await txRequest(store.get(String(localId)));
      if (!row || Number(row.company_id) !== id) return null;
      row.status = status;
      row.last_error = String(error || '');
      row.updated_at = new Date().toISOString();
      await txRequest(store.put(row));
      return row;
    });
  }

  function saveContext(context) {
    if (!context?.company_id) return;
    const safe = {
      company_id: requireCompanyId(context.company_id),
      company_name: String(context.company_name || ''),
      user_id: context.user_id == null ? null : Number(context.user_id),
      email: String(context.email || ''),
      role: String(context.role || ''),
      is_superadmin: context.is_superadmin === true,
      expires_at: Number(context.expires_at || 0)
    };
    sessionStorage.setItem(CONTEXT_KEY, JSON.stringify(safe));
  }

  function loadContext() {
    try {
      const value = JSON.parse(sessionStorage.getItem(CONTEXT_KEY) || 'null');
      if (!value?.company_id || !value.expires_at || Date.now() >= value.expires_at) return null;
      value.company_id = requireCompanyId(value.company_id);
      return value;
    } catch {
      return null;
    }
  }

  function clearContext() {
    sessionStorage.removeItem(CONTEXT_KEY);
  }

  function tokenExpiryMs(token) {
    try {
      const part = String(token || '').split('.')[1];
      if (!part) return 0;
      const normalized = part.replace(/-/g, '+').replace(/_/g, '/');
      const payload = JSON.parse(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')));
      return Number(payload.exp || 0) * 1000;
    } catch {
      return 0;
    }
  }

  window.TAGCHECK_OFFLINE = {
    putSnapshot, getSnapshot, enqueueCreate, listQueue, deleteQueueItem, markQueueItem,
    saveContext, loadContext, clearContext, tokenExpiryMs
  };
})();