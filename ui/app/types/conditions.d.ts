export type ConditionItem = {
  id?: string
  name: string
  filter: string
  cli: string
  [key: string]: any
}

export type ImportedConditionItem = ConditionItem & {
  _type: string
  _version: string
}
