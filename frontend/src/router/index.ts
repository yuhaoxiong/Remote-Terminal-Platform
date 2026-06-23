import { createRouter, createWebHistory } from "vue-router";

// 路由骨架占位——Phase 3 最后一步将所有 activeSection v-if 切换为 router-view。
// 当前只有一个根路由，实际展示由 App.vue 内联 section 通过左侧导航切换。
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      component: {
        template: "<div></div>",
      },
    },
  ],
});

export default router;
