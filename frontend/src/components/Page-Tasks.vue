<template>
  <div class="mt-3 is-unselectable">
    <p class="title is-3">
      <span class="icon-text">
        <span class="icon">
          <font-awesome-icon icon="fa-solid fa-tasks" />
        </span>
        <span>Tasks</span>
      </span>
    </p>
    <p class="subtitle is-4 has-text-danger">
      This section is not working yet.
    </p>
  </div>

  <div class="columns is-multiline">
    <div class="column is-12 has-text-right">
      <button class="button is-primary" @click="$emit('task_new')">
        <span class="icon-text">
          <span class="icon">
            <font-awesome-icon icon="fa-solid fa-plus" />
          </span>
          <span>New Task</span>
        </span>
      </button>
    </div>

    <div class="column is-12">
      <div class="table-container">
        <table class="table is-bordered is-narrow is-hoverable is-striped is-fullwidth is-fixed">
          <thead class="has-text-centered">
            <tr>
              <th class="has-text-centered" width="20%">Name</th>
              <th class="has-text-centered" width="50%">URL</th>
              <th class="has-text-centered" width="20%">Timer</th>
              <th class="has-text-centered" width="10%">Options</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item, key in tasks" :key="key">
              <td class="is-text-overflow has-text-centered" v-if="item.name">{{ item.name }}</td>
              <td class="has-text-centered" v-else>Not set</td>
              <td class="is-text-overflow">
                <a :href="item.url" target="_blank">
                  {{ item.url }}
                </a>
              </td>
              <td class="has-text-centered" v-if="item.timer">{{ item.timer }}</td>
              <td class="has-text-centered" v-else>once an hour</td>
              <td class="has-text-centered">
                <div class="field is-grouped">
                  <div class="control is-expanded">
                    <button class="button is-small is-danger" @click="$emit('removeTask', key, item)"
                      data-tooltip="Remove task">
                      <span class="icon">
                        <font-awesome-icon icon="fa-solid fa-trash" />
                      </span>
                    </button>
                  </div>
                  <div class="control is-expanded">
                    <button class="button is-small is-info" data-tooltip="Modify task">
                      <span class="icon">
                        <font-awesome-icon icon="fa-solid fa-cog" />
                      </span>
                    </button>
                  </div>
                </div>
              </td>
            </tr>
            <tr v-if="tasks.length < 1">
              <td colspan="4" class="has-text-centered has-text-danger">
                No tasks are defined.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue'

defineEmits(['task_new', 'task_add', 'removeTask', 'tasks_updated'])

defineProps({
  tasks: {
    type: Array,
    required: true
  }
})

</script>

<style scoped>
table.is-fixed {
  table-layout: fixed;
}

div.table-container {
  overflow: hidden;
}
</style>
