import type {
  ToolboxDefinition,
  ToolboxDefinitionInput,
  ToolboxDefinitionPayload,
  ToolboxParam,
} from '~/types/toolbox';
import { decode, encode } from '~/utils';

const TYPE = 'toolbox_definition';

type ToolboxParamDraft = {
  name: string;
  kind: 'boolean' | 'number' | 'choices';
  checked: boolean;
  number: number | undefined;
  min: number | undefined;
  max: number | undefined;
  choices: string[];
  choice: number | undefined;
};

export const newToolboxParam = (name = '', param?: ToolboxParam): ToolboxParamDraft => ({
  name,
  kind:
    typeof param?.default === 'number'
      ? 'number'
      : typeof param?.default === 'string'
        ? 'choices'
        : 'boolean',
  checked: param?.default === true,
  number: typeof param?.default === 'number' ? param.default : undefined,
  min: param?.min ?? undefined,
  max: param?.max ?? undefined,
  choices: param?.choices?.slice() ?? [],
  choice: typeof param?.default === 'string' ? param.choices?.indexOf(param.default) : undefined,
});

export const makeToolboxDraft = (definition?: ToolboxDefinitionInput | null) => ({
  name: definition?.name ?? '',
  description: definition?.description ?? '',
  output_extension: definition?.output_extension ?? '',
  supports_overwrite: definition?.supports_overwrite ?? false,
  executable: definition?.command[0] ?? '',
  args: definition?.command.slice(1) ?? [],
  env: Object.entries(definition?.env ?? {}).map(([key, value]) => ({ key, value })),
  params: Object.entries(definition?.params ?? {}).map(([name, param]) =>
    newToolboxParam(name, param),
  ),
});

export const buildToolboxDefinition = (
  draft: ReturnType<typeof makeToolboxDraft>,
):
  | { value: ToolboxDefinitionPayload; duplicate?: never }
  | { value?: never; duplicate: { field: string; key: string } } => {
  const { name, description, output_extension, supports_overwrite, executable, args, env, params } =
    draft;

  const variables = new Map<string, string>();
  for (const [index, { key, value }] of env.entries()) {
    if (variables.has(key)) return { duplicate: { field: `env.${index}.key`, key } };
    variables.set(key, value);
  }

  const options = new Map<string, ToolboxDefinitionPayload['params'][string]>();
  for (const [index, param] of params.entries()) {
    if (options.has(param.name))
      return { duplicate: { field: `params.${index}.name`, key: param.name } };

    switch (param.kind) {
      case 'boolean':
        options.set(param.name, { default: param.checked });
        break;
      case 'number':
        options.set(param.name, {
          default: param.number,
          ...(param.min === undefined ? {} : { min: param.min }),
          ...(param.max === undefined ? {} : { max: param.max }),
        });
        break;
      case 'choices':
        options.set(param.name, {
          default: param.choice === undefined ? undefined : param.choices[param.choice],
          choices: [...param.choices],
        });
        break;
    }
  }

  return {
    value: {
      name,
      description,
      output_extension,
      supports_overwrite,
      command: [executable, ...args],
      env: Object.fromEntries(variables),
      params: Object.fromEntries(options),
    },
  };
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const isStrings = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((item) => typeof item === 'string');

const isNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

const isParam = (value: unknown): value is ToolboxParam =>
  isRecord(value) &&
  (typeof value.default === 'string' ||
    typeof value.default === 'boolean' ||
    isNumber(value.default)) &&
  (value.min == null || isNumber(value.min)) &&
  (value.max == null || isNumber(value.max)) &&
  (value.choices == null || isStrings(value.choices));

type DefinitionResult =
  | { value: ToolboxDefinitionInput; invalid?: never }
  | { value?: never; invalid: 'command' | 'env' | 'params' | 'definition' };

export const parseToolboxDefinition = (value: unknown): DefinitionResult => {
  if (!isRecord(value)) return { invalid: 'definition' };
  const { name, description, output_extension, supports_overwrite, command, env, params } = value;
  if (
    typeof name !== 'string' ||
    typeof description !== 'string' ||
    typeof output_extension !== 'string' ||
    typeof supports_overwrite !== 'boolean'
  )
    return { invalid: 'definition' };
  if (!isStrings(command)) return { invalid: 'command' };
  if (!isRecord(env)) return { invalid: 'env' };
  const envEntries = Object.entries(env).filter((entry): entry is [string, string] => {
    return typeof entry[1] === 'string';
  });
  if (envEntries.length !== Object.keys(env).length) return { invalid: 'env' };
  if (!isRecord(params)) return { invalid: 'params' };
  const paramEntries = Object.entries(params).filter((entry): entry is [string, ToolboxParam] => {
    return isParam(entry[1]);
  });
  if (paramEntries.length !== Object.keys(params).length) return { invalid: 'params' };
  return {
    value: {
      name,
      description,
      output_extension,
      supports_overwrite,
      command,
      env: Object.fromEntries(envEntries),
      params: Object.fromEntries(paramEntries),
    },
  };
};

export const importToolboxDefinition = (text: string): ToolboxDefinitionInput | null => {
  try {
    const item: unknown = decode(text.trim());
    if (!isRecord(item) || item._type !== TYPE || 'id' in item) return null;
    return parseToolboxDefinition(item).value ?? null;
  } catch {
    return null;
  }
};

export const exportToolboxDefinition = (definition: ToolboxDefinition): string | null => {
  if (definition.default) return null;
  const { value } = parseToolboxDefinition(definition);
  return value ? encode({ ...value, _type: TYPE, _version: '1.0' }) : null;
};
