import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileJson, ClipboardList, ArrowLeft, ArrowRight, CheckCircle2 } from 'lucide-react';
import { useAppSelector } from '../../store/hooks';
import { SPHERES, Sphere, Direction, Topic } from './competencyData';
import styles from './Competency.module.css';

type FilledBy = 'hr' | 'lead' | 'self';

interface GapTopic { sphere: string; dir: string; topic: string; val: number; level: string; order: number; }

export default function CompetencyPage() {
  const { user } = useAppSelector(s => s.auth);
  const navigate = useNavigate();

  const [step, setStep] = useState(1);
  const [empName, setEmpName] = useState(user?.name || '');
  const [empPosition, setEmpPosition] = useState('');
  const [empDept, setEmpDept] = useState('');
  const [empFilledBy, setEmpFilledBy] = useState<FilledBy>('hr');
  const [selectedSpheres, setSelectedSpheres] = useState<Set<string>>(new Set());
  const [selectedDirs, setSelectedDirs] = useState<Set<string>>(new Set());
  const [topicScores, setTopicScores] = useState<Record<string, number>>({});
  const [openDirs, setOpenDirs] = useState<Set<string>>(new Set());

  const toggleSphere = (id: string) => {
    setSelectedSpheres(prev => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  };

  const toggleDir = (key: string) => {
    setSelectedDirs(prev => {
      const n = new Set(prev);
      if (n.has(key)) n.delete(key); else n.add(key);
      return n;
    });
  };

  const toggleOpenDir = (key: string) => {
    setOpenDirs(prev => {
      const n = new Set(prev);
      if (n.has(key)) n.delete(key); else n.add(key);
      return n;
    });
  };

  const setScore = (key: string, val: number) => {
    setTopicScores(prev => ({ ...prev, [key]: val }));
  };

  const calcDirAvg = (sId: string, dId: string, topics: Topic[]) => {
    let sum = 0;
    topics.forEach(t => { sum += (topicScores[`${sId}/${dId}/${t.id}`] || 0); });
    return Math.round(sum / topics.length);
  };

  const goStep = (n: number) => {
    if (n === 2 && !empName.trim()) return;
    if (n === 3 && selectedSpheres.size === 0) return;
    if (n === 4 && selectedDirs.size === 0) return;
    if (n === 4) {
      // Auto-open all selected dirs for assessment
      const ao = new Set<string>();
      selectedDirs.forEach(k => ao.add(k));
      setOpenDirs(ao);
    }
    setStep(n);
  };

  // Summary calculations
  const summary = useMemo(() => {
    let totalTopics = 0, knownFull = 0, needStudy = 0, totalPct = 0;
    const gaps: GapTopic[] = [];
    const mastered: GapTopic[] = [];

    SPHERES.filter(s => selectedSpheres.has(s.id)).forEach(s => {
      s.directions.forEach(d => {
        if (!selectedDirs.has(`${s.id}/${d.id}`)) return;
        d.topics.forEach(t => {
          const val = topicScores[`${s.id}/${d.id}/${t.id}`] || 0;
          totalTopics++; totalPct += val;
          if (val === 100) { knownFull++; mastered.push({ sphere: s.name, dir: d.name, topic: t.name, val, level: t.level, order: t.order }); }
          else { needStudy++; gaps.push({ sphere: s.name, dir: d.name, topic: t.name, val, level: t.level, order: t.order }); }
        });
      });
    });

    return { totalTopics, knownFull, needStudy, avgPct: totalTopics ? Math.round(totalPct / totalTopics) : 0, gaps, mastered };
  }, [step, topicScores, selectedSpheres, selectedDirs]);

  const exportProfile = () => {
    const directions: { sphereId: string; sphere: string; dirId: string; direction: string; avgScore: number; topics: { id: string; name: string; level: string; order: number; score: number }[] }[] = [];
    SPHERES.filter(s => selectedSpheres.has(s.id)).forEach(s => {
      s.directions.forEach(d => {
        if (!selectedDirs.has(`${s.id}/${d.id}`)) return;
        const topics = d.topics.map(t => ({ id: t.id, name: t.name, level: t.level, order: t.order, score: topicScores[`${s.id}/${d.id}/${t.id}`] || 0 }));
        const avg = Math.round(topics.reduce((a, t) => a + t.score, 0) / topics.length);
        directions.push({ sphereId: s.id, sphere: s.name, dirId: d.id, direction: d.name, avgScore: avg, topics });
      });
    });
    const profile = {
      id: Date.now().toString(36) + Math.random().toString(36).substring(2, 7),
      date: new Date().toISOString(),
      employee: { name: empName, position: empPosition, department: empDept, filledBy: empFilledBy },
      directions,
    };
    const blob = new Blob([JSON.stringify(profile, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `competency_${empName.replace(/\s+/g, '_')}_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const generatePlan = () => {
    if (!summary.gaps.length) return;

    // Save competency profile to localStorage
    const profileId = Date.now().toString(36) + Math.random().toString(36).substring(2, 7);
    const profileDirs: { sphereId: string; sphere: string; dirId: string; direction: string; avgScore: number; topics: { id: string; name: string; level: string; order: number; score: number }[] }[] = [];
    SPHERES.filter(s => selectedSpheres.has(s.id)).forEach(s => {
      s.directions.forEach(d => {
        if (!selectedDirs.has(`${s.id}/${d.id}`)) return;
        const topics = d.topics.map(t => ({ id: t.id, name: t.name, level: t.level, order: t.order, score: topicScores[`${s.id}/${d.id}/${t.id}`] || 0 }));
        const avg = Math.round(topics.reduce((a, t) => a + t.score, 0) / topics.length);
        profileDirs.push({ sphereId: s.id, sphere: s.name, dirId: d.id, direction: d.name, avgScore: avg, topics });
      });
    });
    const profile = {
      id: profileId,
      date: new Date().toISOString(),
      employee: { name: empName, position: empPosition, department: empDept, filledBy: empFilledBy },
      directions: profileDirs,
    };
    try {
      const profiles = JSON.parse(localStorage.getItem('agile_competency_profiles') || '[]');
      profiles.push(profile);
      localStorage.setItem('agile_competency_profiles', JSON.stringify(profiles));
    } catch { /* ignore */ }

    // Build learning plan (matching workspace.html data structure)
    const planId = Date.now().toString(36) + Math.random().toString(36).substring(2, 7);
    const planDirections: { sphereId: string; sphere: string; dirId: string; direction: string; modules: { order: number; topicId: string; name: string; level: string; currentScore: number; priority: string; status: string }[] }[] = [];
    profileDirs.forEach(pd => {
      const gaps = pd.topics.filter(t => t.score < 100);
      if (!gaps.length) return;
      const levelOrder = { basic: 0, medium: 1, advanced: 2 } as Record<string, number>;
      gaps.sort((a, b) => (levelOrder[a.level] || 0) - (levelOrder[b.level] || 0) || a.order - b.order);
      const modules = gaps.map((t, i) => ({
        order: i + 1,
        topicId: t.id,
        name: t.name,
        level: t.level,
        currentScore: t.score,
        priority: t.score === 0 ? 'high' : t.score < 50 ? 'medium' : 'low',
        status: 'not_started',
      }));
      planDirections.push({ sphereId: pd.sphereId, sphere: pd.sphere, dirId: pd.dirId, direction: pd.direction, modules });
    });
    const plan = {
      id: planId,
      profileId,
      date: new Date().toISOString(),
      employee: { name: empName, position: empPosition, department: empDept, filledBy: empFilledBy },
      directions: planDirections,
    };
    try {
      const plans = JSON.parse(localStorage.getItem('agile_learning_plans') || '[]');
      plans.push(plan);
      localStorage.setItem('agile_learning_plans', JSON.stringify(plans));
    } catch { /* ignore */ }

    window.dispatchEvent(new Event('plans-updated'));
    navigate('/training');
  };

  const levelLabel = (l: string) => l === 'basic' ? 'Базовый' : l === 'medium' ? 'Средний' : 'Продвинутый';

  const stepLabels = ['Сотрудник', 'Сфера', 'Направления', 'Оценка', 'Итог'];

  return (
    <div className={styles.wrap}>
      <h1 className={styles.pageTitle}>Конструктор <span className={styles.titleAccent}>компетенций</span></h1>
      <p className={styles.pageSub}>Оценка знаний сотрудника для формирования персонального плана обучения</p>

      {/* Stepper */}
      <div className={styles.stepper}>
        {stepLabels.map((label, i) => {
          const n = i + 1;
          const cls = n === step ? styles.stepActive : n < step ? styles.stepDone : '';
          return (
            <div key={n} className={styles.stepRow}>
              {i > 0 && <div className={`${styles.stepLine} ${n <= step ? styles.stepLineDone : ''}`} />}
              <div className={`${styles.step} ${cls}`}>
                <div className={styles.stepNum}>{n}</div>
                <div className={styles.stepLabel}>{label}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Step 1: Employee Info */}
      {step === 1 && (
        <div className={styles.card}>
          <h2 className={styles.cardTitle}>Информация о сотруднике</h2>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Имя и фамилия *</label>
              <input value={empName} onChange={e => setEmpName(e.target.value)} placeholder="Иван Иванов" maxLength={80} />
            </div>
            <div className={styles.formGroup}>
              <label>Должность</label>
              <input value={empPosition} onChange={e => setEmpPosition(e.target.value)} placeholder="Frontend-разработчик" maxLength={80} />
            </div>
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Отдел / команда</label>
              <input value={empDept} onChange={e => setEmpDept(e.target.value)} placeholder="Отдел разработки" maxLength={80} />
            </div>
            <div className={styles.formGroup}>
              <label>Кто заполняет</label>
              <select value={empFilledBy} onChange={e => setEmpFilledBy(e.target.value as FilledBy)}>
                <option value="hr">HR / Рекрутер</option>
                <option value="lead">Тимлид / Руководитель</option>
                <option value="self">Сам сотрудник</option>
              </select>
            </div>
          </div>
            <div className={styles.actionsBar}>
              <div />
              <button className="btn btn-primary" onClick={() => goStep(2)} disabled={!empName.trim()}>
                <span style={{ marginRight: 6 }}>Далее — Выбор сферы</span>
                <ArrowRight size={16} />
              </button>
            </div>
        </div>
      )}

      {/* Step 2: Spheres */}
      {step === 2 && (
        <div>
          <h2 className={styles.sectionTitle}>Выберите профессиональную сферу</h2>
          <p className={styles.sectionSub}>Отметьте одну или несколько сфер, в которых работает сотрудник</p>
          {SPHERES.map(s => (
            <div key={s.id} className={`${styles.sphereCard} ${selectedSpheres.has(s.id) ? styles.sphereSelected : ''}`} onClick={() => toggleSphere(s.id)}>
              <div className={styles.sphereIcon} style={{ background: s.color + '14', color: s.color }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={s.icon} /></svg>
              </div>
              <div className={styles.sphereInfo}>
                <h3>{s.name}</h3>
                <p>{s.desc} — {s.directions.length} направлений</p>
              </div>
              <div className={`${styles.sphereCheck} ${selectedSpheres.has(s.id) ? styles.sphereCheckActive : ''}`} />
            </div>
          ))}
            <div className={styles.actionsBar}>
              <button className="btn btn-secondary" onClick={() => goStep(1)}>
                <ArrowLeft size={16} style={{ marginRight: 6 }} /> Назад
              </button>
              <button className="btn btn-primary" onClick={() => goStep(3)} disabled={selectedSpheres.size === 0}>
                <span style={{ marginRight: 6 }}>Далее — Направления</span>
                <ArrowRight size={16} />
              </button>
            </div>
        </div>
      )}

      {/* Step 3: Directions */}
      {step === 3 && (
        <div>
          <h2 className={styles.sectionTitle}>Выберите направления</h2>
          <p className={styles.sectionSub}>Отметьте направления, которые релевантны для сотрудника</p>
          {SPHERES.filter(s => selectedSpheres.has(s.id)).map(s => (
            <div key={s.id}>
              <h3 className={styles.sphereGroupTitle} style={{ color: s.color }}>{s.name}</h3>
              {s.directions.map(d => {
                const key = `${s.id}/${d.id}`;
                return (
                  <div key={key} className={`${styles.sphereCard} ${selectedDirs.has(key) ? styles.sphereSelected : ''}`} onClick={() => toggleDir(key)}>
                    <div className={`${styles.dirCheck} ${selectedDirs.has(key) ? styles.dirCheckActive : ''}`} />
                    <div className={styles.sphereInfo}>
                      <h3>{d.name}</h3>
                      <p>{d.topics.length} тем</p>
                    </div>
                    <div className={`${styles.sphereCheck} ${selectedDirs.has(key) ? styles.sphereCheckActive : ''}`} />
                  </div>
                );
              })}
            </div>
          ))}
          <div className={styles.actionsBar}>
            <button className="btn btn-secondary" onClick={() => goStep(2)}>
              <ArrowLeft size={16} style={{ marginRight: 6 }} /> Назад
            </button>
            <button className="btn btn-primary" onClick={() => goStep(4)} disabled={selectedDirs.size === 0}>
              <span style={{ marginRight: 6 }}>Далее — Оценка</span>
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Assessment */}
      {step === 4 && (
        <div>
          <h2 className={styles.sectionTitle}>Оценка знаний по темам</h2>
          <p className={styles.sectionSub}>Установите процент владения для каждой темы — от 0% до 100%</p>
          {SPHERES.filter(s => selectedSpheres.has(s.id)).map(s =>
            s.directions.filter(d => selectedDirs.has(`${s.id}/${d.id}`)).map(d => {
              const dirKey = `${s.id}/${d.id}`;
              const avg = calcDirAvg(s.id, d.id, d.topics);
              const isOpen = openDirs.has(dirKey);
              return (
                <div key={dirKey} className={`${styles.dirCard} ${isOpen ? styles.dirOpen : ''}`}>
                  <div className={styles.dirHeader} onClick={() => toggleOpenDir(dirKey)}>
                    <div className={styles.dirDot} style={{ background: s.color }} />
                    <div className={styles.dirTitle}>{d.name}</div>
                    <div className={styles.dirPct}>{avg}%</div>
                    <svg className={`${styles.dirChevron} ${isOpen ? styles.dirChevronOpen : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9" /></svg>
                  </div>
                  {isOpen && (
                    <div className={styles.dirBody}>
                      {[...d.topics].sort((a, b) => a.order - b.order).map(t => {
                        const tkey = `${s.id}/${d.id}/${t.id}`;
                        const val = topicScores[tkey] || 0;
                        const valCls = val === 100 ? styles.sliderFull : val > 0 ? styles.sliderPartial : styles.sliderZero;
                        return (
                          <div key={tkey} className={styles.topicRow}>
                            <div className={styles.topicName}>{t.name}</div>
                            <div className={`${styles.topicLevel} ${styles['level_' + t.level]}`}>{levelLabel(t.level)}</div>
                            <div className={styles.sliderWrap}>
                              <input type="range" min={0} max={100} step={5} value={val} onChange={e => setScore(tkey, +e.target.value)} />
                              <div className={`${styles.sliderVal} ${valCls}`}>{val}%</div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })
          )}
          <div className={styles.actionsBar}>
            <button className="btn btn-secondary" onClick={() => goStep(3)}>
              <ArrowLeft size={16} style={{ marginRight: 6 }} /> Назад
            </button>
            <button className="btn btn-primary" onClick={() => goStep(5)}>
              <span style={{ marginRight: 6 }}>Просмотр итогов</span>
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* Step 5: Summary */}
      {step === 5 && (
        <div>
          <h2 className={styles.sectionTitle}>Итоговый профиль компетенций</h2>
          <p className={styles.sectionSub}>Проверьте результаты перед формированием плана обучения</p>

          <div className={styles.statsGrid}>
            <div className={styles.statCard}><div className={styles.statValue} style={{ color: '#2563eb' }}>{summary.totalTopics}</div><div className={styles.statLabel}>Всего тем</div></div>
            <div className={styles.statCard}><div className={styles.statValue} style={{ color: '#16a34a' }}>{summary.knownFull}</div><div className={styles.statLabel}>Знает на 100%</div></div>
            <div className={styles.statCard}><div className={styles.statValue} style={{ color: '#ca8a04' }}>{summary.needStudy}</div><div className={styles.statLabel}>Требует изучения</div></div>
            <div className={styles.statCard}><div className={styles.statValue} style={{ color: 'var(--color-accent)' }}>{summary.avgPct}%</div><div className={styles.statLabel}>Средний балл</div></div>
          </div>

          <div className={styles.empCard}>
            <strong>{empName}</strong>
            {empPosition && <span className={styles.badgeBlue}>{empPosition}</span>}
            {empDept && <span className={styles.badgeGray}>{empDept}</span>}
          </div>

          {/* Gaps */}
          {summary.gaps.length > 0 && (
            <div className={styles.summarySection}>
              <h3><span style={{ color: 'var(--color-accent)' }}>●</span> Требует изучения ({summary.gaps.length} тем)</h3>
              <div className={styles.summaryCard}>
                {(() => {
                  const grouped: Record<string, GapTopic[]> = {};
                  summary.gaps.forEach(g => {
                    const k = `${g.sphere} -> ${g.dir}`;
                    if (!grouped[k]) grouped[k] = [];
                    grouped[k].push(g);
                  });
                  return Object.entries(grouped).map(([dk, topics]) => (
                    <div key={dk}>
                      <div className={styles.summaryGroupHeader}>{dk}</div>
                      {topics.sort((a, b) => a.order - b.order).map((g, i) => {
                        const barCls = g.val < 50 ? styles.barRed : styles.barYellow;
                        return (
                          <div key={i} className={styles.summaryItem}>
                            <div className={styles.summaryTopicName}>{g.topic}</div>
                            <div className={`${styles.topicLevel} ${styles['level_' + g.level]}`}>{levelLabel(g.level)}</div>
                            <div className={styles.summaryBarWrap}><div className={`${styles.summaryBar} ${barCls}`} style={{ width: g.val + '%' }} /></div>
                            <div className={styles.summaryPct} style={{ color: g.val === 0 ? 'var(--color-text-muted)' : g.val < 50 ? '#ef4444' : '#ca8a04' }}>{g.val}%</div>
                          </div>
                        );
                      })}
                    </div>
                  ));
                })()}
              </div>
            </div>
          )}

          {/* Mastered */}
          {summary.mastered.length > 0 && (
            <div className={styles.summarySection}>
              <h3><span style={{ color: '#16a34a' }}>●</span> Знает полностью ({summary.mastered.length} тем)</h3>
              <div className={styles.summaryCard}>
                {(() => {
                  const grouped: Record<string, GapTopic[]> = {};
                  summary.mastered.forEach(m => {
                    const k = `${m.sphere} -> ${m.dir}`;
                    if (!grouped[k]) grouped[k] = [];
                    grouped[k].push(m);
                  });
                  return Object.entries(grouped).map(([dk, topics]) => (
                    <div key={dk}>
                      <div className={styles.summaryGroupHeader}>{dk}</div>
                      {topics.map((m, i) => (
                        <div key={i} className={styles.summaryItem}>
                          <div className={styles.summaryTopicName}>{m.topic}</div>
                          <div className={styles.summaryPct} style={{ color: '#16a34a' }}>100%</div>
                        </div>
                      ))}
                    </div>
                  ));
                })()}
              </div>
            </div>
          )}

          {!summary.gaps.length && summary.mastered.length > 0 && (
            <div className={styles.allGood}>
              <CheckCircle2 size={18} style={{ marginRight: 6 }} /> Сотрудник владеет всеми выбранными темами на 100%. Обучение не требуется.
            </div>
          )}

          <div className={styles.actionsBar}>
            <button className="btn btn-secondary" onClick={() => goStep(4)}>
              <ArrowLeft size={16} style={{ marginRight: 6 }} /> Назад к оценке
            </button>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-secondary" onClick={exportProfile}>
                <FileJson size={16} style={{ marginRight: 6 }} /> Экспорт JSON
              </button>
              <button className="btn btn-primary" onClick={generatePlan} disabled={summary.gaps.length === 0}>
                <ClipboardList size={16} style={{ marginRight: 6 }} /> Сформировать план обучения
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
