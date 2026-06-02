/** Относительный путь от axios baseURL `/api` (без ведущего `/`). */
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Колонки доски: `/api/tasks/iteration/{id}/board-columns` (тот же роутер, что и список задач).
 * Дублирует `/api/iterations/{id}/board-columns` на бэкенде — надёжнее при странных 404 на iterations.
 */
export function iterationBoardColumnsPath(iterationId: string): string {
  const id = String(iterationId ?? '').trim();
  if (!UUID_RE.test(id)) {
    throw new Error(`Invalid iteration id: ${iterationId}`);
  }
  return `tasks/iteration/${id}/board-columns`;
}
