import { toValue, watch, type MaybeRefOrGetter, type Ref } from 'vue';

type SelectionEvent = Event & { shiftKey?: boolean };

export const useRangeSelection = <Id>(selected: Ref<Id[]>, displayed: MaybeRefOrGetter<Id[]>) => {
  let anchor: Id | undefined;
  let lastDisplayed = toValue(displayed);
  let keyboardShift = false;

  const sameIds = (left: Id[], right: Id[]): boolean =>
    left.length === right.length && left.every((id, index) => id === right[index]);

  const reset = (): void => {
    anchor = undefined;
  };

  watch(
    () => toValue(displayed),
    (ids) => {
      if (!sameIds(ids, lastDisplayed)) {
        reset();
        lastDisplayed = [...ids];
      }
    },
    { deep: true },
  );

  const select = (id: Id, shiftKey = false): void => {
    const ids = toValue(displayed);

    if (!sameIds(ids, lastDisplayed)) {
      reset();
      lastDisplayed = [...ids];
    }

    const clickedIndex = ids.indexOf(id);
    const anchorIndex = anchor === undefined ? -1 : ids.indexOf(anchor);

    if (!shiftKey || clickedIndex === -1 || anchorIndex === -1) {
      anchor = id;
      return;
    }

    const start = Math.min(anchorIndex, clickedIndex);
    const end = Math.max(anchorIndex, clickedIndex);
    const range = ids.slice(start, end + 1);
    const shouldSelect = selected.value.includes(id);

    if (shouldSelect) {
      selected.value = [
        ...selected.value,
        ...range.filter((rangeId) => !selected.value.includes(rangeId)),
      ];
    } else {
      selected.value = selected.value.filter((selectedId) => !range.includes(selectedId));
    }

    anchor = id;
  };

  const handleKeydown = (event: KeyboardEvent): void => {
    if (event.key === ' ' || event.key === 'Spacebar') {
      keyboardShift = event.shiftKey;
    }
  };

  const handleClick = (event: MouseEvent): void => {
    keyboardShift = event.shiftKey;
  };

  const handleChange = (id: Id, event: SelectionEvent): void => {
    const shiftKey = Boolean(event.shiftKey) || keyboardShift;
    keyboardShift = false;
    select(id, shiftKey);
  };

  return { handleChange, handleClick, handleKeydown, reset, select };
};
