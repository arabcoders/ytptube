import { defineStore } from 'pinia'
import { reactive, toRefs } from 'vue'
import type { StoreItem } from '~/types/store'

type StateType = 'queue' | 'history'
type KeyType = string
type ValueType = StoreItem

interface State {
  queue: Record<KeyType, ValueType>
  history: Record<KeyType, ValueType>
}

export const useStateStore = defineStore('state', () => {
  const state = reactive<State>({ queue: {}, history: {} })

  const add = (type: StateType, key: KeyType, value: ValueType): void => {
    state[type][key] = value
  }

  const update = (type: StateType, key: KeyType, value: ValueType): void => {
    state[type][key] = value
  }

  const remove = (type: StateType, key: KeyType): void => {
    if (state[type][key]) {
      delete state[type][key]
    }
  }

  const get = (type: StateType, key: KeyType, defaultValue: ValueType | null | object = null): ValueType | null => {
    return state[type][key] || defaultValue
  }

  const has = (type: StateType, key: KeyType): boolean => {
    return !!state[type][key]
  }

  const clearAll = (type: StateType): void => {
    state[type] = {}
  }

  const addAll = (type: StateType, data: Record<KeyType, ValueType>): void => {
    state[type] = data
  }

  const move = (fromType: StateType, toType: StateType, key: KeyType): void => {
    if (state[fromType][key]) {
      state[toType][key] = state[fromType][key]
      delete state[fromType][key]
    }
  }

  const count = (type: StateType): number => {
    return Object.keys(state[type]).length
  }

  return { ...toRefs(state), add, update, remove, get, has, clearAll, addAll, move, count }
})
