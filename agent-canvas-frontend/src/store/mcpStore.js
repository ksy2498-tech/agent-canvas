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

export const useMCPStore = create((set, get) => ({
  globalServers: [],
  graphServers: {},

  loadServers: async () => {
    const data = await client.listMCPServers();
    set(normalizeServers(data));
  },
  addServer: async (server, scope = 'global') => {
    const saved = await client.saveMCPServer(server, scope);
    const next = saved.server || { ...server, id: server.id || crypto.randomUUID(), status: 'disconnected', tools: server.tools || [] };
    set((state) =>
      scope === 'global'
        ? { globalServers: [...state.globalServers, next] }
        : { graphServers: { ...state.graphServers, [scope]: [...(state.graphServers[scope] || []), next] } },
    );
  },
  upsertLocalServer: (server, scope = 'global') =>
    set((state) => {
      const next = { ...server, id: server.id || crypto.randomUUID(), tools: server.tools || [] };
      if (scope === 'global') {
        const exists = state.globalServers.some((s) => s.id === next.id);
        return { globalServers: exists ? updateServer(state.globalServers, next.id, next) : [...state.globalServers, next] };
      }
      const current = state.graphServers[scope] || [];
      const exists = current.some((s) => s.id === next.id);
      return { graphServers: { ...state.graphServers, [scope]: exists ? updateServer(current, next.id, next) : [...current, next] } };
    }),
  removeServer: async (id, scope = 'global') => {
    await client.deleteMCPServer(id, scope);
    set((state) =>
      scope === 'global'
        ? { globalServers: state.globalServers.filter((server) => server.id !== id) }
        : { graphServers: { ...state.graphServers, [scope]: (state.graphServers[scope] || []).filter((server) => server.id !== id) } },
    );
  },
  testConnection: async (id) => {
    const result = await client.testMCPConnection(id);
    const status = result.status || 'connected';
    set((state) => ({
      globalServers: updateServer(state.globalServers, id, { status }),
      graphServers: Object.fromEntries(
        Object.entries(state.graphServers).map(([graphId, servers]) => [graphId, updateServer(servers, id, { status })]),
      ),
    }));
    return result;
  },
  fetchTools: async (id) => {
    const tools = normalizeTools(await client.fetchMCPTools(id));
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
