import { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { Task } from '../../types';
import type { Translations } from '../../i18n';
import styles from './ProjectViews.module.css';

const LOCALE_MAP: Record<string, string> = { ru: 'ru-RU', ka: 'ka-GE', en: 'en-US', ar: 'ar-SA' };

function parseD(d?: string | null): Date | null {
  if (!d) return null;
  const x = new Date(d);
  return Number.isNaN(x.getTime()) ? null : x;
}

function workDaysBetween(a: Date, b: Date): number {
  let n = 0;
  const cur = new Date(a);
  cur.setHours(0, 0, 0, 0);
  const end = new Date(b);
  end.setHours(0, 0, 0, 0);
  while (cur <= end) {
    const w = cur.getDay();
    if (w !== 0 && w !== 6) n++;
    cur.setDate(cur.getDate() + 1);
  }
  return Math.max(1, n);
}

export function ProjectGanttView({
  tasks,
  iterationName,
  lang,
  language,
}: {
  tasks: Task[];
  iterationName: string;
  lang: Translations;
  language: string;
}) {
  const locale = LOCALE_MAP[language] || 'en-US';
  const rows = useMemo(() => {
    return tasks.map(t => {
      const end = parseD(t.deadline) || parseD(t.updated_at) || parseD(t.created_at) || new Date();
      const start = parseD(t.start_date) || parseD(t.created_at) || end;
      const safeStart = start <= end ? start : end;
      const days = workDaysBetween(safeStart, end);
      return { task: t, start: safeStart, end, days };
    });
  }, [tasks]);

  const { min, max, span } = useMemo(() => {
    if (rows.length === 0) {
      const t = new Date();
      return { min: t, max: t, span: 7 };
    }
    let mn = rows[0].start.getTime();
    let mx = rows[0].end.getTime();
    rows.forEach(r => {
      mn = Math.min(mn, r.start.getTime());
      mx = Math.max(mx, r.end.getTime());
    });
    const d0 = new Date(mn);
    const d1 = new Date(mx);
    d1.setDate(d1.getDate() + 3);
    const spanDays = Math.max(7, Math.ceil((d1.getTime() - d0.getTime()) / 86400000));
    return { min: d0, max: d1, span: spanDays };
  }, [rows]);

  const rangeMs = Math.max(86400000, max.getTime() - min.getTime());

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const todayOffset = Math.max(0, Math.floor((today.getTime() - min.getTime()) / 86400000));

  return (
    <div className={styles.ganttWrap}>
      <div className={styles.ganttToolbar}>
        <span className={styles.ganttScale}>{lang.workspace.ganttWeeks}</span>
        <div className={styles.ganttNav}>
          <button type="button" className={styles.ganttNavBtn}>
            − {lang.workspace.today} +
          </button>
        </div>
      </div>
      <div className={styles.ganttGrid}>
        <div className={styles.ganttTable}>
          <div className={styles.ganttHeadRow}>
            <div className={styles.ganttColName}>{lang.workspace.colName}</div>
            <div className={styles.ganttColSmall}>{lang.workspace.colAssignee}</div>
            <div className={styles.ganttColRange}>{lang.workspace.colDateRange}</div>
            <div className={styles.ganttColDays}>{lang.workspace.colWorkDays}</div>
          </div>
          <div className={styles.ganttTreeRow}>
            <div className={styles.ganttColName}>
              <strong>{iterationName}</strong>
            </div>
            <div className={styles.ganttColSmall} />
            <div className={styles.ganttColRange} />
            <div className={styles.ganttColDays} />
          </div>
          {rows.map(({ task, start, end, days }) => {
            const left = ((start.getTime() - min.getTime()) / rangeMs) * 100;
            const w = ((end.getTime() - start.getTime()) / rangeMs) * 100;
            return (
              <div key={task.id} className={styles.ganttDataRow}>
                <div className={styles.ganttColName}>
                  <span className={styles.ganttTaskTitle}>{task.title}</span>
                </div>
                <div className={styles.ganttColSmall}>
                  <span className={styles.ganttInitials}>{(task.assignee_name || '?').slice(0, 2)}</span>
                </div>
                <div className={styles.ganttColRange}>
                  {start.toLocaleDateString(locale, { day: 'numeric', month: 'short' })} —{' '}
                  {end.toLocaleDateString(locale, { day: 'numeric', month: 'short' })}
                </div>
                <div className={styles.ganttColDays}>
                  {days} {lang.workspace.daysShort}
                </div>
                <div className={styles.ganttBarTrack}>
                  <div
                    className={styles.ganttBar}
                    style={{
                      left: `${Math.max(0, Math.min(95, left))}%`,
                      width: `${Math.max(4, Math.min(100, w || 8))}%`,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
        <div className={styles.ganttTimeline}>
          <div className={styles.ganttTimelineHeader}>
            {min.toLocaleDateString(locale, { month: 'long', year: 'numeric' })}
          </div>
          <div className={styles.ganttTimelineInner}>
            <div
              className={styles.ganttTodayLine}
              style={{ left: `${Math.min(100, (todayOffset / span) * 100)}%` }}
            />
            {Array.from({ length: Math.min(14, span) }).map((_, i) => (
              <div key={i} className={styles.ganttWeekCell} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

const HOURS = [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19];

export function ProjectCalendarView({
  tasks,
  lang,
  language,
}: {
  tasks: Task[];
  lang: Translations;
  language: string;
}) {
  const locale = LOCALE_MAP[language] || 'en-US';
  const [weekStart, setWeekStart] = useState(() => {
    const t = new Date();
    const d = t.getDay();
    const diff = t.getDate() - d + (d === 0 ? -6 : 1);
    const mon = new Date(t);
    mon.setDate(diff);
    mon.setHours(0, 0, 0, 0);
    return mon;
  });

  const days = useMemo(() => {
    return Array.from({ length: 7 }).map((_, i) => {
      const x = new Date(weekStart);
      x.setDate(weekStart.getDate() + i);
      return x;
    });
  }, [weekStart]);

  const weekEnd = days[6];
  const isToday = (d: Date) => d.toDateString() === new Date().toDateString();
  const isWeekend = (d: Date) => {
    const w = d.getDay();
    return w === 0 || w === 6;
  };

  const tasksByDay = useMemo(() => {
    const m: Record<string, Task[]> = {};
    days.forEach(d => {
      m[d.toDateString()] = [];
    });
    tasks.forEach(t => {
      const start = parseD(t.start_date) || parseD(t.deadline);
      const end = parseD(t.deadline) || start;
      if (start && end) {
        const cursor = new Date(start <= end ? start : end);
        const limit = new Date(end >= start ? end : start);
        cursor.setHours(0, 0, 0, 0);
        limit.setHours(0, 0, 0, 0);
        while (cursor <= limit) {
          const key = cursor.toDateString();
          if (m[key]) m[key].push(t);
          cursor.setDate(cursor.getDate() + 1);
        }
      }
    });
    return m;
  }, [tasks, days]);

  const weekNum = (() => {
    const t = new Date(Date.UTC(weekStart.getFullYear(), weekStart.getMonth(), weekStart.getDate()));
    const dayNum = t.getUTCDay() || 7;
    t.setUTCDate(t.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
    return Math.ceil(((t.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  })();

  return (
    <div className={styles.calWrap}>
      <div className={styles.calToolbar}>
        <div className={styles.calRange}>
          {weekStart.toLocaleDateString(locale, { month: 'long', day: 'numeric' })}—{weekEnd.getDate()}
        </div>
        <div className={styles.calNav}>
          <button
            type="button"
            className={styles.calNavBtn}
            aria-label="prev"
            onClick={() => {
              const n = new Date(weekStart);
              n.setDate(n.getDate() - 7);
              setWeekStart(n);
            }}
          >
            <ChevronLeft size={18} />
          </button>
          <button type="button" className={styles.calTodayBtn} onClick={() => setWeekStart(new Date())}>
            {lang.workspace.today}
          </button>
          <button
            type="button"
            className={styles.calNavBtn}
            aria-label="next"
            onClick={() => {
              const n = new Date(weekStart);
              n.setDate(n.getDate() + 7);
              setWeekStart(n);
            }}
          >
            <ChevronRight size={18} />
          </button>
        </div>
        <div className={styles.calWeekNum}>
          {lang.workspace.weekNumber} {weekNum}
        </div>
      </div>
      <div className={styles.calGrid}>
        <div className={styles.calCorner} />
        {days.map(d => (
          <div
            key={d.toISOString()}
            className={`${styles.calDayHead} ${isToday(d) ? styles.calDayToday : ''} ${isWeekend(d) ? styles.calDayWeekend : ''}`}
          >
            <span className={styles.calDayShort}>
              {d.toLocaleDateString(locale, { weekday: 'short' })}
            </span>
            <span className={styles.calDayNum}>{d.getDate()}</span>
          </div>
        ))}
        <div className={styles.calAllDayLabel}>{lang.workspace.allDay}</div>
        {days.map(d => (
          <div
            key={`ad-${d.toISOString()}`}
            className={`${styles.calAllDayCell} ${isWeekend(d) ? styles.calDayWeekend : ''}`}
          >
            {tasksByDay[d.toDateString()]?.map(t => (
              <div key={t.id} className={styles.calChip}>
                {t.title.slice(0, 40)}
                {t.title.length > 40 ? '…' : ''}
              </div>
            ))}
          </div>
        ))}
        <div className={styles.calTimeCol}>
          {HOURS.map(h => (
            <div key={h} className={styles.calHour}>
              {String(h).padStart(2, '0')}:00
            </div>
          ))}
        </div>
        {days.map(d => (
          <div
            key={`grid-${d.toISOString()}`}
            className={`${styles.calDayColumn} ${isWeekend(d) ? styles.calDayWeekend : ''}`}
          >
            {HOURS.map(h => (
              <div key={h} className={styles.calSlot}>
                {isToday(d) && h === 14 && <button type="button" className={styles.calSlotPlus} title="+">+</button>}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function SubtasksPanel({
  lang,
  subtasks,
  onAddSubtask,
}: {
  lang: Translations;
  subtasks: Task[];
  onAddSubtask: () => void;
}) {
  const done = subtasks.filter(s => s.is_completed).length;
  const total = subtasks.length;
  const pct = total ? Math.round((done / total) * 100) : 0;
  return (
    <div className={styles.subtasksPanel}>
      <div className={styles.subtasksHead}>
        <span>{lang.workspace.subtasksHeading}</span>
        <span className={styles.subtasksCount}>
          {done}/{total}
        </span>
      </div>
      <div className={styles.subtasksBar}>
        <div className={styles.subtasksBarFill} style={{ width: `${pct}%` }} />
      </div>
      {subtasks.length === 0 ? (
        <p className={styles.subtasksEmpty}>{lang.workspace.subtasksEmpty}</p>
      ) : (
        <ul className={styles.subtasksList}>
          {subtasks.map(s => (
            <li key={s.id} className={styles.subtasksListItem}>
              <span className={s.is_completed ? styles.subtasksDone : ''}>{s.title}</span>
            </li>
          ))}
        </ul>
      )}
      <button type="button" className={styles.subtaskAdd} onClick={onAddSubtask}>
        + {lang.workspace.addSubtask}
      </button>
    </div>
  );
}
