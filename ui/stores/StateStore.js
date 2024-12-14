export const useStateStore = defineStore('state', () => {
  const state = reactive({
    queue: {},
    history: {}
  });

  const actions = {
    add(type, key, value) {
      state[type][key] = value;
    },
    update(type, key, value) {
      state[type][key] = value;
    },
    remove(type, key) {
      if (state[type][key]) {
        delete state[type][key];
      }
    },
    get(type, key, defaultValue = null) {
      return state[type][key] || defaultValue;
    },
    has(type, key) {
      return !!state[type][key];
    },
    clearAll(type) {
      state[type] = {};
    },
    addAll(type, data) {
      state[type] = data;
    },
    move(fromType, toType, key) {
      if (state[fromType][key]) {
        state[toType][key] = state[fromType][key];
        delete state[fromType][key];
      }
    },
    count(type) {
      return Object.keys(state[type]).length;
    }
  }

  return { ...toRefs(state), ...actions };
});
