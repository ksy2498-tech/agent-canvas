import { BaseFields, Field, SelectInput, TextInput } from './common.jsx';
import { useGraphStore } from '../../../store/graphStore';
export default function NLPNodePanel({ node }) {
  const updateNodeData = useGraphStore((s) => s.updateNodeData);
  const data = { id: node.id, engine: 'Kiwi', analysisType: 'morpheme', outputKey: 'nlp_result', ...node.data };
  const setData = (patch) => updateNodeData(node.id, patch);
  return <BaseFields data={data} setData={setData} mcpModes={['tool-only']}><Field label="Engine"><SelectInput value={data.engine} onChange={(engine) => setData({ engine })} options={['Kiwi', 'Mecab', 'Komoran']} /></Field><Field label="Analysis type"><SelectInput value={data.analysisType} onChange={(analysisType) => setData({ analysisType })} options={['morpheme', 'noun-extraction', 'sentiment']} /></Field><Field label="Output key"><TextInput value={data.outputKey} onChange={(outputKey) => setData({ outputKey })} /></Field></BaseFields>;
}
