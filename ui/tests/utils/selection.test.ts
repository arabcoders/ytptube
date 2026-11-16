import { describe, expect, it } from 'bun:test';
import { setSelected } from '~/utils/selection';

describe('checkbox selection', () => {
  it('adds checked items', () => {
    const selected = [1, 2];

    expect(setSelected(selected, 3, true)).toEqual([1, 2, 3]);
    expect(selected).toEqual([1, 2]);
    expect(setSelected(selected, 2, true)).toBe(selected);
  });

  it('removes unchecked items', () => {
    expect(setSelected([1, 2, 3], 2, false)).toEqual([1, 3]);
    expect(setSelected([1, 3], 2, false)).toEqual([1, 3]);
    expect(setSelected([1, 2, 3], 2, 'indeterminate')).toEqual([1, 3]);
  });

  it('preserves bulk selection', () => {
    const selected = setSelected([1, 2, 3], 2, false);

    expect(setSelected(selected, 2, true)).toEqual([1, 3, 2]);
    expect(setSelected([], 3, true)).toEqual([3]);
  });

  it('ignores missing ids', () => {
    const selected = [1, 2];

    expect(setSelected(selected, undefined, true)).toBe(selected);
    expect(setSelected(selected, undefined, false)).toBe(selected);
  });
});
