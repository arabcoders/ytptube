export const setSelected = <Id extends string | number>(
  selected: Id[],
  id: Id | undefined,
  checked: boolean | 'indeterminate',
): Id[] => {
  if (id === undefined) {
    return selected;
  }

  if (checked === true) {
    return selected.includes(id) ? selected : [...selected, id];
  }

  return selected.filter((value) => value !== id);
};
