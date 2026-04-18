window.TAGCHECK_ADMIN_CONFIG = {
  APP_VERSION: '1.0.0',
  APP_NAME: 'TagCheck Admin',
  API_BASE_URL: 'https://tag-pro.onrender.com',
  VIEWER_BASE_URL: 'https://tag-viewer.onrender.com',
  REQUEST_TIMEOUT_MS: 15000,
  STORAGE_KEYS: {
    language: 'tagcheck_admin_language',
    lastSearch: 'tagcheck_admin_last_search'
  },
  ENDPOINTS: {
    list: '/equipment',
    create: '/equipment',
    byTag: '/equipment/tag/:tag',
    health: '/health'
  }
};