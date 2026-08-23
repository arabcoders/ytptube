import { readdirSync, readFileSync } from 'node:fs';
import { dirname, extname, join } from 'node:path';

type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
type Shape = 'object' | 'leaf';

const localesDir = join(dirname(import.meta.dir), 'i18n', 'locales');
const localeFiles = readdirSync(localesDir)
  .filter((file) => extname(file) === '.json')
  .sort();
const englishFile = 'en.json';

const isObject = (value: JsonValue): value is { [key: string]: JsonValue } =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const getShape = (value: JsonValue): Shape => (isObject(value) ? 'object' : 'leaf');

const collectPaths = (
  value: JsonValue,
  path = '',
  shapes = new Map<string, Shape>(),
  leaves = new Set<string>(),
) => {
  if (!path) {
    shapes.set('$', getShape(value));
    if (isObject(value)) {
      for (const [key, child] of Object.entries(value)) collectPaths(child, key, shapes, leaves);
    } else {
      leaves.add('$');
    }
    return { shapes, leaves };
  }

  const shape = getShape(value);
  shapes.set(path, shape);
  if (shape === 'leaf') {
    leaves.add(path);
  } else {
    for (const [key, child] of Object.entries(value))
      collectPaths(child, `${path}.${key}`, shapes, leaves);
  }
  return { shapes, leaves };
};

const readJson = (file: string): JsonValue =>
  JSON.parse(readFileSync(join(localesDir, file), 'utf8')) as JsonValue;

if (!localeFiles.includes(englishFile)) {
  console.error(`i18n:check failed: missing authoritative locale ${englishFile}`);
  process.exit(1);
}

let english: JsonValue;
try {
  english = readJson(englishFile);
} catch (error) {
  console.error(`en.json: invalid JSON: ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
}

const expected = collectPaths(english);
const failures: string[] = [];

for (const file of localeFiles) {
  if (file === englishFile) continue;

  let locale: JsonValue;
  try {
    locale = readJson(file);
  } catch (error) {
    failures.push(
      `${file}: invalid JSON: ${error instanceof Error ? error.message : String(error)}`,
    );
    continue;
  }

  const actual = collectPaths(locale);
  const missing = [
    ...[...expected.leaves].filter((path) => !actual.leaves.has(path)),
    ...[...expected.shapes]
      .filter(
        ([path, shape]) =>
          shape === 'object' &&
          path !== '$' &&
          !actual.shapes.has(path) &&
          ![...expected.leaves].some((leaf) => leaf.startsWith(`${path}.`)),
      )
      .map(([path]) => path),
  ].sort();
  const extra = [
    ...[...actual.leaves].filter((path) => !expected.leaves.has(path)),
    ...[...actual.shapes]
      .filter(
        ([path, shape]) =>
          shape === 'object' &&
          path !== '$' &&
          !expected.shapes.has(path) &&
          ![...actual.leaves].some((leaf) => leaf.startsWith(`${path}.`)),
      )
      .map(([path]) => path),
  ].sort();
  const mismatched = [...new Set([...expected.shapes.keys(), ...actual.shapes.keys()])]
    .filter(
      (path) =>
        expected.shapes.has(path) &&
        actual.shapes.has(path) &&
        expected.shapes.get(path) !== actual.shapes.get(path),
    )
    .sort();

  if (missing.length || extra.length || mismatched.length) {
    failures.push(`${file}:`);
    if (missing.length) failures.push(`  missing: ${missing.join(', ')}`);
    if (extra.length) failures.push(`  extra: ${extra.join(', ')}`);
    if (mismatched.length) {
      failures.push(
        `  mismatched: ${mismatched.map((path) => `${path} (expected ${expected.shapes.get(path) ?? 'missing'}, found ${actual.shapes.get(path) ?? 'missing'})`).join(', ')}`,
      );
    }
  }
}

if (failures.length) {
  console.error(['i18n:check failed:', ...failures].join('\n'));
  process.exit(1);
}

console.log(`i18n:check passed (${localeFiles.length - 1} locales, ${expected.leaves.size} keys)`);
