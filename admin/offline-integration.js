(() => {
  const CONFIG = window.TAGCHECK_ADMIN_CONFIG;
  const OFFLINE = window.TAGCHECK_OFFLINE;
  if (!CONFIG || !OFFLINE) return;

  const metroKeys = ['measurand','measurement_unit','range_min','range_max','accuracy_class','resolution','ema','reading_contribution'];

  function state() {
    return window.TAGCHECK_ADMIN_STATE || {};
  }

  function hooks() {
    return window.TAGCHECK_ADMIN_OFFLINE_HOOKS || {};
  }

  function authToken() {
    return sessionStorage.getItem(CONFIG.STORAGE_KEYS.authToken) || '';
  }

  function tokenCompanyId(token) {
    try {
      const part = String(token).split('.')[1];
      if (!part) return null;
      const normalized = part.replace(/-/g, '+').replace(/_/g, '/');
      const payload = JSON.parse(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')));
      return payload.company_id == null ? null : Number(payload.company_id);
    } catch {
      return null;
    }
  }

  function activeContext() {
    const s = state();
    const context = OFFLINE.loadContext();
    if (!context || !s.companyId) return null;
    if (Number(context.company_id) !== Number(s.companyId)) return null;
    return context;
  }

  function field(id) {
    return document.getElementById(id)?.value?.trim() || '';
  }

  function capturePayload() {
    const payload = {
      tag: field('tagInput').toUpperCase(),
      name: field('nameInput'),
      equipment_type: field('createTypeInput'),
      sector: field('createSectorInput'),
      location: field('createLocationInput'),
      manufacturer: field('createManufacturerInput'),
      model: field('createModelInput'),
      serial_number: field('createSerialInput'),
      calibration_date: field('createCalibrationDateInput'),
      next_calibration_date: field('createNextCalibrationDateInput'),
      status: field('createStatusInput') || 'Ativo',
      notes: field('createNotesInput'),
      category_id: field('createCategoryInput')
    };
    metroKeys.forEach(key => { payload[key] = field('createMetro_' + key); });
    return payload;
  }

  function photoFile() {
    return document.getElementById('photoInput')?.files?.[0] || state().createPhotoFile || null;
  }

  function setFeedback(html) {
    const node = document.getElementById('createFeedback');
    if (node) node.innerHTML = html;
  }

  async function refreshStatus() {
    const s = state();
    if (!s.companyId) return 0;
    const rows = await OFFLINE.listQueue(s.companyId);
    s.pendingOfflineCount = rows.length;
    renderStatus(rows);
    return rows.length;
  }

  function renderStatus(rows = []) {
    const s = state();
    const row = document.querySelector('.badge-row');
    if (!row || !s.companyId) return;
    let badge = document.getElementById('offlineTenantStatus');
    if (!badge) {
      badge = document.createElement('span');
      badge.id = 'offlineTenantStatus';
      badge.className = 'badge';
      row.appendChild(badge);
    }
    const count = Array.isArray(rows) ? rows.length : Number(s.pendingOfflineCount || 0);
    const text = navigator.onLine
      ? (count ? `Sincronização: ${count} pendente(s)` : 'Online — sincronizado')
      : `Offline — ${count} pendente(s)`;
    if (badge.textContent !== text) badge.textContent = text;

    let button = document.getElementById('offlineSyncNow');
    if (navigator.onLine && count) {
      if (!button) {
        button = document.createElement('button');
        button.id = 'offlineSyncNow';
        button.type = 'button';
        button.className = 'outline-button';
        button.textContent = 'Sincronizar agora';
        button.addEventListener('click', syncQueue);
        row.appendChild(button);
      }
    } else if (button) {
      button.remove();
    }
  }

  function pendingItem(row) {
    return {
      id: row.local_id,
      tag: row.payload?.tag || '-',
      name: row.payload?.name || 'Instrumento',
      photo: row.photo ? URL.createObjectURL(row.photo) : null,
      equipment_type: row.payload?.equipment_type || '',
      sector: row.payload?.sector || '',
      location: row.payload?.location || '',
      manufacturer: row.payload?.manufacturer || '',
      model: row.payload?.model || '',
      serial_number: row.payload?.serial_number || '',
      calibration_date: row.payload?.calibration_date || '',
      next_calibration_date: row.payload?.next_calibration_date || '',
      status: row.status === 'sync_error' ? 'Erro de sincronização' : 'Pendente de sincronização',
      notes: row.payload?.notes || '',
      category_id: row.payload?.category_id || '',
      category_path: [],
      qr_payload: '',
      offline_pending: true,
      offline_status: row.status
    };
  }

  async function queueCurrentCreate() {
    const s = state();
    const context = activeContext();
    if (!context || !s.authToken || !s.companyId) {
      throw new Error('Faça login online e selecione a empresa antes de trabalhar offline.');
    }
    const payload = capturePayload();
    const photo = photoFile();
    if (!payload.tag || !payload.name || !photo) {
      throw new Error('Digite TAG, nome e selecione uma foto.');
    }
    const row = await OFFLINE.enqueueCreate(s.companyId, s.userId, payload, photo);
    s.pendingOfflineCount = Number(s.pendingOfflineCount || 0) + 1;
    s.items = [pendingItem(row), ...(s.items || []).filter(item => item.id !== row.local_id)];
    if (typeof hooks().resetCreateForm === 'function') hooks().resetCreateForm();
    if (typeof hooks().renderCurrentView === 'function') {
      hooks().renderCurrentView('<div class="notice success">Cadastro salvo offline nesta empresa. Será sincronizado quando a conexão voltar.</div>');
    } else {
      setFeedback('<div class="notice success">Cadastro salvo offline. Aguardando sincronização.</div>');
    }
    await refreshStatus();
  }

  function buildFormData(row) {
    const form = new FormData();
    Object.entries(row.payload || {}).forEach(([key, value]) => form.append(key, value ?? ''));
    if (row.photo) form.append('photo', row.photo, row.photo.name || 'offline-photo.jpg');
    return form;
  }

  async function syncQueue() {
    const s = state();
    const context = activeContext();
    const token = authToken();
    if (!navigator.onLine || !context || !token || !s.companyId) return;

    const claimCompany = tokenCompanyId(token);
    if (claimCompany != null && Number(claimCompany) !== Number(s.companyId)) {
      throw new Error('Empresa da sessão não corresponde ao armazenamento offline.');
    }

    const rows = await OFFLINE.listQueue(s.companyId);
    for (const row of rows) {
      if (Number(row.company_id) !== Number(s.companyId)) continue;
      await OFFLINE.markQueueItem(s.companyId, row.local_id, 'syncing');
      try {
        const response = await fetch(CONFIG.API_BASE_URL.replace(/\/$/, '') + CONFIG.ENDPOINTS.create, {
          method: 'POST',
          headers: { Authorization: 'Bearer ' + token },
          body: buildFormData(row),
          cache: 'no-store'
        });
        if (response.status === 401 || response.status === 403) {
          await OFFLINE.markQueueItem(s.companyId, row.local_id, 'pending_sync', 'Sessão expirada ou sem permissão.');
          break;
        }
        if (!response.ok) {
          const message = await response.text().catch(() => '');
          await OFFLINE.markQueueItem(s.companyId, row.local_id, 'sync_error', message || 'Cadastro rejeitado pela API.');
          continue;
        }
        await OFFLINE.deleteQueueItem(s.companyId, row.local_id);
      } catch (error) {
        await OFFLINE.markQueueItem(s.companyId, row.local_id, 'pending_sync', error?.message || 'Sem conexão.');
        break;
      }
    }

    s.apiReachable = true;
    await refreshStatus();
    if (typeof hooks().loadItems === 'function') {
      try { await hooks().loadItems(); } catch {}
    }
    if (typeof hooks().renderCurrentView === 'function') hooks().renderCurrentView();
  }

  document.addEventListener('click', event => {
    const target = event.target?.closest?.('#createButton');
    if (!target) return;
    const s = state();
    if (navigator.onLine && s.apiReachable !== false) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    queueCurrentCreate().catch(error => {
      setFeedback('<div class="notice error">' + String(error.message || error) + '</div>');
    });
  }, true);

  window.addEventListener('online', () => {
    const s = state();
    s.apiReachable = true;
    syncQueue().catch(() => refreshStatus());
  });

  window.addEventListener('offline', () => {
    const s = state();
    s.apiReachable = false;
    refreshStatus().catch(() => null);
  });

  let statusScheduled = false;
  const observer = new MutationObserver(() => {
    if (statusScheduled) return;
    statusScheduled = true;
    setTimeout(() => {
      statusScheduled = false;
      refreshStatus().catch(() => null);
    }, 50);
  });
  observer.observe(document.getElementById('app'), { childList: true, subtree: true });

  setTimeout(() => {
    refreshStatus().then(count => {
      if (navigator.onLine && count) syncQueue().catch(() => null);
    }).catch(() => null);
  }, 500);
})();