/**
 * Запуск uvicorn с первым доступным Python (.venv / .venv-1 / py / python3).
 * Использование: node scripts/run-server.mjs
 */
import { spawn, spawnSync } from 'child_process';
import { existsSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const serverDir = path.join(root, 'server');

const win = process.platform === 'win32';
const pyExe = win ? 'python.exe' : 'python';

const candidates = [
  path.join(root, '.venv', win ? `Scripts/${pyExe}` : 'bin/python'),
  path.join(root, '.venv-1', win ? `Scripts/${pyExe}` : 'bin/python'),
  path.join(serverDir, '.venv', win ? `Scripts/${pyExe}` : 'bin/python'),
];

/** Пропускаем битые venv (например, ссылка на удалённый Python из Store). */
function resolvePython() {
  for (const p of candidates) {
    if (!existsSync(p)) continue;
    const r = spawnSync(p, ['--version'], { encoding: 'utf8', timeout: 8000 });
    if (r.status === 0) return p;
  }
  return null;
}

const python = resolvePython();

const env = { ...process.env, PYTHONUNBUFFERED: '1' };

// Без `--reload`: reload может перезапускать uvicorn в момент запроса и фронт ловит 500/ECONNREFUSED.
const uvicornArgs = ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'];

function start(cmd, args) {
  const child = spawn(cmd, args, {
    cwd: serverDir,
    env,
    stdio: 'inherit',
    shell: false,
  });
  child.on('exit', (code) => process.exit(code ?? 1));
}

if (python) {
  start(python, uvicornArgs);
} else if (win) {
  start('py', ['-3', ...uvicornArgs]);
} else {
  start('python3', uvicornArgs);
}
