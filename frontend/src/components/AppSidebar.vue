<script setup lang="ts">
import type { Component } from "vue";

import StatusBadge from "./StatusBadge.vue";

export interface SidebarItem {
  id: string;
  label: string;
  icon: Component;
  group: "overview" | "operations" | "governance";
}

defineProps<{
  active: string;
  items: SidebarItem[];
}>();

const emit = defineEmits<{
  select: [id: string];
}>();

const groupLabels: Record<SidebarItem["group"], string> = {
  overview: "总览",
  operations: "运维",
  governance: "治理",
};

const groups: SidebarItem["group"][] = ["overview", "operations", "governance"];
</script>

<template>
  <aside class="app-sidebar">
    <div class="brand">
      <span class="brand-mark">EP</span>
      <span>
        <strong>AI 边缘设备远程管理平台</strong>
        <small>基于 Debian 的边缘设备管理</small>
      </span>
    </div>

    <nav class="nav-groups" aria-label="主导航">
      <section v-for="group in groups" :key="group" class="nav-group">
        <p>{{ groupLabels[group] }}</p>
        <button
          v-for="item in items.filter((entry) => entry.group === group)"
          :key="item.id"
          type="button"
          class="nav-item"
          :class="{ 'is-active': active === item.id }"
          :data-testid="`nav-${item.id}`"
          @click="emit('select', item.id)"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </button>
      </section>
    </nav>

    <div class="sidebar-foot">
      <StatusBadge label="平台版本" state="success" detail="v1.2.0" />
      <small>© 2024 Edge Manager</small>
    </div>
  </aside>
</template>
