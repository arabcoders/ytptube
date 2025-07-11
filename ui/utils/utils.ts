import type { convert_args_response } from "~/@types/responses";

const separators = [
  { name: 'Comma', value: ',', },
  { name: 'Semicolon', value: ';', },
  { name: 'Colon', value: ':', },
  { name: 'Pipe', value: '|', },
  { name: 'Space', value: ' ', }
]

/**
 * Get the name of a separator based on its value
 *
 * @param {string} value - The separator value
 *
 * @returns {string} The name of the separator, or 'Unknown' if not found
 */
const getSeparatorsName = (value: string): string => {
  const sep = separators.find(s => s.value === value)
  return sep ? `${sep.name} (${value})` : 'Unknown'
}


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

export { convertCliOptions, separators, getSeparatorsName }
