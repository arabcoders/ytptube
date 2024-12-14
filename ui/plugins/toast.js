import Toast from 'vue-toastification'
import 'vue-toastification/dist/index.css'

export default defineNuxtPlugin(nuxtApp => nuxtApp.vueApp.use(Toast, {
  transition: "Vue-Toastification__bounce",
  //position: "bottom-right",
  maxToasts: 5,
  newestOnTop: true
}))
