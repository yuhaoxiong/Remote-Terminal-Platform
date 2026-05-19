import "element-plus/dist/index.css";
import "@xterm/xterm/css/xterm.css";
import "./styles.css";

import ElementPlus from "element-plus";
import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "./App.vue";
import router from "./router";

createApp(App).use(createPinia()).use(router).use(ElementPlus).mount("#app");
