function renderRows(items) {
  if (!items.length) {
    return `<tr><td colspan="7">Vazio</td></tr>`;
  }

  return items.map(item => `
    <tr>
      <td>${item.id}</td>
      <td><strong>${item.tag}</strong></td>
      <td>${item.name}</td>
      <td><img src="${item.photo}" class="thumb"/></td>
      <td>${statusPill(item.status)}</td>
      <td>${qrHtml(item.tag)}</td>
      <td>
        <button onclick="editItem(${item.id})">Editar</button>
        <button class="danger-button" onclick="deleteItem(${item.id})">Excluir</button>
      </td>
    </tr>
  `).join('');
}
window.deleteItem = async function(id) {
  if (!confirm("Excluir item?")) return;

  await fetch(`${CONFIG.API_BASE_URL}/equipment/${id}`, {
    method: "DELETE"
  });

  await loadItems();
  renderApp();
};

window.editItem = async function(id) {
  const tag = prompt("Nova TAG:");
  const name = prompt("Novo nome:");

  if (!tag || !name) return;

  const form = new FormData();
  form.append("tag", tag);
  form.append("name", name);

  await fetch(`${CONFIG.API_BASE_URL}/equipment/${id}`, {
    method: "PUT",
    body: form
  });

  await loadItems();
  renderApp();
};