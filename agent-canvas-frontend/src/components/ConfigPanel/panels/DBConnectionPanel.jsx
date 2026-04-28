import { BaseFields, Field, SelectInput, TextInput, testDb } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
export default function DBConnectionPanel({ node }) {
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = { id: node.id, dbType: 'SQLite', ...node.data };
  const setData = (patch) => updateNodeData(node.id, patch);
  return <BaseFields data={data} setData={setData}><Field label="DB Type"><SelectInput value={data.dbType} onChange={(dbType) => setData({ dbType })} options={['SQLite', 'PostgreSQL', 'MySQL', 'Redis']} /></Field><Field label="Connection string"><TextInput value={data.connectionString} onChange={(connectionString) => setData({ connectionString })} /></Field><Field label="Connection alias"><TextInput value={data.alias} onChange={(alias) => setData({ alias })} /></Field><button className="secondary-btn" onClick={() => testDb(data)}>Test Connection</button></BaseFields>;
}
