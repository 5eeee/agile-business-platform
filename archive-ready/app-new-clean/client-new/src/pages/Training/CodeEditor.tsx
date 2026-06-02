import { useState, useCallback } from 'react';
import Editor from '@monaco-editor/react';
import { Play } from 'lucide-react';
import { trainingApi, type CodeRunResult } from '../../api/training';
import styles from './CodeEditor.module.css';

const LANGUAGES = [
  { value: 'python', label: 'Python' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'typescript', label: 'TypeScript' },
  { value: 'bash', label: 'Bash' },
  { value: 'html', label: 'HTML' },
];

const LANG_DEFAULTS: Record<string, string> = {
  python: '# Write your Python code here\nprint("Hello, World!")\n',
  javascript: '// Write your JavaScript code here\nconsole.log("Hello, World!");\n',
  typescript: '// Write your TypeScript code here\nconst greeting: string = "Hello, World!";\nconsole.log(greeting);\n',
  bash: '#!/bin/bash\necho "Hello, World!"\n',
  html: '<!DOCTYPE html>\n<html>\n<head><title>Preview</title></head>\n<body>\n  <h1>Hello, World!</h1>\n</body>\n</html>\n',
};

export default function CodeEditor() {
  const [language, setLanguage] = useState('python');
  const [code, setCode] = useState(LANG_DEFAULTS['python']);
  const [result, setResult] = useState<CodeRunResult | null>(null);
  const [running, setRunning] = useState(false);
  const [htmlPreview, setHtmlPreview] = useState('');

  const handleLanguageChange = useCallback((lang: string) => {
    setLanguage(lang);
    setCode(LANG_DEFAULTS[lang] || '');
    setResult(null);
    setHtmlPreview('');
  }, []);

  const handleRun = useCallback(async () => {
    if (!code.trim()) return;
    setRunning(true);
    setResult(null);
    setHtmlPreview('');
    try {
      const { data } = await trainingApi.runCode(language, code);
      setResult(data);
      if (language === 'html') {
        setHtmlPreview(data.stdout);
      }
    } catch {
      setResult({ stdout: '', stderr: 'Failed to execute code', exit_code: 1, timed_out: false });
    } finally {
      setRunning(false);
    }
  }, [code, language]);

  const monacoLang = language === 'bash' ? 'shell' : language;

  return (
    <div className={styles.editor}>
      <div className={styles.toolbar}>
        <div className={styles.langSelect}>
          {LANGUAGES.map(l => (
            <button
              key={l.value}
              className={`${styles.langBtn} ${language === l.value ? styles.langActive : ''}`}
              onClick={() => handleLanguageChange(l.value)}
            >
              {l.label}
            </button>
          ))}
        </div>
        <button
          className={styles.runBtn}
          onClick={handleRun}
          disabled={running || !code.trim()}
        >
          {running ? 'Выполнение...' : <><Play size={16} style={{ marginRight: 6 }} /> Запустить</>}
        </button>
      </div>

      <div className={styles.editorPane}>
        <Editor
          height="300px"
          language={monacoLang}
          value={code}
          onChange={(v: string | undefined) => setCode(v || '')}
          theme="vs-dark"
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 2,
            wordWrap: 'on',
          }}
        />
      </div>

      {result && (
        <div className={styles.output}>
          <div className={styles.outputHeader}>
            <span>Вывод</span>
            {result.timed_out && <span className={styles.timeout}>Таймаут</span>}
            {result.exit_code !== 0 && !result.timed_out && <span className={styles.errorBadge}>Exit: {result.exit_code}</span>}
            {result.exit_code === 0 && !result.timed_out && <span className={styles.successBadge}>OK</span>}
          </div>
          {language === 'html' && htmlPreview ? (
            <iframe
              className={styles.htmlPreview}
              srcDoc={htmlPreview}
              sandbox="allow-scripts"
              title="HTML Preview"
            />
          ) : (
            <pre className={styles.outputText}>
              {result.stdout}{result.stderr ? `\n--- stderr ---\n${result.stderr}` : ''}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
