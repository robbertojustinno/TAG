const CONFIG = window.TAGCHECK_VIEWER_CONFIG;
const app = document.getElementById('app');
const backButton = document.getElementById('backButton');
const installButton = document.getElementById('installButton');

const state = {
  screen: 'home',
  currentItem: null,
  deferredPrompt: null,
  scanner: null,
  apiReachable: null,
  currentNotice: '',
};

function safeJsonParse(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
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

function getStorageValue(key, fallback) {
  return safeJsonParse(localStorage.getItem(key)) ?? fallback;
}

function setStorageValue(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function getSettings() {
  return getStorageValue(CONFIG.STORAGE_KEYS.settings, { autoOpenSheet: false });
}

function saveRecentItem(item) {
  if (!item) return;
  const key = CONFIG.STORAGE_KEYS.recentItems;
  const current = getStorageValue(key, []);
  const normalized = normalizeEquipment(item);
  const idKey = normalized.id || normalized.tag;
  const deduped = [normalized, ...current.filter((x) => (x.id || x.tag) !== idKey)].slice(0, 10);
  setStorageValue(key, deduped);
}

function getRecentItems() {
  return getStorageValue(CONFIG.STORAGE_KEYS.recentItems, []);
}

function saveFallbackCache(item) {
  if (!item?.tag) return;
  const cache = getStorageValue(CONFIG.STORAGE_KEYS.fallbackCache, {});
  cache[item.tag] = normalizeEquipment(item);
  setStorageValue(CONFIG.STORAGE_KEYS.fallbackCache, cache);
}

function getFallbackByTag(tag) {
  const cache = getStorageValue(CONFIG.STORAGE_KEYS.fallbackCache, {});
  return cache[tag] || null;
}

function statusClass(status) {
  const value = normalizeText(status).toLowerCase();
  if (['ativo', 'em uso', 'ok', 'calibrado', 'disponível', 'disponivel'].some((term) => value.includes(term))) return 'status-ok';
  if (['manutenção', 'manutencao', 'atenção', 'atencao', 'pendente', 'revisão', 'revisao'].some((term) => value.includes(term))) return 'status-warning';
  if (['inativo', 'bloqueado', 'vencido', 'erro', 'crítico', 'critico'].some((term) => value.includes(term))) return 'status-danger';
  return 'status-neutral';
}

function normalizeEquipment(raw) {
  if (!raw) return null;
  const source = typeof raw === 'object' ? raw : { raw };

  return {
    id: source.id ?? source.instrument_id ?? source.equipment_id ?? source.asset_id ?? null,
    tag: source.tag ?? source.codigo ?? source.code ?? source.patrimonio ?? source.asset_code ?? source.instrument_tag ?? '-',
    name: source.name ?? source.nome ?? source.description ?? source.descricao ?? source.instrumento ?? source.equipment_name ?? 'Instrumento',
    type: source.type ?? source.tipo ?? source.category ?? source.categoria ?? '-',
    serial: source.serial ?? source.serial_number ?? source.numero_serie ?? '-',
    sector: source.sector ?? source.setor ?? source.area ?? source.location_sector ?? '-',
    location: source.location ?? source.localizacao ?? source.local ?? source.room ?? '-',
    status: source.status ?? source.situacao ?? source.condition ?? '-',
    calibrationDate: source.calibration_date ?? source.data_calibracao ?? source.last_calibration ?? '-',
    validityDate: source.validity_date ?? source.data_validade ?? source.next_due_date ?? source.expiration_date ?? '-',
    manufacturer: source.manufacturer ?? source.fabricante ?? '-',
    model: source.model ?? source.modelo ?? '-',
    range: source.range ?? source.faixa ?? '-',
    resolution: source.resolution ?? source.resolucao ?? '-',
    certificate: source.certificate ?? source.certificado ?? '-',
    owner: source.owner ?? source.responsavel ?? '-',
    notes: source.notes ?? source.observacoes ?? source.obs ?? '-',
    photo: source.photo ?? source.image ?? source.image_url ?? source.photo_url ?? source.foto ?? null,
    sheetUrl: source.sheet_url ?? source.ficha_url ?? source.url ?? source.link ?? source.online_url ?? null,
    source: source.source ?? 'api',
    raw: source.raw ?? source,
  };
}

function buildEndpoint(urlBase, template, tokenName, tokenValue) {
  if (!urlBase) return null;
  return `${urlBase.replace(/\/$/, '')}${template.replace(`:${tokenName}`, encodeURIComponent(tokenValue))}`;
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

async function tryFetchJson(url) {
  if (!url) return null;
  try {
    const response = await fetchWithTimeout(url, { headers: { Accept: 'application/json' } });
    if (!response.ok) return null;

    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
      const text = await response.text();
      return safeJsonParse(text) || null;
    }

    return await response.json();
  } catch {
    return null;
  }
}

function extractBestItem(payload) {
  if (!payload) return null;
  if (Array.isArray(payload)) return payload.length ? normalizeEquipment(payload[0]) : null;
  if (payload.data) return Array.isArray(payload.data) ? (payload.data[0] ? normalizeEquipment(payload.data[0]) : null) : normalizeEquipment(payload.data);
  if (payload.item) return normalizeEquipment(payload.item);
  if (payload.result) return normalizeEquipment(payload.result);
  if (payload.rows && Array.isArray(payload.rows)) return payload.rows[0] ? normalizeEquipment(payload.rows[0]) : null;
  return normalizeEquipment(payload);
}

async function pingApi() {
  const baseUrl = CONFIG.API_BASE_URL.replace(/\/$/, '');
  for (const path of CONFIG.ENDPOINTS.health) {
    try {
      const response = await fetchWithTimeout(`${baseUrl}${path}`, { method: 'GET' });
      if (response.ok || response.status === 401 || response.status === 403) {
        state.apiReachable = true;
        return true;
      }
    } catch {
      // continue
    }
  }
  state.apiReachable = false;
  return false;
}

async function searchByTag(tag) {
  const cleanTag = normalizeText(tag);
  if (!cleanTag) throw new Error('Informe uma TAG válida.');

  localStorage.setItem(CONFIG.STORAGE_KEYS.lastSearch, cleanTag);
  const baseUrl = CONFIG.API_BASE_URL;
  const attempts = CONFIG.ENDPOINTS.byTag.map((template) => buildEndpoint(baseUrl, template, 'tag', cleanTag));

  for (const url of attempts) {
    const payload = await tryFetchJson(url);
    const item = extractBestItem(payload);
    if (item && item.tag && item.name) {
      item.source = 'api';
      saveRecentItem(item);
      saveFallbackCache(item);
      return item;
    }
  }

  const fallback = getFallbackByTag(cleanTag);
  if (fallback) {
    fallback.source = 'offline-cache';
    saveRecentItem(fallback);
    return fallback;
  }

  throw new Error('Nenhum instrumento encontrado para esta TAG.');
}

async function searchById(id) {
  const cleanId = normalizeText(id);
  if (!cleanId) throw new Error('ID inválido.');

  const baseUrl = CONFIG.API_BASE_URL;
  const attempts = CONFIG.ENDPOINTS.byId.map((template) => buildEndpoint(baseUrl, template, 'id', cleanId));

  for (const url of attempts) {
    const payload = await tryFetchJson(url);
    const item = extractBestItem(payload);
    if (item) {
      item.source = 'api';
      saveRecentItem(item);
      if (item.tag && item.tag !== '-') saveFallbackCache(item);
      return item;
    }
  }

  throw new Error('Instrumento não localizado pelo ID recebido no QR.');
}

function parseHybridText(text) {
  const raw = normalizeText(text);
  if (!raw) return null;

  if (/^https?:\/\//i.test(raw)) {
    const url = new URL(raw);
    const params = url.searchParams;
    const result = {
      kind: 'url',
      url: raw,
      id: params.get('id') || null,
      tag: params.get('tag') || params.get('codigo') || params.get('code') || null,
      params: Object.fromEntries(params.entries()),
    };
    return result;
  }

  const json = safeJsonParse(raw);
  if (json && typeof json === 'object') {
    return {
      kind: 'json',
      data: json,
      tag: json.tag ?? json.codigo ?? json.code ?? null,
      id: json.id ?? json.instrument_id ?? null,
    };
  }

  const pairPattern = /([a-zA-Z_]+)\s*[:=]\s*([^|;,\n]+)/g;
  const pairs = {};
  let match = null;
  while ((match = pairPattern.exec(raw)) !== null) {
    pairs[match[1].trim().toLowerCase()] = match[2].trim();
  }

  if (Object.keys(pairs).length) {
    return {
      kind: 'pairs',
      data: pairs,
      tag: CONFIG.QR_PARSE_KEYS.map((key) => pairs[key]).find(Boolean) || null,
      id: pairs.id || null,
    };
  }

  const probableTag = raw.match(/[A-Z0-9._\/-]{4,}/i)?.[0] || null;
  return { kind: 'text', raw, tag: probableTag };
}

async function resolveQrContent(content) {
  const parsed = parseHybridText(content);
  if (!parsed) throw new Error('QR vazio ou inválido.');

  if (parsed.kind === 'url' && parsed.tag) {
    const item = await searchByTag(parsed.tag);
    if (!item.sheetUrl) item.sheetUrl = parsed.url;
    return { item, notice: 'QR reconhecido como link com TAG.' };
  }

  if (parsed.kind === 'url' && parsed.id) {
    const item = await searchById(parsed.id);
    if (!item.sheetUrl) item.sheetUrl = parsed.url;
    return { item, notice: 'QR reconhecido como link com ID do instrumento.' };
  }

  if (parsed.kind === 'json') {
    if (parsed.tag) {
      const item = await searchByTag(parsed.tag).catch(() => null);
      if (item) return { item, notice: 'QR JSON reconhecido e consultado online.' };
    }
    const fallbackItem = normalizeEquipment({ ...parsed.data, source: 'hybrid-offline' });
    saveRecentItem(fallbackItem);
    saveFallbackCache(fallbackItem);
    return { item: fallbackItem, notice: 'QR híbrido lido com dados locais mínimos.' };
  }

  if (parsed.kind === 'pairs') {
    if (parsed.tag) {
      const item = await searchByTag(parsed.tag).catch(() => null);
      if (item) return { item, notice: 'QR híbrido reconhecido por TAG.' };
    }

    const fallbackItem = normalizeEquipment({
      tag: parsed.data.tag || parsed.data.codigo || '-',
      name: parsed.data.nome || parsed.data.name || 'Instrumento',
      serial: parsed.data.serial || '-',
      location: parsed.data.local || parsed.data.location || '-',
      sector: parsed.data.setor || parsed.data.sector || '-',
      status: parsed.data.status || '-',
      source: 'hybrid-offline',
      raw: parsed.data,
    });
    saveRecentItem(fallbackItem);
    if (fallbackItem.tag && fallbackItem.tag !== '-') saveFallbackCache(fallbackItem);
    return { item: fallbackItem, notice: 'QR híbrido aberto em modo fallback.' };
  }

  if (parsed.kind === 'text' && parsed.tag) {
    const item = await searchByTag(parsed.tag);
    return { item, notice: 'TAG identificada a partir do conteúdo do QR.' };
  }

  throw new Error('Não foi possível identificar TAG ou ID no QR lido.');
}

function recentListHtml() {
  const items = getRecentItems();
  if (!items.length) return '<div class="notice">Nenhuma consulta recente ainda.</div>';

  return items.map((item, index) => `
    <div class="list-item">
      <button data-open-recent="${index}">
        <strong>${escapeHtml(item.name)}</strong>
        <div class="muted">TAG: ${escapeHtml(item.tag)} • Série: ${escapeHtml(item.serial)}</div>
        <div class="badge-row">
          <span class="badge">${escapeHtml(item.status || 'Sem status')}</span>
          <span class="badge">${escapeHtml(item.location || '-')}</span>
        </div>
      </button>
    </div>
  `).join('');
}

function metaItem(label, value) {
  return `
    <div class="meta-item">
      <div class="meta-label">${escapeHtml(label)}</div>
      <div class="meta-value">${escapeHtml(value || '-')}</div>
    </div>
  `;
}

function getUrlQuery() {
  const params = new URLSearchParams(window.location.search);
  return {
    tag: params.get('tag') || '',
    id: params.get('id') || '',
  };
}

function updateUrl(item) {
  const url = new URL(window.location.href);
  if (item?.tag && item.tag !== '-') {
    url.searchParams.set('tag', item.tag);
    url.searchParams.delete('id');
  } else if (item?.id) {
    url.searchParams.set('id', item.id);
    url.searchParams.delete('tag');
  } else {
    url.searchParams.delete('tag');
    url.searchParams.delete('id');
  }
  window.history.replaceState({}, '', url.toString());
}

function renderHome() {
  state.screen = 'home';
  state.currentItem = null;
  state.currentNotice = '';
  backButton.classList.add('hidden');
  updateUrl(null);

  const apiStatus = state.apiReachable === null
    ? '<span class="badge">API ainda não testada</span>'
    : state.apiReachable
      ? '<span class="badge">API alcançável</span>'
      : '<span class="badge">API indisponível ou rota não confirmada</span>';

  app.innerHTML = `
    <section class="screen">
      <div class="card hero">
        <div>
          <h2>Consulta rápida por QR ou TAG</h2>
          <p class="subtle">Viewer V3 - rápido e profissional.</p>
        </div>

        <div class="badge-row">
          <span class="badge">Versão ${escapeHtml(CONFIG.APP_VERSION)}</span>
          ${apiStatus}
          <span class="badge">PWA instalável</span>
        </div>

        <div class="grid-3">
          <button class="card action-card" id="goScan">
            <div class="action-icon">📷</div>
            <div>
              <h3>Escanear QR</h3>
              <p class="muted">Abrir câmera e interpretar QR inteligente.</p>
            </div>
          </button>

          <button class="card action-card" id="goSearch">
            <div class="action-icon">🏷️</div>
            <div>
              <h3>Buscar TAG</h3>
              <p class="muted">Pesquisar online pelo código da TAG.</p>
            </div>
          </button>

          <button class="card action-card" id="goPaste">
            <div class="action-icon">🧾</div>
            <div>
              <h3>Colar conteúdo do QR</h3>
              <p class="muted">Útil para testar QR híbrido sem câmera.</p>
            </div>
          </button>
        </div>
      </div>

      <div class="card panel">
        <h3>Consultas recentes</h3>
        <div class="list">${recentListHtml()}</div>
      </div>

      <div class="card panel">
        <h3>Conexão</h3>
        <div class="inline-actions">
          <button id="runApiTest" class="secondary-button">Testar API</button>
          <button id="clearRecent" class="outline-button">Limpar recentes</button>
        </div>
        <div class="notice">Se você abrir o Viewer com <strong>?tag=TAG-001</strong> ou <strong>?id=15</strong>, a consulta já pode abrir direta.</div>
      </div>

      <div class="footer-note">Viewer V3 • TagCheck • Smart Asset Tracking</div>
    </section>
  `;

  document.getElementById('goScan')?.addEventListener('click', renderScanner);
  document.getElementById('goSearch')?.addEventListener('click', renderSearch);
  document.getElementById('goPaste')?.addEventListener('click', renderManualQr);
  document.getElementById('runApiTest')?.addEventListener('click', async () => {
    const ok = await pingApi();
    alert(ok ? 'API respondeu.' : 'API não confirmada. Verifique API_BASE_URL e endpoints.');
    renderHome();
  });
  document.getElementById('clearRecent')?.addEventListener('click', () => {
    localStorage.removeItem(CONFIG.STORAGE_KEYS.recentItems);
    renderHome();
  });

  document.querySelectorAll('[data-open-recent]').forEach((button) => {
    button.addEventListener('click', (event) => {
      const index = Number(event.currentTarget.dataset.openRecent);
      const item = getRecentItems()[index];
      if (item) renderDetail(item, 'Consulta recente');
    });
  });
}

function renderSearch() {
  state.screen = 'search';
  backButton.classList.remove('hidden');
  const last = localStorage.getItem(CONFIG.STORAGE_KEYS.lastSearch) || '';

  app.innerHTML = `
    <section class="screen">
      <div class="card panel">
        <h3>Buscar por TAG</h3>
        <p class="muted">Digite a TAG do instrumento para consultar os dados online.</p>
        <div class="search-row">
          <input id="tagInput" class="input" placeholder="Ex.: TAG-00123" value="${escapeHtml(last)}" />
          <button id="searchButton" class="primary-button">Consultar</button>
        </div>
        <div id="searchFeedback"></div>
      </div>

      <div class="card panel">
        <h3>Dica</h3>
        <div class="notice">Quando a API falhar, o Viewer tenta exibir cache local da última leitura conhecida para aquela TAG.</div>
      </div>
    </section>
  `;

  const input = document.getElementById('tagInput');
  const feedback = document.getElementById('searchFeedback');

  const runSearch = async () => {
    feedback.innerHTML = '<div class="notice center-row"><div class="loader"></div><span>Consultando TAG...</span></div>';
    try {
      const item = await searchByTag(input.value);
      renderDetail(item, item.source === 'offline-cache' ? 'Exibindo cache offline' : 'Consulta online concluída');
    } catch (error) {
      feedback.innerHTML = `<div class="notice error">${escapeHtml(error.message || 'Falha ao consultar a TAG.')}</div>`;
    }
  };

  document.getElementById('searchButton')?.addEventListener('click', runSearch);
  input?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') runSearch();
  });
}

function destroyScanner() {
  if (state.scanner) {
    state.scanner.stop().catch(() => null).finally(() => {
      state.scanner.clear().catch(() => null);
      state.scanner = null;
    });
  }
}

function renderScanner() {
  state.screen = 'scanner';
  backButton.classList.remove('hidden');

  app.innerHTML = `
    <section class="screen">
      <div class="card panel">
        <h3>Escanear QR</h3>
        <p class="muted">Aponte a câmera para o QR da etiqueta. O Viewer tenta ler link, JSON híbrido, pares texto e TAG direta.</p>
        <div id="reader" class="reader"></div>
        <div class="detail-actions">
          <button id="startScanner" class="primary-button">Iniciar câmera</button>
          <button id="stopScanner" class="secondary-button">Parar</button>
          <button id="manualEntry" class="outline-button">Digitar TAG</button>
          <button id="pasteEntry" class="outline-button">Colar conteúdo</button>
        </div>
        <div id="scannerFeedback"></div>
      </div>
    </section>
  `;

  const feedback = document.getElementById('scannerFeedback');

  const startScanner = async () => {
    feedback.innerHTML = '<div class="notice">Abrindo câmera...</div>';
    try {
      destroyScanner();
      state.scanner = new Html5Qrcode('reader');
      await state.scanner.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 240, height: 240 } },
        async (decodedText) => {
          feedback.innerHTML = `<div class="notice">QR lido: ${escapeHtml(decodedText.slice(0, 120))}</div>`;
          destroyScanner();
          try {
            const result = await resolveQrContent(decodedText);
            renderDetail(result.item, result.notice);
          } catch (error) {
            feedback.innerHTML = `<div class="notice error">${escapeHtml(error.message || 'Falha ao processar o QR.')}</div>`;
          }
        },
        () => null
      );
      feedback.innerHTML = '<div class="notice">Câmera ativa. Posicione o QR dentro da área de leitura.</div>';
    } catch {
      feedback.innerHTML = '<div class="notice error">Não foi possível iniciar a câmera. Verifique a permissão do navegador.</div>';
    }
  };

  document.getElementById('startScanner')?.addEventListener('click', startScanner);
  document.getElementById('stopScanner')?.addEventListener('click', () => {
    destroyScanner();
    feedback.innerHTML = '<div class="notice warning">Leitura interrompida.</div>';
  });
  document.getElementById('manualEntry')?.addEventListener('click', () => {
    destroyScanner();
    renderSearch();
  });
  document.getElementById('pasteEntry')?.addEventListener('click', () => {
    destroyScanner();
    renderManualQr();
  });
}

function renderManualQr() {
  state.screen = 'manual-qr';
  backButton.classList.remove('hidden');

  app.innerHTML = `
    <section class="screen">
      <div class="card panel">
        <h3>Colar conteúdo do QR</h3>
        <p class="muted">Cole aqui o texto bruto do QR para testar sem usar câmera.</p>
        <textarea id="qrPayload" class="textarea" placeholder="Ex.: TAG: TAG-001 | NOME: Paquímetro | SERIAL: ABC123"></textarea>
        <div class="inline-actions">
          <button id="processQr" class="primary-button">Processar</button>
          <button id="goToScanner" class="secondary-button">Abrir câmera</button>
        </div>
        <div id="manualQrFeedback"></div>
      </div>
    </section>
  `;

  const feedback = document.getElementById('manualQrFeedback');
  document.getElementById('processQr')?.addEventListener('click', async () => {
    const content = document.getElementById('qrPayload')?.value || '';
    feedback.innerHTML = '<div class="notice center-row"><div class="loader"></div><span>Processando conteúdo...</span></div>';
    try {
      const result = await resolveQrContent(content);
      renderDetail(result.item, result.notice);
    } catch (error) {
      feedback.innerHTML = `<div class="notice error">${escapeHtml(error.message || 'Falha ao processar o conteúdo.')}</div>`;
    }
  });
  document.getElementById('goToScanner')?.addEventListener('click', renderScanner);
}

function renderDetail(item, noticeText = '') {
  destroyScanner();
  state.screen = 'detail';
  state.currentItem = normalizeEquipment(item);
  state.currentNotice = noticeText;
  saveRecentItem(state.currentItem);
  if (state.currentItem?.tag && state.currentItem.tag !== '-') saveFallbackCache(state.currentItem);
  backButton.classList.remove('hidden');
  updateUrl(state.currentItem);

  const itemSafe = state.currentItem;
  const notesBlock = itemSafe.notes && itemSafe.notes !== '-'
    ? `<div class="card panel"><h3>Observações</h3><div>${escapeHtml(itemSafe.notes)}</div></div>`
    : '';

  const rawFallbackBlock = itemSafe.source === 'hybrid-offline'
    ? `<div class="card panel"><h3>Modo fallback</h3><div class="notice warning">A API não foi usada para completar esta leitura. Os dados exibidos vieram do conteúdo mínimo do próprio QR.</div></div>`
    : '';

  const photoBlock = itemSafe.photo
    ? `
      <div class="detail-photo-wrap">
        <div class="photo-bg" style="background-image: url('${itemSafe.photo}')"></div>
        <img
          src="${escapeHtml(itemSafe.photo)}"
          alt="${escapeHtml(itemSafe.name)}"
          class="detail-photo"
          loading="lazy"
          referrerpolicy="no-referrer"
          onclick="openImageModal('${itemSafe.photo}')"
          onerror="this.style.display='none'; this.parentElement.style.display='none';"
        />
      </div>
    `
    : '';

  app.innerHTML = `
    <section class="screen">
      <div class="card detail-header">
        ${noticeText ? `<div class="notice">${escapeHtml(noticeText)}</div>` : ''}
        ${photoBlock}
        <div class="status-pill ${statusClass(itemSafe.status)}">${escapeHtml(itemSafe.status || 'Sem status')}</div>
        <h2 class="detail-title">${escapeHtml(itemSafe.name)}</h2>
        <div class="detail-subtitle">TAG: <strong>${escapeHtml(itemSafe.tag)}</strong> • Série: <strong>${escapeHtml(itemSafe.serial)}</strong></div>
        <div class="detail-actions">
          ${itemSafe.sheetUrl ? `<a class="primary-button" href="${escapeHtml(itemSafe.sheetUrl)}" target="_blank" rel="noopener noreferrer">Abrir ficha online</a>` : ''}
          <button id="copyTag" class="secondary-button">Copiar TAG</button>
          <button id="refreshItem" class="outline-button">Atualizar dados</button>
          <button id="shareItem" class="outline-button">Copiar link</button>
          <button id="newQuery" class="outline-button">Nova consulta</button>
        </div>
      </div>

      <div class="card panel">
        <h3>Dados do instrumento</h3>
        <div class="meta-grid">
          ${metaItem('Tipo', itemSafe.type)}
          ${metaItem('Setor', itemSafe.sector)}
          ${metaItem('Localização', itemSafe.location)}
          ${metaItem('Fabricante', itemSafe.manufacturer)}
          ${metaItem('Modelo', itemSafe.model)}
          ${metaItem('Faixa', itemSafe.range)}
          ${metaItem('Resolução', itemSafe.resolution)}
          ${metaItem('Responsável', itemSafe.owner)}
          ${metaItem('Data de calibração', itemSafe.calibrationDate)}
          ${metaItem('Validade', itemSafe.validityDate)}
          ${metaItem('Certificado', itemSafe.certificate)}
          ${metaItem('Origem', itemSafe.source)}
        </div>
      </div>

      <div class="card panel">
        <h3>Dados técnicos</h3>
        <div class="code-block">${escapeHtml(JSON.stringify(itemSafe.raw, null, 2))}</div>
      </div>

      ${notesBlock}
      ${rawFallbackBlock}
    </section>
  `;

  document.getElementById('copyTag')?.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(itemSafe.tag || '');
      alert('TAG copiada.');
    } catch {
      alert('Não foi possível copiar a TAG.');
    }
  });

  document.getElementById('shareItem')?.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      alert('Link copiado.');
    } catch {
      alert('Não foi possível copiar o link.');
    }
  });

  document.getElementById('refreshItem')?.addEventListener('click', async () => {
    try {
      const refreshed = itemSafe.tag && itemSafe.tag !== '-'
        ? await searchByTag(itemSafe.tag)
        : (itemSafe.id ? await searchById(itemSafe.id) : null);
      if (!refreshed) throw new Error('Sem referência para atualizar.');
      renderDetail(refreshed, 'Dados atualizados a partir da API.');
    } catch (error) {
      alert(error.message || 'Falha ao atualizar.');
    }
  });

  document.getElementById('newQuery')?.addEventListener('click', renderHome);
}

function openImageModal(src) {
  const modal = document.createElement('div');
  modal.className = 'image-modal';
  modal.innerHTML = `
    <div class="image-modal-content">
      <img src="${src}" alt="Imagem ampliada" />
    </div>
  `;

  modal.onclick = () => modal.remove();
  document.body.appendChild(modal);
}

backButton.addEventListener('click', () => {
  destroyScanner();
  renderHome();
});

window.addEventListener('beforeinstallprompt', (event) => {
  event.preventDefault();
  state.deferredPrompt = event;
  installButton.classList.remove('hidden');
});

installButton.addEventListener('click', async () => {
  if (!state.deferredPrompt) return;
  state.deferredPrompt.prompt();
  await state.deferredPrompt.userChoice;
  state.deferredPrompt = null;
  installButton.classList.add('hidden');
});

window.addEventListener('appinstalled', () => {
  installButton.classList.add('hidden');
});

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('./sw.js').catch(() => null);
  });
}

async function boot() {
  await pingApi().catch(() => null);
  const query = getUrlQuery();

  if (query.tag) {
    try {
      const item = await searchByTag(query.tag);
      renderDetail(item, 'Consulta aberta diretamente pelo link.');
      return;
    } catch {
      // continue to home
    }
  }

  if (query.id) {
    try {
      const item = await searchById(query.id);
      renderDetail(item, 'Consulta aberta diretamente pelo link.');
      return;
    } catch {
      // continue to home
    }
  }

  renderHome();
}

boot();