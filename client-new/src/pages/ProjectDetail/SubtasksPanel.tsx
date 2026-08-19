import type { Task } from '../../types';
import type { Translations } from '../../i18n';
import styles from './SubtasksPanel.module.css';

export function SubtasksPanel({
  lang,
  subtasks,
  onAddSubtask,
}: {
  lang: Translations;
  subtasks: Task[];
  onAddSubtask: () => void;
}) {
  const done = subtasks.filter(task => task.is_completed).length;
  const total = subtasks.length;
  const progress = total ? Math.round((done / total) * 100) : 0;

  return (
    <div className={styles.panel}>
      <div className={styles.head}>
        <span>{lang.workspace.subtasksHeading}</span>
        <span className={styles.count}>{done}/{total}</span>
      </div>
      <div className={styles.bar}>
        <div className={styles.barFill} style={{ width: `${progress}%` }} />
      </div>
      {subtasks.length === 0 ? (
        <p className={styles.empty}>{lang.workspace.subtasksEmpty}</p>
      ) : (
        <ul className={styles.list}>
          {subtasks.map(task => (
            <li key={task.id} className={styles.listItem}>
              <span className={task.is_completed ? styles.done : ''}>{task.title}</span>
            </li>
          ))}
        </ul>
      )}
      <button type="button" className={styles.add} onClick={onAddSubtask}>
        + {lang.workspace.addSubtask}
      </button>
    </div>
  );
}
