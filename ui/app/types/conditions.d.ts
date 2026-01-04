export type ConditionItem = {
  id?: string
  name: string
  filter: string
  cli: string
  extras: Record<string, any>
  enabled: boolean
}

export type ImportedConditionItem = ConditionItem & {
  _type: string
  _version: string
}
