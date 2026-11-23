import type { Paginated } from '~/types/responses';
import type {
  ToolboxDefinition,
  ToolboxDefinitionPayload,
  ToolboxDefinitionSummary,
} from '~/types/toolbox';
import { ensure_api_success, parse_api_response, parse_list_response, request } from '~/utils';

const PATH = '/api/toolbox/definitions';

export const useToolboxDefinitions = () => {
  const list = async (
    page = 1,
    { includeDefaults = false } = {},
  ): Promise<Paginated<ToolboxDefinitionSummary>> => {
    const query = new URLSearchParams({ page: String(page), per_page: '50' });
    if (includeDefaults) query.set('include_defaults', 'true');
    const response = await request(`${PATH}?${query}`, { timeout: 20 });
    await ensure_api_success(response);
    return parse_list_response<ToolboxDefinitionSummary>(response.json());
  };

  const listForImport = async (): Promise<ToolboxDefinitionSummary[]> => {
    const items: ToolboxDefinitionSummary[] = [];
    let page = 1;
    let more: boolean;
    do {
      const result = await list(page++, { includeDefaults: true });
      items.push(...result.items);
      more = result.pagination.has_next;
    } while (more);
    return items;
  };

  const get = async (id: number): Promise<ToolboxDefinition> => {
    const response = await request(`${PATH}/${id}`, { timeout: 20 });
    await ensure_api_success(response);
    return parse_api_response<ToolboxDefinition>(response.json());
  };

  const save = async (
    definition: ToolboxDefinitionPayload,
    editingId?: number,
  ): Promise<ToolboxDefinition> => {
    const editing = editingId !== undefined;
    const response = await request(editing ? `${PATH}/${editingId}` : PATH, {
      method: editing ? 'PUT' : 'POST',
      body: JSON.stringify(definition),
      timeout: 20,
    });
    await ensure_api_success(response);
    return parse_api_response<ToolboxDefinition>(response.json());
  };

  const remove = async (id: number): Promise<void> => {
    const response = await request(`${PATH}/${id}`, {
      method: 'DELETE',
      timeout: 20,
    });
    await ensure_api_success(response);
  };

  return { list, listForImport, get, save, remove };
};
