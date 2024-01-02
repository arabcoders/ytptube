import { createApp } from 'vue'
import App from './App.vue'
import Toast from 'vue-toastification'
import { library } from '@fortawesome/fontawesome-svg-core'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import {
  faCog, faTrash, faLink, faPlus, faTrashCan, faCircleXmark, faCircleCheck, faRotateRight, faDownload, faUpRightFromSquare,
  faSpinner, faArrowUp, faArrowDown, faTasks
} from '@fortawesome/free-solid-svg-icons'

import { faSquare, faSquareCheck } from '@fortawesome/free-regular-svg-icons'

import 'vue-toastification/dist/index.css'
import './assets/css/bulma-light.css'
import './assets/css/bulma-dark.css'
import './assets/css/style.css'
import '@creativebulma/bulma-tooltip/dist/bulma-tooltip.min.css';

library.add(faCog, faTrash, faLink, faPlus, faTrashCan, faCircleXmark, faCircleCheck, faRotateRight, faDownload, faUpRightFromSquare,
  faSquare, faSquareCheck, faSpinner, faArrowUp, faArrowDown, faTasks,)
const app = createApp(App);

app.config.globalProperties.capitalize = s => s && s[0].toUpperCase() + s.slice(1);
app.config.globalProperties.makeDownload = (config, item, base = 'download') => {
  let baseDir = `${base}/`;

  if (item.folder) {
    item.folder = item.folder.replace('#', '%23');
    baseDir += item.folder + '/';
  }

  return config.app.url_host + config.app.url_prefix + baseDir + encodeURIComponent(item.filename);
}
app.config.globalProperties.formatBytes = (bytes, decimals = 2) => {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB'];

  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

app.use(Toast, {
  transition: "Vue-Toastification__bounce",
  position: "bottom-right",
  maxToasts: 5,
  newestOnTop: true
});

app.component('font-awesome-icon', FontAwesomeIcon)

app.mount('#app')
