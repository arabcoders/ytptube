import { describe, expect, it } from 'bun:test';
import { createTV } from 'tailwind-variants';
import dropdown from '../../.nuxt/ui/dropdown-menu';
import popover from '../../.nuxt/ui/popover';
import select from '../../.nuxt/ui/select';
import selectMenu from '../../.nuxt/ui/select-menu';

const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'defineAppConfig');
Object.defineProperty(globalThis, 'defineAppConfig', {
  configurable: true,
  value: <T>(config: T): T => config,
});
const { default: config } = await import('../../app/app.config').finally(() => {
  if (descriptor) {
    Object.defineProperty(globalThis, 'defineAppConfig', descriptor);
  } else {
    Reflect.deleteProperty(globalThis, 'defineAppConfig');
  }
});

const themes = [
  ['dropdown', dropdown, config.ui.dropdownMenu],
  ['popover', popover, config.ui.popover],
  ['select', select, config.ui.select],
  ['selectMenu', selectMenu, config.ui.selectMenu],
] as const;

describe('floating surfaces', () => {
  it.each(themes)('%s keeps glass', (_name, theme, overrides) => {
    const ui = createTV()({ extend: theme, ...overrides })();
    const classes = ui.content({ class: 'max-w-96' }).split(/\s+/);

    // Retained Nuxt background and shadow utilities override component-layer surface CSS.
    expect(classes.filter((value) => value.startsWith('bg-'))).toEqual(['bg-(--ytp-floating-bg)']);
    expect(classes.filter((value) => value.startsWith('shadow-'))).toEqual([
      'shadow-(--ytp-floating-shadow)',
    ]);
    expect(classes).toContain('max-w-96');
  });
});
