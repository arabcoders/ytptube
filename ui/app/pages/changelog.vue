<style scoped>
.logs-container {
  padding: 1rem;
  min-width: 100%;
  max-height: 73vh;
  overflow-y: auto;
  overflow-x: auto;
}

hr {
  background-color: unset;
  border-bottom: 1px solid var(--bulma-grey-light) !important
}
</style>

<template>
  <main>
    <div class="mt-1 columns is-multiline">
      <div class="column is-12 is-clearfix is-unselectable">
        <span class="title is-4">
          <span class="icon"><i class="fas fa-cogs" /></span>
          CHANGELOG
        </span>

        <div class="is-hidden-mobile">
          <span class="subtitle">This page display the latest changes and updates from the project.</span>
        </div>
      </div>
    </div>

    <div class="columns is-multiline" v-if="isLoading">
      <div class="column is-12">
        <Message message_class="has-background-info-90 has-text-dark" title="Loading" icon="fas fa-spinner fa-spin"
          message="Loading data. Please wait..." />
      </div>
    </div>

    <template v-if="!isLoading">
      <div class="logs-container">
        <div class="columns is-multiline">
          <div class="column p-0 m-0 is-12" v-for="(log, index) in logs" :key="log.tag">
            <div class="content p-0 m-0">
              <h1 class="is-4">
                <span class="icon"><i class="fas fa-code-branch" /></span>
                {{ log.tag }} <span class="tag has-text-success" v-if="isInstalled(log)">Installed</span>
              </h1>
              <hr>
              <ul>
                <li v-for="commit in log.commits" :key="commit.sha">
                  <strong>
                    {{ ucFirst(commit.message).replace(/\.$/, "") }}.
                  </strong> -
                  <small>
                    <NuxtLink :to="`${REPO}/commit/${commit.full_sha}`" target="_blank">
                      <span class="has-tooltip" v-tooltip="`SHA: ${commit.full_sha} - Date: ${commit.date}`">
                        {{ moment(commit.date).fromNow() }}
                      </span>
                    </NuxtLink>
                    <span v-tooltip="'Code is at this commit.'" v-if="commit.full_sha === app_sha" class="icon has-text-success"><i
                        class="fas fa-check" /></span>
                  </small>
                </li>
              </ul>
              <hr v-if="index < logs.length - 1">
            </div>
          </div>
        </div>
      </div>
    </template>
  </main>
</template>

<script setup lang="ts">
import moment from 'moment'
import type { changelogs, changeset } from '~/types/changelogs'

const toast = useNotification()
const config = useConfigStore()

useHead({ title: 'CHANGELOG' })

const PROJECT = 'ytptube'
const REPO = `https://github.com/arabcoders/${PROJECT}`
const REPO_URL = `https://arabcoders.github.io/${PROJECT}/CHANGELOG.json?version={version}`

const logs = ref<changelogs>([])
const app_version = ref('')
const app_branch = ref('')
const app_sha = ref('')
const isLoading = ref(true)

const loadContent = async () => {
  if ('' === app_version.value || logs.value.length > 0) {
    return
  }

  try {
    try {
      const changes = await fetch(REPO_URL.replace('{branch}', app_branch.value).replace('{version}', app_version.value))
      logs.value = await changes.json()
    } catch (e) {
      console.error(e)
      logs.value = await (await request(uri('/CHANGELOG.json'), { method: 'GET' })).json()
    }

    await nextTick()
    logs.value = logs.value.slice(0, 10)
  } catch (e: any) {
    console.error(e)
    toast.error(`Failed to fetch changelog. ${e.message}`)
  } finally {
    isLoading.value = false
  }
}

const isInstalled = (log: changeset) => {
  const installed = String(app_sha.value)

  if (log.full_sha.startsWith(installed)) {
    return true
  }

  for (const commit of log?.commits ?? []) {
    if (commit.full_sha.startsWith(installed)) {
      return true
    }
  }

  return false
}

onMounted(async () => {
  await awaiter(config.isLoaded)
  app_branch.value = config.app.app_branch
  app_version.value = config.app.app_version
  app_sha.value = config.app.app_commit_sha
  loadContent()
})
</script>
