import { createRouter, createWebHistory } from "vue-router";

import { installRouteGuards } from "./guards";
import { APP_ROUTES } from "./routes";

const router = createRouter({
  history: createWebHistory(),
  routes: APP_ROUTES,
});

installRouteGuards(router);

export default router;
