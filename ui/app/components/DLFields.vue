<template>
  <form class="modal is-active" @submit.prevent="updateItems">
    <div class="modal-background" @click="cancel" />
    <div class="modal-card" style="min-width:calc(100vw - 30vw);">
      <header class="modal-card-head">
        <p class="modal-card-title">Manage Custom Fields</p>
        <button type="button" class="delete" aria-label="close" @click="cancel" />
      </header>
      <section class="modal-card-body">
        <div class="columns is-multiline">
          <div class="column is-12 is-clearfix is-unselectable">
            <div class="is-pulled-right">
              <div class="field is-grouped">
                <p class="control">
                  <button type="button" class="button is-primary" @click="addNewField" :disabled="isLoading">
                    <span class="icon"><i class="fas fa-add" /></span>
                  </button>
                </p>
                <p class="control">
                  <button type="button" class="button is-info" @click="loadContent()"
                    :class="{ 'is-loading': isLoading }" :disabled="isLoading">
                    <span class="icon"><i class="fas fa-refresh" /></span>
                  </button>
                </p>
              </div>
            </div>
          </div>

          <div class="column is-12" v-for="(item, index) in items" :key="item.id || index">
            <div class="box">
              <div class="columns is-multiline">
                <div class="column is-12 is-12-mobile">
                  <NuxtLink @click="deleteField(index)" :disabled="isLoading" class="has-text-danger">
                    <span class="icon"><i class="fas fa-trash" /></span>
                    <span>Delete Field</span>
                  </NuxtLink>
                </div>

                <div class="column is-6 is-12-mobile">
                  <div class="field">
                    <label class="label">Field Type</label>
                    <div class="select is-fullwidth" :class="{ 'is-loading': isLoading }">
                      <select v-model="item.kind" :disabled="isLoading" class="is-capitalized">
                        <option v-for="kind in Object.values(FieldTypes)" :key="`kind-${kind}`" :value="kind"
                          v-text="kind" />
                      </select>
                    </div>
                    <span class="help is-bold">
                      Field Type.
                    </span>
                  </div>
                </div>
                <div class="column is-6 is-12-mobile">
                  <div class="field">
                    <label class="label">Field Name</label>
                    <input type="text" v-model="item.name" class="input" :disabled="isLoading" />
                    <span class="help is-bold">
                      The name of the field, it will be shown in the UI.
                    </span>
                  </div>
                </div>
                <div class="column is-6 is-12-mobile">
                  <div class="field">
                    <label class="label">Associated yt-dlp option</label>
                    <input type="text" v-model="item.field" class="input" :disabled="isLoading" />
                    <span class="help is-bold">
                      The long form of yt-dlp option name, e.g. <code>--no-overwrites</code> not <code>-w</code>.
                    </span>
                  </div>
                </div>
                <div class="column is-6 is-12-mobile">
                  <div class="field">
                    <label class="label">Description</label>
                    <input type="text" v-model="item.description" class="input" :disabled="isLoading" />
                    <span class="help is-bold">
                      A short description of the field, it will be shown in the UI.
                    </span>
                  </div>
                </div>

                <!--
                <div class="column is-6 is-12-mobile">
                  <div class="field">
                    <label class="label is-unselectable" :for="`p-${index}`">Persist the value?</label>

                    <input :id="`p-${index}`" type="checkbox" v-model="item.extras.persist" :disabled="isLoading"
                      class="switch is-success" />
                    <label class="label is-unselectable" :for="`p-${index}`">
                      {{ item.extras?.persist ? 'Yes' : 'No' }}
                    </label>
                    <span class="help is-bold">If enabled the value will persist.</span>
                  </div>
                </div>

                <div class="column is-6 is-12-mobile">
                  <div class="field">
                    <label class="label">Value</label>
                    <input type="text" v-model="item.value" class="input" :disabled="true" />
                    <span class="help is-bold">
                      This field will be used in the future to store values for select type field.
                    </span>
                  </div>
                </div> -->

              </div>
            </div>
          </div>

          <div class="column is-12">
            <Message message_class="has-background-warning-90 has-text-dark" v-if="items.length === 0">
              <span class="icon">
                <i class="fas fa-exclamation-circle" />
              </span>
              <span>
                No custom fields found, you can add new fields using the button above.
              </span>
            </Message>
          </div>
        </div>
      </section>
      <footer class="modal-card-foot p-5">
        <div class="field is-grouped" style="width:100%">
          <div class="control is-expanded">
            <button type="submit" class="button is-fullwidth is-primary" :disabled="isLoading">
              <span class="icon"><i class="fas fa-save" /></span>
              <span>Save</span>
            </button>
          </div>
          <div class="control is-expanded">
            <button type="button" class="button is-fullwidth is-danger" @click="cancel" :disabled="isLoading">
              <span class="icon"><i class="fas fa-times" /></span>
              <span>Cancel</span>
            </button>
          </div>
        </div>
      </footer>
    </div>
  </form>
</template>

<script setup lang="ts">
import { defineEmits, ref } from 'vue'
import type { DLField } from '~/types/dl_fields'

const emitter = defineEmits<{ (e: 'cancel'): void }>()

const toast = useNotification()

const isLoading = ref<boolean>(false)
const items = ref<DLField[]>([])

const FieldTypes = {
  STRING: 'string',
  TEXT: 'text',
  BOOL: 'bool'
}

const cancel = () => emitter('cancel')

const loadContent = async () => {
  try {
    isLoading.value = true
    const response = await request('/api/dl_fields')

    const data = await response.json()
    if (0 === data.length) {
      return
    }

    items.value = data
  } catch (e: any) {
    console.error(e)
    toast.error('Failed to fetch page content.')
  } finally {
    isLoading.value = false
  }
}

const updateItems = async () => {

  for (const item of items.value) {
    if (validateItem(item, items.value.indexOf(item) + 1)) {
      continue
    }
    return
  }

  try {
    isLoading.value = true
    const resp = await request('/api/dl_fields', {
      method: 'PUT',
      body: JSON.stringify(items.value)
    })

    if (!resp.ok) {
      const error = await resp.json()
      toast.error(`Failed to update fields: ${error.error || 'Unknown error'}`)
      return
    }

    toast.success('Fields updated successfully.')
    emitter('cancel')
  } finally {
    isLoading.value = false
  }
}

const addNewField = () => items.value.push({
  name: '',
  description: '',
  kind: 'string',
  field: '',
  value: '',
  extras: {}
})


const deleteField = (index: number) => items.value.splice(index, 1)

const validateItem = (item: DLField, index: number): boolean => {

  const requiredFields = ['name', 'field', 'kind', 'description']

  for (const field of requiredFields) {
    if (!item[field as keyof DLField] || item[field as keyof DLField]?.trim() === '') {
      toast.error(`${item.name || index}: Field ${field} is required.`)
      return false
    }
  }

  if (!Object.values(FieldTypes).includes(item.kind)) {
    toast.error(`${item.name || index}: Invalid field type: ${item.kind}`)
    return false
  }

  if (!/^--[a-zA-Z0-9\-]+$/.test(item.field)) {
    toast.error(`${item.name || index}: Invalid field format, it must start with '--' and contain no spaces.`)
    return false
  }

  return true
}

onMounted(async () => await loadContent())
</script>
