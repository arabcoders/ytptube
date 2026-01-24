type ImportedItem = {
  _type: string,
  _version: string
}

type version_check = {
  app: {
    status: 'up_to_date' | 'update_available' | 'error',
    current_version: string,
    new_version: string
  },
  ytdlp: {
    status: 'up_to_date' | 'update_available' | 'error',
    current_version: string,
    new_version: string
  }
}

export { ImportedItem, version_check }
