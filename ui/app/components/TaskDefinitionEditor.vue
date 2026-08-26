<template>
  <div class="space-y-6">
    <UAlert
      v-if="validationError && hasEditorContent"
      color="warning"
      variant="soft"
      icon="i-lucide-triangle-alert"
      :title="validationError"
      class="sticky top-0 z-10 shadow-sm"
    />

    <div class="flex flex-wrap items-center gap-2">
      <UButton
        type="button"
        color="neutral"
        variant="ghost"
        size="sm"
        :icon="showImport ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
        :disabled="isBusy"
        @click="
          () => {
            showImport = !showImport;
          }
        "
      >
        {{ showImport ? t('common.hideImport') : t('common.showImport') }}
      </UButton>
    </div>

    <div
      v-if="showImport"
      class="grid gap-4 rounded-lg border border-default bg-muted/10 p-4 lg:grid-cols-2"
    >
      <UFormField
        v-if="editorDefinitions.length"
        :ui="fieldUi"
        :description="t('common.prefillFromDef')"
      >
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-copy" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.importFromExisting') }}</span>
          </div>
        </template>

        <USelectMenu
          v-model="selectedExistingValue"
          :items="existingDefinitionItems"
          :placeholder="t('common.selectDefinition')"
          value-key="value"
          label-key="label"
          color="neutral"
          class="w-full"
          :ui="{ content: 'min-w-[13rem]', item: 'ps-6' }"
          :search-input="{ placeholder: t('common.searchPresets') }"
          :disabled="isBusy"
          @update:model-value="importExisting"
        />
      </UFormField>

      <UFormField :ui="fieldUi" :description="t('common.importStringDesc')">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-import" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.importString') }}</span>
          </div>
        </template>

        <UFieldGroup size="lg" class="w-full">
          <UInput
            v-model="importString"
            type="text"
            autocomplete="off"
            class="min-w-0 flex-1"
            :ui="inputUi"
            :disabled="isBusy"
            dir="ltr"
          />

          <UButton
            type="button"
            color="neutral"
            variant="outline"
            icon="i-lucide-import"
            class="justify-center sm:min-w-28"
            :disabled="isBusy || !importString.trim()"
            @click="importFromString"
          >
            {{ t('common.import') }}
          </UButton>
        </UFieldGroup>
      </UFormField>
    </div>

    <UAlert
      v-if="loading"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      :title="t('common.loading')"
      :description="t('common.loadingData')"
    />

    <UAlert
      v-if="!guiSupported"
      color="warning"
      variant="soft"
      icon="i-lucide-triangle-alert"
      :title="t('common.advancedModeRequired')"
      :description="guiDiagnostics || t('common.advancedModeRequiredDesc')"
    />

    <template v-if="mode === 'gui'">
      <div class="grid gap-4 md:grid-cols-12">
        <UFormField
          class="md:col-span-6"
          :ui="fieldUi"
          :description="t('common.definitionNameDesc')"
        >
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-type" class="size-4 text-toned" />
              <span class="font-semibold text-default">{{ t('common.name') }}</span>
            </div>
          </template>

          <UInput
            v-model="guiState.name"
            type="text"
            class="w-full"
            :ui="inputUi"
            :disabled="isBusy"
          />
        </UFormField>

        <UFormField
          class="md:col-span-3"
          :ui="fieldUi"
          :description="t('common.definitionPriorityDesc')"
        >
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-list-ordered" class="size-4 text-toned" />
              <span class="font-semibold text-default">{{ t('common.priority') }}</span>
            </div>
          </template>

          <UInput
            v-model.number="guiState.priority"
            type="number"
            min="0"
            class="w-full"
            :ui="inputUi"
            :disabled="isBusy"
          />
        </UFormField>

        <UFormField class="md:col-span-3" :ui="fieldUi">
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-power" class="size-4 text-toned" />
              <span class="font-semibold text-default">{{ t('common.status') }}</span>
            </div>
          </template>
          <template #description>
            <span>&nbsp;</span>
          </template>

          <div
            class="flex min-h-11 items-center rounded-md border border-default bg-elevated/40 px-3"
          >
            <USwitch v-model="guiState.enabled" :disabled="isBusy" />
            <span class="ms-3 text-sm text-default">{{
              guiState.enabled ? t('common.enabled') : t('common.disabled')
            }}</span>
          </div>
        </UFormField>

        <UFormField
          class="md:col-span-12"
          :ui="fieldUi"
          :description="t('common.matchPatternsDesc')"
        >
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-link" class="size-4 text-toned" />
              <span class="font-semibold text-default">{{ t('common.matchPatterns') }}</span>
            </div>
          </template>

          <UTextarea
            v-model="guiState.matchText"
            :rows="4"
            placeholder="https://example.com/*&#10;/https\:\/\/example\.org\/channel\/\d+/"
            class="w-full"
            :ui="textareaUi"
            :disabled="isBusy"
            dir="ltr"
          />
        </UFormField>
      </div>

      <div class="space-y-5 border-t border-default pt-5">
        <div class="space-y-4">
          <div class="space-y-1">
            <div
              class="flex items-center justify-between gap-2 text-sm font-semibold text-highlighted"
            >
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-settings-2" class="size-4 text-toned" />
                <span>{{ t('common.requestSetup') }}</span>
              </div>
              <UButton
                type="button"
                color="neutral"
                :variant="showAdvancedRequestOptions ? 'soft' : 'outline'"
                size="sm"
                icon="i-lucide-settings-2"
                :aria-label="
                  showAdvancedRequestOptions ? t('common.hideOptions') : t('common.showOptions')
                "
                :aria-expanded="showAdvancedRequestOptions"
                aria-controls="request-advanced-options"
                class="shrink-0"
                :disabled="isBusy"
                @click="showAdvancedRequestOptions = !showAdvancedRequestOptions"
              >
                {{ showAdvancedRequestOptions ? t('common.hideOptions') : t('common.showOptions') }}
              </UButton>
            </div>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <UFormField :ui="fieldUi" :description="t('common.engineDesc')">
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-cpu" class="size-4 text-toned" />
                  <span class="font-semibold text-default">{{ t('common.engine') }}</span>
                </div>
              </template>

              <USelect
                v-model="guiState.engineType"
                :items="engineItems"
                value-key="value"
                label-key="label"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
                dir="ltr"
              />
            </UFormField>

            <UFormField :ui="fieldUi" :description="t('common.requestMethodDesc')">
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-arrow-right-left" class="size-4 text-toned" />
                  <span class="font-semibold text-default">{{ t('common.requestMethod') }}</span>
                </div>
              </template>
              <USelect
                v-model="guiState.requestMethod"
                :items="requestMethodItems"
                value-key="value"
                label-key="label"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
                dir="ltr"
              />
            </UFormField>

            <UFormField :ui="fieldUi" :description="t('common.requestUrlDesc')">
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-link" class="size-4 text-toned" />
                  <span class="font-semibold text-default">{{ t('common.requestUrl') }}</span>
                </div>
              </template>
              <UInput
                v-model="guiState.requestUrl"
                type="url"
                placeholder="https://example.com/feed"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
                dir="ltr"
              />
            </UFormField>

            <UFormField
              v-if="guiState.engineType === 'browser'"
              :ui="fieldUi"
              :description="t('common.browserEndpointUrlDesc')"
            >
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-server" class="size-4 text-toned" />
                  <span class="font-semibold text-default">{{
                    t('common.browserEndpointUrl')
                  }}</span>
                </div>
              </template>
              <UInput
                v-model="guiState.engineUrl"
                type="url"
                placeholder="http://chrome:9222"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
                dir="ltr"
              />
            </UFormField>

            <UFormField
              v-if="guiState.requestMethod === 'POST'"
              :class="guiState.engineType === 'browser' ? '' : 'md:col-span-2'"
              :ui="fieldUi"
              :description="t('common.requestBodyTypeDesc')"
            >
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-braces" class="size-4 text-toned" />
                  <span class="font-semibold text-default">{{ t('common.requestBodyType') }}</span>
                </div>
              </template>

              <USelect
                v-model="guiState.requestBodyType"
                :items="requestBodyTypeItems"
                value-key="value"
                label-key="label"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
              />
            </UFormField>

            <UFormField
              v-if="guiState.requestMethod === 'POST' && guiState.requestBodyType === 'raw'"
              class="md:col-span-2"
              :ui="fieldUi"
              :description="t('common.requestBodyDesc')"
            >
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-file-json" class="size-4 text-toned" />
                  <span class="font-semibold text-default">{{ t('common.requestBody') }}</span>
                </div>
              </template>

              <UTextarea
                v-model="guiState.requestBody"
                :rows="5"
                :placeholder="requestBodyPlaceholder"
                class="w-full"
                :ui="textareaUi"
                :disabled="isBusy"
                dir="ltr"
              />
            </UFormField>

            <div
              v-if="
                guiState.requestMethod === 'POST' &&
                ['form', 'json'].includes(guiState.requestBodyType)
              "
              class="space-y-3 md:col-span-2"
            >
              <div class="flex flex-wrap items-center justify-between gap-2">
                <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
                  <UIcon name="i-lucide-file-json" class="size-4 text-toned" />
                  <span>{{ t('common.requestBody') }}</span>
                </div>
                <UButton
                  type="button"
                  color="neutral"
                  variant="outline"
                  size="sm"
                  icon="i-lucide-plus"
                  :disabled="isBusy"
                  @click="addRequestPair('body')"
                >
                  {{ t('common.add') }}
                </UButton>
              </div>
              <p class="text-sm text-toned">
                {{
                  guiState.requestBodyType === 'json'
                    ? t('common.requestJsonFieldsDesc')
                    : t('common.requestFormFieldsDesc')
                }}
              </p>

              <UTextarea
                v-if="guiState.requestBodyType === 'json' && guiState.requestJsonFallback"
                v-model="guiState.requestJsonText"
                :rows="6"
                class="w-full"
                :ui="textareaUi"
                :disabled="isBusy"
                dir="ltr"
              />

              <div
                v-for="(pair, index) in guiState.requestBodyPairs"
                :key="`request-body-${index}`"
                class="grid gap-2 rounded-lg border border-default bg-muted/20 p-3"
                :class="
                  guiState.requestBodyType === 'form'
                    ? 'md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto]'
                    : 'md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]'
                "
                dir="ltr"
              >
                <UInput
                  v-model="pair.key"
                  :placeholder="t('common.keyLabel')"
                  :disabled="isBusy"
                  :ui="inputUi"
                />
                <template v-if="guiState.requestBodyType === 'form'">
                  <USelect
                    v-model="pair.type"
                    :items="scalarTypeItems"
                    value-key="value"
                    label-key="label"
                    :ui="inputUi"
                    :disabled="isBusy"
                  />
                  <USelect
                    v-if="pair.type === 'boolean'"
                    v-model="pair.value"
                    :items="booleanValueItems"
                    value-key="value"
                    label-key="label"
                    :ui="inputUi"
                    :disabled="isBusy"
                  />
                  <UInput
                    v-else-if="pair.type !== 'null'"
                    v-model="pair.value"
                    :placeholder="t('common.valueLabel')"
                    :disabled="isBusy"
                    :ui="inputUi"
                  />
                  <UInput v-else disabled placeholder="null" :ui="inputUi" />
                </template>
                <UInput
                  v-else
                  v-model="pair.value"
                  :placeholder="t('common.jsonValue')"
                  :disabled="isBusy"
                  :ui="inputUi"
                />
                <UButton
                  type="button"
                  color="neutral"
                  variant="outline"
                  icon="i-lucide-trash"
                  :aria-label="t('common.remove')"
                  :disabled="isBusy"
                  @click="guiState.requestBodyPairs.splice(index, 1)"
                />
              </div>
            </div>
          </div>
        </div>

        <div
          id="request-advanced-options"
          v-if="showAdvancedRequestOptions"
          class="grid gap-4 md:grid-cols-2"
        >
          <template v-if="guiState.engineType === 'http'">
            <UFormField :ui="fieldUi" :description="t('common.impersonateDesc')">
              <template #label>{{ t('common.impersonate') }}</template>
              <USelectMenu
                v-model="httpImpersonate"
                :items="impersonateTargetItems"
                :search-input="true"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy || !impersonateTargetItems.length"
                dir="ltr"
              />
            </UFormField>
            <UFormField :ui="fieldUi" :description="t('common.curlDefaultHeadersDesc')">
              <template #label>{{ t('common.curlDefaultHeaders') }}</template>
              <div
                class="flex min-h-11 items-center rounded-md border border-default bg-elevated/40 px-3"
              >
                <USwitch v-model="curlDefaultHeaders" :disabled="isBusy" />
              </div>
            </UFormField>
            <UFormField :ui="fieldUi" :description="t('common.flaresolverrDesc')">
              <template #label>{{ t('common.flaresolverr') }}</template>
              <div
                class="flex min-h-11 items-center rounded-md border border-default bg-elevated/40 px-3"
              >
                <USwitch v-model="flaresolverr" :disabled="isBusy" />
              </div>
            </UFormField>
          </template>

          <template v-if="guiState.engineType === 'browser'">
            <UFormField :ui="fieldUi" :description="t('common.waitForDesc')">
              <template #label>{{ t('common.waitFor') }}</template>
              <div class="grid gap-2 sm:grid-cols-2">
                <USelect
                  v-model="browserWaitType"
                  :items="waitTypeItems"
                  value-key="value"
                  label-key="label"
                  :ui="inputUi"
                  :disabled="isBusy"
                />
                <UInput
                  v-model="browserWaitExpression"
                  :placeholder="t('common.waitExpression')"
                  :ui="inputUi"
                  :disabled="isBusy"
                  dir="ltr"
                />
              </div>
            </UFormField>
            <UFormField :ui="fieldUi" :description="t('common.waitTimeoutDesc')">
              <template #label>{{ t('common.waitTimeout') }}</template>
              <UInput
                v-model="browserWaitTimeout"
                type="number"
                min="0"
                max="300"
                step="any"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
                dir="ltr"
              />
            </UFormField>
            <UFormField :ui="fieldUi" :description="t('common.pageLoadTimeoutDesc')">
              <template #label>{{ t('common.pageLoadTimeout') }}</template>
              <UInput
                v-model="pageLoadTimeout"
                type="number"
                min="0"
                max="300"
                step="any"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
                dir="ltr"
              />
            </UFormField>
          </template>

          <UFormField :ui="fieldUi" :description="t('common.requestTimeoutDesc')">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-timer" class="size-4 text-toned" />
                <span class="font-semibold text-default">{{ t('common.requestTimeout') }}</span>
              </div>
            </template>
            <UInput
              v-model="guiState.requestTimeout"
              type="number"
              min="0"
              step="any"
              placeholder="120"
              class="w-full"
              :ui="inputUi"
              :disabled="isBusy"
              dir="ltr"
            />
          </UFormField>

          <div class="space-y-3">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
                <UIcon name="i-lucide-list-plus" class="size-4 text-toned" />
                <span>{{ t('common.queryParameters') }}</span>
              </div>
              <UButton
                type="button"
                color="neutral"
                variant="outline"
                size="sm"
                icon="i-lucide-plus"
                :disabled="isBusy"
                @click="addRequestPair('params')"
              >
                {{ t('common.add') }}
              </UButton>
            </div>
            <p class="text-sm text-toned">{{ t('common.queryParametersDesc') }}</p>
            <div
              v-for="(param, index) in guiState.requestParams"
              :key="`request-param-${index}`"
              class="grid gap-2 rounded-lg border border-default bg-muted/20 p-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto]"
              dir="ltr"
            >
              <UInput
                v-model="param.key"
                :placeholder="t('common.keyLabel')"
                :disabled="isBusy"
                :ui="inputUi"
              />
              <USelect
                v-model="param.type"
                :items="scalarTypeItems"
                value-key="value"
                label-key="label"
                :ui="inputUi"
                :disabled="isBusy"
              />
              <USelect
                v-if="param.type === 'boolean'"
                v-model="param.value"
                :items="booleanValueItems"
                value-key="value"
                label-key="label"
                :ui="inputUi"
                :disabled="isBusy"
              />
              <UInput
                v-else-if="param.type !== 'null'"
                v-model="param.value"
                :placeholder="t('common.valueLabel')"
                :disabled="isBusy"
                :ui="inputUi"
              />
              <UInput v-else disabled placeholder="null" :ui="inputUi" />
              <UButton
                type="button"
                color="neutral"
                variant="outline"
                icon="i-lucide-trash"
                :aria-label="t('common.remove')"
                :disabled="isBusy"
                @click="guiState.requestParams.splice(index, 1)"
              />
            </div>
          </div>

          <div class="space-y-3">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
                <UIcon name="i-lucide-key-round" class="size-4 text-toned" />
                <span>{{ t('common.requestHeaders') }}</span>
              </div>
              <UButton
                type="button"
                color="neutral"
                variant="outline"
                size="sm"
                icon="i-lucide-plus"
                :disabled="isBusy"
                @click="addRequestPair('headers')"
              >
                {{ t('common.add') }}
              </UButton>
            </div>
            <p class="text-sm text-toned">{{ t('common.requestHeadersDesc') }}</p>
            <div
              v-for="(header, index) in guiState.requestHeaders"
              :key="`request-header-${index}`"
              class="grid gap-2 rounded-lg border border-default bg-muted/20 p-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
              dir="ltr"
            >
              <UInput
                v-model="header.key"
                :placeholder="t('common.keyLabel')"
                :disabled="isBusy"
                :ui="inputUi"
              />
              <UInput
                v-model="header.value"
                :placeholder="t('common.valueLabel')"
                :disabled="isBusy"
                :ui="inputUi"
              />
              <UButton
                type="button"
                color="neutral"
                variant="outline"
                icon="i-lucide-trash"
                :aria-label="t('common.remove')"
                :disabled="isBusy"
                @click="guiState.requestHeaders.splice(index, 1)"
              />
            </div>
          </div>
        </div>

        <div class="space-y-4">
          <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
            <UIcon name="i-lucide-list-tree" class="size-4 text-toned" />
            <span>{{ t('common.parseSetup') }}</span>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <UFormField :ui="fieldUi" :description="t('common.responseTypeDesc')">
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-file-output" class="size-4 text-toned" />
                  <span class="font-semibold text-default">{{ t('common.responseType') }}</span>
                </div>
              </template>
              <USelect
                v-model="guiState.responseType"
                :items="responseTypeItems"
                value-key="value"
                label-key="label"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
              />
            </UFormField>

            <UFormField :ui="fieldUi" :description="t('common.parseModeDesc')">
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-list-tree" class="size-4 text-toned" />
                  <span class="font-semibold text-default">{{ t('common.parseMode') }}</span>
                </div>
              </template>
              <USelect
                v-model="guiState.parseMode"
                :items="parseModeItems"
                value-key="value"
                label-key="label"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
              />
            </UFormField>
          </div>
        </div>

        <div v-if="guiState.parseMode === 'container'" class="space-y-4">
          <div class="space-y-1">
            <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
              <UIcon name="i-lucide-list-tree" class="size-4 text-toned" />
              <span>{{ t('common.containerSelector') }}</span>
            </div>
          </div>

          <div class="grid gap-4 md:grid-cols-12">
            <UFormField class="md:col-span-4" :ui="fieldUi" :description="t('common.selectorType')">
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-shapes" class="size-4 text-toned" />
                  <span class="font-semibold text-default">{{ t('common.type') }}</span>
                </div>
              </template>

              <USelect
                v-model="guiState.containerType"
                :items="containerTypeItems"
                value-key="value"
                label-key="label"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
                dir="ltr"
              />
            </UFormField>

            <UFormField
              class="md:col-span-8"
              :ui="fieldUi"
              :description="t('common.matchExpression')"
            >
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-crosshair" class="size-4 text-toned" />
                  <span class="font-semibold text-default">{{
                    t('common.selectorExpression')
                  }}</span>
                </div>
              </template>

              <UInput
                v-model="guiState.containerSelector"
                type="text"
                placeholder="div.card"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
                dir="ltr"
              />
            </UFormField>
          </div>
        </div>
      </div>

      <div class="space-y-4 border-t border-default pt-5">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div class="space-y-1">
            <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
              <UIcon name="i-lucide-braces" class="size-4 text-toned" />
              <span>{{ t('common.extractedFields') }}</span>
            </div>
          </div>

          <UButton
            type="button"
            color="neutral"
            variant="outline"
            size="sm"
            icon="i-lucide-plus"
            :disabled="isBusy"
            @click="addField"
          >
            {{ t('common.add') }}
          </UButton>
        </div>

        <div class="w-full min-w-0 overflow-x-auto overscroll-x-contain ytp-table-surface">
          <table class="table-fixed w-full text-sm" dir="ltr">
            <thead class="bg-elevated/60 text-xs uppercase tracking-wide text-toned">
              <tr
                class="text-start [&>th]:border-e [&>th]:border-default/60 [&>th]:px-2 [&>th]:py-2.5 [&>th]:font-semibold [&>th:last-child]:border-e-0"
              >
                <th class="w-28">
                  <span class="inline-flex items-center gap-1.5">
                    <UIcon name="i-lucide-key" class="size-3.5 text-toned" />
                    <span>{{ t('common.keyLabel') }}</span>
                  </span>
                </th>
                <th class="w-28">
                  <span class="inline-flex items-center gap-1.5">
                    <UIcon name="i-lucide-shapes" class="size-3.5 text-toned" />
                    <span>{{ t('common.fieldType') }}</span>
                  </span>
                </th>
                <th class="w-auto">
                  <span class="inline-flex items-center gap-1.5">
                    <UIcon name="i-lucide-code" class="size-3.5 text-toned" />
                    <span>{{ t('common.fieldExpression') }}</span>
                  </span>
                </th>
                <th class="w-28">
                  <span class="inline-flex items-center gap-1.5">
                    <UIcon name="i-lucide-at-sign" class="size-3.5 text-toned" />
                    <span>{{ t('common.fieldAttribute') }}</span>
                  </span>
                </th>
                <th class="w-40">{{ t('common.filter') }}</th>
                <th class="w-12">
                  <span class="inline-flex items-center gap-1.5">
                    <UIcon name="i-lucide-trash-2" class="size-3.5 text-toned" />
                  </span>
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-default">
              <tr v-if="!guiState.fields.length">
                <td colspan="6" class="px-2 py-6 text-center text-sm text-toned">
                  {{ t('common.noExtractorFields') }}
                </td>
              </tr>
              <tr
                v-for="(field, index) in guiState.fields"
                :key="`${index}-${field.key}`"
                class="align-top [&>td]:border-e [&>td]:border-default/60 [&>td:last-child]:border-e-0"
              >
                <td class="px-2 py-2">
                  <UInput
                    v-model="field.key"
                    type="text"
                    class="w-full"
                    :ui="inputUi"
                    :disabled="isBusy"
                    dir="ltr"
                  />
                </td>
                <td class="px-2 py-2">
                  <USelect
                    v-model="field.type"
                    :items="fieldTypeItems"
                    value-key="value"
                    label-key="label"
                    class="w-full"
                    :ui="inputUi"
                    :disabled="isBusy"
                    dir="ltr"
                  />
                </td>
                <td class="px-2 py-2">
                  <UInput
                    v-model="field.expression"
                    type="text"
                    class="w-full"
                    :ui="inputUi"
                    :disabled="isBusy"
                    dir="ltr"
                  />
                </td>
                <td class="px-2 py-2">
                  <UInput
                    v-model="field.attribute"
                    type="text"
                    :placeholder="t('common.optional')"
                    class="w-full"
                    :ui="inputUi"
                    :disabled="isBusy"
                    dir="ltr"
                  />
                </td>
                <td class="px-2 py-2">
                  <div class="space-y-2">
                    <UInput
                      v-model="field.postFilter.filter"
                      :placeholder="t('common.filter')"
                      :ui="inputUi"
                      :disabled="isBusy"
                      dir="ltr"
                    />
                    <UInput
                      v-model="field.postFilter.value"
                      :placeholder="t('common.optional')"
                      :ui="inputUi"
                      :disabled="isBusy"
                      dir="ltr"
                    />
                  </div>
                </td>
                <td class="px-2 py-2 text-end">
                  <UButton
                    type="button"
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-trash"
                    square
                    :disabled="isBusy"
                    @click="removeField(index)"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <UAlert
        v-if="guiError"
        color="error"
        variant="soft"
        icon="i-lucide-circle-alert"
        :title="t('common.unableToBuildDef')"
        :description="guiError"
      />
    </template>

    <template v-else>
      <UFormField :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-file-code-2" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.rawJson') }}</span>
          </div>
        </template>

        <UTextarea
          v-model="jsonText"
          :rows="22"
          spellcheck="false"
          :readonly="submitting"
          class="w-full font-mono text-sm"
          :ui="advancedTextareaUi"
          dir="ltr"
        />
      </UFormField>

      <UAlert
        v-if="errorMessage"
        color="error"
        variant="soft"
        icon="i-lucide-circle-alert"
        :title="t('common.invalidJson')"
        :description="errorMessage"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { useTaskDefinitionEditor } from '~/composables/useTaskDefinitionEditor';
import type { TaskDefinitionDocument, TaskDefinitionSummary } from '~/types/task_definitions';

const props = defineProps<{
  title?: string;
  document: TaskDefinitionDocument | null;
  loading?: boolean;
  submitting?: boolean;
  availableDefinitions?: readonly TaskDefinitionSummary[];
  impersonateTargets?: readonly string[];
  initialShowImport?: boolean;
}>();

const emit = defineEmits<{
  (e: 'submit', payload: TaskDefinitionDocument): void;
  (e: 'dirty-change' | 'valid-change', value: boolean): void;
  (e: 'import-existing', id: number): void;
}>();

const editor = useTaskDefinitionEditor(props, emit);
const {
  t,
  submit,
  buildDocument,
  beautify,
  switchMode,
  advancedMode,
  guiSupported,
  isBusy,
  mode,
  submitting: editorSubmitting,
  availableDefinitions: editorDefinitions,
  impersonateTargets: impersonateTargetItems,
} = editor;
const {
  jsonText,
  errorMessage,
  guiError,
  showImport,
  importString,
  selectedExistingValue,
  guiState,
  showAdvancedRequestOptions,
  guiDiagnostics,
  fieldUi,
  inputUi,
  textareaUi,
  advancedTextareaUi,
  engineItems,
  requestMethodItems,
  requestBodyTypeItems,
  parseModeItems,
  responseTypeItems,
  waitTypeItems,
  requestBodyPlaceholder,
  httpImpersonate,
  curlDefaultHeaders,
  flaresolverr,
  browserWaitType,
  browserWaitExpression,
  browserWaitTimeout,
  pageLoadTimeout,
  containerTypeItems,
  fieldTypeItems,
  scalarTypeItems,
  booleanValueItems,
  existingDefinitionItems,
  hasEditorContent,
  validationError,
  addField,
  removeField,
  addRequestPair,
  importFromString,
  importExisting,
} = editor;
defineExpose({
  submit,
  beautify,
  switchMode,
  advancedMode,
  guiSupported,
  isBusy,
  mode,
  submitting: editorSubmitting,
  buildDocument,
});
</script>
