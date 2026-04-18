window.TAGCHECK_VIEWER_CONFIG = {
  APP_VERSION: '2.0.0',
  APP_NAME: 'TagCheck Viewer',
  API_BASE_URL: 'https://tag-pro.onrender.com',
  REQUEST_TIMEOUT_MS: 12000,
  ENABLE_DEBUG: false,
  ENDPOINTS: {
  byTag: [
    '/equipment/tag/:tag'
  ],
  byId: [
    '/equipment'
  ],
  health: [
    '/health'
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
