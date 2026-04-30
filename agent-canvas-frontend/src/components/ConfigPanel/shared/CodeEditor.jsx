import Editor from '@monaco-editor/react';

export default function CodeEditor({ value, onChange, language = 'python', height = 240 }) {
  const stopCanvasEvent = (event) => {
    event.stopPropagation();
  };

  return (
    <div
      className="overflow-hidden rounded-md border border-slate-200 dark:border-slate-700"
      onMouseDown={stopCanvasEvent}
      onPointerDown={stopCanvasEvent}
      onClick={stopCanvasEvent}
      onDoubleClick={stopCanvasEvent}
    >
      <Editor
        height={height}
        language={language}
        value={value || ''}
        onChange={(next) => onChange(next || '')}
        theme={document.documentElement.classList.contains('dark') ? 'vs-dark' : 'light'}
        options={{ minimap: { enabled: false }, fontSize: 13, scrollBeyondLastLine: false }}
      />
    </div>
  );
}
