import { createApp } from 'vue'
import App from './App.vue'
import Toast from 'vue-toastification'
import 'vue-toastification/dist/index.css'
import 'bulma/css/bulma.css'
import './assets/css/style.css'
import '@creativebulma/bulma-tooltip/dist/bulma-tooltip.min.css';

const app = createApp(App);

app.config.globalProperties.capitalize = s => s && s[0].toUpperCase() + s.slice(1);
app.config.globalProperties.makeDownload = (config, item) => {
  let baseDir = 'download/';

  if (item.folder) {
    baseDir += item.folder + '/';
  }

  return config.app.url_host + config.app.url_prefix + baseDir + encodeURIComponent(item.filename);
}

app.use(Toast, {
  transition: "Vue-Toastification__bounce",
  maxToasts: 5,
  newestOnTop: true
});

app.mount('#app')
