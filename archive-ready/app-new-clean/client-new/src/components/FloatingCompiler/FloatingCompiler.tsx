import { useState, useCallback, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import { Terminal, X, Play } from 'lucide-react';
import { trainingApi, type CodeRunResult } from '../../api/training';
import { useAppDispatch } from '../../store/hooks';
import { toggleSidebar } from '../../store/slices/uiSlice';
import { useAppSelector } from '../../store/hooks';
import styles from './FloatingCompiler.module.css';

const LANGUAGES = [
  { value: 'python', label: 'Python' },
  { value: 'javascript', label: 'JS' },
  { value: 'typescript', label: 'TS' },
  { value: 'bash', label: 'Bash' },
  { value: 'html', label: 'HTML' },
];

const DEFAULTS: Record<string, string> = {
  python: '# Python\nprint("Hello, World!")\n',
  javascript: '// JavaScript\nconsole.log("Hello, World!");\n',
  typescript: '// TypeScript\nconst msg: string = "Hello!";\nconsole.log(msg);\n',
  bash: '#!/bin/bash\necho "Hello, World!"\n',
  html: '<!DOCTYPE html>\n<html><body>\n  <h1>Hello!</h1>\n</body></html>\n',
};

export default function FloatingCompiler() {
  const [open, setOpen] = useState(false);
  const [language, setLanguage] = useState('python');
  const [code, setCode] = useState(DEFAULTS['python']);
  const [result, setResult] = useState<CodeRunResult | null>(null);
  const [running, setRunning] = useState(false);
  const dispatch = useAppDispatch();
  const sidebarOpen = useAppSelector(s => s.ui.sidebarOpen);

  // При открытии компилятора закрываем сайдбар
  const handleOpen = useCallback(() => {
    setOpen(true);
    if (sidebarOpen) dispatch(toggleSidebar());
  }, [sidebarOpen, dispatch]);

  const handleClose = useCallback(() => {
    setOpen(false);
    if (!sidebarOpen) dispatch(toggleSidebar());
  }, [sidebarOpen, dispatch]);

  // ESC закрывает панель
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') handleClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [open, handleClose]);

  const handleLang = useCallback((lang: string) => {
    setLanguage(lang);
    setCode(DEFAULTS[lang] || '');
    setResult(null);
  }, []);

  const handleRun = useCallback(async () => {
    if (!code.trim()) return;
    setRunning(true);
    setResult(null);
    try {
      const { data } = await trainingApi.runCode(language, code);
      setResult(data);
    } catch {
      setResult({ stdout: '', stderr: 'Ошибка выполнения', exit_code: 1, timed_out: false });
    } finally {
      setRunning(false);
    }
  }, [code, language]);

  const monacoLang = language === 'bash' ? 'shell' : language;

  if (!open) {
    return (
      <button className={styles.floatingBtn} onClick={handleOpen} title="Открыть компилятор">
        <Terminal size={18} />
        <span>Открыть компилятор</span>
      </button>
    );
  }

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <div className={styles.panelTitle}>
          <Terminal size={16} /> Компилятор
        </div>
        <button className={styles.closeBtn} onClick={handleClose} title="Закрыть">
          <X size={18} />
        </button>
      </div>
      <div className={styles.panelBody}>
        {/* Language bar */}
        <div className={styles.langBar}>
          <div className={styles.langBtns}>
            {LANGUAGES.map(l => (
              <button key={l.value}
                className={`${styles.langChip} ${language === l.value ? styles.langChipActive : ''}`}
                onClick={() => handleLang(l.value)}>
                {l.label}
              </button>
            ))}
          </div>
          <button className={styles.runBtn} onClick={handleRun} disabled={running || !code.trim()}>
            <Play size={14} /> {running ? 'Выполнение...' : 'Запустить'}
          </button>
        </div>

        {/* Editor (top half) */}
        <div className={styles.editorWrap}>
          <Editor
            height="100%"
            language={monacoLang}
            value={code}
            onChange={(v: string | undefined) => setCode(v || '')}
            theme="vs-dark"
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              lineNumbers: 'on',
              scrollBeyondLastLine: false,
              automaticLayout: true,
              tabSize: 2,
              wordWrap: 'on',
            }}
          />
        </div>

        {/* Output (bottom) */}
        <div className={styles.outputWrap}>
          <div className={styles.outputHeader}>
            <span className={styles.outputLabel}>Вывод</span>
            {result && (
              result.timed_out
                ? <span className={`${styles.badge} ${styles.badgeTimeout}`}>Таймаут</span>
                : result.exit_code === 0
                  ? <span className={`${styles.badge} ${styles.badgeOk}`}>OK</span>
                  : <span className={`${styles.badge} ${styles.badgeErr}`}>Exit: {result.exit_code}</span>
            )}
          </div>
          {result ? (
            language === 'html' && result.exit_code === 0 ? (
              <iframe className={styles.htmlPreview} srcDoc={result.stdout} sandbox="allow-scripts" title="HTML Preview" />
            ) : (
              <pre className={styles.outputText}>
                {result.stdout}{result.stderr ? `\n--- stderr ---\n${result.stderr}` : ''}
              </pre>
            )
          ) : (
            <div className={styles.emptyOutput}>Нажмите «Запустить» для выполнения кода</div>
          )}
        </div>
      </div>
    </div>
  );
}
