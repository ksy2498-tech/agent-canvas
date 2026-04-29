import { create } from 'zustand';
import * as client from '../api/client';

const updateServer = (servers, id, patch) => servers.map((server) => (server.id === id ? { ...server, ...patch } : server));
const normalizeTools = (payload) => (Array.isArray(payload) ? payload : payload?.tools || []);
const normalizeServers = (payload) => {
  if (Array.isArray(payload)) {
    return {
      globalServers: payload.filter((server) => server.scope === 'global'),
      graphServers: payload
        .filter((server) => server.scope !== 'global')
        .reduce((groups, server) => ({ ...groups, [server.scope]: [...(groups[server.scope] || []), server] }), {}),
    };
  }
  return {
    globalServers: payload?.globalServers || [],
    graphServers: payload?.graphServers || {},
  };
};

const withUiFields = (server) => ({
  ...server,
  ...(server.config || {}),
  status: server.status || 'disconnected',
  tools: server.tools || [],
});

const upsertServer = (state, server, scope = 'global') => {
  const next = withUiFields(server);
  if (scope === 'global') {
    const exists = state.globalServers.some((s) => s.id === next.id);
    return { globalServers: exists ? updateServer(state.globalServers, next.id, next) : [...state.globalServers, next] };
  }
  const current = state.graphServers[scope] || [];
  const exists = current.some((s) => s.id === next.id);
  return { graphServers: { ...state.graphServers, [scope]: exists ? updateServer(current, next.id, next) : [...current, next] } };
};

export const useMCPStore = create((set, get) => ({
  globalServers: [],
  graphServers: {},

  loadServers: async () => {
    const data = await client.listMCPServers();
    set(normalizeServers(data));
  },
  saveServer: async (server, scope = 'global') => {
    const saved = await client.saveMCPServer(server, scope);
    const next = { ...server, ...saved, status: 'disconnected', tools: server.tools || [] };
    set((state) => upsertServer(state, next, scope));
    return next;
  },
  addServer: async (server, scope = 'global') => {
    const saved = await client.saveMCPServer(server, scope);
    const next = { ...server, ...saved, status: 'disconnected', tools: server.tools || [] };
    set((state) => upsertServer(state, next, scope));
    return next;
  },
  upsertLocalServer: (server, scope = 'global') =>
    set((state) => upsertServer(state, server, scope)),
  removeServer: async (id, scope = 'global') => {
    await client.deleteMCPServer(id);
    set((state) =>
      scope === 'global'
        ? { globalServers: state.globalServers.filter((server) => server.id !== id) }
        : { graphServers: { ...state.graphServers, [scope]: (state.graphServers[scope] || []).filter((server) => server.id !== id) } },
    );
  },
  testConnection: async (server, scope = 'global') => {
    const result = await client.testMCPConnection(server, scope);
    const status = result.status || 'connected';
    const id = server.id;
    set((state) => ({
      globalServers: updateServer(state.globalServers, id, { status }),
      graphServers: Object.fromEntries(
        Object.entries(state.graphServers).map(([graphId, servers]) => [graphId, updateServer(servers, id, { status })]),
      ),
    }));
    return result;
  },
  fetchTools: async (server, scope = 'global') => {
    const tools = normalizeTools(await client.fetchMCPTools(server, scope));
    const id = server.id;
    set((state) => ({
      globalServers: updateServer(state.globalServers, id, { tools }),
      graphServers: Object.fromEntries(
        Object.entries(state.graphServers).map(([graphId, servers]) => [graphId, updateServer(servers, id, { tools })]),
      ),
    }));
    return tools;
  },
  getServersForGraph: (graphId) => [...get().globalServers, ...(get().graphServers[graphId] || [])],
}));
