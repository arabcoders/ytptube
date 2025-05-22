const sources = [
  {
    name: 'youtube',
    url: 'https://www.youtube-nocookie.com/embed/',
    regex: /(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:shorts\/|[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)(?<id>[a-zA-Z0-9_-]{11})/,
  },
  {
    name: "instagram_post",
    url: "https://www.instagram.com/p/",
    regex: /https?:\/\/(?:www\.)?instagram\.com\/p\/(?<id>[^/?#&]+)/,
  },
  {
    name: "instagram_story",
    url: "https://www.instagram.com/stories/highlights/",
    regex: /https?:\/\/(?:www\.)?instagram\.com\/stories\/highlights\/(?<id>[^/?#&]+)/,
  },
  {
    name: "twitter",
    url: "https://twitter.com/i/status/",
    regex: /https?:\/\/(?:www\.)?(twitter\.com|x\.com)\/.+?\/status\/(?<id>[^/?#&]+)/,
  },
  {
    name: "facebook",
    url: "https://www.facebook.com/plugins/post.php?href=",
    regex: /https?:\/\/(?:www\.)?facebook\.com\/(?:[^/?#&]+)\/posts\/(?<id>[^/?#&]+)/,
  },
  {
    name: "tiktok",
    url: "https://www.tiktok.com/embed/",
    regex: /https?:\/\/(?:www\.)?tiktok\.com\/(?:[^/?#&]+)\/video\/(?<id>[^/?#&]+)/,
  },
  {
    name: "vimeo",
    url: "https://player.vimeo.com/video/",
    regex: /https?:\/\/(?:www\.)?vimeo\.com(?:\/[^/?#&]+)?\/(?<id>[^/?#&]+)/,
  },
  {
    name: "spotify",
    url: "https://open.spotify.com/embed/",
    regex: /https?:\/\/(?:open\.)?spotify\.com\/(?:[^/?#&]+)\/(?<id>[^/?#&]+)/,
  },
  {
    name: "twitch_vod",
    url: "https://player.twitch.tv/?parent={origin}&video=",
    regex: /https?:\/\/(?:www\.)?twitch\.tv\/(?:[^/?#&]+)\/(?<id>[^/?#&]+)/,
  },
  {
    name: "twitch_clip",
    url: "https://clips.twitch.tv/embed?parent={origin}&clip=",
    regex: /https?:\/\/(?:www\.)?twitch\.tv\/(?:[^/?#&]+)\/clip\/(?<id>[^/?#&]+)/,
  },
  {
    name: "twitch_channel",
    url: "https://player.twitch.tv/?parent={origin}&channel=",
    regex: /https?:\/\/(?:www\.)?twitch\.tv\/(?<id>[^/?#&]+)/,
  },
  {
    name: "dailymotion",
    url: "https://www.dailymotion.com/embed/video/",
    regex: /^.+dailymotion.com\/(video|hub)\/(?<id>[^_]+)[^#]*(#video=([^_&]+))?/,
  },
]

const isEmbedable = url => {
  return sources.some(source => source.regex.test(url));
}

const getEmbedable = url => {
  const source = sources.find(source => source.regex.test(url));
  if (!source) {
    return null;
  }

  source.url.replace(/\{origin\}/g, window.location.origin);

  return source.url + source.regex.exec(url)['groups'].id;
}

export { isEmbedable, getEmbedable };
