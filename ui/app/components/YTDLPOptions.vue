<!-- ui/app/pages/options.vue -->
<template>
  <div class="p-1 container" style="border-radius: 0; padding:0">

    <div class="box m-2">
      <div class="columns is-multiline is-vcentered">
        <div class="column is-12 is-6-desktop">
          <label class="label is-small">Search</label>
          <div class="control has-icons-left">
            <input v-model.trim="filters.query" type="text" class="input" placeholder="Filter by flag or description..."
              autocomplete="off" />
            <span class="icon is-left"><i class="fa-solid fa-magnifying-glass" /></span>
          </div>
        </div>

        <div class="column is-6-tablet is-3-desktop">
          <label class="label is-small">Group Filter</label>
          <div class="select is-fullwidth">
            <select v-model="filters.group">
              <option value="">All</option>
              <option v-for="g in groupNames" :key="g" :value="g">{{ g }}</option>
            </select>
          </div>
        </div>

        <div class="column is-6-tablet is-3-desktop">
          <label class="label is-small">Display</label>
          <div class="control">
            <div class="select is-fullwidth">
              <select v-model="displayMode">
                <option value="grouped">Grouped</option>
                <option value="list">List</option>
              </select>
            </div>
          </div>
        </div>

        <div class="column is-6-tablet is-3-desktop">
          <label class="label is-small">Sort By</label>
          <div class="select is-fullwidth">
            <select v-model="sortBy">
              <option value="flag">Flag</option>
              <option value="group">Group</option>
            </select>
          </div>
        </div>

        <div class="column is-6-tablet is-3-desktop">
          <label class="label is-small">Order</label>
          <div class="select is-fullwidth">
            <select v-model="sortDir">
              <option value="asc">Asc</option>
              <option value="desc">Desc</option>
            </select>
          </div>
        </div>

        <div class="column is-12 is-6-desktop">
          <label class="label is-small">Flags</label>
          <div class="buttons are-small">
            <button class="button" :class="{ 'is-link': filters.flagKind === 'any' }"
              @click="filters.flagKind = 'any'">Any</button>
            <button class="button" :class="{ 'is-link': filters.flagKind === 'short' }"
              @click="filters.flagKind = 'short'">Short Only (-x)</button>
            <button class="button" :class="{ 'is-link': filters.flagKind === 'long' }"
              @click="filters.flagKind = 'long'">Long Only (--xyz)</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="0 === visible.length" class="has-text-centered has-text-grey">
      <p>No options match your criteria.</p>
    </div>

    <template v-if="'grouped' === displayMode && 0 !== grouped.length">
      <section v-for="group in grouped" :key="group.name" class="m-2 mb-5">
        <h2 class="title is-6 mb-3">
          <span class="icon-text">
            <span class="icon"><i class="fa-regular fa-folder-open" /></span>
            <span>{{ group.name }} <small class="has-text-grey">({{ group.items.length }})</small></span>
          </span>
        </h2>
        <div class="table-container">
          <table class="table is-fullwidth is-striped is-hoverable is-bordered">
            <thead>
              <tr>
                <th style="width: 30%">Flags</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="opt in group.items" :key="opt.flags.join('|')">
                <tr v-if="!opt.ignored">
                  <td>
                    <i class="has-text-primary is-pointer is-pulled-right fa-regular fa-copy is-unselectable"
                      @click="copyFlag(opt.flags)" />
                    <div class="is-flex is-align-items-center">
                      <div class="tags">
                        <span v-for="f in opt.flags" :key="f" class="tag is-info">{{ f }}</span>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span v-if="opt.description && 0 !== opt.description.length">{{ opt.description }}</span>
                    <span v-else class="has-text-grey">—</span>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <template v-else>
      <div class="table-container">
        <table class="table is-fullwidth is-striped is-hoverable is-bordered m-2">
          <thead>
            <tr>
              <th style="width: 30%">Flags</th>
              <th style="width: 20%">Group</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="opt in visible" :key="opt.flags.join('|')">
              <tr v-if="!opt.ignored">
                <td>
                  <i class="has-text-primary is-pointer is-pulled-right fa-regular fa-copy is-unselectable"
                    @click="copyFlag(opt.flags)" />
                  <div class="is-flex is-align-items-center">
                    <div class="tags">
                      <span v-for="f in opt.flags" :key="f" class="tag is-info">{{ f }}</span>
                    </div>
                  </div>
                </td>
                <td class="is-bold">
                  {{ opt.group || 'root' }}
                </td>
                <td>
                  <span v-if="opt.description && 0 !== opt.description.length">{{ opt.description }}</span>
                  <span v-else class="has-text-grey">—</span>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'

type YTDLPOption = {
  flags: string[],
  description: string | null,
  group: string | null,
  ignored: boolean,
}

const isLoading = ref(false)
const options = ref<YTDLPOption[]>([])
const displayMode = useStorage<'grouped' | 'list'>('opts_display', 'grouped')
const sortBy = useStorage<'flag' | 'group'>('opts_sort_by', 'flag')
const sortDir = useStorage<'asc' | 'desc'>('opts_sort_dir', 'asc')

const filters = reactive({
  query: '',
  group: '',
  flagKind: 'any' as 'any' | 'short' | 'long',
})

const reload = async (): Promise<void> => {
  try {
    isLoading.value = true
    const resp = await request('/api/yt-dlp/options', { credentials: 'include' })
    if (!resp.ok) {
      return
    }
    const data = await resp.json()
    if (Array.isArray(data)) {
      options.value = data as YTDLPOption[]
    }
  } finally {
    isLoading.value = false
  }
}

const copyFlag = async (flags: string[]): Promise<void> => {
  const longFlag = flags.find(f => f.startsWith('--'))
  if (!longFlag) {
    return
  }
  copyText(longFlag)
}

onMounted(async () => await reload())

const groupNames = computed<string[]>(() => {
  const s = new Set<string>()
  for (const o of options.value) {
    s.add(o.group || 'root')
  }
  return Array.from(s).sort((a, b) => a.localeCompare(b))
})

const filtered = computed<YTDLPOption[]>(() => {
  const q = filters.query.toLowerCase()
  const g = filters.group

  return options.value.filter((o) => {
    if (g && (o.group || 'root') !== g) {
      return false
    }

    if ('short' === filters.flagKind && !o.flags.some((f) => /^-\w(,|$)|^-\w$/.test(f))) {
      return false
    }

    if ('long' === filters.flagKind && !o.flags.some((f) => /^--[a-zA-Z0-9][\w-]*/.test(f))) {
      return false
    }

    if (0 !== q.length) {
      const hay = [o.flags.join(' '), o.description || '', o.group || 'root'].join(' ').toLowerCase()
      if (-1 === hay.indexOf(q)) {
        return false
      }
    }

    return true
  })
})

const sorted = computed<YTDLPOption[]>(() => {
  const dir = 'asc' === sortDir.value ? 1 : -1
  const arr = [...filtered.value]

  arr.sort((a, b) => {
    if ('group' === sortBy.value) {
      const ga = (a.group || 'root').localeCompare(b.group || 'root')
      if (0 !== ga) {
        return ga * dir
      }
    }

    const fa = (a.flags[0] || '').localeCompare(b.flags[0] || '')
    return fa * dir
  })

  return arr
})

const visible = computed<YTDLPOption[]>(() => sorted.value)

const grouped = computed<{ name: string, items: YTDLPOption[] }[]>(() => {
  const map = new Map<string, YTDLPOption[]>()

  for (const o of visible.value) {
    const key = o.group || 'root'
    if (!map.has(key)) {
      map.set(key, [])
    }
    map.get(key)!.push(o)
  }

  const out = Array.from(map.entries()).map(([name, items]) => {
    items.sort((a, b) => (a.flags[0] || '').localeCompare(b.flags[0] || ''))
    return { name, items }
  })

  out.sort((a, b) => a.name.localeCompare(b.name))
  return out
})
</script>

<style scoped>
.table td,
.table th {
  vertical-align: top;
}
</style>
