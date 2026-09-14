import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
});

export const getSummary = () => api.get('/analytics/summary').then(res => res.data);
export const getSignals = () => api.get('/analytics/signals').then(res => res.data);
export const getChartData = () => api.get('/analytics/chart').then(res => res.data);
export const runDailyCheck = () => api.post('/scheduler/run').then(res => res.data);
export const getHistory = () => api.get('/scheduler/history').then(res => res.data);
export const sendChat = (message) => api.post('/chat', { message }).then(res => res.data);

export default api;
