/**
 * Vue composable for handling YouTube-style keyboard shortcuts in video player
 */

import { ref } from 'vue'
import type { Ref } from 'vue'
import {
  handlePlayPause,
  handleRewind,
  handleForward,
  handleMute,
  handleVolumeChange,
  handlePlaybackSpeedChange,
  handleFrameStep,
  handleSeekToPercent,
  handleSeekBackward,
  handleSeekForward,
  handleFullscreen,
  handlePictureInPicture,
  handleToggleCaptions,
  shouldHandleKeyboardShortcut,
  isModifierKey,
} from '~/utils/keyboard'
import type { KeyboardShortcutContext } from '~/types/video'


export interface UseKeyboardShortcutsOptions {
  videoElement: Ref<HTMLVideoElement | null | undefined>
  enabled?: Ref<boolean>
  closePlayer?: () => void
  onHelpToggle?: () => void
}

export const useKeyboardShortcuts = (options: UseKeyboardShortcutsOptions) => {
  const { videoElement, enabled, closePlayer, onHelpToggle } = options
  const showHelp = ref(false)

  const handleKeyDown = async (event: KeyboardEvent) => {
    // Don't handle if composable is disabled
    if (enabled && !enabled.value) {
      return
    }

    // Don't handle if user is typing in an input
    if (!shouldHandleKeyboardShortcut(event)) {
      return
    }

    const video = videoElement.value
    if (!video) {
      return
    }

    // Skip if modifier keys are pressed (except for shortcuts that need them)
    if (isModifierKey(event) && !['f', 'p', '?'].includes(event.key.toLowerCase())) {
      return
    }

    const key = event.key.toLowerCase()
    const ctx: KeyboardShortcutContext = { video }

    try {
      switch (key) {
        // Play/Pause
        case ' ':
        case 'k':
          event.preventDefault()
          handlePlayPause(ctx)
          break

        // Rewind 10 seconds (J key)
        case 'j':
          event.preventDefault()
          handleRewind(ctx, 10)
          break

        // Forward 10 seconds (L key)
        case 'l':
          event.preventDefault()
          handleForward(ctx, 10)
          break

        // Seek backward 5 seconds (left arrow)
        case 'arrowleft':
          event.preventDefault()
          handleSeekBackward(ctx, 5)
          break

        // Seek forward 5 seconds (right arrow)
        case 'arrowright':
          event.preventDefault()
          handleSeekForward(ctx, 5)
          break

        // Increase volume (up arrow)
        case 'arrowup':
          event.preventDefault()
          handleVolumeChange(ctx, 0.1)
          break

        // Decrease volume (down arrow)
        case 'arrowdown':
          event.preventDefault()
          handleVolumeChange(ctx, -0.1)
          break

        // Mute/Unmute
        case 'm':
          event.preventDefault()
          handleMute(ctx)
          break

        // Toggle fullscreen
        case 'f':
          event.preventDefault()
          handleFullscreen(video)
          break

        // Picture-in-Picture
        case 'p':
          event.preventDefault()
          await handlePictureInPicture(video)
          break

        // Toggle captions
        case 'c':
          event.preventDefault()
          handleToggleCaptions(video)
          break

        // Frame advance (period key) / Increase playback speed (> or ')
        case '.':
        case "'": {
          event.preventDefault()
          if ('.' === key) {
            handleFrameStep(ctx, 'forward')
          } else {
            handlePlaybackSpeedChange(ctx, 0.25)
          }
          break
        }

        // Frame rewind (comma key) / Decrease playback speed (< or ;)
        case ',':
        case ';': {
          event.preventDefault()
          if (',' === key) {
            handleFrameStep(ctx, 'backward')
          } else {
            handlePlaybackSpeedChange(ctx, -0.25)
          }
          break
        }

        // Jump to percentage (0-9 keys)
        case '0':
        case '1':
        case '2':
        case '3':
        case '4':
        case '5':
        case '6':
        case '7':
        case '8':
        case '9': {
          event.preventDefault()
          const percent = parseInt(key) * 10
          handleSeekToPercent(ctx, percent)
          break
        }

        // Jump to start (Home)
        case 'home':
          event.preventDefault()
          video.currentTime = 0
          break

        // Jump to end (End)
        case 'end':
          event.preventDefault()
          video.currentTime = video.duration
          break

        // Show/hide help (Shift+/)
        case '?':
        case '/': {
          event.preventDefault()
          showHelp.value = !showHelp.value
          onHelpToggle?.()
          break
        }

        // Close player (Escape - already handled elsewhere but kept for completeness)
        case 'escape':
          event.preventDefault()
          closePlayer?.()
          break

        default:
          // No action for unrecognized keys
          break
      }
    } catch (error) {
      console.error('Error handling keyboard shortcut:', error)
    }
  }

  const attach = () => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }

  return {
    showHelp,
    attach,
  }
}
