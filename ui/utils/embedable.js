const sources = [
  {
    name: 'youtube',
    url: 'https://www.youtube-nocookie.com/embed/',
    regex: /(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:shorts\/|[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})/,
  },
  {
    name: "instagram",
    url: "https://www.instagram.com/p/",
    regex: /https?:\/\/(?:www\.)?instagram\.com\/p\/([^/?#&]+)/,
  },
  {
    name: "twitter",
    url: "https://twitter.com/i/status/",
    regex: /https?:\/\/(?:www\.)?twitter\.com\/i\/status\/([^/?#&]+)/,
  },
  {
    name: "facebook",
    url: "https://www.facebook.com/plugins/post.php?href=",
    regex: /https?:\/\/(?:www\.)?facebook\.com\/(?:[^/?#&]+)\/posts\/([^/?#&]+)/,
  },
  {
    name: "tiktok",
    url: "https://www.tiktok.com/embed/",
    regex: /https?:\/\/(?:www\.)?tiktok\.com\/(?:[^/?#&]+)\/video\/([^/?#&]+)/,
  },
  {
    name: "vimeo",
    url: "https://player.vimeo.com/video/",
    regex: /https?:\/\/(?:www\.)?vimeo\.com\/(?:[^/?#&]+)\/([^/?#&]+)/,
  },
  {
    name: "soundcloud",
    url: "https://w.soundcloud.com/player/?url=",
    regex: /https?:\/\/(?:www\.)?soundcloud\.com\/(?:[^/?#&]+)\/([^/?#&]+)/,
  },
  {
    name: "spotify",
    url: "https://open.spotify.com/embed/",
    regex: /https?:\/\/(?:open\.)?spotify\.com\/(?:[^/?#&]+)\/([^/?#&]+)/,
  },
  {
    name: "twitch",
    url: "https://player.twitch.tv/?channel=",
    regex: /https?:\/\/(?:www\.)?twitch\.tv\/(?:[^/?#&]+)\/([^/?#&]+)/,
  },
  {
    name: "mixcloud",
    url: "https://www.mixcloud.com/widget/iframe/",
    regex: /https?:\/\/(?:www\.)?mixcloud\.com\/(?:[^/?#&]+)\/([^/?#&]+)/,
  },
  {
    name: "dailymotion",
    url: "https://www.dailymotion.com/embed/video/",
    regex: /https?:\/\/(?:www\.)?dailymotion\.com\/(?:[^/?#&]+)\/video\/([^/?#&]+)/,
  },
]

const isEmbedable = url => {
  return sources.some(source => source.regex.test(url));
}

const getEmbedable = url => {
  const source = sources.find(source => source.regex.test(url));
  const id = source.regex.exec(url)[1];
  return source.url + id;
}

export { isEmbedable, getEmbedable };
