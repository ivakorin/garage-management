import { createApp } from 'vue';
import App from './App.vue';
import naive from 'naive-ui';
import router from './router';
import i18n from "./i18n.ts";


createApp(App)
  .use(naive)
    .use(router)
    .use(i18n)
  .mount('#app');