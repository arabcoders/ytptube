<template>
  <h1 class="mt-3 is-size-3 is-clickable is-unselectable">
    <span class="icon-text title is-4">
      <span class="icon"><font-awesome-icon icon="fa-solid fa-tasks" /></span>
      <span>Tasks</span>
    </span>
  </h1>

  <div class="columns is-multiline">
    <div class="column is-12">
      <div class="table-container">
        <table class="table is-bordered is-narrow is-hoverable is-striped is-fullwidth is-fixed">
          <thead class="has-text-centered">
            <tr>
              <th class="has-text-centered" width="25%">Name</th>
              <th class="has-text-centered" width="50%">URL</th>
              <th class="has-text-centered" width="25%">Next run</th>
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
              <td class="has-text-centered" v-if="item.timer">
                <span v-tooltip="'Timer: ' + item.timer">
                  {{ moment(parseExpression(item.timer).next().toISOString()).fromNow() }}
                </span>
              </td>
              <td class="has-text-centered" v-else>once an hour</td>
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
import { defineProps } from 'vue'
import moment from "moment";
import { parseExpression } from 'cron-parser';

defineProps({
  tasks: {
    type: Array,
    required: true
  },
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
