import axios from 'axios';

export const api = axios.create({
  baseURL: '/api',
});

export const listGraphs = () => api.get('/graphs').then((r) => r.data);
export const getGraph = (id) => api.get(`/graphs/${id}`).then((r) => r.data);
export const createGraph = (name) => api.post('/graphs', { name }).then((r) => r.data);
export const saveGraph = (id, payload) =>
  api.put(`/graphs/${id}`, payload).then((r) => r.data).catch((error) => {
    console.error('saveGraph failed', error.response?.data || error);
    throw error;
  });
export const deleteGraph = (id) => api.delete(`/graphs/${id}`).then((r) => r.data);

const splitSSEFrames = (chunk) => chunk.replace(/\r\n/g, '\n').split('\n\n');

const parseStreamPayloads = (chunk) =>
  splitSSEFrames(chunk)
    .map((frame) => {
      const lines = frame
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean);
      const event = lines.find((line) => line.startsWith('event:'))?.slice(6).trim();
      const data = lines
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trim())
        .join('\n');

      if (!data || data === '[DONE]') return null;

      try {
        const payload = JSON.parse(data);
        return event && !payload.type ? { ...payload, type: event } : payload;
      } catch {
        return { type: event || 'message', text: data };
      }
    })
    .filter(Boolean);

export const runGraph = async (id, query, breakpoints, edgeBreakpoints, onEvent) => {
  const response = await fetch(`/api/graphs/${id}/run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({
      query,
      breakpoints: breakpoints || {},
      edgeBreakpoints: edgeBreakpoints || {},
    }),
  });

  if (!response.ok) {
    let detail = '';
    try {
      const payload = await response.json();
      detail = payload.detail || payload.message || '';
    } catch {
      detail = await response.text().catch(() => '');
    }
    throw new Error(detail ? `Run failed with ${response.status}: ${detail}` : `Run failed with ${response.status}`);
  }

  if (!response.body) {
    const payload = await response.json();
    onEvent?.(payload);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = buffer.replace(/\r\n/g, '\n');
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || '';
    parseStreamPayloads(parts.join('\n\n')).forEach((payload) => onEvent?.(payload));
  }

  if (buffer.trim()) {
    parseStreamPayloads(buffer).forEach((payload) => onEvent?.(payload));
  }
};

export const resumeExecution = (id, editedState) =>
  api.post(`/graphs/${id}/resume`, { editedState }).then((r) => r.data);

export const downloadCode = async (id, filename = 'agent-graph.zip') => {
  const response = await api.get(`/graphs/${id}/download`, { responseType: 'blob' });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
};

export const listMCPServers = () => api.get('/mcp/servers').then((r) => r.data);
export const saveMCPServer = (server, scope) => api.post('/mcp/servers', { server, scope }).then((r) => r.data);
export const deleteMCPServer = (id, scope) => api.delete(`/mcp/servers/${id}`, { data: { scope } }).then((r) => r.data);
export const testMCPConnection = (id) => api.post('/mcp/test', { id }).then((r) => r.data);
export const fetchMCPTools = (id) => api.get(`/mcp/servers/${id}/tools`).then((r) => r.data);
export const testDBConnection = (connectionString, dbType) =>
  api.post('/db/test', { connectionString, dbType }).then((r) => r.data);
