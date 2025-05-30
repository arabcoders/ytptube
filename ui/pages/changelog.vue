<template>
  <div>
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
    <div class="column is-12" v-for="(log, index) in logs" :key="log.tag">
      <div class="content">
        <h1 class="is-4">
          <span class="icon-text">
            <span class="icon"><i class="fas fa-code-branch"></i></span>
            <span>
              {{ log.tag }} <span class="tag has-text-success" v-if="isInstalled(log.tag)">Installed</span>
            </span>
          </span>
        </h1>
        <hr>
        <ul>
          <li v-for="commit in log.commits" :key="commit.sha">
            <strong>{{ ucFirst(commit.message).replace(/\.$/, "") }}.</strong> -
            <small>
              <NuxtLink :to="`https://github.com/arabcoders/watchstate/commit/${commit.sha}`" target="_blank">
                <span class="has-tooltip" v-tooltip="`SHA: ${commit.sha} - Date: ${commit.date}`">
                  {{ moment(commit.date).fromNow() }}
                </span>
              </NuxtLink>
            </small>
          </li>
        </ul>
        <hr v-if="index < logs.length - 1">
      </div>
    </div>
  </div>
</template>
<script setup>
import moment from 'moment'

useHead({ title: 'Change log' })

const REPO_URL = "https://arabcoders.github.io/ytptube/CHANGELOG-{branch}.json?version={version}";
const logs = ref([]);
const config = useConfigStore()
const api_version = ref('')
const toast = useToast()

const branch = computed(() => {
  const branch = String(api_version.value).split('-')[0] ?? 'master';
  return ['master', 'dev'].includes(branch) ? branch : 'master';
});

watch(() => config.app.version, async value => {
  if (!value) {
    return
  }

  api_version.value = value

  await nextTick();
  await loadContent();
}, { immediate: true })

const loadContent = async () => {
  if ('' === api_version.value) {
    return
  }

  try {
    const changes = await fetch(r(REPO_URL, { branch: branch.value, version: api_version.value }));
    logs.value = await changes.json();
  } catch (e) {
    console.error(e);
    notification('error', 'Error', `Failed to fetch changelog. ${e.message}`);
  }
}

const isInstalled = tag => {
  const installed = String(api_version.value).split('-').pop();
  return tag.endsWith(installed);
}

onMounted(() => loadContent());
</script>
