import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
});

// ── Existing endpoints (preserved)
export const getSummary     = () => api.get('/analytics/summary').then(r => r.data);
export const getSignals     = () => api.get('/analytics/signals').then(r => r.data);
export const getChartData   = () => api.get('/analytics/chart').then(r => r.data);
export const runDailyCheck  = () => api.post('/scheduler/run').then(r => r.data);
export const getHistory     = () => api.get('/scheduler/history').then(r => r.data);
export const sendChat       = (message) => api.post('/chat', { message }).then(r => r.data);

// ── New endpoints (n8n + Cognee integration)
export const getInventory       = () => api.get('/analytics/inventory').then(r => r.data);
export const getMerchantProfile = () => api.get('/analytics/merchant-profile').then(r => r.data);
export const getAlertsData      = () => api.get('/analytics/alerts').then(r => r.data);

export const addMemory = (text, memory_type = 'MERCHANT_CONTEXT') =>
  api.post('/cognee/add-memory', { text, memory_type }).then(r => r.data);

export const searchMemory = (q) =>
  api.get('/cognee/search', { params: { q } }).then(r => r.data);

export const seedMemories = () => api.post('/cognee/seed').then(r => r.data);
export const getCogneeStatus = () => api.get('/cognee/status').then(r => r.data);

export default api;
