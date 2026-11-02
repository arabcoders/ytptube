import type {
  ToolboxJob,
  ToolboxOptionField,
  ToolboxOptions,
  ToolboxOptionValue,
  ToolboxStatus,
} from '~/types/toolbox';

export const isToolboxActive = (job: ToolboxJob): boolean =>
  job.status === 'queued' || job.status === 'running';

export const toolboxStatusColor = (
  status: ToolboxStatus,
): 'success' | 'error' | 'warning' | 'neutral' | 'info' => {
  if (status === 'succeeded') return 'success';
  if (status === 'failed') return 'error';
  if (status === 'interrupted' || status === 'cancelled') return 'warning';
  return status === 'running' ? 'info' : 'neutral';
};

export const toolboxStatusLabel = (status: ToolboxStatus, t: (key: string) => string): string => {
  if (status === 'succeeded') return t('common.completed');
  return t(`common.${status}`);
};

export const toolboxShowMessage = (job: ToolboxJob, t: (key: string) => string): boolean => {
  const message = job.message?.trim();
  if (!message || message === job.error?.trim()) return false;
  return ![
    job.status,
    job.status === 'succeeded' ? 'completed' : '',
    toolboxStatusLabel(job.status, t),
  ].some(
    (status) => status.toLocaleLowerCase() === message.toLocaleLowerCase().replace(/[.!]+$/, ''),
  );
};

const isSchema = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const isOptionValue = (value: unknown): value is ToolboxOptionValue =>
  value === null || ['string', 'number', 'boolean'].includes(typeof value);

export const toolboxOptionFields = (
  schema: Record<string, unknown>,
): { fields: ToolboxOptionField[]; unsupported: string[] } => {
  const fields: ToolboxOptionField[] = [];
  const unsupported: string[] = [];
  const required = Array.isArray(schema.required) ? schema.required : [];
  const defs = isSchema(schema.$defs) ? schema.$defs : {};

  const resolve = (value: Record<string, unknown>): Record<string, unknown> => {
    if (typeof value.$ref !== 'string') return value;
    const name = value.$ref.startsWith('#/$defs/') ? value.$ref.slice(8) : '';
    const target = defs[name];
    if (!isSchema(target) || target.$ref) return value;
    const { $ref: _, ...rest } = value;
    return { ...target, ...rest };
  };

  for (const [name, value] of Object.entries(
    isSchema(schema.properties) ? schema.properties : {},
  )) {
    if (!isSchema(value)) {
      unsupported.push(name);
      continue;
    }
    let property = resolve(value);
    let nullable = false;
    if (Array.isArray(property.anyOf)) {
      const variants = property.anyOf.filter(isSchema);
      const types = variants.filter((variant) => variant.type !== 'null');
      if (variants.length === 2 && types.length === 1) {
        nullable = true;
        const { anyOf: _, ...rest } = property;
        property = { ...resolve(types[0]!), ...rest };
      }
    }
    const field: ToolboxOptionField = {
      name,
      label: typeof property.title === 'string' ? property.title : name,
      description: typeof property.description === 'string' ? property.description : undefined,
      type: 'string',
      required: required.includes(name),
      nullable,
    };
    if (property.$ref || property.anyOf || property.oneOf || property.allOf) {
      unsupported.push(name);
      continue;
    }
    if (property.enum !== undefined) {
      if (
        !Array.isArray(property.enum) ||
        !property.enum.length ||
        !property.enum.every(isOptionValue)
      ) {
        unsupported.push(name);
        continue;
      }
      field.type = 'select';
      field.nullable ||= property.enum.includes(null);
      field.items = property.enum.map((item) => ({ label: String(item), value: item }));
    } else if (property.type === 'string') {
      field.type = property.format === 'textarea' ? 'text' : 'string';
    } else if (property.type === 'boolean') {
      field.type = nullable ? 'select' : 'bool';
      if (nullable)
        field.items = [true, false].map((item) => ({ label: String(item), value: item }));
    } else if (property.type === 'integer' || property.type === 'number') {
      field.type = 'number';
      field.min = typeof property.minimum === 'number' ? property.minimum : undefined;
      field.max = typeof property.maximum === 'number' ? property.maximum : undefined;
      field.step =
        typeof property.multipleOf === 'number'
          ? property.multipleOf
          : property.type === 'integer'
            ? 1
            : 'any';
    } else {
      unsupported.push(name);
      continue;
    }
    if (isOptionValue(property.default)) field.defaultValue = property.default;
    fields.push(field);
  }
  return { fields, unsupported };
};

export const toolboxOptionDefaults = (fields: ToolboxOptionField[]): ToolboxOptions =>
  Object.fromEntries(
    fields
      .filter(
        (field) => field.defaultValue !== undefined || (field.required && field.type === 'bool'),
      )
      .map((field) => [field.name, field.defaultValue !== undefined ? field.defaultValue : false]),
  );
