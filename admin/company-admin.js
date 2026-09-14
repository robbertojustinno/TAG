/* Company administration. The API independently enforces every permission. */
window.TAGCHECK_COMPANY = {
  async mount(host, request, escape, back, refreshIdentity) {
    const panel = document.createElement('section');
    panel.id = 'companyAdminPanel'; panel.className = 'screen'; host.replaceChildren(panel);
    panel.innerHTML = '<div class="card panel">Carregando administração...</div>';
    const roles = {company_admin: 'Administrador', supervisor: 'Supervisor', operator: 'Operador', viewer: 'Somente leitura'};
    let users = [], editing = null;
    try {
      const company = await request('/company');
      users = await request('/company/users');
      if (!panel.isConnected) return;
      panel.innerHTML = `<div class="card panel"><div class="inline-actions"><h2>Administração</h2><button id="companyBack" class="outline-button">Equipamentos e unidades</button></div>
        <h3>${escape(company.name)}</h3><p>Empresa ${company.active ? 'ativa' : 'inativa'}</p></div>
        <div class="card panel" id="companyIdentity"></div>
        <div class="card panel"><div class="inline-actions"><h3>Usuários</h3><button id="newCompanyUser" class="outline-button">Novo usuário</button></div><p id="companyFeedback" role="status" aria-live="polite"></p>
        <div class="table-wrap"><table><thead><tr><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Status</th><th>Ações</th></tr></thead><tbody id="companyUserRows"></tbody></table></div>
        <h3 id="companyUserTitle">Novo usuário</h3><form id="companyUserForm" class="login-stack" autocomplete="off">
        <label>Nome<input class="input" name="name" required maxlength="200"></label>
        <label>E-mail<input class="input" name="email" type="email" required maxlength="254"></label>
        <label id="initialPassword">Senha inicial (mínimo de 12 caracteres)<input class="input" name="password" type="password" required minlength="12" maxlength="1024" autocomplete="new-password"></label>
        <label>Perfil<select class="input" name="role">${Object.entries(roles).filter(([r])=>r!=='company_admin').map(([r,l])=>`<option value="${r}">${l}</option>`).join('')}</select></label>
        <div class="inline-actions"><button class="primary-button">Salvar usuário</button><button id="cancelCompanyUser" type="button" class="outline-button">Cancelar</button></div></form>
        <form id="companyPasswordForm" class="login-stack hidden" autocomplete="off"><h3>Redefinir senha</h3><p id="passwordUser"></p>
        <label>Nova senha<input class="input" name="password" type="password" required minlength="12" maxlength="1024" autocomplete="new-password"></label>
        <label>Confirme a senha<input class="input" name="confirmation" type="password" required minlength="12" maxlength="1024" autocomplete="new-password"></label>
        <button class="primary-button">Redefinir senha</button></form></div>`;
      const find = s => panel.querySelector(s), feedback = m => { find('#companyFeedback').textContent = m; };
      const run = async action => {
        const controls = [...panel.querySelectorAll('button')]; controls.forEach(b=>b.disabled=true);
        try { await action(); feedback('Operação concluída com sucesso.'); }
        catch(e) { feedback(e.message); }
        finally { controls.forEach(b=>b.disabled=false); }
      };
      const rows = () => { find('#companyUserRows').innerHTML = users.map(u=>`<tr data-user-id="${u.id}"><td>${escape(u.name)}</td><td>${escape(u.email)}</td><td>${roles[u.role]}</td><td>${u.active?'Ativo':'Inativo'}</td><td>${u.role==='company_admin'?'':`<div class="inline-actions"><button class="outline-button" data-edit="${u.id}">Editar</button><button class="outline-button" data-reset="${u.id}">Redefinir senha</button><button class="outline-button" data-toggle="${u.id}">${u.membership_active?'Desativar':'Ativar'}</button></div>`}</td></tr>`).join(''); };
      const form = find('#companyUserForm');
      const clear = () => { editing=null; form.reset(); form.elements.password.required=true; find('#initialPassword').classList.remove('hidden'); find('#companyUserTitle').textContent='Novo usuário'; };
      find('#companyBack').onclick=back;
      find('#cancelCompanyUser').onclick=clear;
      find('#newCompanyUser').onclick=()=>{clear();form.elements.name.focus();};
      form.onsubmit = e => { e.preventDefault(); const data=Object.fromEntries(new FormData(form)); const id=editing;
        if(id) delete data.password; form.elements.password.value='';
        run(async()=>{await request(id?`/company/users/${id}`:'/company/users',id?'PATCH':'POST',data); users=await request('/company/users'); rows(); clear();});
      };
      let resetId=null;
      find('#companyUserRows').onclick=e=>{
        const button=e.target.closest('button'); if(!button)return;
        const id=Number(button.dataset.edit||button.dataset.reset||button.dataset.toggle), u=users.find(x=>x.id===id);
        if(button.dataset.edit){editing=id; form.elements.name.value=u.name; form.elements.email.value=u.email; form.elements.role.value=u.role; form.elements.password.required=false; find('#initialPassword').classList.add('hidden'); find('#companyUserTitle').textContent='Editar usuário';}
        else if(button.dataset.toggle)run(async()=>{await request(`/company/users/${id}`,'PATCH',{active:!u.membership_active});users=await request('/company/users');rows();});
        else {resetId=id;find('#companyPasswordForm').classList.remove('hidden');find('#companyPasswordForm').reset();find('#passwordUser').textContent=u.name;}
      };
      find('#companyPasswordForm').onsubmit=e=>{e.preventDefault();const f=e.currentTarget,password=f.elements.password.value;
        if(password!==f.elements.confirmation.value){feedback('As senhas devem coincidir.');return;}
        f.reset();run(async()=>{await request(`/company/users/${resetId}/reset-password`,'POST',{password});f.classList.add('hidden');});
      };
      rows();
      await window.TAGCHECK_IDENTITY.mount(find('#companyIdentity'), company, '/company/logo', request, escape, refreshIdentity);
    } catch(e) { if(panel.isConnected) panel.textContent=e.message; }
  }
};

window.TAGCHECK_IDENTITY = {
  async mount(host, company, path, request, escape, onChange) {
    host.innerHTML=`<h3>Identidade visual</h3><p>${escape(company.name)}</p><img class="company-logo-preview" alt="Logo atual" src="./public/logo.png">
      <form class="login-stack"><label>Alterar logo<input class="input" name="file" type="file" accept="image/png,image/jpeg,image/webp" required></label>
      <p>PNG, JPG ou WEBP. Máximo de 2 MB.</p><div class="inline-actions"><button class="primary-button">Salvar logo</button><button type="button" class="outline-button" data-remove-logo>Remover logo</button></div></form><p role="status" aria-live="polite"></p>`;
    const img=host.querySelector('img'), form=host.querySelector('form'), status=host.querySelector('[role=status]');
    let preview=null, generation=0;
    const cleanup=new MutationObserver(()=>{
      if (!host.isConnected) { generation++; if(preview)URL.revokeObjectURL(preview); cleanup.disconnect(); }
    });
    cleanup.observe(document.body,{childList:true,subtree:true});
    const show=blob=>{if(preview)URL.revokeObjectURL(preview);preview=blob?URL.createObjectURL(blob):null;img.src=preview||'./public/logo.png';};
    const load=async()=>{const version=++generation;if(company.logo_url){const blob=await request(path,'GET',undefined,true);if(host.isConnected&&version===generation)show(blob);}else show(null);};
    form.elements.file.onchange=()=>{generation++;const file=form.elements.file.files[0];status.textContent='';
      if(!file)return;
      if(!['image/png','image/jpeg','image/webp'].includes(file.type)||!file.size||file.size>2*1024*1024){form.reset();status.textContent='Use PNG, JPG ou WEBP de até 2 MB.';return;}
      show(file);status.textContent='Prévia. Salve para aplicar a logo.';
    };
    const save=async(method,data)=>{const buttons=[...host.querySelectorAll('button,input')];buttons.forEach(b=>b.disabled=true);
      try{company=await request(path,method,data);form.reset();await load();await onChange();status.textContent=method==='DELETE'?'Logo removida com sucesso.':'Logo atualizada com sucesso.';}
      catch(e){status.textContent=e.message;}finally{buttons.forEach(b=>b.disabled=false);}
    };
    form.onsubmit=e=>{e.preventDefault();save('POST',new FormData(form));};
    host.querySelector('[data-remove-logo]').onclick=()=>save('DELETE');
    try{await load();}catch(e){status.textContent=e.message;}
  }
};
