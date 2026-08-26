import { describe, expect, it } from 'bun:test';
import { nextTick, ref } from 'vue';
import { useRangeSelection } from '~/composables/useRangeSelection';

const selection = (ids: string[] = ['a', 'b', 'c', 'd']) => {
  const selected = ref<string[]>([]);
  const range = useRangeSelection(selected, ref(ids));
  return { range, selected };
};

describe('useRangeSelection', () => {
  it('selects forward range', () => {
    const { range, selected } = selection();
    range.select('b');
    selected.value = ['b', 'd'];
    range.select('d', true);
    expect(selected.value).toEqual(['b', 'd', 'c']);
  });

  it('selects reverse range', () => {
    const { range, selected } = selection();
    range.select('d');
    selected.value = ['d', 'b'];
    range.select('b', true);
    expect(selected.value).toEqual(['d', 'b', 'c']);
  });

  it('deselects forward range', () => {
    const { range, selected } = selection();
    range.select('b');
    selected.value = ['b', 'c'];
    range.select('d', true);
    expect(selected.value).toEqual([]);
  });

  it('deselects reverse range', () => {
    const { range, selected } = selection();
    range.select('d');
    selected.value = ['c', 'd'];
    range.select('b', true);
    expect(selected.value).toEqual([]);
  });

  it('handles missing anchor', () => {
    const ids = ref(['a', 'b', 'c', 'd']);
    const selected = ref<string[]>([]);
    const range = useRangeSelection(selected, ids);
    range.select('b');
    ids.value = ['a', 'c', 'd'];
    selected.value = ['c'];
    range.select('d', true);
    expect(selected.value).toEqual(['c']);
  });

  it('resets changed dataset', async () => {
    const ids = ref(['a', 'b', 'c']);
    const selected = ref<string[]>([]);
    const range = useRangeSelection(selected, ids);
    range.select('a');
    ids.value = ['a', 'c', 'd'];
    await nextTick();
    selected.value = ['c'];
    range.select('d', true);
    expect(selected.value).toEqual(['c']);
  });

  it('toggles normal selection', () => {
    const { range, selected } = selection();
    range.select('b');
    selected.value = ['b'];
    range.select('b');
    expect(selected.value).toEqual(['b']);
  });

  it('handles keyboard shift', () => {
    const { range, selected } = selection();
    range.select('b');
    selected.value = ['b', 'd'];
    range.handleKeydown({ key: ' ', shiftKey: true } as KeyboardEvent);
    range.handleChange('d', {});
    expect(selected.value).toEqual(['b', 'd', 'c']);
  });
});
