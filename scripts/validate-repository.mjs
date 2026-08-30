import { existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const required = [
  'apps/web',
  'apps/api',
  'packages/ui/src',
  'packages/ui/src/global.css',
  '.env.example',
  'pnpm-workspace.yaml',
  'turbo.json',
];

const missing = required.filter((path) => !existsSync(join(process.cwd(), path)));
const forbidden = existsSync('apps/web/app/components')
  ? readdirSync('apps/web/app/components', { withFileTypes: true }).map((entry) => entry.name)
  : [];

if (missing.length || forbidden.length) {
  if (missing.length) console.error(`Missing repository baseline paths: ${missing.join(', ')}`);
  if (forbidden.length)
    console.error('Reusable components must not be placed in apps/web/app/components.');
  process.exit(1);
}

console.log('RecoveryOS repository baseline is valid.');
