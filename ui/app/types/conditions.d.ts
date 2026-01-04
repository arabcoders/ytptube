export type ConditionItem = {
  id?: string
  name: string
  filter: string
  cli: string
  extras: Record<string, any>
  enabled: boolean
  priority: number
  description: string
}

export type ImportedConditionItem = ConditionItem & {
  _type: string
  _version: string
}
