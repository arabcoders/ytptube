<template>
  <div>
    <div class="mt-1 columns is-multiline">
      <div class="column is-12 is-clearfix is-unselectable">
        <span class="title is-4">
          <span class="icon-text">
            <template v-if="toggleForm">
              <span class="icon"><i class="fa-solid" :class="{ 'fa-edit': itemRef, 'fa-plus': !itemRef }" /></span>
              <span>{{ itemRef ? `Edit - ${item.name}` : 'Add new field' }}</span>
            </template>
            <template v-else>
              <span class="icon"><i class="fa-solid fa-file-lines" /></span>
              <span>Custom Fields</span>
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
                <span v-if="!isMobile">New Field</span>
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
            Custom fields allow you to add new fields to the download form.
          </span>
        </div>
      </div>

      <div class="column is-12" v-if="!toggleForm && paging?.total_pages > 1">
        <Pager :page="paging.page" :last_page="paging.total_pages" :isLoading="isLoading"
          @navigate="async (newPage) => { page = newPage; await loadContent(newPage); }" />
      </div>

      <div class="column is-12" v-if="toggleForm">
        <DLFieldForm :addInProgress="dlFields.addInProgress.value" :reference="itemRef" :item="(item as DLField)"
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
                  <span>Field</span>
                </th>
                <th width="20%">
                  <span class="icon"><i class="fa-solid fa-gear" /></span>
                  <span>Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="field in filteredItems" :key="field.id">
                <td class="is-vcentered">
                  <div class="is-text-overflow is-bold">
                    {{ field.name }}
                  </div>
                  <div class="is-unselectable">
                    <span class="icon-text">
                      <span class="icon"><i class="fa-solid fa-terminal" /></span>
                      <span>{{ field.field }}</span>
                    </span>
                    &nbsp;
                    <span class="icon-text">
                      <span class="icon"><i class="fa-solid fa-sort-numeric-down" /></span>
                      <span>Order: {{ field.order }}</span>
                    </span>
                  </div>
                </td>
                <td class="is-vcentered is-items-center">
                  <div class="field is-grouped is-grouped-centered">
                    <div class="control">
                      <button class="button is-info is-small is-fullwidth" @click="exportItem(field)">
                        <span class="icon"><i class="fa-solid fa-file-export" /></span>
                        <span v-if="!isMobile">Export</span>
                      </button>
                    </div>
                    <div class="control">
                      <button class="button is-warning is-small is-fullwidth" @click="editItem(field)">
                        <span class="icon"><i class="fa-solid fa-edit" /></span>
                        <span v-if="!isMobile">Edit</span>
                      </button>
                    </div>
                    <div class="control">
                      <button class="button is-danger is-small is-fullwidth" @click="deleteItem(field)">
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
        <div class="column is-6" v-for="field in filteredItems" :key="field.id">
          <div class="card is-flex is-full-height is-flex-direction-column">
            <header class="card-header">
              <div class="card-header-title is-text-overflow is-block" v-text="field.name" />
              <div class="card-header-icon">
                <div class="field is-grouped">
                  <div class="control">
                    <span class="tag is-dark">
                      <span class="icon"><i class="fa-solid fa-sort-numeric-down" /></span>
                      <span v-text="field.order" />
                    </span>
                  </div>
                  <div class="control">
                    <a class="has-text-info" v-tooltip="'Export item'" @click.prevent="exportItem(field)">
                      <span class="icon"><i class="fa-solid fa-file-export" /></span>
                    </a>
                  </div>
                </div>
              </div>
            </header>
            <div class="card-content is-flex-grow-1">
              <div class="content">
                <p class="is-text-overflow">
                  <span class="icon"><i class="fa-solid fa-terminal" /></span>
                  <span v-text="field.field" />
                </p>
                <p class="is-text-overflow" v-if="field.description">
                  <span class="icon"><i class="fa-solid fa-comment" /></span>
                  <span>{{ field.description }}</span>
                </p>
              </div>
            </div>
            <div class="card-footer mt-auto">
              <div class="card-footer-item">
                <button class="button is-warning is-fullwidth" @click="editItem(field)">
                  <span class="icon"><i class="fa-solid fa-edit" /></span>
                  <span>Edit</span>
                </button>
              </div>
              <div class="card-footer-item">
                <button class="button is-danger is-fullwidth" @click="deleteItem(field)">
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
          There are no custom defined fields yet. Click the <span class="icon"><i class="fas fa-add" /></span>
          <strong>New Field</strong> button to add your first field.
        </Message>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import type { DLField } from '~/types/dl_fields'
import { useConfirm } from '~/composables/useConfirm'
import { useDlFields } from '~/composables/useDlFields'
import type { APIResponse } from '~/types/responses'
import { copyText, encode } from '~/utils'

const box = useConfirm()
const isMobile = useMediaQuery({ maxWidth: 1024 })
const display_style = useStorage<'list' | 'grid'>('dl_fields_display_style', 'grid')
const dlFields = useDlFields()
const route = useRoute()

const items = dlFields.dlFields as Ref<DLField[]>
const paging = dlFields.pagination
const isLoading = dlFields.isLoading
const page = ref<number>(route.query.page ? parseInt(route.query.page as string, 10) : 1)
const item = ref<Partial<DLField>>({})
const itemRef = ref<number | null | undefined>(null)
const toggleForm = ref(false)
const query = ref<string>('')
const toggleFilter = ref(false)

const filteredItems = computed<DLField[]>(() => {
  const q = query.value?.toLowerCase()
  if (!q) return items.value
  return items.value.filter(entry => deepIncludes(entry, q, new WeakSet()))
})

const loadContent = async (pageNumber: number = 1): Promise<void> => {
  await dlFields.loadDlFields(pageNumber)
  await nextTick()
  if (dlFields.pagination.value.total_pages > 1) {
    useRouter().replace({ query: { ...route.query, page: pageNumber.toString() } })
  }
}

watch(toggleFilter, value => {
  if (!value) {
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

const deleteItem = async (field: DLField): Promise<void> => {
  if (true !== (await box.confirm(`Delete '${field.name}'?`))) {
    return
  }
  await dlFields.deleteDlField(field.id!)
}

const updateItem = async ({ reference, item: updatedItem }: {
  reference: number | null | undefined,
  item: DLField
}): Promise<void> => {
  const cb = (resp: APIResponse) => {
    if (resp.success) {
      resetForm(true)
    }
  }

  if (reference) {
    await dlFields.patchDlField(reference, updatedItem, cb)
  } else {
    await dlFields.createDlField(updatedItem, cb)
  }
}

const editItem = (field: DLField): void => {
  item.value = { ...field }
  itemRef.value = field.id
  toggleForm.value = true
}

const exportItem = (field: DLField): void => copyText(encode({
  ...Object.fromEntries(Object.entries(field).filter(([k, v]) => !!v && 'id' !== k)),
  _type: 'dl_field',
  _version: '1.0',
}))

onMounted(async () => await loadContent(page.value))
</script>
