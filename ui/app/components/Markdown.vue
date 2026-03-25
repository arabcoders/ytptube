<style>
.docs-markdown {
  min-width: 0;
  color: var(--ui-text);
  font-size: 0.975rem;
  line-height: 1.75;
}

.docs-markdown > :first-child {
  margin-top: 0 !important;
}

.docs-markdown > :last-child {
  margin-bottom: 0;
}

.docs-markdown :where(h1, h2, h3, h4, h5, h6) {
  margin-top: 1.75em;
  color: var(--ui-text-highlighted);
  font-weight: 700;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.docs-markdown h1 {
  font-size: clamp(1.85rem, 1.55rem + 1vw, 2.4rem);
}

.docs-markdown h2 {
  font-size: clamp(1.5rem, 1.3rem + 0.7vw, 1.95rem);
  padding-top: 0.35rem;
  border-top: 1px solid color-mix(in oklab, var(--ui-border) 80%, transparent);
}

.docs-markdown h3 {
  font-size: 1.3rem;
}

.docs-markdown h4 {
  font-size: 1.15rem;
}

.docs-markdown h5,
.docs-markdown h6 {
  font-size: 1rem;
}

.docs-markdown :where(p, ul, ol, pre, blockquote, .markdown-alert, .docs-markdown__table-wrap, hr) {
  margin-top: 1rem;
}

.docs-markdown :where(p, li, blockquote, th, td) {
  overflow-wrap: anywhere;
}

.docs-markdown :where(strong) {
  color: var(--ui-text-highlighted);
  font-weight: 700;
}

.docs-markdown :where(ul, ol) {
  padding-left: 1.5rem;
}

.docs-markdown ul {
  list-style: disc;
}

.docs-markdown ol {
  list-style: decimal;
}

.docs-markdown li + li {
  margin-top: 0.35rem;
}

.docs-markdown li > :where(ul, ol) {
  margin-top: 0.5rem;
}

.docs-markdown a {
  color: color-mix(in oklab, var(--ui-info) 60%, var(--ui-text-highlighted) 40%);
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 0.18em;
  overflow-wrap: anywhere;
}

.docs-markdown a:hover {
  color: var(--ui-text-highlighted);
}

.docs-markdown :not(pre) > code {
  display: inline;
  border: 1px solid color-mix(in oklab, var(--ui-border) 80%, transparent);
  border-radius: 0.45rem;
  background: color-mix(in oklab, var(--ui-bg-muted) 60%, var(--ui-bg) 40%);
  padding: 0.125rem 0.375rem;
  font-size: 0.875em;
  white-space: normal;
  overflow-wrap: anywhere;
}

.docs-markdown pre {
  max-width: 100%;
  overflow-x: auto;
  border: 1px solid color-mix(in oklab, var(--ui-border) 80%, transparent);
  border-radius: 0.9rem;
  background: color-mix(in oklab, var(--ui-bg-muted) 40%, var(--ui-bg) 60%);
  padding: 0.9rem 1rem;
}

.docs-markdown pre code {
  display: block;
  min-width: 0;
  background: transparent;
  border: 0;
  padding: 0;
  color: inherit;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.docs-markdown blockquote {
  border-left: 0.3rem solid color-mix(in oklab, var(--ui-info) 60%, var(--ui-border) 40%);
  border-radius: 0.85rem;
  background: color-mix(in oklab, var(--ui-info) 7%, var(--ui-bg) 93%);
  padding: 0.95rem 1rem;
  color: var(--ui-text-toned);
}

.docs-markdown blockquote > :first-child,
.docs-markdown blockquote > :first-child > :first-child,
.markdown-alert > :first-child {
  margin-top: 0;
}

.docs-markdown blockquote > :last-child,
.markdown-alert > :last-child {
  margin-bottom: 0;
}

.docs-markdown hr {
  border: 0;
  border-top: 1px solid color-mix(in oklab, var(--ui-border) 85%, transparent);
}

.docs-markdown__table-wrap {
  max-width: 100%;
  overflow-x: auto;
  border: 1px solid color-mix(in oklab, var(--ui-border) 85%, transparent);
  border-radius: 0.95rem;
  background: var(--ui-bg);
}

.docs-markdown__table {
  width: max-content;
  min-width: 100%;
  border-collapse: separate;
  border-spacing: 0;
}

.docs-markdown__table :where(th, td) {
  min-width: 0;
  padding: 0.75rem 0.9rem;
  border-right: 1px solid color-mix(in oklab, var(--ui-border) 70%, transparent);
  border-bottom: 1px solid color-mix(in oklab, var(--ui-border) 70%, transparent);
  text-align: left;
  vertical-align: top;
}

.docs-markdown__table :where(th:last-child, td:last-child) {
  border-right: 0;
}

.docs-markdown__table thead th {
  background: color-mix(in oklab, var(--ui-bg-muted) 60%, var(--ui-bg) 40%);
  color: var(--ui-text-toned);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.docs-markdown__table tbody tr:nth-child(odd) {
  background: color-mix(in oklab, var(--ui-bg-muted) 24%, var(--ui-bg) 76%);
}

.docs-markdown__table tbody tr:hover {
  background: color-mix(in oklab, var(--ui-bg-elevated) 65%, var(--ui-bg-muted) 35%);
}

.docs-markdown__table tbody tr:last-child td {
  border-bottom: 0;
}

.docs-markdown img {
  display: block;
  max-width: 100%;
  height: auto;
  border: 1px solid color-mix(in oklab, var(--ui-border) 75%, transparent);
  border-radius: 0.9rem;
}

.markdown-alert {
  --markdown-alert-accent: color-mix(in oklab, var(--ui-border-accented) 70%, transparent);
  margin-top: 1rem;
  border: 1px solid color-mix(in oklab, var(--markdown-alert-accent) 35%, var(--ui-border) 65%);
  border-left-width: 0.35rem;
  border-left-color: var(--markdown-alert-accent);
  border-radius: 0.9rem;
  background: color-mix(in oklab, var(--markdown-alert-accent) 9%, var(--ui-bg) 91%);
  padding: 0.9rem 1rem;
  color: inherit;
}

.markdown-alert-title {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.45rem;
  color: color-mix(in oklab, var(--markdown-alert-accent) 70%, var(--ui-text-highlighted) 30%);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  user-select: none;
}

.markdown-alert-note {
  --markdown-alert-accent: var(--ui-info);
}

.markdown-alert-tip {
  --markdown-alert-accent: var(--ui-success);
}

.markdown-alert-important {
  --markdown-alert-accent: color-mix(in oklab, var(--ui-primary) 60%, var(--ui-info) 40%);
}

.markdown-alert-warning {
  --markdown-alert-accent: var(--ui-warning);
}

.markdown-alert-caution {
  --markdown-alert-accent: var(--ui-error);
}
</style>

<template>
  <div class="relative min-h-64 min-w-0">
    <div v-if="isLoading" class="flex min-h-64 items-center justify-center text-toned">
      <UIcon name="i-lucide-loader-circle" class="size-10 animate-spin" />
    </div>

    <UAlert
      v-else-if="error"
      color="warning"
      variant="soft"
      icon="i-lucide-triangle-alert"
      title="Error"
      :description="error"
    />

    <div v-else class="docs-markdown min-w-0 max-w-none" v-html="content" @click="handleClick" />
  </div>
</template>

<script setup lang="ts">
import { Marked } from 'marked';
import { baseUrl } from 'marked-base-url';
import markedAlert from 'marked-alert';
import { gfmHeadingId } from 'marked-gfm-heading-id';
import { resolveDocsImageSrc, resolveDocsLink } from '~/composables/useDocs';
import { parse_api_error, request } from '~/utils';

type MarkdownToken = {
  type: string;
  href?: string;
  title?: string | null;
  text?: string;
  tokens?: Array<unknown>;
  header?: Array<{ tokens: Array<unknown> }>;
  rows?: Array<Array<{ tokens: Array<unknown> }>>;
  _external?: boolean;
  _docRoute?: string;
  _isExternalImage?: boolean;
};

const props = defineProps<{ file: string }>();

const content = ref('');
const error = ref('');
const isLoading = ref(true);

const createMarkdownParser = () => {
  const parser = new Marked();

  parser.use(gfmHeadingId());
  parser.use(baseUrl(window.origin));
  parser.use(markedAlert());
  parser.use({
    gfm: true,
    hooks: {
      postprocess: (text: string) =>
        text.replace(
          /<!--\s*?i:([\w.-]+)\s*?-->/gi,
          (_, list) =>
            `<span class="icon"><i class="fas ${list
              .split('.')
              .map((name: string) => name.trim())
              .join(' ')}"></i></span>`,
        ),
    },
    walkTokens: (token: MarkdownToken) => {
      if (token.type === 'link' && token.href) {
        const resolved = resolveDocsLink(token.href);
        token.href = resolved.href;
        token._external = resolved.external;
        token._docRoute = resolved.docRoute;
        return;
      }

      if (token.type === 'image' && token.href) {
        const resolvedHref = resolveDocsImageSrc(token.href);
        token._isExternalImage = /^https?:\/\//i.test(resolvedHref);
        token.href = resolvedHref;
      }
    },
    renderer: {
      link(token: MarkdownToken) {
        const inlineTokens = Array.isArray(token.tokens) ? (token.tokens as any[]) : [];
        const text = this.parser.parseInline(inlineTokens as any);
        const title = token.title ? ` title="${token.title}"` : '';
        const attrs = token._external ? ' target="_blank" rel="noopener noreferrer"' : '';
        const docRoute = token._docRoute ? ` data-doc-route="${token._docRoute}"` : '';
        return `<a href="${token.href || ''}"${docRoute}${title}${attrs}>${text}</a>`;
      },
      table(token: MarkdownToken) {
        const headerHtml = `<thead><tr>${(token.header || [])
          .map((cell) => {
            const inlineTokens = Array.isArray((cell as any).tokens)
              ? ((cell as any).tokens as any[])
              : [];
            return `<th>${this.parser.parseInline(inlineTokens as any)}</th>`;
          })
          .join('')}</tr></thead>`;

        const bodyHtml = (token.rows || [])
          .map((row) => {
            const columns = row
              .map((cell) => {
                const inlineTokens = Array.isArray((cell as any).tokens)
                  ? ((cell as any).tokens as any[])
                  : [];
                return `<td>${this.parser.parseInline(inlineTokens as any)}</td>`;
              })
              .join('');

            return `<tr>${columns}</tr>`;
          })
          .join('');

        return `<div class="docs-markdown__table-wrap"><table class="docs-markdown__table">\n${headerHtml}\n<tbody>\n${bodyHtml}\n</tbody>\n</table></div>`;
      },
      image(token: MarkdownToken) {
        const alt = token.text ? ` alt="${token.text}"` : ' alt=""';
        const title = token.title ? ` title="${token.title}"` : '';
        const refPolicy = ' referrerpolicy="no-referrer"';
        const crossorigin = token._isExternalImage ? ' crossorigin="anonymous"' : '';
        const loading = ' loading="lazy"';
        return `<img src="${token.href || ''}"${alt}${title}${refPolicy}${crossorigin}${loading} />`;
      },
    },
  });

  return parser;
};

const loader = async (file: string) => {
  if (!file) {
    content.value = '';
    error.value = '';
    isLoading.value = false;
    return;
  }

  try {
    isLoading.value = true;
    error.value = '';
    content.value = '';
    const markdownParser = createMarkdownParser();

    const response = await request(`${file}?_=${Date.now()}`, {
      headers: {
        Accept: 'text/plain',
      },
    });

    if (!response.ok) {
      let message = response.statusText || 'Failed to load documentation';

      try {
        message = await parse_api_error(response.json());
      } catch {}

      error.value = message;
      return;
    }

    const text = await response.text();
    content.value = String(markdownParser.parse(text));
  } catch (e: unknown) {
    console.error(e);
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    isLoading.value = false;
  }
};

const handleClick = async (event: MouseEvent) => {
  const target = (event.target as HTMLElement | null)?.closest(
    'a[data-doc-route]',
  ) as HTMLAnchorElement | null;

  if (!target) {
    return;
  }

  const href = target.getAttribute('data-doc-route');
  if (!href) {
    return;
  }

  event.preventDefault();
  await navigateTo(href);
};

watch(
  () => props.file,
  async (file) => {
    if (import.meta.server) {
      return;
    }

    await loader(file);
  },
  { immediate: true },
);
</script>
