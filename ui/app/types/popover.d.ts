export type PopoverPlacement = 'top' | 'bottom' | 'left' | 'right'
export type PopoverTrigger = 'hover' | 'click' | 'focus'

export interface PopoverProps {
  title?: string
  description?: string
  placement?: PopoverPlacement
  trigger?: PopoverTrigger
  offset?: number
  disabled?: boolean
  closeOnClickOutside?: boolean
  minWidth?: number
  maxWidth?: number
  maxHeight?: number
  showDelay?: number
}
