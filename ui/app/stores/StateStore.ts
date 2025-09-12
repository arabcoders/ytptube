import { defineStore } from 'pinia'
import type { StoreItem } from '~/types/store'

type StateType = 'queue' | 'history'
type KeyType = string

interface State {
  queue: Record<KeyType, StoreItem>
  history: Record<KeyType, StoreItem>
}

export const useStateStore = defineStore('state', () => {
  const state = reactive<State>({ queue: {}, history: {} })

  const add = (type: StateType, key: KeyType, value: StoreItem): void => {
    state[type][key] = value
  }

  const update = (type: StateType, key: KeyType, value: StoreItem): void => {
    state[type][key] = value
  }

  const remove = (type: StateType, key: KeyType): void => {
    if (state[type][key]) {
      const { [key]: _, ...rest } = state[type]
      state[type] = rest
    }
  }

  const get = (type: StateType, key: KeyType, defaultValue: StoreItem | null = null): StoreItem | null => {
    return state[type][key] || defaultValue
  }

  const has = (type: StateType, key: KeyType): boolean => {
    return !!state[type][key]
  }

  const clearAll = (type: StateType): void => {
    state[type] = {}
  }

  const addAll = (type: StateType, data: Record<KeyType, StoreItem>): void => {
    state[type] = data
  }

  const move = (fromType: StateType, toType: StateType, key: KeyType): void => {
    if (state[fromType][key]) {
      state[toType][key] = state[fromType][key]
      const { [key]: _, ...rest } = state[fromType]
      state[fromType] = rest
    }
  }

  const count = (type: StateType): number => {
    return Object.keys(state[type]).length
  }

  return { ...toRefs(state), add, update, remove, get, has, clearAll, addAll, move, count }
})
