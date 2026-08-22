import type { User, UserRole } from '../types';

export type SectionKey =
  | 'profile'
  | 'company'
  | 'projects'
  | 'kpi'
  | 'applications'
  | 'leaderboard'
  | 'events'
  | 'call'
  | 'finance'
  | 'admin';

export const SECTION_DEFINITIONS: Array<{ key: SectionKey; label: string; description: string }> = [
  { key: 'profile', label: 'Профиль', description: 'Личные данные и безопасность' },
  { key: 'company', label: 'Панель компании', description: 'Сводка команды и заказов' },
  { key: 'projects', label: 'Задачи и проекты', description: 'Свои и доступные рабочие доски' },
  { key: 'kpi', label: 'KPI', description: 'Личные или управленческие показатели' },
  { key: 'applications', label: 'Заявки', description: 'Входящие обращения с сайта' },
  { key: 'leaderboard', label: 'Лидерборд KPI', description: 'Рейтинг сотрудников по KPI' },
  { key: 'events', label: 'События', description: 'Корпоративные события' },
  { key: 'call', label: 'Конференции', description: 'Расписание и подключение к звонкам' },
  { key: 'finance', label: 'Финансы владельца', description: 'Доходы и расходы; только владелец' },
  { key: 'admin', label: 'Управление доступами', description: 'Сотрудники, роли и права' },
];

export const ROLE_ACCESS_PRESETS: Record<UserRole, SectionKey[]> = {
  owner: SECTION_DEFINITIONS.map(section => section.key),
  deputy_owner: ['profile', 'company', 'projects', 'kpi', 'applications', 'leaderboard', 'events', 'call', 'admin'],
  admin: ['profile', 'company', 'projects', 'kpi', 'applications', 'leaderboard', 'events', 'call', 'admin'],
  consultant: ['profile', 'applications', 'call'],
  user: ['profile', 'projects', 'kpi', 'events', 'call'],
  intern: ['profile', 'projects', 'kpi', 'call'],
};

export function effectiveSectionAccess(user: User): SectionKey[] {
  if (user.role === 'owner') return ROLE_ACCESS_PRESETS.owner;
  if (Array.isArray(user.section_access)) {
    const allowed = new Set(SECTION_DEFINITIONS.map(section => section.key));
    return user.section_access.filter((key): key is SectionKey => allowed.has(key as SectionKey));
  }
  return ROLE_ACCESS_PRESETS[user.role];
}

export function canAccessSection(user: User | null | undefined, section: SectionKey): boolean {
  if (!user) return false;
  if (section === 'finance') return user.role === 'owner';
  if (section === 'profile') return true;
  return effectiveSectionAccess(user).includes(section);
}
