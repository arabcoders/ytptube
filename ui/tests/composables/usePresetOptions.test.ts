import { beforeAll, describe, expect, it, mock } from 'bun:test'

import type { Preset } from '~/types/presets'

let configState = {
  presets: [] as Preset[],
  app: {
    download_path: '/downloads',
  },
}

mock.module('~/composables/useYtpConfig', () => ({
  useYtpConfig: () => configState,
}))

let usePresetOptions: typeof import('~/composables/usePresetOptions').usePresetOptions

beforeAll(async () => {
  ;({ usePresetOptions } = await import('~/composables/usePresetOptions'))
})

const buildPreset = (name: string, isDefault: boolean): Preset => ({
  name,
  default: isDefault,
  description: '',
  folder: '',
  template: '',
  cookies: '',
  cli: '',
  priority: 0,
})

const setConfigStore = (presets: Preset[]) => {
  configState = {
    presets,
    app: {
      download_path: '/downloads',
    },
  }
}

describe('usePresetOptions', () => {
  it('groups custom presets before default presets by default', () => {
    setConfigStore([
      buildPreset('default_video', true),
      buildPreset('custom_audio', false),
    ])

    const { selectItems } = usePresetOptions()

    expect(selectItems.value).toEqual([
      { type: 'label', label: 'Custom presets' },
      { label: 'Custom Audio', value: 'custom_audio' },
      { type: 'label', label: 'Default presets' },
      { label: 'Default Video', value: 'default_video' },
    ])
  })

  it('supports default-first grouping when requested', () => {
    setConfigStore([
      buildPreset('default_video', true),
      buildPreset('custom_audio', false),
    ])

    const { selectItems } = usePresetOptions(undefined, { order: 'default-first' })

    expect(selectItems.value).toEqual([
      { type: 'label', label: 'Default presets' },
      { label: 'Default Video', value: 'default_video' },
      { type: 'label', label: 'Custom presets' },
      { label: 'Custom Audio', value: 'custom_audio' },
    ])
  })
})
