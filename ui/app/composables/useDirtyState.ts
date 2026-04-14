import { computed, ref, toValue, type MaybeRefOrGetter } from 'vue';

const serializeDirtyValue = <T>(value: T): string => JSON.stringify(toValue(value));

export const useDirtyState = <T>(source: MaybeRefOrGetter<T>) => {
  const snapshot = ref<string>('');

  const markClean = (): void => {
    snapshot.value = serializeDirtyValue(toValue(source));
  };

  const isDirty = computed<boolean>(() => {
    return snapshot.value !== serializeDirtyValue(toValue(source));
  });

  return {
    isDirty,
    markClean,
  };
};
