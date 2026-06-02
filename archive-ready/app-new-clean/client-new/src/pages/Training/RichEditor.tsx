import { useRef, useEffect, useCallback } from 'react';
import {
  Bold, Italic, Underline, Strikethrough, Heading2, Heading3, Heading4, Pilcrow,
  List, ListOrdered, Table, Link, Quote, Code2, AlignLeft, AlignCenter, AlignRight
} from 'lucide-react';
import styles from './RichEditor.module.css';

interface Props {
  content: string;
  onChange: (html: string) => void;
}

export default function RichEditor({ content, onChange }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (ref.current) ref.current.innerHTML = content || '';
  }, []); // mount only — use key prop to remount

  const fire = useCallback(() => {
    if (ref.current) onChange(ref.current.innerHTML);
  }, [onChange]);

  const exec = useCallback((cmd: string, val?: string) => {
    document.execCommand(cmd, false, val);
    ref.current?.focus();
    fire();
  }, [fire]);

  const insertTable = () => {
    const r = parseInt(prompt('Строк:', '3') || '0');
    const c = parseInt(prompt('Столбцов:', '3') || '0');
    if (!r || !c || r < 1 || c < 1 || r > 50 || c > 20) return;
    let h = '<table><thead><tr>';
    for (let i = 0; i < c; i++) h += '<th>Заголовок</th>';
    h += '</tr></thead><tbody>';
    for (let i = 0; i < r - 1; i++) { h += '<tr>'; for (let j = 0; j < c; j++) h += '<td>&nbsp;</td>'; h += '</tr>'; }
    h += '</tbody></table><p></p>';
    document.execCommand('insertHTML', false, h);
    fire();
  };

  const pd = (e: React.MouseEvent) => e.preventDefault(); // prevent blur

  return (
    <div className={styles.editor}>
      <div className={styles.toolbar}>
        <button type="button" onMouseDown={pd} onClick={() => exec('bold')} title="Жирный"><Bold size={15} /></button>
        <button type="button" onMouseDown={pd} onClick={() => exec('italic')} title="Курсив"><Italic size={15} /></button>
        <button type="button" onMouseDown={pd} onClick={() => exec('underline')} title="Подчёркнутый"><Underline size={15} /></button>
        <button type="button" onMouseDown={pd} onClick={() => exec('strikeThrough')} title="Зачёркнутый"><Strikethrough size={15} /></button>
        <span className={styles.sep} />
        <button type="button" onMouseDown={pd} onClick={() => exec('formatBlock', '<h2>')} title="Заголовок 2"><Heading2 size={15} /></button>
        <button type="button" onMouseDown={pd} onClick={() => exec('formatBlock', '<h3>')} title="Заголовок 3"><Heading3 size={15} /></button>
        <button type="button" onMouseDown={pd} onClick={() => exec('formatBlock', '<h4>')} title="Заголовок 4"><Heading4 size={15} /></button>
        <button type="button" onMouseDown={pd} onClick={() => exec('formatBlock', '<p>')} title="Абзац"><Pilcrow size={15} /></button>
        <span className={styles.sep} />
        <button type="button" onMouseDown={pd} onClick={() => exec('insertUnorderedList')} title="Маркированный список"><List size={15} /></button>
        <button type="button" onMouseDown={pd} onClick={() => exec('insertOrderedList')} title="Нумерованный список"><ListOrdered size={15} /></button>
        <span className={styles.sep} />
        <button type="button" onMouseDown={pd} onClick={insertTable} title="Таблица"><Table size={15} /></button>
        <button type="button" onMouseDown={pd} onClick={() => { const u = prompt('URL:'); if (u && /^https?:\/\//i.test(u)) exec('createLink', u); }} title="Ссылка"><Link size={15} /></button>
        <button type="button" onMouseDown={pd} onClick={() => exec('formatBlock', '<blockquote>')} title="Цитата"><Quote size={15} /></button>
        <button type="button" onMouseDown={pd} onClick={() => { document.execCommand('insertHTML', false, '<pre><code>code</code></pre><p></p>'); fire(); }} title="Блок кода"><Code2 size={15} /></button>
        <span className={styles.sep} />
        <button type="button" onMouseDown={pd} onClick={() => exec('justifyLeft')} title="По левому"><AlignLeft size={15} /></button>
        <button type="button" onMouseDown={pd} onClick={() => exec('justifyCenter')} title="По центру"><AlignCenter size={15} /></button>
        <button type="button" onMouseDown={pd} onClick={() => exec('justifyRight')} title="По правому"><AlignRight size={15} /></button>
      </div>
      <div ref={ref} className={styles.content} contentEditable onInput={fire} suppressContentEditableWarning />
    </div>
  );
}
