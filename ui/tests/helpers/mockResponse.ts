type MockResponseInput = {
  ok: boolean;
  status: number;
  jsonData: unknown;
};

export const createMockResponse = ({ ok, status, jsonData }: MockResponseInput): Response => {
  const response = new Response(JSON.stringify(jsonData), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
  Object.defineProperty(response, 'ok', { value: ok });
  return response;
};
