window.TAGCHECK_VIEWER_CONFIG = {
  APP_VERSION: '2.0.0',
  APP_NAME: 'TagCheck Viewer',
  API_BASE_URL: 'https://SEU-BACKEND-AQUI.onrender.com',
  REQUEST_TIMEOUT_MS: 12000,
  ENABLE_DEBUG: false,
  ENDPOINTS: {
    byTag: [
      '/api/equipments/tag/:tag',
      '/api/equipment/tag/:tag',
      '/api/public/equipment/tag/:tag',
      '/api/public/equipments/tag/:tag',
      '/api/instruments/tag/:tag',
      '/equipments/tag/:tag',
      '/equipment/tag/:tag',
      '/api/equipments/search?tag=:tag',
      '/api/equipment/search?tag=:tag',
      '/api/public/equipment/search?tag=:tag',
      '/api/equipments?tag=:tag',
      '/api/equipment?tag=:tag',
      '/api/public/equipments?tag=:tag'
    ],
    byId: [
      '/api/equipments/:id',
      '/api/equipment/:id',
      '/api/public/equipment/:id',
      '/api/instruments/:id',
      '/equipments/:id',
      '/equipment/:id'
    ],
    health: [
      '/health',
      '/api/health',
      '/docs'
    ]
  },
  QR_PARSE_KEYS: ['tag', 'codigo', 'code', 'id', 'instrumento', 'instrument', 'asset'],
  STORAGE_KEYS: {
    lastSearch: 'tagcheck_viewer_last_search',
    recentItems: 'tagcheck_viewer_recent_items',
    fallbackCache: 'tagcheck_viewer_fallback_cache',
    settings: 'tagcheck_viewer_settings'
  },
  OFFLINE_FALLBACK: {
    enabled: true,
    allowHybridTextParsing: true
  }
};
