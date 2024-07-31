import { createApp } from 'vue'
import App from './App.vue'
import Toast from 'vue-toastification'
import FloatingVue from 'floating-vue'
import { library } from '@fortawesome/fontawesome-svg-core'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import {
  faCog, faTrash, faLink, faPlus, faTrashCan, faCircleXmark, faCircleCheck, faRotateRight, faDownload, faUpRightFromSquare,
  faSpinner, faArrowUp, faArrowDown, faTasks, faCalendar, faArrowUpAZ, faArrowDownAZ, faEject, faGlobe, faMoon, faSun,
  faTerminal,
  faBroom,
  faServer,
  faPowerOff,
  faPaperPlane,
  faBoxArchive
} from '@fortawesome/free-solid-svg-icons'

import { faSquare, faSquareCheck } from '@fortawesome/free-regular-svg-icons'

import 'vue-toastification/dist/index.css'
import './assets/css/bulma.css'
import './assets/css/style.css'
import 'floating-vue/dist/style.css'

library.add(faCog, faTrash, faLink, faPlus, faTrashCan, faCircleXmark, faCircleCheck, faRotateRight, faDownload,
  faUpRightFromSquare, faSquare, faSquareCheck, faSpinner, faArrowUp, faArrowDown, faTasks, faCalendar, faArrowUpAZ,
  faArrowDownAZ, faEject, faGlobe, faMoon, faSun, faTerminal, faBroom, faServer, faPowerOff, faBroom, faServer,
  faPowerOff, faPaperPlane, faBoxArchive)
const app = createApp(App);

app.config.globalProperties.capitalize = s => s && s[0].toUpperCase() + s.slice(1);
app.config.globalProperties.makeDownload = (config, item, base = 'download') => {
  let baseDir = 'download' === base ? `${base}/` : 'player/playlist/';

  if (item.folder) {
    item.folder = item.folder.replace('#', '%23');
    baseDir += item.folder + '/';
  }

  let url = config.app.url_host + config.app.url_prefix + baseDir + encodeURIComponent(item.filename);
  return ('m3u8' === base) ? url + '.m3u8' : url;
}

app.config.globalProperties.formatBytes = (bytes, decimals = 2) => {
  if (!+bytes) return '0 Bytes'

  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['Bytes', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']

  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
}

app.use(Toast, {
  transition: "Vue-Toastification__bounce",
  position: "bottom-right",
  maxToasts: 5,
  newestOnTop: true
});

app.use(FloatingVue, {
  themes: {
    tooltip: {
      placement: 'top',
      triggers: ['hover', 'focus', 'touch', 'click'],
    }
  }
})

app.component('font-awesome-icon', FontAwesomeIcon)

app.mount('#app')
