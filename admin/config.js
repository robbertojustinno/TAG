window.TAGCHECK_ADMIN_CONFIG = {
  APP_VERSION: '3.0.0',
  APP_NAME: 'TagCheck Admin',
  API_BASE_URL: 'https://tag-1-xfzk.onrender.com',
  VIEWER_BASE_URL: 'https://tag-viewer.onrender.com/',
  REQUEST_TIMEOUT_MS: 15000,
  STORAGE_KEYS: {
    language: 'tagcheck_admin_language',
    lastSearch: 'tagcheck_admin_last_search',
    authToken: 'tagcheck_admin_auth_token',
    authUser: 'tagcheck_admin_auth_user'
  },
  ENDPOINTS: {
    login: '/auth/login',
    list: '/equipment',
    create: '/equipment',
    byTag: '/equipment/tag/:tag',
    health: '/health'
  }
};