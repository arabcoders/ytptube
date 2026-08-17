import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, test } from 'bun:test';
import { IconUsageScanner } from '@nuxt/icon/utils';
import { isRelevantSource, renderCatalog, writeCatalogIfChanged } from '../../modules/icon-catalog';

test('test source filtering', () => {
  const root = '/workspace/ui';

  expect(isRelevantSource('app/components/Icon.vue', root)).toBe(true);
  expect(isRelevantSource('/workspace/ui/app/utils/generatedIconCatalog.ts', root)).toBe(false);
  expect(isRelevantSource('/workspace/ui/app/styles/icons.css', root)).toBe(false);
  expect(isRelevantSource('/workspace/ui/tests/Icon.vue', root)).toBe(false);
});

test('test catalog rendering', () => {
  expect(renderCatalog(new Set(['i:lucide:zap', 'lucide:activity', 'mdi:close']))).toBe(
    `${`// Generated from Nuxt Icon's client bundle. Do not edit manually.\n\nexport const bundledIconNames = [\n  "lucide:activity",\n  "lucide:zap"\n] as const;\n\nexport const bundledUiIconNames = [\n  "i-lucide-activity",\n  "i-lucide-zap"\n] as const;\n\nconst bundledUiIconSet = new Set<string>(bundledUiIconNames);\n\nexport const isBundledUiIcon = (name?: string | null): name is (typeof bundledUiIconNames)[number] =>\n  typeof name === 'string' && bundledUiIconSet.has(name);\n`}`,
  );
});

test('test incremental extraction', () => {
  const scanner = new IconUsageScanner({ globInclude: ['app/**/*.{vue,ts,js}'] });
  const icons = new Set<string>();

  scanner.extractFromCode('<Icon name="i-lucide-alarm-clock-minus" />', icons);

  expect(icons).toEqual(new Set(['lucide:alarm-clock-minus']));
});

test('test unchanged catalog', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'ytptube-icon-catalog-'));
  const path = join(directory, 'catalog.ts');
  const content = renderCatalog(['lucide:activity']);

  try {
    expect(await writeCatalogIfChanged(path, content)).toBe(true);
    expect(await writeCatalogIfChanged(path, content)).toBe(false);
    expect(await readFile(path, 'utf8')).toBe(content);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
