const API = window.API_BASE_URL || "/api";

const byId = (id) => document.getElementById(id);

const state = {
  equipments: [],
  filteredEquipments: [],
  dashboard: null,
};

function formatDateBR(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("pt-BR");
}

function formatDateTimeBR(value) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("pt-BR");
}

function daysUntil(dateValue) {
  if (!dateValue) return null;
  const target = new Date(dateValue);
  if (Number.isNaN(target.getTime())) return null;

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const targetDay = new Date(target.getFullYear(), target.getMonth(), target.getDate());
  const diffMs = targetDay.getTime() - today.getTime();
  return Math.ceil(diffMs / 86400000);
}

function getCalibrationStatus(item) {
  const dateValue =
    item.next_calibration_date ||
    item.next_calibration ||
    item.calibration_due_date ||
    item.next_due_date ||
    item.valid_until ||
    null;

  const diff = daysUntil(dateValue);

  if (diff === null) {
    return {
      key: "active",
      label: "Sem data",
      className: "active",
      priority: 3,
      dueText: "-"
    };
  }

  if (diff < 0) {
    return {
      key: "expired",
      label: "Vencido",
      className: "expired",
      priority: 1,
      dueText: `${Math.abs(diff)} dia(s) em atraso`
    };
  }

  if (diff <= 30) {
    return {
      key: "soon",
      label: "Próximo",
      className: "soon",
      priority: 2,
      dueText: `${diff} dia(s) restantes`
    };
  }

  return {
    key: "active",
    label: "Ativo",
    className: "active",
    priority: 3,
    dueText: `${diff} dia(s) restantes`
  };
}

function getPhotoUrl(item) {
  return (
    item.photo ||
    item.image ||
    item.photo_url ||
    item.image_url ||
    item.picture ||
    null
  );
}

function getQrUrl(item) {
  return (
    item.qrcode ||
    item.qr_code ||
    item.qrcode_url ||
    item.qr_code_url ||
    null
  );
}

function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function setLastUpdate() {
  byId("lastUpdateLabel").textContent = `Última atualização: ${formatDateTimeBR(new Date())}`;
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API}${path}`, {
    ...options,
    headers
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || data.message || "Erro na requisição");
  }

  return data;
}

async function loadDashboard() {
  try {
    const data = await api("/dashboard");
    state.dashboard = data || {};
  } catch (error) {
    state.dashboard = null;
    console.warn("Dashboard endpoint indisponível:", error.message);
  }
}

async function loadEquipments() {
  const possibleEndpoints = [
    "/equipments",
    "/equipment",
    "/instruments",
    "/items"
  ];

  let loaded = null;
  let lastError = null;

  for (const endpoint of possibleEndpoints) {
    try {
      const response = await api(endpoint);
      if (Array.isArray(response)) {
        loaded = response;
      } else if (Array.isArray(response.items)) {
        loaded = response.items;
      } else if (Array.isArray(response.data)) {
        loaded = response.data;
      } else {
        loaded = [];
      }
      break;
    } catch (error) {
      lastError = error;
    }
  }

  if (!loaded) {
    throw lastError || new Error("Não foi possível carregar os instrumentos.");
  }

  state.equipments = loaded;
  state.filteredEquipments = [...loaded];
}

function computeSummary(items) {
  const total = items.length;
  const active = items.filter((item) => getCalibrationStatus(item).key === "active").length;
  const soon = items.filter((item) => getCalibrationStatus(item).key === "soon").length;
  const expired = items.filter((item) => getCalibrationStatus(item).key === "expired").length;
  const withPhoto = items.filter((item) => !!getPhotoUrl(item)).length;
  const withoutPhoto = total - withPhoto;
  const withQr = items.filter((item) => !!getQrUrl(item)).length;
  const withoutQr = total - withQr;

  return {
    total,
    active,
    soon,
    expired,
    withPhoto,
    withoutPhoto,
    withQr,
    withoutQr
  };
}

function renderMetrics() {
  const summary = computeSummary(state.equipments);

  byId("metricTotal").textContent = state.dashboard?.total ?? summary.total;
  byId("metricActive").textContent =
    state.dashboard?.active ?? state.dashboard?.ativos ?? summary.active;
  byId("metricSoon").textContent =
    state.dashboard?.soon ?? state.dashboard?.proximos ?? summary.soon;
  byId("metricExpired").textContent =
    state.dashboard?.expired ?? state.dashboard?.vencidos ?? summary.expired;

  byId("summaryWithPhoto").textContent =
    state.dashboard?.with_photo ?? state.dashboard?.com_foto ?? summary.withPhoto;
  byId("summaryWithoutPhoto").textContent =
    state.dashboard?.without_photo ?? state.dashboard?.sem_foto ?? summary.withoutPhoto;
  byId("summaryWithQr").textContent =
    state.dashboard?.with_qr ?? state.dashboard?.com_qr ?? summary.withQr;
  byId("summaryWithoutQr").textContent =
    state.dashboard?.without_qr ?? state.dashboard?.sem_qr ?? summary.withoutQr;
}

function renderPriorityAlerts() {
  const target = byId("priorityAlerts");
  const priorityItems = [...state.equipments]
    .map((item) => ({ item, status: getCalibrationStatus(item) }))
    .filter(({ status }) => status.key === "expired" || status.key === "soon")
    .sort((a, b) => a.status.priority - b.status.priority)
    .slice(0, 5);

  if (!priorityItems.length) {
    target.innerHTML = `<div class="empty-state small">Nenhum alerta prioritário no momento.</div>`;
    return;
  }

  target.innerHTML = priorityItems
    .map(({ item, status }) => {
      const name = item.name || item.description || item.tag || "Instrumento";
      const tag = item.tag || item.code || item.identification || "-";
      return `
        <div class="alert-item ${status.className}">
          <div class="alert-item-main">
            <div class="alert-item-title">${escapeHtml(name)}</div>
            <div class="alert-item-subtitle">TAG: ${escapeHtml(tag)} • ${escapeHtml(status.dueText)}</div>
          </div>
          <span class="badge ${status.className}">${status.label}</span>
        </div>
      `;
    })
    .join("");
}

function renderAlertsSection() {
  const target = byId("alertsList");
  const items = [...state.equipments]
    .map((item) => ({ item, status: getCalibrationStatus(item) }))
    .filter(({ status }) => status.key === "expired" || status.key === "soon")
    .sort((a, b) => a.status.priority - b.status.priority);

  if (!items.length) {
    target.innerHTML = `<div class="empty-state">Nenhum alerta de calibração encontrado.</div>`;
    return;
  }

  target.innerHTML = items
    .map(({ item, status }) => {
      const nextDate =
        item.next_calibration_date ||
        item.next_calibration ||
        item.calibration_due_date ||
        item.next_due_date ||
        item.valid_until ||
        null;

      return `
        <div class="alert-item ${status.className}">
          <div class="alert-item-main">
            <div class="alert-item-title">${escapeHtml(item.name || item.description || item.tag || "Instrumento")}</div>
            <div class="alert-item-subtitle">
              TAG: ${escapeHtml(item.tag || "-")} • Próxima calibração: ${escapeHtml(formatDateBR(nextDate))} • ${escapeHtml(status.dueText)}
            </div>
          </div>
          <span class="badge ${status.className}">${status.label}</span>
        </div>
      `;
    })
    .join("");
}

function buildMetaLine(item) {
  const manufacturer = item.manufacturer || "Fabricante não informado";
  const model = item.model || "Modelo não informado";
  const serial = item.serial || item.serial_number || "Sem série";
  return `${manufacturer} • ${model} • Série: ${serial}`;
}

function renderEquipmentList(items = state.filteredEquipments) {
  const grid = byId("equipmentGrid");
  const template = byId("equipmentCardTemplate");

  if (!items.length) {
    grid.innerHTML = `<div class="empty-state">Nenhum instrumento encontrado com os filtros atuais.</div>`;
    return;
  }

  grid.innerHTML = "";

  items.forEach((item) => {
    const status = getCalibrationStatus(item);
    const clone = template.content.cloneNode(true);

    const card = clone.querySelector(".equipment-card");
    const thumb = clone.querySelector(".equipment-thumb");
    const fallback = clone.querySelector(".equipment-thumb-fallback");
    const nameEl = clone.querySelector(".equipment-name");
    const tagEl = clone.querySelector(".equipment-tag");
    const metaEl = clone.querySelector(".equipment-meta");
    const typeEl = clone.querySelector(".equipment-type");
    const sectorEl = clone.querySelector(".equipment-sector");
    const locationEl = clone.querySelector(".equipment-location");
    const nextCalibrationEl = clone.querySelector(".equipment-next-calibration");
    const badgeEl = clone.querySelector(".calibration-badge");
    const jsonContent = clone.querySelector(".equipment-json-content");
    const downloadBtn = clone.querySelector(".download-label-btn");
    const viewJsonBtn = clone.querySelector(".view-json-btn");

    card.classList.add(status.className);

    const photoUrl = getPhotoUrl(item);
    if (photoUrl) {
      thumb.src = photoUrl;
      thumb.classList.add("has-image");
      fallback.style.display = "none";
    }

    nameEl.textContent = item.name || item.description || item.tag || "Instrumento";
    tagEl.textContent = item.tag || item.code || item.identification || "SEM TAG";
    metaEl.textContent = buildMetaLine(item);
    typeEl.textContent = item.equipment_type || item.type || "-";
    sectorEl.textContent = item.sector || "-";
    locationEl.textContent = item.location || "-";

    const nextDate =
      item.next_calibration_date ||
      item.next_calibration ||
      item.calibration_due_date ||
      item.next_due_date ||
      item.valid_until ||
      null;

    nextCalibrationEl.textContent = formatDateBR(nextDate);
    badgeEl.textContent = status.label;
    badgeEl.className = `badge calibration-badge ${status.className}`;

    jsonContent.textContent = JSON.stringify(item, null, 2);

    viewJsonBtn.addEventListener("click", () => {
      const details = card.querySelector(".equipment-json");
      details.open = !details.open;
    });

    downloadBtn.addEventListener("click", async () => {
      await handleDownloadLabel(item);
    });

    grid.appendChild(clone);
  });
}

function updateListLabels() {
  const count = state.filteredEquipments.length;
  const statusValue = byId("statusFilter").value;
  const photoValue = byId("photoFilter").value;
  const searchValue = byId("searchInput").value.trim();

  byId("listCountLabel").textContent = `${count} registro(s)`;

  const tags = [];
  if (statusValue !== "all") tags.push(`status: ${statusValue}`);
  if (photoValue !== "all") tags.push(`foto: ${photoValue}`);
  if (searchValue) tags.push(`busca: "${searchValue}"`);

  byId("listMetaLabel").textContent = tags.length
    ? tags.join(" • ")
    : "Sem filtros aplicados";
}

function applyFilters() {
  const query = normalizeText(byId("searchInput").value);
  const statusFilter = byId("statusFilter").value;
  const photoFilter = byId("photoFilter").value;

  state.filteredEquipments = state.equipments.filter((item) => {
    const status = getCalibrationStatus(item);
    const photoUrl = getPhotoUrl(item);

    const haystack = normalizeText([
      item.tag,
      item.name,
      item.description,
      item.equipment_type,
      item.type,
      item.sector,
      item.location,
      item.manufacturer,
      item.model,
      item.serial,
      item.serial_number
    ].join(" "));

    const matchesQuery = !query || haystack.includes(query);
    const matchesStatus = statusFilter === "all" || status.key === statusFilter;
    const matchesPhoto =
      photoFilter === "all" ||
      (photoFilter === "with_photo" && !!photoUrl) ||
      (photoFilter === "without_photo" && !photoUrl);

    return matchesQuery && matchesStatus && matchesPhoto;
  });

  renderEquipmentList();
  updateListLabels();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function handleDownloadLabel(item) {
  const id = item.id;
  if (!id) {
    alert("Este registro não possui ID para gerar etiqueta.");
    return;
  }

  const candidates = [
    `/equipments/${id}/label`,
    `/equipments/${id}/label/pdf`,
    `/equipments/${id}/qrcode/pdf`,
    `/labels/${id}/pdf`
  ];

  for (const endpoint of candidates) {
    try {
      const response = await fetch(`${API}${endpoint}`);
      if (!response.ok) continue;

      const blob = await response.blob();
      const fileUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = fileUrl;
      a.download = `etiqueta-${item.tag || id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(fileUrl);
      return;
    } catch (error) {
      console.warn("Falha ao baixar etiqueta:", endpoint, error.message);
    }
  }

  alert("O endpoint de download da etiqueta PDF ainda precisa ser alinhado ao seu backend.");
}

function setActiveSection(sectionId) {
  document.querySelectorAll(".section").forEach((section) => {
    section.classList.toggle("active", section.id === sectionId);
  });

  document.querySelectorAll(".nav-link").forEach((button) => {
    button.classList.toggle("active", button.dataset.sectionTarget === sectionId);
  });
}

function bindNavigation() {
  document.querySelectorAll(".nav-link").forEach((button) => {
    button.addEventListener("click", () => {
      setActiveSection(button.dataset.sectionTarget);
      closeSidebarMobile();
    });
  });
}

function openSidebarMobile() {
  byId("sidebar").classList.add("open");
  byId("drawerBackdrop").classList.add("show");
}

function closeSidebarMobile() {
  byId("sidebar").classList.remove("open");
  byId("drawerBackdrop").classList.remove("show");
}

function bindMobileMenu() {
  byId("mobileMenuBtn").addEventListener("click", openSidebarMobile);
  byId("drawerBackdrop").addEventListener("click", closeSidebarMobile);
}

function bindFilters() {
  byId("filtersForm").addEventListener("submit", (event) => {
    event.preventDefault();
    applyFilters();
  });

  byId("clearFiltersBtn").addEventListener("click", () => {
    byId("searchInput").value = "";
    byId("statusFilter").value = "all";
    byId("photoFilter").value = "all";
    applyFilters();
  });
}

function bindRefresh() {
  byId("refreshDashboardBtn").addEventListener("click", async () => {
    await initializeData();
  });
}

async function initializeData() {
  const equipmentGrid = byId("equipmentGrid");
  const alertsList = byId("alertsList");
  const priorityAlerts = byId("priorityAlerts");

  equipmentGrid.innerHTML = `<div class="empty-state">Carregando instrumentos...</div>`;
  alertsList.innerHTML = `<div class="empty-state">Carregando alertas...</div>`;
  priorityAlerts.innerHTML = `<div class="empty-state small">Carregando alertas...</div>`;

  try {
    await Promise.all([loadDashboard(), loadEquipments()]);
    renderMetrics();
    renderPriorityAlerts();
    renderAlertsSection();
    applyFilters();
    setLastUpdate();
  } catch (error) {
    console.error(error);
    equipmentGrid.innerHTML = `<div class="empty-state">Erro ao carregar instrumentos: ${escapeHtml(error.message)}</div>`;
    alertsList.innerHTML = `<div class="empty-state">Erro ao carregar alertas: ${escapeHtml(error.message)}</div>`;
    priorityAlerts.innerHTML = `<div class="empty-state small">Erro ao carregar alertas.</div>`;
  }
}

function start() {
  bindNavigation();
  bindMobileMenu();
  bindFilters();
  bindRefresh();
  setActiveSection("dashboardSection");
  initializeData();
}

window.addEventListener("DOMContentLoaded", start);