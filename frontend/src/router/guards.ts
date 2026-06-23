import type { Router } from "vue-router";

import { useAuthStore } from "../stores/auth";

export function installRouteGuards(router: Router) {
  router.beforeEach((to) => {
    const authStore = useAuthStore();

    if (!to.meta.requiresAuth) {
      return true;
    }

    if (!authStore.authenticated) {
      return to.name === "dashboard" ? true : { name: "dashboard", query: { redirect: to.fullPath } };
    }

    if (to.meta.adminOnly && authStore.currentUser && !authStore.isAdmin) {
      return { name: "dashboard" };
    }

    return true;
  });
}
