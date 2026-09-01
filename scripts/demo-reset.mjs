import { spawnSync } from 'node:child_process';

const databaseName = process.env.DEMO_DATABASE_NAME ?? 'recoveryos_demo';
const container = process.env.POSTGRES_CONTAINER ?? 'recoveryos-postgres-1';
const databaseUrl =
  process.env.DEMO_DATABASE_URL ??
  `postgresql+psycopg://recoveryos:recoveryos@127.0.0.1:5433/${databaseName}`;
const adminPassword = process.env.POSTGRES_PASSWORD ?? 'recoveryos';

if (databaseName !== 'recoveryos_demo') {
  throw new Error('Refusing to reset a database other than the dedicated recoveryos_demo database');
}

function run(command, args, env = {}, cwd = process.cwd()) {
  const result = spawnSync(command, args, {
    stdio: 'inherit',
    env: { ...process.env, ...env },
    cwd,
  });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

run('docker', [
  'exec',
  '-e',
  `PGPASSWORD=${adminPassword}`,
  container,
  'psql',
  '-U',
  'recoveryos',
  '-d',
  'postgres',
  '-v',
  'ON_ERROR_STOP=1',
  '-c',
  'DROP DATABASE IF EXISTS recoveryos_demo WITH (FORCE)',
  '-c',
  'CREATE DATABASE recoveryos_demo OWNER recoveryos',
]);

run(
  process.execPath,
  ['../../scripts/run-python.mjs', '-m', 'alembic', 'upgrade', 'head'],
  { DATABASE_URL: databaseUrl },
  new URL('../apps/api/', import.meta.url),
);

console.log('Demo database reset and migrated. Seed it with:');
console.log(
  '  $env:DEMO_AUTH_SECRET="local-demo-only"; $env:DATABASE_URL="' +
    databaseUrl +
    '"; $env:DEMO_AUTH_TOKEN = (node scripts/run-python.mjs apps/api/scripts/seed_demo.py); pnpm demo:e2e',
);
