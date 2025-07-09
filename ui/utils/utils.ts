import type { convert_args_response } from "~/@types/responses";

/**
 * Convert options to JSON
 *
 * @param {string} opts
 *
 * @returns {Promise<convert_args_response>} The converted options
 */
const convertCliOptions = async (opts: string): Promise<convert_args_response> => {
  const response = await request('/api/yt-dlp/convert', {
    method: 'POST',
    body: JSON.stringify({ args: opts }),
  });

  const data = await response.json()
  if (200 !== response.status) {
    throw new Error(`Error: (${response.status}): ${data.error}`)
  }

  return data
}

export { convertCliOptions }
