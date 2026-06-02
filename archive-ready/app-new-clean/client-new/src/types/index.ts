// Типы данных приложения

export interface User {
  id: string;
  name: string;
  last_name?: string;
  patronymic?: string;
  no_patronymic?: boolean;
  email: string;
  city?: string;
  skills?: string[];
  about?: string;
  listening_to?: string;
  avatar_url?: string;
  role: 'admin' | 'user' | 'intern';
  training_role?: 'intern' | 'training_editor' | null;
  status: 'pending' | 'active' | 'rejected' | 'fired' | 'blocked';
  is_online: boolean;
  last_seen?: string;
  theme: string;
  language: string;
  section_access?: string[];
  sphere_roles: SphereRole[];
  created_at: string;
  // Extended admin fields
  email_confirmed?: boolean;
  telegram_username?: string;
  fire_message?: string;
  notify_tasks?: boolean;
  notify_messages?: boolean;
  notify_events?: boolean;
  show_iterations?: boolean;
  totp_enabled?: boolean;
}

export interface SphereRole {
  id: string;
  sphere: string;
  role_title: string;
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  creator_id: string;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  members?: ProjectMember[];
}

export interface ProjectMember {
  id: string;
  user_id: string;
  user_name?: string;
  is_admin: boolean;
  joined_at: string;
}

export interface Iteration {
  id: string;
  project_id: string;
  name: string;
  start_date: string;
  end_date: string;
  status: 'active' | 'completed' | 'archived';
  template_name?: string;
  created_at: string;
}

export interface BoardColumn {
  id: string;
  iteration_id: string;
  title: string;
  sort_order: number;
  color?: string | null;
  created_at: string;
}

export interface Task {
  id: string;
  iteration_id: string;
  title: string;
  description?: string;
  status: string;
  priority: string;
  assignee_id?: string;
  assignee_name?: string;
  creator_id: string;
  creator_name?: string;
  start_date?: string;
  deadline?: string;
  parent_id?: string | null;
  board_column_id?: string | null;
  is_completed?: boolean;
  created_at: string;
  updated_at: string;
  comments?: TaskComment[];
  history?: TaskHistory[];
  attachments?: TaskAttachment[];
}

export interface TaskComment {
  id: string;
  task_id: string;
  user_id: string;
  user_name?: string;
  content: string;
  created_at: string;
}

export interface TaskHistory {
  id: string;
  task_id: string;
  user_id: string;
  user_name?: string;
  field: string;
  old_value?: string;
  new_value?: string;
  created_at: string;
}

export interface TaskAttachment {
  id: string;
  filename: string;
  file_url: string;
  file_size?: number;
  mime_type?: string;
}

export interface BacklogItem {
  id: string;
  project_id: string;
  title: string;
  description?: string;
  creator_id: string;
  creator_name?: string;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  iteration_id: string;
  user_id: string;
  user_name?: string;
  user_avatar?: string;
  content: string;
  file_url?: string;
  file_name?: string;
  file_size?: number;
  file_mime?: string;
  is_edited: boolean;
  is_deleted: boolean;
  poll?: ChatPoll;
  reply_to_id?: string;
  reply_to_content?: string;
  reply_to_user_name?: string;
  created_at: string;
  updated_at: string;
}

export interface ChatPoll {
  id: string;
  question: string;
  is_multiple: boolean;
  is_closed: boolean;
  options: ChatPollOption[];
}

export interface ChatPollOption {
  id: string;
  text: string;
  votes_count: number;
  voters: { user_id: string }[];
}

export interface EventParticipant {
  user_id: string;
  user_name?: string;
  status: 'attending' | 'not_attending';
}

export interface Event {
  id: string;
  title: string;
  description?: string;
  location?: string;
  photo_url?: string;
  start_date: string;
  end_date?: string;
  event_date?: string;
  creator_id: string;
  is_active: boolean;
  participant_count: number;
  user_status?: string;
  participants?: EventParticipant[];
  created_at: string;
}

export interface Notification {
  id: string;
  title: string;
  message: string;
  type: string;
  link?: string;
  is_read: boolean;
  created_at: string;
}

export interface Retrospective {
  id: string;
  iteration_id: string;
  answers: RetrospectiveAnswer[];
  created_at: string;
}

export interface RetrospectiveAnswer {
  id: string;
  user_id: string;
  user_name?: string;
  went_well?: string;
  to_improve?: string;
  to_try?: string;
  created_at: string;
}

export interface Document {
  id: string;
  iteration_id: string;
  filename: string;
  description?: string;
  current_version: number;
  uploader_id: string;
  uploader_name?: string;
  file_url?: string;
  file_size?: number;
  mime_type?: string;
  created_at: string;
}

// Сферы деятельности
export const SPHERES = [
  'Управление и Стратегия',
  'Аналитика и Данные',
  'Финансовый консалтинг и учет',
  'Инвестиции и оценка',
  'ИТ и разработка',
  'Маркетинг',
  'Продажи и развитие клиентов',
  'Креатив дизайн',
  'Операции и Логистика',
  'Кадры и организации (HR)',
  'Юридическое Сопровождение',
] as const;

export const TASK_STATUSES = [
  'Готово к запуску',
  'Создаёт ценность',
  'Доставлено клиенту',
] as const;

export const TASK_PRIORITIES = ['Низкий', 'Средний', 'Высокий'] as const;
