import { useState, useEffect, useRef, useCallback } from 'react';
import { FileJson, FileSpreadsheet, RotateCcw, Timer, ArrowLeft, ArrowRight } from 'lucide-react';
import { useAppSelector } from '../../store/hooks';
import { t } from '../../i18n';
import { DIVISIONS, IT_TOPICS, getDefaultQuestions, Question, Division, ITTopic } from './assessmentData';
import styles from './Assessment.module.css';

type Screen = 'landing' | 'topics' | 'name' | 'quiz' | 'results';

interface QuizResult {
  name: string; division: string; divId: string; date: string; duration: number;
  choiceCorrect: number; choiceTotal: number; openTotal: number; caseTotal: number;
  totalQuestions: number; answered: number; pct: number;
  questions: { type: string; text: string; answer: string; correct: boolean | null; correctAnswer: string | null; expected: string | null }[];
}

const MAX_TIME = 3 * 60 * 60;

export default function AssessmentPage() {
  const { language } = useAppSelector(s => s.ui);
  const { user } = useAppSelector(s => s.auth);
  const lang = t(language);

  const [screen, setScreen] = useState<Screen>('landing');
  const [selectedDiv, setSelectedDiv] = useState<Division | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<ITTopic | null>(null);
  const [userName, setUserName] = useState(user?.name || '');
  const [quizQs, setQuizQs] = useState<Question[]>([]);
  const [curQ, setCurQ] = useState(0);
  const [answers, setAnswers] = useState<Record<string, number | string>>({});
  const [startTime, setStartTime] = useState(0);
  const [timerText, setTimerText] = useState('03:00:00');
  const [timerClass, setTimerClass] = useState('');
  const [result, setResult] = useState<QuizResult | null>(null);
  const [questionsDB, setQuestionsDB] = useState<Record<string, Question[]>>({});
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load questions DB
  useEffect(() => {
    const def = getDefaultQuestions();
    const allKeys = [...DIVISIONS.filter(d => !d.hasTopics).map(d => d.id), ...IT_TOPICS.map(t => t.id)];
    const db: Record<string, Question[]> = {};
    allKeys.forEach(k => { db[k] = (def[k] || []).map((q, i) => ({ ...q, id: k + '_' + i })); });
    setQuestionsDB(db);
  }, []);

  // Timer
  useEffect(() => {
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  const finishQuiz = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    let correct = 0, totalChoice = 0, totalOpen = 0, totalCase = 0, answered = 0;
    quizQs.forEach(q => {
      if (q.type === 'choice') { totalChoice++; if (answers[q.id] === q.correct) correct++; if (answers[q.id] !== undefined) answered++; }
      else if (q.type === 'open') { totalOpen++; if (answers[q.id] && String(answers[q.id]).trim()) answered++; }
      else { totalCase++; if (answers[q.id] && String(answers[q.id]).trim()) answered++; }
    });
    const pct = totalChoice ? Math.round(correct / totalChoice * 100) : 0;
    const divName = selectedTopic ? 'IT: ' + selectedTopic.name : selectedDiv!.name;
    const r: QuizResult = {
      name: userName, division: divName, divId: selectedTopic ? selectedTopic.id : selectedDiv!.id,
      date: new Date().toISOString(), duration: elapsed,
      choiceCorrect: correct, choiceTotal: totalChoice, openTotal: totalOpen, caseTotal: totalCase,
      totalQuestions: quizQs.length, answered, pct,
      questions: quizQs.map(q => ({
        type: q.type, text: q.text,
        answer: q.type === 'choice' ? (q.options?.[answers[q.id] as number] || '—') : (String(answers[q.id] || '')),
        correct: q.type === 'choice' ? answers[q.id] === q.correct : null,
        correctAnswer: q.type === 'choice' ? (q.options?.[q.correct!] ?? null) : null,
        expected: q.expected || null,
      })),
    };
    setResult(r);
    setScreen('results');
  }, [startTime, quizQs, answers, userName, selectedDiv, selectedTopic]);

  const startTimer = useCallback((st: number) => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      const el = Math.floor((Date.now() - st) / 1000);
      const rem = MAX_TIME - el;
      if (rem <= 0) { finishQuiz(); return; }
      const h = String(Math.floor(rem / 3600)).padStart(2, '0');
      const m = String(Math.floor((rem % 3600) / 60)).padStart(2, '0');
      const s = String(rem % 60).padStart(2, '0');
      setTimerText(`${h}:${m}:${s}`);
      setTimerClass(rem < 300 ? 'danger' : rem < 900 ? 'warning' : '');
    }, 1000);
  }, [finishQuiz]);

  const selectDiv = (id: string) => {
    const div = DIVISIONS.find(d => d.id === id)!;
    setSelectedDiv(div);
    setSelectedTopic(null);
    if (div.hasTopics) { setScreen('topics'); }
    else { setScreen('name'); setUserName(user?.name || ''); }
  };

  const selectTopic = (id: string) => {
    const topic = IT_TOPICS.find(t => t.id === id)!;
    setSelectedTopic(topic);
    setScreen('name');
    setUserName(user?.name || '');
  };

  const startQuiz = () => {
    if (!userName.trim() || userName.trim().length < 2) return;
    const key = selectedTopic ? selectedTopic.id : selectedDiv!.id;
    const qs = [...(questionsDB[key] || [])];
    setQuizQs(qs);
    setCurQ(0);
    setAnswers({});
    const st = Date.now();
    setStartTime(st);
    setScreen('quiz');
    startTimer(st);
  };

  const selectOption = (qId: string, idx: number) => {
    setAnswers(prev => ({ ...prev, [qId]: idx }));
  };

  const setTextAnswer = (qId: string, val: string) => {
    setAnswers(prev => ({ ...prev, [qId]: val }));
  };

  const prevQ = () => { if (curQ > 0) setCurQ(curQ - 1); };
  const nextQ = () => {
    if (curQ >= quizQs.length - 1) { finishQuiz(); return; }
    setCurQ(curQ + 1);
  };

  const fmtTime = (s: number) => {
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), ss = s % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
  };

  const exportJSON = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `assessment_${result.name.replace(/\s+/g, '_')}_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const exportCSV = () => {
    if (!result) return;
    let csv = 'Тип;Вопрос;Ответ;Верно;Ожидаемый\n';
    result.questions.forEach(q => {
      const t = q.type === 'choice' ? 'Тестовый' : q.type === 'open' ? 'Практический' : 'Кейс';
      csv += `"${t}";"${q.text.replace(/"/g, '""')}";"${q.answer.replace(/"/g, '""')}";"${q.correct === null ? '—' : q.correct ? 'Да' : 'Нет'}";"${(q.correctAnswer || q.expected || '').replace(/"/g, '""')}"\n`;
    });
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `assessment_${result.name.replace(/\s+/g, '_')}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  // ===== RENDER SCREENS =====

  if (screen === 'landing') {
    return (
      <div className={styles.wrap}>
        <div className={styles.header}>
          <h1 className={styles.title}>Agile<span className={styles.titleAccent}>.Assessment</span></h1>
          <p className={styles.subtitle}>Платформа оценки компетенций сотрудников</p>
        </div>
        <div className={styles.divisionsGrid}>
          {DIVISIONS.map(d => {
            const n = d.hasTopics
              ? IT_TOPICS.reduce((s, tp) => s + (questionsDB[tp.id] || []).length, 0)
              : (questionsDB[d.id] || []).length;
            const sub = d.hasTopics ? IT_TOPICS.length + ' направлений, ' : '';
            return (
              <div key={d.id} className={styles.divCard} onClick={() => selectDiv(d.id)}>
                <div className={styles.divIcon} style={{ background: d.color + '14', color: d.color }}>
                  <svg viewBox="0 0 24 24"><path d={d.icon} /></svg>
                </div>
                <div className={styles.divInfo}>
                  <h3>{d.name}</h3>
                  <p>{sub}{n} вопросов</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (screen === 'topics') {
    return (
      <div className={styles.topicsWrap}>
        <button className="btn btn-ghost btn-sm" onClick={() => setScreen('landing')} style={{ marginBottom: 16 }}>← Назад</button>
        <h2>Информационные технологии</h2>
        <p className={styles.topicsSub}>Выберите направление для тестирования</p>
        {IT_TOPICS.map(tp => {
          const n = (questionsDB[tp.id] || []).length;
          return (
            <div key={tp.id} className={styles.topicCard} onClick={() => selectTopic(tp.id)}>
              <div className={styles.topicIcon}>
                <svg viewBox="0 0 24 24"><path d={tp.icon} /></svg>
              </div>
              <div>
                <h4>{tp.name}</h4>
                <p>{tp.desc} — {n} вопросов</p>
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  if (screen === 'name') {
    const divName = selectedTopic ? 'IT: ' + selectedTopic.name : selectedDiv!.name;
    const key = selectedTopic ? selectedTopic.id : selectedDiv!.id;
    const n = (questionsDB[key] || []).length;
    return (
      <div className={styles.nameSection}>
        <button className="btn btn-ghost btn-sm" onClick={() => setScreen(selectedTopic ? 'topics' : 'landing')} style={{ marginBottom: 16 }}>← Назад</button>
        <h2>{divName}</h2>
        <p>Тест содержит {n} вопросов: 6 тестовых, 6 практических и 1 кейс.<br />Максимальное время — 3 часа.</p>
        <input
          type="text" value={userName}
          onChange={e => setUserName(e.target.value)}
          placeholder="Имя и фамилия" maxLength={60} autoFocus
          onKeyDown={e => { if (e.key === 'Enter' && userName.trim().length >= 2) startQuiz(); }}
        />
        <button className="btn btn-primary" onClick={startQuiz} disabled={userName.trim().length < 2}>
          Начать тестирование
        </button>
      </div>
    );
  }

  if (screen === 'quiz' && quizQs.length > 0) {
    const q = quizQs[curQ];
    const total = quizQs.length;
    const typeLabel = q.type === 'choice' ? 'Тестовый' : q.type === 'open' ? 'Практический' : 'Кейс';
    const typeBadge = q.type === 'choice' ? styles.badgeAccent : q.type === 'open' ? styles.badgeBlue : styles.badgeYellow;
    const LABELS = 'АБВГ';
    return (
      <div className={styles.quizWrap}>
        <div className={styles.quizTop}>
          <div className={styles.quizBadges}>
            <span className={`${styles.badge} ${styles.badgeAccent}`}>{curQ + 1}/{total}</span>
            <span className={`${styles.badge} ${typeBadge}`}>{typeLabel}</span>
          </div>
          <div className={`${styles.quizTimer} ${timerClass === 'warning' ? styles.timerWarning : timerClass === 'danger' ? styles.timerDanger : ''}`}>
              <Timer size={14} style={{ marginRight: 6 }} />
              {timerText}
          </div>
        </div>
        <div className={styles.progressBar}><div className={styles.progressFill} style={{ width: ((curQ + 1) / total * 100) + '%' }} /></div>
        <div className={styles.qCard}>
          <div className={styles.qLabel}>
            <span className={`${styles.badge} ${typeBadge}`} style={{ fontSize: 11 }}>{typeLabel}</span>
            <span>Вопрос {curQ + 1}</span>
          </div>
          <div className={styles.qText}>{q.text}</div>
          {q.type === 'choice' && (
            <div className={styles.opts}>
              {(q.options || []).map((o, i) => (
                <button key={i} className={`${styles.opt} ${answers[q.id] === i ? styles.optSel : ''}`} onClick={() => selectOption(q.id, i)}>
                  <span className={styles.optLabel}>{LABELS[i]}</span>
                  <span>{o}</span>
                </button>
              ))}
            </div>
          )}
          {q.type === 'open' && (
            <textarea className={styles.openArea} placeholder="Введите ваш ответ..."
              value={String(answers[q.id] || '')} onChange={e => setTextAnswer(q.id, e.target.value)} />
          )}
          {q.type === 'case' && (
            <textarea className={styles.caseArea} placeholder="Опишите ваше решение подробно..."
              value={String(answers[q.id] || '')} onChange={e => setTextAnswer(q.id, e.target.value)} />
          )}
        </div>
        <div className={styles.quizNav}>
          <button className="btn btn-secondary btn-sm" onClick={prevQ} disabled={curQ === 0}>
            <ArrowLeft size={14} style={{ marginRight: 6 }} /> Назад
          </button>
          <button className="btn btn-primary btn-sm" onClick={nextQ}>
            {curQ === total - 1 ? 'Завершить' : <><span>Далее</span> <ArrowRight size={14} /></>}
          </button>
        </div>
      </div>
    );
  }

  if (screen === 'results' && result) {
    const choiceQs = result.questions.filter(q => q.type === 'choice');
    const openQs = result.questions.filter(q => q.type === 'open');
    const caseQs = result.questions.filter(q => q.type === 'case');
    return (
      <div className={styles.resultsWrap}>
        <div className={styles.resultsHeader}>
          <div className={styles.resultsScore}>{result.pct}%</div>
          <h2 style={{ marginTop: 10 }}>{result.name}</h2>
          <p style={{ color: 'var(--color-text-muted)', marginTop: 2 }}>{result.division}</p>
        </div>
        <div className={styles.statsGrid}>
          <div className={styles.statCard}>
            <div className={styles.statValue} style={{ color: 'var(--color-success)' }}>{result.choiceCorrect}/{result.choiceTotal}</div>
            <div className={styles.statLabel}>Тестовых верно</div>
          </div>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{result.totalQuestions}</div>
            <div className={styles.statLabel}>Всего вопросов</div>
          </div>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{fmtTime(result.duration)}</div>
            <div className={styles.statLabel}>Время</div>
          </div>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{result.answered}</div>
            <div className={styles.statLabel}>Отвечено</div>
          </div>
        </div>

        <div className={styles.rSection}><h3>Тестовые вопросы</h3>
          {choiceQs.map((q, i) => {
            const cls = q.answer === '—' ? styles.rPending : q.correct ? styles.rCorrect : styles.rWrong;
            return (
              <div key={i} className={styles.rItem}>
                <div className={styles.rQ}>{i + 1}. {q.text}</div>
                <div className={`${styles.rAns} ${cls}`}>{q.answer !== '—' ? 'Ваш ответ: ' + q.answer : 'Нет ответа'}</div>
                {!q.correct && q.correctAnswer && <div className={styles.rExpected}>Правильно: {q.correctAnswer}</div>}
              </div>
            );
          })}
        </div>

        {openQs.length > 0 && (
          <div className={styles.rSection}><h3>Практические задания</h3>
            {openQs.map((q, i) => (
              <div key={i} className={styles.rItem}>
                <div className={styles.rQ}>{i + 1}. {q.text}</div>
                <div className={`${styles.rAns} ${styles.rPending}`}>{q.answer.trim() || 'Нет ответа'}</div>
                {q.expected && <div className={styles.rExpected}>Ожидаемый: {q.expected}</div>}
              </div>
            ))}
          </div>
        )}

        {caseQs.length > 0 && (
          <div className={styles.rSection}><h3>Кейсы</h3>
            {caseQs.map((q, i) => (
              <div key={i} className={styles.rItem}>
                <div className={styles.rQ}>Кейс: {q.text.substring(0, 150)}...</div>
                <div className={`${styles.rAns} ${styles.rPending}`}>{q.answer.trim() || 'Нет ответа'}</div>
                {q.expected && <div className={styles.rExpected}>Ожидаемый: {q.expected}</div>}
              </div>
            ))}
          </div>
        )}

        <div className={styles.exportBar}>
          <button className="btn btn-secondary btn-sm" onClick={exportJSON}>
            <FileJson size={16} style={{ marginRight: 6 }} /> JSON
          </button>
          <button className="btn btn-secondary btn-sm" onClick={exportCSV}>
            <FileSpreadsheet size={16} style={{ marginRight: 6 }} /> CSV
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => { setScreen('landing'); setResult(null); }}>
            <RotateCcw size={16} style={{ marginRight: 6 }} /> Заново
          </button>
        </div>
      </div>
    );
  }

  return null;
}
