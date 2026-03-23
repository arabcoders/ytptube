import { setNuxtToastManager } from '~/utils/nuxtToastManager';

export default defineNuxtPlugin(() => {
  const toast = useToast();

  setNuxtToastManager({
    add: (payload) => toast.add(payload),
    remove: (id) => toast.remove(id),
  });
});
