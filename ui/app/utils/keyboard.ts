import type { KeyboardShortcutContext } from '~/types/video'

export const handlePlayPause = (ctx: KeyboardShortcutContext) => {
  if (ctx.video.paused) {
    ctx.video.play()
  } else {
    ctx.video.pause()
  }
}

export const handleRewind = (ctx: KeyboardShortcutContext, seconds: number = 10) => {
  ctx.video.currentTime = Math.max(0, ctx.video.currentTime - seconds)
}

export const handleForward = (ctx: KeyboardShortcutContext, seconds: number = 10) => {
  ctx.video.currentTime = Math.min(ctx.video.duration, ctx.video.currentTime + seconds)
}

export const handleMute = (ctx: KeyboardShortcutContext) => {
  ctx.video.muted = !ctx.video.muted
}

export const handleVolumeChange = (ctx: KeyboardShortcutContext, delta: number) => {
  const newVolume = Math.max(0, Math.min(1, ctx.video.volume + delta))
  ctx.video.volume = newVolume
}

export const handlePlaybackSpeedChange = (ctx: KeyboardShortcutContext, delta: number) => {
  const currentSpeed = ctx.video.playbackRate
  const newSpeed = Math.max(0.25, Math.min(2, currentSpeed + delta))
  ctx.video.playbackRate = newSpeed
}

export const handleFrameStep = (ctx: KeyboardShortcutContext, direction: 'forward' | 'backward' = 'forward') => {
  if (!ctx.video.paused) {
    ctx.video.pause()
  }

  // Frame step by ~33ms (approximately 1 frame at 30fps, ~16.7ms at 60fps)
  const frameStep = 'forward' === direction ? 0.033 : -0.033
  ctx.video.currentTime = Math.max(0, Math.min(ctx.video.duration, ctx.video.currentTime + frameStep))
}

export const handleSeekToPercent = (ctx: KeyboardShortcutContext, percent: number) => {
  ctx.video.currentTime = (percent / 100) * ctx.video.duration
}

export const handleSeekBackward = (ctx: KeyboardShortcutContext, seconds: number = 5) => {
  ctx.video.currentTime = Math.max(0, ctx.video.currentTime - seconds)
}

export const handleSeekForward = (ctx: KeyboardShortcutContext, seconds: number = 5) => {
  ctx.video.currentTime = Math.min(ctx.video.duration, ctx.video.currentTime + seconds)
}

export const handleFullscreen = (videoElement: HTMLVideoElement) => {
  if (!document.fullscreenElement) {
    videoElement.requestFullscreen().catch(err => {
      console.error(`Error attempting to enable fullscreen: ${err.message}`)
    })
  } else {
    document.exitFullscreen()
  }
}

export const handlePictureInPicture = async (videoElement: HTMLVideoElement) => {
  try {
    if (document.pictureInPictureElement) {
      await document.exitPictureInPicture()
    } else if (document.pictureInPictureEnabled) {
      await videoElement.requestPictureInPicture()
    }
  } catch (error) {
    console.error(`Picture-in-Picture error: ${error}`)
  }
}

export const handleToggleCaptions = (videoElement: HTMLVideoElement) => {
  const textTracks = videoElement.textTracks

  if (0 === textTracks.length) {
    return
  }

  for (let i = 0; i < textTracks.length; i++) {
    const track = textTracks[i] as TextTrack | null
    if (track && ('captions' === track.kind || 'subtitles' === track.kind)) {
      track.mode = 'showing' === track.mode ? 'hidden' : 'showing'
      break
    }
  }
}

export const shouldHandleKeyboardShortcut = (event: KeyboardEvent): boolean => {
  const target = event.target as HTMLElement
  const tagName = target?.tagName?.toLowerCase()
  if ('input' === tagName || 'textarea' === tagName || 'true' === target?.contentEditable || 'true' === target?.getAttribute('contenteditable')) {
    return false
  }

  return true
}

export const isModifierKey = (event: KeyboardEvent): boolean => event.ctrlKey || event.metaKey || event.altKey
