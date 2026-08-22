import { computed, nextTick, reactive, ref, watch } from 'vue';
import { decode, prettyName } from '~/utils';
import { useDirtyState } from '~/composables/useDirtyState';
import { useDialog } from '~/composables/useDialog';
import {
  EditorInputError,
  analyzeTaskDefinition,
  clearStaleFields,
  cloneEditorState,
  defaultEditorState,
  defaultField,
  fromGui as buildGuiDocument,
  formatEditorDiagnostics,
  hasAdvancedRequestOptions,
  parseImportedDocument as normalizeImport,
  staleFields,
  toGui,
  type EditorMode,
  type EditorState,
} from '~/utils/taskDefinitionEditor';
import type { TaskDefinitionDocument, TaskDefinitionSummary } from '~/types/task_definitions';

type Props = {
  title?: string;
  document: TaskDefinitionDocument | null;
  loading?: boolean;
  submitting?: boolean;
  availableDefinitions?: readonly TaskDefinitionSummary[];
  impersonateTargets?: readonly string[];
  initialShowImport?: boolean;
};
type Emit = {
  (event: 'submit', payload: TaskDefinitionDocument): void;
  (event: 'dirty-change' | 'valid-change', payload: boolean): void;
  (event: 'import-existing', payload: number): void;
};

export const useTaskDefinitionEditor = (props: Props, emit: Emit) => {
  const { t } = useI18n();
  const { confirmDialog } = useDialog();
  const translateError = (error: unknown, fallback: string): Error =>
    error instanceof EditorInputError
      ? new Error(
          t(`common.${error.code}`, {
            ...error.params,
            ...(error.params.label ? { label: t(`common.${error.params.label}`) } : {}),
            ...(error.params.key ? { key: t(`common.${error.params.key}`) } : {}),
          }),
        )
      : error instanceof Error
        ? error
        : new Error(t(fallback));
  const fromGui = (state: EditorState): TaskDefinitionDocument => {
    try {
      return buildGuiDocument(state);
    } catch (error) {
      throw translateError(error, 'common.unableToBuildDef');
    }
  };
  const parseImportedDocument = (payload: unknown): TaskDefinitionDocument => {
    try {
      return normalizeImport(payload);
    } catch (error) {
      throw translateError(error, 'common.unableToImportDefinition');
    }
  };
  const jsonText = ref('');
  const errorMessage = ref<string | null>(null);
  const guiError = ref<string | null>(null);
  const guiSupported = ref(true);
  const mode = ref<EditorMode>('gui');
  const showImport = ref(false);
  const showAdvancedRequestOptions = ref(false);
  const importString = ref('');
  const selectedExisting = ref<number | null>(null);
  const selectedExistingValue = computed<number | undefined>({
    get: () => selectedExisting.value ?? undefined,
    set: (value) => {
      selectedExisting.value = value ?? null;
    },
  });

  const availableDefinitions = computed(() => props.availableDefinitions ?? []);
  const impersonateTargets = computed(() => [...(props.impersonateTargets ?? [])]);

  const guiState = reactive<EditorState>(defaultEditorState());

  const loading = computed(() => props.loading ?? false);
  const submitting = computed(() => props.submitting ?? false);
  const isBusy = computed(() => loading.value || submitting.value);
  const advancedMode = computed(() => mode.value === 'advanced');
  const guiDiagnostics = ref('');

  const fieldUi = {
    label: 'font-semibold text-default',
    container: 'space-y-2',
    description: 'text-sm text-toned',
    hint: 'text-sm text-toned',
  };

  const inputUi = {
    root: 'w-full',
    base: 'w-full bg-elevated/60 ring-default focus-visible:ring-primary',
  };

  const textareaUi = {
    root: 'w-full',
    base: 'min-h-[8rem] w-full bg-elevated/60 ring-default focus-visible:ring-primary',
  };

  const advancedTextareaUi = {
    root: 'w-full',
    base: 'min-h-[24rem] w-full bg-elevated/60 font-mono text-sm ring-default focus-visible:ring-primary',
  };

  const engineItems = [
    { label: 'HTTP', value: 'http' },
    { label: 'Browser', value: 'browser' },
  ];

  const requestMethodItems = [
    { label: 'GET', value: 'GET' },
    { label: 'POST', value: 'POST' },
  ];

  const requestBodyTypeItems = computed(() => [
    { label: t('common.requestBodyNone'), value: 'none' },
    { label: t('common.requestTypeForm'), value: 'form' },
    { label: t('common.requestTypeJson'), value: 'json' },
    { label: t('common.requestBodyRaw'), value: 'raw' },
  ]);

  const parseModeItems = computed(() => [
    { label: t('common.parseContainer'), value: 'container' },
    { label: t('common.parseDirect'), value: 'direct' },
  ]);

  const responseTypeItems = computed(() => [
    { label: t('common.responseHtml'), value: 'html' },
    { label: t('common.requestTypeJson'), value: 'json' },
  ]);

  const waitTypeItems = [
    { label: 'CSS', value: 'css' },
    { label: 'XPath', value: 'xpath' },
  ];

  const requestBodyPlaceholder = computed(() =>
    guiState.requestBodyType === 'raw' ? 'key=value' : '{\n  "key": "value"\n}',
  );

  const httpImpersonate = computed<string>({
    get: () =>
      typeof guiState.engineOptions.impersonate === 'string'
        ? guiState.engineOptions.impersonate
        : 'chrome',
    set: (value) => {
      if (value) guiState.engineOptions.impersonate = value;
      else delete guiState.engineOptions.impersonate;
    },
  });

  const curlDefaultHeaders = computed<boolean>({
    get: () => guiState.engineOptions.curl_default_headers !== false,
    set: (value) => {
      if (value) guiState.engineOptions.curl_default_headers = true;
      else guiState.engineOptions.curl_default_headers = false;
    },
  });

  const flaresolverr = computed<boolean>({
    get: () => guiState.engineOptions.flaresolverr === true,
    set: (value) => {
      if (value) guiState.engineOptions.flaresolverr = true;
      else delete guiState.engineOptions.flaresolverr;
    },
  });

  const browserWaitType = computed<string>({
    get: () => {
      const wait = guiState.engineOptions.wait_for;
      const options =
        wait && typeof wait === 'object' && !Array.isArray(wait)
          ? (wait as Record<string, unknown>)
          : null;
      return options?.type === 'xpath' ? 'xpath' : 'css';
    },
    set: (value) => {
      const wait = guiState.engineOptions.wait_for;
      guiState.engineOptions.wait_for = {
        ...(wait && typeof wait === 'object' && !Array.isArray(wait)
          ? (wait as Record<string, unknown>)
          : {}),
        type: value,
      };
    },
  });

  const browserWaitExpression = computed<string>({
    get: () => {
      const wait = guiState.engineOptions.wait_for;
      const options =
        wait && typeof wait === 'object' && !Array.isArray(wait)
          ? (wait as Record<string, unknown>)
          : null;
      return typeof options?.expression === 'string' ? options.expression : '';
    },
    set: (value) => {
      const wait = guiState.engineOptions.wait_for;
      const options =
        wait && typeof wait === 'object' && !Array.isArray(wait)
          ? (wait as Record<string, unknown>)
          : null;
      if (!value) {
        if (options) delete options.expression;
        return;
      }
      guiState.engineOptions.wait_for = {
        ...(options ?? {}),
        expression: value,
      };
    },
  });

  const browserWaitTimeout = computed<string>({
    get: () =>
      typeof guiState.engineOptions.wait_timeout === 'number'
        ? String(guiState.engineOptions.wait_timeout)
        : '',
    set: (value) => {
      if (value.trim()) guiState.engineOptions.wait_timeout = Number(value);
      else delete guiState.engineOptions.wait_timeout;
    },
  });

  const pageLoadTimeout = computed<string>({
    get: () =>
      typeof guiState.engineOptions.page_load_timeout === 'number'
        ? String(guiState.engineOptions.page_load_timeout)
        : '',
    set: (value) => {
      if (value.trim()) guiState.engineOptions.page_load_timeout = Number(value);
      else delete guiState.engineOptions.page_load_timeout;
    },
  });

  const containerTypeItems = [
    { label: 'CSS', value: 'css' },
    { label: 'XPath', value: 'xpath' },
    { label: 'JSONPath', value: 'jsonpath' },
  ];

  const scalarTypeItems = computed(() => [
    { label: t('common.fieldTypeString'), value: 'string' },
    { label: t('common.valueNumber'), value: 'number' },
    { label: t('common.valueBoolean'), value: 'boolean' },
    { label: t('common.valueNull'), value: 'null' },
  ]);

  const booleanValueItems = [
    { label: 'true', value: 'true' },
    { label: 'false', value: 'false' },
  ];

  const fieldTypeItems = [
    { label: 'CSS', value: 'css' },
    { label: 'XPath', value: 'xpath' },
    { label: 'Regex', value: 'regex' },
    { label: 'JSONPath', value: 'jsonpath' },
  ];

  const existingDefinitionItems = computed(() => {
    return availableDefinitions.value.map((item) => ({
      label: prettyName(item.name || String(item.id)),
      value: item.id,
    }));
  });

  const dirtySource = computed(() => ({
    mode: mode.value,
    showImport: showImport.value,
    importString: importString.value,
    selectedExisting: selectedExisting.value,
    jsonText: jsonText.value,
    guiState: JSON.parse(JSON.stringify(guiState)),
  }));
  const { isDirty, markClean } = useDirtyState(dirtySource);

  const resetEditorState = (state: EditorState): void => {
    Object.assign(guiState, cloneEditorState(state));
  };

  const addField = (): void => {
    guiState.fields.push(defaultField());
  };

  const removeField = (index: number): void => {
    guiState.fields.splice(index, 1);
  };

  const addRequestPair = (type: 'params' | 'headers' | 'body'): void => {
    const pair = { key: '', value: '', type: 'string' as const };
    if (type === 'params') {
      guiState.requestParams.push(pair);
    } else if (type === 'headers') {
      guiState.requestHeaders.push(pair);
    } else {
      guiState.requestBodyPairs.push(pair);
    }
  };

  const confirmStaleFields = async (): Promise<boolean> => {
    const fields = staleFields(guiState);
    if (!fields.length) {
      return true;
    }

    const { status } = await confirmDialog({
      title: t('common.pleaseConfirm'),
      message: t('common.stripFieldsConfirm', {
        fields: fields.map((field) => `- ${field}`).join('\n'),
      }),
      confirmText: t('common.continue'),
      confirmColor: 'warning',
    });
    if (status) {
      clearStaleFields(guiState);
    }
    return status;
  };

  const hasEditorContent = computed(() => {
    if (mode.value === 'advanced') {
      return Boolean(jsonText.value.trim());
    }

    return Boolean(
      guiState.name.trim() ||
      guiState.matchText.trim() ||
      guiState.containerSelector.trim() ||
      guiState.engineUrl.trim() ||
      guiState.requestUrl.trim() ||
      guiState.requestTimeout.trim() ||
      guiState.requestBody.trim() ||
      guiState.requestBodyPairs.some((item) => item.key || item.value) ||
      guiState.requestParams.some((item) => item.key || item.value) ||
      guiState.requestHeaders.some((item) => item.key || item.value) ||
      guiState.fields.some((field) => field.key.trim() || field.expression.trim()),
    );
  });

  const validationError = computed(() => {
    if (mode.value === 'gui') {
      try {
        fromGui(guiState);
        return '';
      } catch (error) {
        return error instanceof Error ? error.message : t('common.unableToBuildDef');
      }
    }

    if (!jsonText.value.trim()) {
      return t('common.validationDefinitionEmpty');
    }

    try {
      const parsed = JSON.parse(jsonText.value) as unknown;
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
        return t('common.validationDefinitionObject');
      }
      const diagnostics = analyzeTaskDefinition(parsed);
      if (diagnostics.length) {
        return formatEditorDiagnostics(diagnostics);
      }
    } catch (error) {
      return error instanceof Error ? error.message : t('common.invalidJsonDocument');
    }

    return '';
  });
  watch(
    validationError,
    (value) => {
      emit('valid-change', !value);
      if (!value) {
        if (mode.value === 'gui') {
          guiError.value = null;
        } else {
          errorMessage.value = null;
        }
      }
    },
    { immediate: true },
  );

  const parseDocument = (): TaskDefinitionDocument | null => {
    try {
      if (!jsonText.value.trim()) {
        throw new Error(t('common.validationDefinitionEmpty'));
      }

      const parsed = JSON.parse(jsonText.value) as unknown;
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
        throw new Error(t('common.validationDefinitionObject'));
      }

      const document = parsed as TaskDefinitionDocument;
      errorMessage.value = null;
      return document;
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : t('common.invalidJsonDocument');
      return null;
    }
  };

  const applyDocument = (document: TaskDefinitionDocument | null): void => {
    const shouldShowImport = props.initialShowImport ?? !document;
    showImport.value = shouldShowImport;
    importString.value = '';
    selectedExisting.value = null;
    guiError.value = null;
    errorMessage.value = null;
    guiDiagnostics.value = '';

    if (!document) {
      showAdvancedRequestOptions.value = false;
      jsonText.value = '';
      guiSupported.value = true;
      resetEditorState({
        name: '',
        priority: 0,
        enabled: true,
        matchText: '',
        engineType: 'http',
        engineUrl: '',
        engineOptions: {},
        parseMode: 'container',
        requestMethod: 'GET',
        requestUrl: '',
        requestTimeout: '',
        requestBodyType: 'none',
        requestBody: '',
        requestJsonText: '',
        requestJsonFallback: false,
        requestBodyPairs: [],
        requestParams: [],
        requestHeaders: [],
        containerType: 'css',
        containerSelector: '',
        fields: [defaultField()],
        responseType: 'html',
      });
      nextTick(() => {
        markClean();
        emit('dirty-change', false);
        emit('valid-change', !validationError.value);
      });
      return;
    }

    try {
      jsonText.value = JSON.stringify(document, null, 2);
      const gui = toGui(document);
      const diagnostics = analyzeTaskDefinition(document);
      if (gui && !diagnostics.length) {
        guiSupported.value = true;
        resetEditorState(gui);
        showAdvancedRequestOptions.value = hasAdvancedRequestOptions(gui);
        if (mode.value !== 'gui') {
          mode.value = 'gui';
        }
      } else {
        guiSupported.value = false;
        mode.value = 'advanced';
        guiDiagnostics.value =
          formatEditorDiagnostics(diagnostics) || t('common.advancedModeRequiredDesc');
      }
    } catch (error) {
      console.error('Failed to prepare definition for editing.', error);
      jsonText.value = '';
      guiSupported.value = false;
      mode.value = 'advanced';
      errorMessage.value = t('common.failedPrepareDefinition');
    }

    nextTick(() => {
      markClean();
      emit('dirty-change', false);
      emit('valid-change', !validationError.value);
    });
  };

  const importFromString = (): void => {
    if (isBusy.value) {
      return;
    }

    if (!importString.value.trim()) {
      guiError.value = t('common.importStringEmpty');
      return;
    }

    try {
      const decoded = decode(importString.value.trim());
      const document = parseImportedDocument(decoded);
      applyDocument(document);
      importString.value = '';
      showImport.value = false;
    } catch (error) {
      guiError.value =
        error instanceof Error ? error.message : t('common.unableToImportDefinition');
    }
  };

  const importExisting = (): void => {
    if (!selectedExisting.value || isBusy.value) {
      return;
    }

    emit('import-existing', Number(selectedExisting.value));
    selectedExisting.value = null;
  };

  watch(
    () => props.document,
    (doc) => applyDocument(doc),
    { immediate: true },
  );

  watch(isDirty, (value: boolean) => emit('dirty-change', value));

  const switchMode = async (next: EditorMode): Promise<void> => {
    if (isBusy.value || next === mode.value) {
      return;
    }

    if (next === 'gui') {
      if (!guiSupported.value) {
        return;
      }

      const parsed = parseDocument();
      if (!parsed) {
        return;
      }

      const gui = toGui(parsed);
      const diagnostics = analyzeTaskDefinition(parsed);
      if (!gui || diagnostics.length) {
        guiSupported.value = false;
        guiDiagnostics.value =
          formatEditorDiagnostics(diagnostics) || t('common.advancedModeRequiredDesc');
        return;
      }

      resetEditorState(gui);
      guiSupported.value = true;
    }

    if (next === 'advanced') {
      if (!(await confirmStaleFields())) {
        return;
      }
      try {
        const doc = fromGui(guiState);
        jsonText.value = JSON.stringify(doc, null, 2);
        errorMessage.value = null;
        guiError.value = null;
      } catch (error) {
        guiError.value = error instanceof Error ? error.message : t('common.failedSerializeGui');
        return;
      }
    }

    mode.value = next;
  };

  const buildDocument = async (): Promise<TaskDefinitionDocument | null> => {
    if (isBusy.value || validationError.value) return null;
    if (mode.value === 'gui') {
      if (!(await confirmStaleFields())) {
        return null;
      }
      try {
        const document = fromGui(guiState);
        guiError.value = null;
        return document;
      } catch (error) {
        guiError.value = error instanceof Error ? error.message : t('common.unableToBuildDef');
        return null;
      }
    }

    const parsed = parseDocument();
    return parsed;
  };

  const submit = async (): Promise<void> => {
    const document = await buildDocument();
    if (document) emit('submit', document);
  };

  const beautify = (): void => {
    if (mode.value !== 'advanced') {
      return;
    }

    const parsed = parseDocument();
    if (!parsed) {
      return;
    }

    jsonText.value = JSON.stringify(parsed, null, 2);
    errorMessage.value = null;
  };

  return {
    t,
    jsonText,
    errorMessage,
    guiError,
    guiSupported,
    mode,
    showImport,
    showAdvancedRequestOptions,
    importString,
    selectedExistingValue,
    availableDefinitions,
    impersonateTargets,
    guiState,
    loading,
    submitting,
    isBusy,
    advancedMode,
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
    isDirty,
    hasEditorContent,
    validationError,
    buildDocument,
    addField,
    removeField,
    addRequestPair,
    importFromString,
    importExisting,
    switchMode,
    submit,
    beautify,
  };
};
