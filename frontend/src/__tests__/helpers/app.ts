import { mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { nextTick } from "vue";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createMemoryHistory, type Router } from "vue-router";

import App from "../../App.vue";
import { installRouteGuards } from "../../router/guards";
import { TEST_ROUTES } from "../../router/test-routes";

export async function mountApp() {
  const pinia = createPinia();
  setActivePinia(pinia);
  const router = createRouter({
    history: createMemoryHistory(),
    routes: TEST_ROUTES,
  });
  installRouteGuards(router);
  router.push("/");
  await router.isReady();
  const wrapper = mount(App, {
    global: {
      plugins: [ElementPlus, pinia, router],
      stubs: { teleport: true },
    },
  });
  return { wrapper, router };
}

export async function flushAsync() {
  for (let index = 0; index < 4; index += 1) {
    await nextTick();
    await Promise.resolve();
  }
}

export async function navigateTo(router: Router, section: string) {
  await router.push({ name: section });
  await router.isReady();
  await flushAsync();
}

export async function waitUntil(assertion: () => void) {
  let lastError: unknown;
  for (let index = 0; index < 20; index += 1) {
    try {
      assertion();
      return;
    } catch (error) {
      lastError = error;
      await flushAsync();
    }
  }
  throw lastError;
}
