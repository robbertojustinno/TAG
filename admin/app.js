const API = window.CONFIG?.API_BASE_URL || "";

const app = document.getElementById("app");

function renderApp() {
  app.innerHTML = `
    <div class="card panel">
      <h3>Buscar por TAG</h3>

      <input id="searchTag" class="input" placeholder="Ex: PI001" />

      <div class="inline-actions">
        <button class="primary-button" onclick="buscar()">Buscar</button>
        <button class="secondary-button" onclick="listar()">Atualizar lista</button>
        <button class="outline-button" onclick="gerarPDF()">Imprimir PDF QR</button>
      </div>
    </div>

    <div id="lista" class="card panel"></div>
  `;
}

async function buscar() {
  const tag = document.getElementById("searchTag").value;
  if (!tag) return;

  try {
    const res = await fetch(\`\${API}/equipment/tag/\${tag}\`);
    const data = await res.json();

    document.getElementById("lista").innerHTML = `
      <div>
        <strong>${data.tag}</strong><br/>
        ${data.name || ""}
      </div>
    `;
  } catch (e) {
    alert("Erro ao buscar");
  }
}

async function listar() {
  try {
    const res = await fetch(`${API}/equipment`);
    const data = await res.json();

    let html = "";

    data.forEach(item => {
      html += `
        <div style="margin-bottom:10px">
          <strong>${item.tag}</strong> - ${item.name || ""}
        </div>
      `;
    });

    document.getElementById("lista").innerHTML = html;
  } catch (e) {
    alert("Erro ao listar");
  }
}

/* ===== BOTÃO PDF ===== */
function gerarPDF() {
  window.open(`${API}/equipment/pdf-labels`, "_blank");
}

renderApp();