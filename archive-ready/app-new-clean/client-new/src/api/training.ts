import api from './client';

/* ============ Types ============ */

export interface Course {
  id: string;
  title: string;
  description: string | null;
  order: number;
  is_published: boolean;
  topic_count: number;
  created_at: string;
}

export interface HashtagType {
  id: string;
  name: string;
  color: string;
}

export interface Topic {
  id: string;
  course_id: string;
  title: string;
  description: string | null;
  order: number;
  section_title: string | null;
  difficulty: string | null;
  has_task: boolean;
  is_unlocked: boolean;
  status: 'locked' | 'in_progress' | 'completed';
  progress: 'not_started' | 'in_progress' | 'completed';
  hashtags: HashtagType[];
  created_at: string;
}

export interface ContentBlock {
  id: string;
  title: string | null;
  body: string | null;
  content_type: string;
  order: number;
}

export interface TaskBrief {
  id: string;
  title: string;
}

export interface TopicDetail extends Topic {
  content_blocks: ContentBlock[];
  task: TaskBrief | null;
}

export interface Task {
  id: string;
  topic_id: string;
  title: string;
  description: string;
  created_at: string;
}

export interface Submission {
  id: string;
  task_id: string;
  user_id: string;
  user_name: string;
  task_title: string;
  content: string | null;
  file_url: string | null;
  status: 'pending' | 'approved' | 'rejected';
  review_comment: string | null;
  reviewer_id: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface Intern {
  id: string;
  name: string;
  email: string;
  training_role: string | null;
}

export interface CourseAssignment {
  id: string;
  course_id: string;
  user_id: string;
  user_name: string;
  user_email: string;
  assigned_by_name: string;
  created_at: string;
}

export interface ProgressResult {
  topic_id: string;
  user_id: string;
  status: string;
  updated_at: string;
}

export interface CodeRunResult {
  stdout: string;
  stderr: string;
  exit_code: number;
  timed_out: boolean;
}

/* ============ API ============ */

export const trainingApi = {
  // Courses
  getCourses: () =>
    api.get<Course[]>('/training/courses'),
  createCourse: (data: { title: string; description?: string }) =>
    api.post<Course>('/training/courses', data),
  updateCourse: (id: string, data: { title?: string; description?: string; order?: number; is_published?: boolean }) =>
    api.put<Course>(`/training/courses/${encodeURIComponent(id)}`, data),
  deleteCourse: (id: string) =>
    api.delete(`/training/courses/${encodeURIComponent(id)}`),

  // Topics
  getTopics: (courseId: string) =>
    api.get<Topic[]>(`/training/courses/${encodeURIComponent(courseId)}/topics`),
  getTopicDetail: (topicId: string) =>
    api.get<TopicDetail>(`/training/topics/${encodeURIComponent(topicId)}`),
  createTopic: (courseId: string, data: { title: string; description?: string; section_title?: string; difficulty?: string }) =>
    api.post<Topic>(`/training/courses/${encodeURIComponent(courseId)}/topics`, data),
  updateTopic: (topicId: string, data: { title?: string; description?: string; order?: number; section_title?: string; difficulty?: string }) =>
    api.put<Topic>(`/training/topics/${encodeURIComponent(topicId)}`, data),
  deleteTopic: (topicId: string) =>
    api.delete(`/training/topics/${encodeURIComponent(topicId)}`),

  // Progress
  updateProgress: (topicId: string, status: string) =>
    api.put<ProgressResult>(`/training/topics/${encodeURIComponent(topicId)}/progress`, { status }),

  // Hashtags
  getHashtags: () =>
    api.get<HashtagType[]>('/training/hashtags'),
  createHashtag: (data: { name: string; color?: string }) =>
    api.post<HashtagType>('/training/hashtags', data),
  deleteHashtag: (id: string) =>
    api.delete(`/training/hashtags/${encodeURIComponent(id)}`),
  assignHashtag: (topicId: string, hashtagId: string) =>
    api.post(`/training/topics/${encodeURIComponent(topicId)}/hashtags/${encodeURIComponent(hashtagId)}`),
  removeHashtag: (topicId: string, hashtagId: string) =>
    api.delete(`/training/topics/${encodeURIComponent(topicId)}/hashtags/${encodeURIComponent(hashtagId)}`),

  // Content blocks
  createContent: (topicId: string, data: { title?: string; body?: string; content_type?: string; order?: number }) =>
    api.post<ContentBlock>(`/training/topics/${encodeURIComponent(topicId)}/content`, data),
  updateContent: (blockId: string, data: { title?: string; body?: string; content_type?: string; order?: number }) =>
    api.put<ContentBlock>(`/training/content/${encodeURIComponent(blockId)}`, data),
  deleteContent: (blockId: string) =>
    api.delete(`/training/content/${encodeURIComponent(blockId)}`),

  // Tasks
  getTask: (taskId: string) =>
    api.get<Task>(`/training/tasks/${encodeURIComponent(taskId)}`),
  createTask: (topicId: string, data: { title: string; description: string }) =>
    api.post<Task>(`/training/topics/${encodeURIComponent(topicId)}/task`, data),
  updateTask: (taskId: string, data: { title?: string; description?: string }) =>
    api.put<Task>(`/training/tasks/${encodeURIComponent(taskId)}`, data),
  deleteTask: (taskId: string) =>
    api.delete(`/training/tasks/${encodeURIComponent(taskId)}`),

  // Submissions
  submitAnswer: (taskId: string, data: { content?: string; file?: File }) => {
    const formData = new FormData();
    if (data.content) formData.append('content', data.content);
    if (data.file) formData.append('file', data.file);
    return api.post<Submission>(`/training/tasks/${encodeURIComponent(taskId)}/submit`, formData);
  },
  getMySubmission: (taskId: string) =>
    api.get<Submission | null>(`/training/tasks/${encodeURIComponent(taskId)}/my-submission`),
  getPendingSubmissions: () =>
    api.get<Submission[]>('/training/submissions/pending'),
  reviewSubmission: (submissionId: string, data: { status: 'approved' | 'rejected'; review_comment?: string }) =>
    api.post<Submission>(`/training/submissions/${encodeURIComponent(submissionId)}/review`, data),

  // Code execution
  runCode: (language: string, code: string) =>
    api.post<CodeRunResult>('/training/code/run', { language, code }),

  // Assignments
  getInterns: () =>
    api.get<Intern[]>('/training/interns'),
  getAssignments: (courseId: string) =>
    api.get<CourseAssignment[]>(`/training/courses/${encodeURIComponent(courseId)}/assignments`),
  assignCourse: (courseId: string, userIds: string[]) =>
    api.post<CourseAssignment[]>(`/training/courses/${encodeURIComponent(courseId)}/assign`, { user_ids: userIds }),
  unassignCourse: (courseId: string, userId: string) =>
    api.delete(`/training/courses/${encodeURIComponent(courseId)}/assign/${encodeURIComponent(userId)}`),
};
