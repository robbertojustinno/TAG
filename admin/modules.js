function openAdminModule(name) {
  if (document.body.dataset.page === 'maintenance') {
    location.assign(window.TAGCHECK_I18N.url(new URL('#' + name, document.baseURI).href));
    return;
  }
  location.hash = name;
}

function openModuleHome() {
  openAdminModule('modulos');
}

function renderModuleHome(notice) {
  const modules = [
    ['Instrumentos', '#instrumentos', state.companyId],
    ['Viewer', openViewerButton.href, true],
    ['Manutenção preventiva', './manutencao/', state.companyId],
    ['Tagueamento', './tagueamento/', state.companyId],
    ['Cadastro Offline', openCampoButton.href, state.companyId && state.role !== 'viewer', 'openCampoButton'],
    ['Administração', '#empresa', state.role === 'company_admin' && !state.isSuperadmin],
    ['Super Admin', '#superadmin', state.isSuperadmin],
    ['Auditoria', '#auditoria', state.isSuperadmin],
  ];
  app.innerHTML = tcH`<section class="screen"><h2>Módulos</h2>${notice}
    <nav class="module-grid" aria-label="${escapeHtml(tcL('Módulos'))}">
      ${modules.filter(([, , visible]) => visible).map(([label, url, , proxy]) => tcH`
        <a class="module-card card" href="${escapeHtml(url)}"${proxy ? ' data-open-campo' : ''}>${escapeHtml(tcL(label))}</a>`).join('')}
    </nav></section>`;
  app.querySelector('[data-open-campo]')?.addEventListener('click', event => {
    event.preventDefault();
    openCampoButton.click();
  });
}

function renderAudit() {
  app.innerHTML = tcH`<section class="screen"><div class="card panel">
    <h2>Auditoria</h2>
    <form id="auditFilters" class="module-grid">
      <label>Empresa (ID)<input class="input" type="number" min="1" name="target_company_id"></label>
      <label>Usuário (ID)<input class="input" type="number" min="1" name="actor_id"></label>
      <label>Registro<select class="input" name="entity"><option value="">Todos</option>
        ${Object.entries(auditEntities).map(([key, label]) => tcH`<option value="${key}">${label}</option>`).join('')}</select></label>
      <label>Ação<select class="input" name="action"><option value="">Todas</option>
        <option value="create">Criação</option><option value="update">Alteração</option><option value="delete">Exclusão</option>
      </select></label>
      <label>De<input class="input" type="datetime-local" name="start"></label>
      <label>Até<input class="input" type="datetime-local" name="end"></label>
      <button class="primary-button">Filtrar</button>
    </form>
    <p data-audit-status role="status"></p>
    <div data-audit-results></div>
    <button type="button" class="outline-button" data-audit-more hidden>Mais registros</button>
  </div></section>`;
  const form = app.querySelector('#auditFilters');
  const results = app.querySelector('[data-audit-results]');
  const status = app.querySelector('[data-audit-status]');
  const more = app.querySelector('[data-audit-more]');
  let filters = new URLSearchParams();
  let cursor;
  let requestNumber = 0;
  async function load(append = false) {
    const current = ++requestNumber;
    const query = new URLSearchParams(filters);
    if (append && cursor) query.set('before_id', cursor);
    status.textContent = tcL('Carregando...');
    more.hidden = true;
    try {
      const rows = await superadminRequest('/superadmin/audit?' + query);
      if (current !== requestNumber) return;
      const markup = rows.map(row => {
        const actor = row.actor_email || (row.actor_id ? String(row.actor_id) : tcL('Sistema ou origem sem identificação'));
        const values = Object.entries(row.changes).map(([key, value]) =>
          tcH`<dt>${escapeHtml(key)}</dt><dd><pre>${escapeHtml(value.redacted ? tcL('Alteração protegida') : JSON.stringify(value, null, 2))}</pre></dd>`).join('');
        const action = {create: 'Criação', update: 'Alteração', delete: 'Exclusão'}[row.action] || row.action;
        return tcH`<details class="audit-entry"><summary>
          ${escapeHtml(new Date(row.occurred_at).toLocaleString(window.TAGCHECK_I18N.locale))} ·
          ${escapeHtml(actor)} · ${tcL('Empresa')} ${escapeHtml(row.company_id)} ·
          ${escapeHtml(tcL(action))} · ${escapeHtml(tcL(auditEntities[row.entity] || row.entity))} #${escapeHtml(row.entity_id)}
        </summary><dl>${values}</dl></details>`;
      }).join('');
      if (append) results.insertAdjacentHTML('beforeend', markup);
      else results.innerHTML = markup;
      cursor = rows.at(-1)?.id;
      more.hidden = rows.length < 50;
      status.textContent = rows.length ? '' : tcL('Nenhum registro encontrado.');
    } catch (error) {
      if (current === requestNumber) status.textContent = error.message;
    }
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    filters = new URLSearchParams();
    for (const [key, value] of new FormData(form)) {
      if (value) filters.set(key, ['start', 'end'].includes(key) ? new Date(value).toISOString() : value);
    }
    load();
  });
  more.addEventListener('click', () => load(true));
  load();
}

const auditEntities = {
  companies: 'Empresas', users: 'Usuários', units: 'Unidades', user_companies: 'Vínculos',
  asset_categories: 'Categorias', tagcheck_equipment: 'Instrumentos', tagging_hierarchies: 'Tagueamento',
  maintenance_plans: 'Planos de manutenção', maintenance_executions: 'Execuções de manutenção',
  billing_sandbox: 'Cobranças de teste', billing_production: 'Assinaturas',
  billing_production_invoices: 'Cobranças', billing_production_extra_invoices: 'Cobranças avulsas',
};
