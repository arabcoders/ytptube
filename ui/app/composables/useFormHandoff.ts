export interface FormHandoff<T> {
  set: (data: T) => void;
  take: () => T | null;
}

export const useFormHandoff = <T>(key: string): FormHandoff<T> => {
  const pending = useState<T | null>(`form-handoff:${key}`, () => null);

  return {
    set: (data) => {
      pending.value = data;
    },
    take: () => {
      const data = pending.value;
      pending.value = null;
      return data;
    },
  };
};
