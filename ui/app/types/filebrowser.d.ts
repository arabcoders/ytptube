type FileItem = {
  type: 'file' | 'dir' | 'link'
  content_type: 'image' | 'video' | 'text' | 'subtitle' | 'metadata' | 'dir' | string
  name: string
  path: string
  size: number
  mime: string
  mtime: string
  ctime: string
  is_dir: boolean
  is_file: boolean
  is_symlink: boolean
}

type FileBrowserResponse = {
  path: string
  contents: FileItem[]
}

export type { FileItem, FileBrowserResponse }
