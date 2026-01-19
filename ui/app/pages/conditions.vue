<template>
  <div>
    <div class="mt-1 columns is-multiline">
      <div class="column is-12 is-clearfix is-unselectable">
        <span class="title is-4">
          <span class="icon-text">
            <template v-if="toggleForm">
              <span class="icon"><i class="fa-solid" :class="{ 'fa-edit': itemRef, 'fa-plus': !itemRef }" /></span>
              <span>{{ itemRef ? `Edit - ${item.name}` : 'Add new condition' }}</span>
            </template>
            <template v-else>
              <span class="icon"><i class="fa-solid fa-filter" /></span>
              <span>Conditions</span>
            </template>
          </span>
        </span>
        <div class="is-pulled-right" v-if="!toggleForm">
          <div class="field is-grouped">
            <p class="control has-icons-left" v-if="toggleFilter && items && items.length > 0">
              <input type="search" v-model.lazy="query" class="input" id="filter"
                placeholder="Filter displayed content">
              <span class="icon is-left"><i class="fas fa-filter" /></span>
            </p>

            <p class="control" v-if="items && items.length > 0">
              <button class="button is-danger is-light" @click="toggleFilter = !toggleFilter">
                <span class="icon"><i class="fas fa-filter" /></span>
                <span v-if="!isMobile">Filter</span>
              </button>
            </p>

            <p class="control">
              <button class="button is-primary" @click="resetForm(false); toggleForm = !toggleForm;">
                <span class="icon"><i class="fas fa-add" /></span>
                <span v-if="!isMobile">New Condition</span>
              </button>
            </p>
            <p class="control">
              <button v-tooltip.bottom="'Change display style'" class="button has-tooltip-bottom"
                @click="() => display_style = display_style === 'list' ? 'grid' : 'list'">
                <span class="icon">
                  <i class="fa-solid"
                    :class="{ 'fa-table': display_style !== 'list', 'fa-table-list': display_style === 'list' }" /></span>
                <span v-if="!isMobile">
                  {{ display_style === 'list' ? 'List' : 'Grid' }}
                </span>
              </button>
            </p>
            <p class="control">
              <button class="button is-info" @click="async () => await loadContent(page)"
                :class="{ 'is-loading': isLoading }" :disabled="isLoading" v-if="items && items.length > 0">
                <span class="icon"><i class="fas fa-refresh" /></span>
                <span v-if="!isMobile">Reload</span>
              </button>
            </p>
          </div>
        </div>
        <div class="is-hidden-mobile" v-if="!toggleForm">
          <span class="subtitle">
            Run yt-dlp custom match filter on returned info. and apply options.
          </span>
        </div>
      </div>

      <div class="column is-12" v-if="!toggleForm && paging?.total_pages > 1">
        <Pager :page="paging.page" :last_page="paging.total_pages" :isLoading="isLoading"
          @navigate="async (newPage) => { page = newPage; await loadContent(newPage); }" />
      </div>

      <div class="column is-12" v-if="toggleForm">
        <ConditionForm :addInProgress="conditions.addInProgress.value" :reference="itemRef" :item="(item as Condition)"
          @cancel="resetForm(true)" @submit="updateItem" />
      </div>
    </div>

    <div class="columns is-multiline" v-if="!isLoading && !toggleForm && (filteredItems && filteredItems.length > 0)">
      <div class="column is-12" v-if="'list' === display_style">
        <div class="table-container">
          <table class="table is-striped is-hoverable is-fullwidth is-bordered"
            style="min-width: 850px; table-layout: fixed;">
            <thead>
              <tr class="has-text-centered is-unselectable">
                <th width="80%">
                  <span class="icon"><i class="fa-solid fa-filter" /></span>
                  <span>Condition</span>
                </th>
                <th width="20%">
                  <span class="icon"><i class="fa-solid fa-gear" /></span>
                  <span>Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="cond in filteredItems" :key="cond.id">
                <td class="is-vcentered">
                  <div class="is-text-overflow is-bold">
                    {{ cond.name }}
                  </div>
                  <div class="is-unselectable">
                    <span class="icon-text is-clickable" @click="toggleEnabled(cond)"
                      v-tooltip="'Click to ' + (cond.enabled !== false ? 'disable' : 'enable') + ' condition'">
                      <span class="icon">
                        <i class="fa-solid fa-power-off"
                          :class="{ 'has-text-success': cond.enabled !== false, 'has-text-danger': cond.enabled === false }" />
                      </span>
                      <span>{{ cond.enabled !== false ? 'Enabled' : 'Disabled' }}</span>
                    </span>
                    &nbsp;
                    <Popover :maxWidth="450">
                      <template #trigger>
                        <span class="is-clickable">
                          <span class="icon"> <i class="fa-solid fa-info-circle" /></span>
                          <span>Show Details</span>
                        </span>
                      </template>

                      <template #title><strong>Condition Details</strong></template>

                      <div v-if="cond.filter">
                        <span class="icon"><i class="fa-solid fa-filter" /></span>
                        <code>{{ cond.filter }}</code>
                      </div>

                      <div v-if="cond.cli">
                        <span class="icon"><i class="fa-solid fa-terminal" /></span>
                        <code>{{ cond.cli }}</code>
                      </div>

                      <span v-if="cond.extras && Object.keys(cond.extras).length > 0">
                        <template v-for="(value, key) in cond.extras" :key="key">
                          <div>
                            <span class="icon"><i class="fa-solid fa-list" /></span>
                            <code>{{ key }}: {{ value }}</code>
                          </div>
                        </template>
                      </span>
                    </Popover>
                    <template v-if="cond.priority > 0">
                      &nbsp;
                      <span class="icon-text">
                        <span class="icon"><i class="fa-solid fa-sort-numeric-down" /></span>
                        <span>Priority: {{ cond.priority }}</span>
                      </span>
                    </template>
                  </div>
                </td>
                <td class="is-vcentered is-items-center">
                  <div class="field is-grouped is-grouped-centered">
                    <div class="control">
                      <button class="button is-info is-small is-fullwidth" @click="exportItem(cond)">
                        <span class="icon"><i class="fa-solid fa-file-export" /></span>
                        <span v-if="!isMobile">Export</span>
                      </button>
                    </div>
                    <div class="control">
                      <button class="button is-warning is-small is-fullwidth" @click="editItem(cond)">
                        <span class="icon"><i class="fa-solid fa-edit" /></span>
                        <span v-if="!isMobile">Edit</span>
                      </button>
                    </div>
                    <div class="control">
                      <button class="button is-danger is-small is-fullwidth" @click="deleteItem(cond)">
                        <span class="icon"><i class="fa-solid fa-trash" /></span>
                        <span v-if="!isMobile">Delete</span>
                      </button>
                    </div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <template v-else>
        <div class="column is-6" v-for="cond in filteredItems" :key="cond.id">
          <div class="card is-flex is-full-height is-flex-direction-column">
            <header class="card-header">
              <div class="card-header-title is-text-overflow is-block" v-text="cond.name" />
              <div class="card-header-icon">
                <div class="field is-grouped">
                  <div class="control" v-if="cond.priority > 0">
                    <span class="tag is-dark">
                      <span class="icon"><i class="fa-solid fa-sort-numeric-down" /></span>
                      <span v-text="cond.priority" />
                    </span>
                  </div>
                  <div class="control" @click="toggleEnabled(cond)">
                    <span class="icon" :class="cond.enabled ? 'has-text-success' : 'has-text-danger'"
                      v-tooltip="`Condition is ${cond.enabled !== false ? 'enabled' : 'disabled'}. Click to toggle.`">
                      <i class="fa-solid fa-power-off" />
                    </span>
                  </div>
                  <div class="control">
                    <a class="has-text-info" v-tooltip="'Export item'" @click.prevent="exportItem(cond)">
                      <span class="icon"><i class="fa-solid fa-file-export" /></span>
                    </a>
                  </div>
                </div>
              </div>
            </header>
            <div class="card-content is-flex-grow-1">
              <div class="content">
                <p class="is-text-overflow">
                  <span class="icon"><i class="fa-solid fa-filter" /></span>
                  <span v-text="cond.filter" />
                </p>
                <p class="is-text-overflow" v-if="cond.cli">
                  <span class="icon"><i class="fa-solid fa-terminal" /></span>
                  <span>{{ cond.cli }}</span>
                </p>
                <p class="is-text-overflow" v-if="cond.extras && Object.keys(cond.extras).length > 0">
                  <span class="icon"><i class="fa-solid fa-list" /></span>
                  <span>Extras:
                    <span v-for="(value, key) in cond.extras" :key="key" class="tag is-info mr-2">
                      <b>{{ key }}</b>: {{ value }}
                    </span>
                  </span>
                </p>
                <p class="is-clickable" :class="{ 'is-text-overflow': !isExpanded(cond.id, 'description') }"
                  v-if="cond.description" @click="toggleExpand(cond.id, 'description')">
                  <span class="icon"><i class="fa-solid fa-comment" /></span>
                  <span>{{ cond.description }}</span>
                </p>
              </div>
            </div>
            <div class="card-footer mt-auto">
              <div class="card-footer-item">
                <button class="button is-warning is-fullwidth" @click="editItem(cond)">
                  <span class="icon"><i class="fa-solid fa-edit" /></span>
                  <span>Edit</span>
                </button>
              </div>
              <div class="card-footer-item">
                <button class="button is-danger is-fullwidth" @click="deleteItem(cond)">
                  <span class="icon"><i class="fa-solid fa-trash" /></span>
                  <span>Delete</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <div class="columns is-multiline" v-if="!toggleForm && (isLoading || !filteredItems || filteredItems.length < 1)">
      <div class="column is-12">
        <Message v-if="isLoading" class="is-info" title="Loading" icon="fas fa-spinner fa-spin">
          Loading data. Please wait...
        </Message>
        <Message title="No Results" class="is-warning" icon="fas fa-search" v-else-if="query" :useClose="true"
          @close="query = ''">
          <p>No results found for the query: <code>{{ query }}</code>.</p>
          <p>Please try a different search term.</p>
        </Message>
        <Message v-else title="No items" class="is-warning" icon="fas fa-exclamation-circle">
          There are no custom defined conditions yet. Click the <span class="icon"><i class="fas fa-add" /></span>
          <strong>New Condition</strong> button to add your first condition.
        </Message>
      </div>
    </div>

    <div class="columns is-multiline" v-if="filteredItems && filteredItems.length > 0 && !toggleForm">
      <div class="column is-12">
        <Message class="is-info" :body_class="'pl-0'">
          <ul>
            <li>Filtering is based on yt-dlp’s <code>--match-filter</code> logic. Any expression that works with
              yt-dlp will also work here, including the same boolean operators. We added extended support for the
              <code>OR</code> ( <code>||</code> ) operator, which yt-dlp does not natively support. This allows you to
              combine multiple conditions more flexibly.
            </li>
            <li>
              The primary use case for this feature is to apply custom cli arguments to specific returned info.
            </li>
            <li>
              For example, i follow specific channel that sometimes region lock some videos, by using the following
              filter i am able to bypass it <code>availability = 'needs_auth' & channel_id = 'channel_id'</code>.
              and set proxy for that specific video, while leaving the rest of the videos to be downloaded normally.
            </li>
            <li>
              The data which the filter is applied on is the same data that yt-dlp returns, simply, click on the
              information button, and check the data to craft your filter. You will get instant feedback if the
              filter matches or not.
            </li>
          </ul>
        </Message>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import type { Condition } from '~/types/conditions'
import { useConfirm } from '~/composables/useConfirm'
import { useConditions } from '~/composables/useConditions'
import type { APIResponse } from '~/types/responses'

type ConditionItemWithUI = Condition & { raw?: boolean }

const socket = useSocketStore()
const box = useConfirm()
const isMobile = useMediaQuery({ maxWidth: 1024 })
const display_style = useStorage<'list' | 'grid'>('conditions_display_style', 'grid')
const conditions = useConditions()
const route = useRoute()

const items = conditions.conditions as Ref<ConditionItemWithUI[]>
const paging = conditions.pagination
const isLoading = conditions.isLoading
const page = ref<number>(route.query.page ? parseInt(route.query.page as string, 10) : 1)
const item = ref<Partial<Condition>>({})
const itemRef = ref<number | null | undefined>(null)
const toggleForm = ref(false)
const initialLoad = ref(true)
const query = ref<string>('')
const toggleFilter = ref(false)

const remove_keys = ['raw', 'toggle_description']
const expandedItems = reactive<Record<number, Set<string>>>({})

const filteredItems = computed<ConditionItemWithUI[]>(() => {
  const q = query.value?.toLowerCase();
  if (!q) return items.value;
  return items.value.filter((item: ConditionItemWithUI) => deepIncludes(item, q, new WeakSet()));
});

const loadContent = async (page: number = 1): Promise<void> => {
  await conditions.loadConditions(page)
  await nextTick()
  if (conditions.pagination.value.total_pages > 1) {
    useRouter().replace({ query: { ...route.query, page: page.toString() } })
  }
}

const toggleExpand = (itemId: number | undefined, field: string) => {
  if (!itemId) return

  if (!expandedItems[itemId]) {
    expandedItems[itemId] = new Set()
  }

  if (expandedItems[itemId].has(field)) {
    expandedItems[itemId].delete(field)
  } else {
    expandedItems[itemId].add(field)
  }
}

const isExpanded = (itemId: number | undefined, field: string): boolean => {
  if (!itemId) return false
  return expandedItems[itemId]?.has(field) ?? false
}

watch(() => socket.isConnected, async () => {
  if (socket.isConnected && initialLoad.value) {
    await loadContent(page.value)
    initialLoad.value = false
  }
})

watch(toggleFilter, val => {
  if (!val) {
    query.value = ''
  }
})

const resetForm = (closeForm = false): void => {
  item.value = {}
  itemRef.value = null
  if (closeForm) {
    toggleForm.value = false
  }
}

const deleteItem = async (cond: Condition): Promise<void> => {
  if (true !== (await box.confirm(`Delete '${cond.name}'?`))) {
    return
  }
  await conditions.deleteCondition(cond.id!)
}

const updateItem = async ({ reference, item: updatedItem }: {
  reference: number | null | undefined,
  item: Condition
}): Promise<void> => {
  updatedItem = cleanObject(updatedItem, remove_keys) as Condition
  const cb = (resp: APIResponse) => {
    if (resp.success) {
      resetForm(true)
    }
  }

  if (reference) {
    await conditions.patchCondition(reference, updatedItem, cb)
  } else {
    await conditions.createCondition(updatedItem, cb)
  }
}

const editItem = (_item: Condition): void => {
  item.value = { ..._item }
  itemRef.value = _item.id
  toggleForm.value = true
}

const toggleEnabled = async (cond: Condition): Promise<void> => {
  const new_state = !cond.enabled
  await conditions.patchCondition(cond.id!, { enabled: new_state })
}

const exportItem = (cond: Condition): void => copyText(encode({
  ...Object.fromEntries(Object.entries(cond).filter(([k, v]) => !!v && !['id', ...remove_keys].includes(k))),
  _type: 'condition',
  _version: '1.2',
}))

onMounted(async () => {
  if (socket.isConnected) {
    await loadContent(page.value)
  }
})
</script>
