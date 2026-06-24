import { computed, ref } from "vue";
import { defineStore } from "pinia";

import {
  clearAuthTokens,
  hasStoredAccessToken,
  setAuthTokens,
  type CurrentUserResponse,
} from "../api/platform";

/**
 * 认证状态 store。
 * 只负责纯认证状态(登录态、当前用户、角色)和 token 写入/清理;
 * 业务数据(设备、分组等)的加载与清空仍由调用方负责。
 */
export const useAuthStore = defineStore("auth", () => {
  const authenticated = ref(hasStoredAccessToken());
  const currentUser = ref<CurrentUserResponse | null>(null);
  const isAdmin = computed(() => currentUser.value?.role === "admin");

  function applyTokens(accessToken: string, refreshToken: string) {
    setAuthTokens(accessToken, refreshToken);
    authenticated.value = true;
  }

  function setCurrentUser(user: CurrentUserResponse | null) {
    currentUser.value = user;
  }

  function reset() {
    clearAuthTokens();
    authenticated.value = false;
    currentUser.value = null;
  }

  return { authenticated, currentUser, isAdmin, applyTokens, setCurrentUser, reset };
});
