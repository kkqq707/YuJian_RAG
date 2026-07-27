import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
// @ts-expect-error element-plus locale types not available
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import 'element-plus/dist/index.css'
import './assets/styles/theme.css'
import App from './App.vue'
import router from './router'

// tsParticles — AI 粒子背景引擎
import Particles from '@tsparticles/vue3'
import { loadSlim } from '@tsparticles/slim'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.use(Particles, { init: loadSlim })

app.mount('#app')
