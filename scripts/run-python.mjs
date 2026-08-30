import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

const root = process.cwd().endsWith(`${join('apps', 'api')}`)
  ? join(process.cwd(), '..', '..')
  : process.cwd();
const localPython =
  process.platform === 'win32'
    ? join(root, '.venv', 'Scripts', 'python.exe')
    : join(root, '.venv', 'bin', 'python');
const python = existsSync(localPython) ? localPython : 'python';
const result = spawnSync(python, process.argv.slice(2), { stdio: 'inherit', shell: false });

if (result.error) {
  console.error(`Unable to start Python runtime: ${result.error.message}`);
  process.exit(1);
}

process.exit(result.status ?? 1);
