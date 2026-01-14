<style>
.markdown-alert {
  padding: 0 1em;
  margin-bottom: 16px;
  color: inherit;
  border-left: 0.25em solid #444c56;
}

.markdown-alert-title {
  display: inline-flex;
  align-items: center;
  font-weight: 500;
  text-transform: uppercase;
  user-select: none;
}

.markdown-alert-note {
  border-left-color: #539bf5;
}

.markdown-alert-tip {
  border-left-color: #57ab5a;
}

.markdown-alert-important {
  border-left-color: #986ee2;
}

.markdown-alert-warning {
  border-left-color: #c69026;
}

.markdown-alert-caution {
  border-left-color: #e5534b;
}

.markdown-alert-note>.markdown-alert-title {
  color: #539bf5;
}

.markdown-alert-tip>.markdown-alert-title {
  color: #57ab5a;
}

.markdown-alert-important>.markdown-alert-title {
  color: #986ee2;
}

.markdown-alert-warning>.markdown-alert-title {
  color: #c69026;
}

.markdown-alert-caution>.markdown-alert-title {
  color: #e5534b;
}

code {
  word-break: break-word !important
}
</style>

<template>
  <div>
    <div class="modal is-active">

      <div class="modal-background" @click="emitter('closeModel')"></div>

      <div class="modal-content modal-content-max">
        <div style="font-size:30vh; width: 99%" class="has-text-centered" v-if="isLoading">
          <i class="fas fa-circle-notch fa-spin" />
        </div>

        <div style="position: relative" v-if="!isLoading">
          <Message v-if="error" class="is-warning" title="Error" icon="fas fa-exclamation">
            {{ error }}
          </Message>
          <div class="card" v-else>
            <div class="card-body p-4">
              <div class="content" v-html="content" />
            </div>
          </div>
        </div>

      </div>

    </div>

  </div>

</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, onUpdated } from 'vue'
import { marked } from 'marked'
import { baseUrl } from 'marked-base-url'
import markedAlert from 'marked-alert'
import { gfmHeadingId } from 'marked-gfm-heading-id'
import Message from '~/components/Message.vue'

const props = defineProps<{ file: string }>()
const emitter = defineEmits<{ (e: 'closeModel'): void }>()

const urls = ['FAQ.md', 'README.md', 'API.md', 'sc_short.jpg', 'sc_simple.jpg']

const content = ref<string>('')
const error = ref<string>('')
const isLoading = ref<boolean>(true)

const handleClick = async (e: MouseEvent) => {
  const target = (e.target as HTMLElement)?.closest('a') as HTMLAnchorElement | null
  if (!target) {
    return
  }
  const href = target.getAttribute('data-url')
  if (!href) {
    return
  }

  e.preventDefault()
  await loader(href)
}

const addListeners = (): void => {
  removeListeners()
  document.querySelectorAll('.content a').forEach((l: Element): void => {
    const href = l.getAttribute('data-url')
    if (!href) {
      return
    }

    (l as HTMLElement).addEventListener('click', handleClick)
  })
}

const removeListeners = (): void => {
  document.querySelectorAll('.content a').forEach((l: Element): void => {
    const href = l.getAttribute('data-url')
    if (!href) {
      return
    }

    (l as HTMLElement).removeEventListener('click', handleClick)
  })
}

const loader = async (file: string) => {
  try {
    isLoading.value = true
    const response = await fetch(`${file}?_=${Date.now()}`)
    if (true !== response.ok) {
      const err = await response.json()
      error.value = err.error.message
      return
    }

    const text = await response.text()

    marked.use(gfmHeadingId())
    marked.use(baseUrl(window.origin))
    marked.use(markedAlert())
    marked.use({
      gfm: true,
      hooks: {
        postprocess: (text: string) => text.replace(
          /<!--\s*?i:([\w.-]+)\s*?-->/gi,
          (_, list) => `<span class="icon"><i class="fas ${list.split('.').map((n: string) => n.trim()).join(' ')}"></i></span>`
        )
      },
      walkTokens: (token: any) => {
        if (token.type !== 'link') {
          return
        }
        if (token.href.startsWith('#')) {
          return
        }

        if (urls.some(l => token.href.includes(l))) {
          const name = urls.find(l => token.href.includes(l)) || ''
          token._external = false
          token.href = `/${name}`
        } else {
          token._external = true
        }
      },
      renderer: {
        link(token: any) {
          const text = this.parser.parseInline(token.tokens)
          const title = token.title ? ` title="${token.title}"` : ''
          const attrs = token._external ? ' target="_blank" rel="noopener noreferrer"' : ''
          let local = ''
          const name = urls.find(l => token.href.includes(l)) || ''
          if (name) {
            local = ` data-url="/api/docs/${name}"`
          }

          return `<a href="${token.href}"${local}${title}${attrs}>${text}</a>`
        },
        table(token: any) {
          // `token.header` and `token.rows` are available
          // Use default table output from built-in renderer to get header + body markup
          // Then wrap with classed <table>

          // We need to generate the inner HTML parts first
          const headerHtml = `<thead><tr>${token.header.map((cell: any) => `<th>${this.parser.parseInline(cell.tokens)}</th>`).join('')}</tr></thead>`

          const bodyHtml = (token.rows || []).map((row: any[]) => {
            const tr = row.map((cell: any) => {
              return `<td>${this.parser.parseInline(cell.tokens)}</td>`
            }).join('')
            return `<tr>${tr}</tr>`
          }).join('')

          return `<div class="table-container"><table class="table is-striped is-hoverable is-fullwidth is-bordered">\n${headerHtml}\n<tbody>\n${bodyHtml}\n</tbody>\n</table></div>`
        },
        image(token: any) {
          const alt = token.text ? ` alt="${token.text}"` : ' alt=""'
          const title = token.title ? ` title="${token.title}"` : ''
          const refPolicy = ' referrerpolicy="no-referrer"'
          const crossorigin = token._isExternalImage ? ' crossorigin="anonymous"' : ''
          const loading = ' loading="lazy"'
          return `<img src="${token.href}"${alt}${title}${refPolicy}${crossorigin}${loading} />`
        },
      },
    })

    content.value = String(marked.parse(text))

  } catch (e: any) {
    console.error(e)
    error.value = e.message
  } finally {
    isLoading.value = false
  }
}

onMounted(async () => loader(props.file))
onUpdated(() => addListeners())
onBeforeUnmount(() => removeListeners())
</script>
