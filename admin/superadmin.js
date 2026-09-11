/* Uses the existing admin styles and authenticated API; stores no credentials. */
window.TAGCHECK_SUPERADMIN = {
  async mount(host, request, escape, back) {
    const panel = document.createElement('section');
    panel.id = 'superadminPanel';
    panel.className = 'screen';
    host.replaceChildren(panel);
    panel.innerHTML = '<div class="card panel">Carregando administração...</div>';
    let companies, users, links = [];
    const status = active => active ? 'Ativa' : 'Inativa';
    try {
      [companies, users] = await Promise.all([request('/companies'), request('/users')]);
      if (!panel.isConnected) return;
      panel.innerHTML = `
        <div class="card panel"><div class="inline-actions"><h2>Super Admin</h2>
          <button id="backToAdmin" class="outline-button">Voltar aos equipamentos</button></div>
          <div id="superadminFeedback" role="status" aria-live="polite"></div></div>
        <div class="grid-2">
          <div class="card panel"><h3>Empresas</h3>
            <div class="table-wrap"><table><thead><tr><th>Nome</th><th>Identificador</th><th>Status</th><th>Ações</th></tr></thead>
              <tbody id="companyRows"></tbody></table></div>
            <form id="companyCreateForm" class="login-stack">
              <label>Nome<input class="input" name="name" required maxlength="200"></label>
              <label>Identificador (letras minúsculas, números e hífens)<input class="input" name="slug" required maxlength="100" pattern="[a-z0-9]+(-[a-z0-9]+)*"></label>
              <button class="primary-button">Criar empresa</button>
            </form>
          </div>
          <div class="card panel"><h3>Usuários</h3>
            <div class="table-wrap"><table><thead><tr><th>Nome</th><th>E-mail</th></tr></thead><tbody id="userRows"></tbody></table></div>
            <form id="userCreateForm" class="login-stack" autocomplete="off">
              <label>Nome<input class="input" name="name" required maxlength="200"></label>
              <label>E-mail<input class="input" name="email" type="email" required maxlength="254"></label>
              <label>Senha inicial (mínimo de 12 caracteres)<input class="input" name="password" type="password" required minlength="12" maxlength="1024" autocomplete="new-password"></label>
              <button class="primary-button">Criar usuário</button>
            </form>
          </div>
        </div>
        <div class="card panel"><h3>Vínculo usuário / empresa</h3>
          <form id="membershipForm" class="login-stack">
            <label>Usuário<select id="memberUser" class="input" required></select></label>
            <label>Empresa<select id="memberCompany" class="input" required></select></label>
            <label>Role<select id="memberRole" class="input" required>
              ${['company_admin', 'supervisor', 'operator', 'viewer'].map(role => `<option>${role}</option>`).join('')}
            </select></label>
            <label><input id="memberActive" type="checkbox" checked> Vínculo ativo</label>
            <p id="membershipStatus"></p>
            <button id="saveMembership" class="primary-button">Salvar vínculo</button>
          </form>
        </div>`;
      const find = selector => panel.querySelector(selector);
      find('#backToAdmin').addEventListener('click', back);
      const feedback = message => { if (panel.isConnected) find('#superadminFeedback').textContent = message; };
      const options = (items, label) => items.map(item => `<option value="${item.id}">${escape(label(item))}</option>`).join('');
      const refreshLists = () => {
        const userId = find('#memberUser').value, companyId = find('#memberCompany').value;
        find('#companyRows').innerHTML = companies.map(company => `<tr data-company-id="${company.id}">
          <td>${escape(company.name)}</td><td>${escape(company.slug)}</td><td>${status(company.active)}</td>
          <td><button class="outline-button" data-toggle-company="${company.id}">${company.active ? 'Desativar' : 'Ativar'}</button></td></tr>`).join('');
        find('#userRows').innerHTML = users.map(user => `<tr data-user-id="${user.id}"><td>${escape(user.name)}</td><td>${escape(user.email)}</td></tr>`).join('');
        find('#memberUser').innerHTML = options(users, user => `${user.name} (${user.email})`);
        find('#memberCompany').innerHTML = options(companies, company => `${company.name} (${status(company.active)})`);
        if (users.some(user => String(user.id) === userId)) find('#memberUser').value = userId;
        if (companies.some(company => String(company.id) === companyId)) find('#memberCompany').value = companyId;
      };
      const showLink = () => {
        const link = links.find(link => String(link.company_id) === find('#memberCompany').value);
        find('#memberRole').value = link?.role || 'viewer';
        find('#memberActive').checked = link ? link.active : true;
        find('#membershipStatus').textContent = link ? `Vínculo ${link.active ? 'ativo' : 'inativo'}` : 'Sem vínculo cadastrado';
      };
      let linkRequest = 0;
      const loadLinks = async () => {
        const version = ++linkRequest;
        find('#saveMembership').disabled = true;
        links = [];
        find('#membershipStatus').textContent = 'Carregando vínculos...';
        const id = find('#memberUser').value;
        try {
          const result = id ? await request(`/users/${id}/companies`) : [];
          if (!panel.isConnected || version !== linkRequest) return;
          links = result;
          showLink();
          find('#saveMembership').disabled = !id || !find('#memberCompany').value;
        } catch (error) { if (version === linkRequest) feedback(error.message); }
      };
      const run = async (element, action) => {
        const controls = [...element.querySelectorAll('input, select, button')];
        if (element.tagName === 'BUTTON') controls.push(element);
        controls.forEach(control => { control.disabled = true; });
        feedback('Salvando...');
        try {
          await action();
          feedback('Operação concluída.');
        } catch (error) { feedback(error.message); }
        finally { controls.forEach(control => { control.disabled = false; }); }
      };
      find('#companyRows').addEventListener('click', event => {
        const button = event.target.closest('[data-toggle-company]');
        if (!button || button.disabled) return;
        const company = companies.find(company => company.id === Number(button.dataset.toggleCompany));
        run(button, async () => {
          const updated = await request(`/companies/${company.id}`, 'PATCH', { active: !company.active });
          if (!panel.isConnected) return;
          companies = companies.map(item => item.id === updated.id ? updated : item);
          refreshLists();
          showLink();
        });
      });
      find('#companyCreateForm').addEventListener('submit', event => {
        event.preventDefault();
        const form = event.currentTarget;
        const data = Object.fromEntries(new FormData(form));
        run(form, async () => {
          const company = await request('/companies', 'POST', data);
          if (!panel.isConnected) return;
          companies.push(company);
          form.reset(); refreshLists(); showLink();
        });
      });
      find('#userCreateForm').addEventListener('submit', event => {
        event.preventDefault();
        const form = event.currentTarget;
        const data = Object.fromEntries(new FormData(form));
        form.elements.password.value = '';
        run(form, async () => {
          const user = await request('/users', 'POST', data);
          if (!panel.isConnected) return;
          users.push(user);
          form.reset(); refreshLists();
        });
      });
      find('#memberUser').addEventListener('change', loadLinks);
      find('#memberCompany').addEventListener('change', showLink);
      find('#membershipForm').addEventListener('submit', event => {
        event.preventDefault();
        const id = find('#memberUser').value;
        const data = {company_id: Number(find('#memberCompany').value), role: find('#memberRole').value, active: find('#memberActive').checked};
        run(event.currentTarget, async () => {
          const link = await request(`/users/${id}/companies`, 'POST', data);
          if (!panel.isConnected) return;
          links = links.filter(item => item.company_id !== link.company_id).concat(link);
          showLink();
        });
      });
      refreshLists();
      await loadLinks();
    } catch (error) {
      if (panel.isConnected) {
        panel.innerHTML = `<div class="card panel"><p role="alert">${escape(error.message)}</p><button class="outline-button">Voltar aos equipamentos</button></div>`;
        panel.querySelector('button').addEventListener('click', back);
      }
    }
  }
};
