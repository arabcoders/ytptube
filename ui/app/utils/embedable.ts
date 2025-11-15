export type EmbedSource = {
  name: string
  url: string
  regex: RegExp
}

const sources: EmbedSource[] = [
  {
    name: 'youtube',
    url: 'https://www.youtube-nocookie.com/embed/{id}',
    regex: /(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:shorts\/|[^/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)(?<id>[a-zA-Z0-9_-]{11})/,
  },
  {
    name: "instagram_post",
    url: "https://www.instagram.com/p/{id}",
    regex: /https?:\/\/(?:www\.)?instagram\.com\/p\/(?<id>[^/?#&]+)/,
  },
  {
    name: "instagram_story",
    url: "https://www.instagram.com/stories/highlights/{id}",
    regex: /https?:\/\/(?:www\.)?instagram\.com\/stories\/highlights\/(?<id>[^/?#&]+)/,
  },
  {
    name: "twitter",
    url: "https://twitter.com/i/status/{id}",
    regex: /https?:\/\/(?:www\.)?(twitter\.com|x\.com)\/.+?\/status\/(?<id>[^/?#&]+)/,
  },
  {
    name: "facebook",
    url: "https://www.facebook.com/plugins/post.php?href={id}",
    regex: /https?:\/\/(?:www\.)?facebook\.com\/(?:[^/?#&]+)\/posts\/(?<id>[^/?#&]+)/,
  },
  {
    name: "tiktok",
    url: "https://www.tiktok.com/embed/{id}",
    regex: /https?:\/\/(?:www\.)?tiktok\.com\/(?:[^/?#&]+)\/video\/(?<id>[^/?#&]+)/,
  },
  {
    name: "vimeo",
    url: "https://player.vimeo.com/video/{id}",
    regex: /https?:\/\/(?:www\.)?vimeo\.com(?:\/[^/?#&]+)?\/(?<id>[^/?#&]+)/,
  },
  {
    name: "spotify",
    url: "https://open.spotify.com/embed/{id}",
    regex: /https?:\/\/(?:open\.)?spotify\.com\/(?:[^/?#&]+)\/(?<id>[^/?#&]+)/,
  },
  {
    name: "twitch_vod",
    url: "https://player.twitch.tv/?parent={origin}&video={id}",
    regex: /https?:\/\/(?:www\.)?twitch\.tv\/(?:[^/?#&]+)\/(?<id>[^/?#&]+)/,
  },
  {
    name: "twitch_clip",
    url: "https://clips.twitch.tv/embed?parent={origin}&clip={id}",
    regex: /https?:\/\/(?:www\.)?twitch\.tv\/(?:[^/?#&]+)\/clip\/(?<id>[^/?#&]+)/,
  },
  {
    name: "twitch_channel",
    url: "https://player.twitch.tv/?parent={origin}&channel={id}",
    regex: /https?:\/\/(?:www\.)?twitch\.tv\/(?<id>[^/?#&]+)/,
  },
  {
    name: "dailymotion",
    url: "https://www.dailymotion.com/embed/video/{id}",
    regex: /^.+dailymotion.com\/(video|hub)\/(?<id>[^_]+)[^#]*(#video=([^_&]+))?/,
  },
  {
    name: "bilibili",
    url: "https://player.bilibili.com/player.html?aid=12569853&bvid={id}&cid=20681553&p=1&high_quality=1",
    regex: /^https?:\/\/(?:www\.)?bilibili\.com\/video\/(?<id>BV[0-9A-Za-z]+)\/?/i,
  },
  {
    name: "googledrive",
    url: "https://drive.google.com/file/d/{id}/preview",
    regex: /https?:\/\/(?:www\.)?drive\.google\.com\/file\/d\/(?<id>[^/?#&]+)/,
  },
]

const isEmbedable = (url: string): boolean => sources.some(source => source.regex.test(url))

const getEmbedable = (url: string): string | null => {
  const source = sources.find(source => source.regex.test(url))
  if (!source) {
    return null
  }

  const match = source.regex.exec(url)
  if (!match || !match.groups?.id) {
    return null
  }

  return source.url.replace(/\{origin\}/g, window.location.origin).replace(/\{id\}/g, match.groups.id)
}

export { isEmbedable, getEmbedable }
