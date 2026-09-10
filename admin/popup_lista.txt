document.getElementById('openAllPopupButton')?.addEventListener('click', async () => {
  const popup = window.open('', '_blank', 'width=1200,height=800');

  if (!popup) {
    alert('Não foi possível abrir a janela.');
    return;
  }

  popup.document.write(`
    <html>
    <head>
      <title>Todos os cadastros</title>
      <style>
        body {
          font-family: Arial;
          margin: 0;
          background: #0f172a;
          color: #e5eefc;
        }
        .top {
          background: #1d4ed8;
          padding: 15px;
        }
        h1 {
          margin: 0;
        }
        table {
          width: 100%;
          border-collapse: collapse;
        }
        th, td {
          padding: 8px;
          border-bottom: 1px solid #333;
        }
        th {
          background: #111827;
        }
      </style>
    </head>
    <body>
      <div class="top">
        <h1>Todos os cadastros</h1>
        <div id="total">Carregando...</div>
      </div>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>TAG</th>
            <th>Nome</th>
            <th>Tipo</th>
            <th>Série</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody id="tbody">
          <tr><td colspan="6">Carregando...</td></tr>
        </tbody>
      </table>
    </body>
    </html>
  `);

  popup.document.close();

  try {
    const items = await loadItems();

    const rows = items.map(i => `
      <tr>
        <td>${i.id}</td>
        <td>${i.tag}</td>
        <td>${i.name}</td>
        <td>${i.equipment_type || ''}</td>
        <td>${i.serial_number || ''}</td>
        <td>${i.status || ''}</td>
      </tr>
    `).join('');

    popup.document.getElementById('total').innerText = "Total: " + items.length;
    popup.document.getElementById('tbody').innerHTML = rows || '<tr><td colspan="6">Nenhum</td></tr>';

  } catch (e) {
    popup.document.getElementById('tbody').innerHTML = '<tr><td colspan="6">Erro ao carregar</td></tr>';
  }
});