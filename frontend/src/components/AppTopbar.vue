<script setup lang="ts">
import { Lock, Refresh, SwitchButton, UserFilled } from "@element-plus/icons-vue";

import StatusBadge from "./StatusBadge.vue";

withDefaults(
  defineProps<{
    title: string;
    userName?: string;
    roleLabel?: string;
    apiHealthy?: boolean;
    apiDetail?: string;
    schedulerRunning?: boolean | null;
  }>(),
  {
    userName: "",
    roleLabel: "",
    apiHealthy: false,
    apiDetail: "待检测",
    schedulerRunning: null,
  },
);

const emit = defineEmits<{
  refreshHealth: [];
  changePassword: [];
  logout: [];
}>();
</script>

<template>
  <header class="app-topbar">
    <div>
      <p class="eyebrow">设备运维</p>
      <h2>{{ title }}</h2>
    </div>

    <div class="topbar-actions">
      <button type="button" class="topbar-refresh" title="刷新后端健康状态" @click="emit('refreshHealth')">
        <el-icon><Refresh /></el-icon>
      </button>
      <StatusBadge label="后端服务健康" :state="apiHealthy ? 'success' : 'warning'" :detail="apiDetail" />
      <StatusBadge
        label="调度器状态"
        :state="schedulerRunning === false ? 'warning' : 'success'"
        :detail="schedulerRunning === null ? '待检查' : schedulerRunning ? '运行中' : '未运行'"
      />
      <span v-if="userName" class="user-chip">
        <el-icon><UserFilled /></el-icon>
        <span>
          <strong>{{ userName }} · {{ roleLabel }}</strong>
          <small>当前账号</small>
        </span>
      </span>
      <el-button data-testid="open-password-change" text :icon="Lock" @click="emit('changePassword')">修改密码</el-button>
      <el-button :icon="SwitchButton" text @click="emit('logout')">退出登录</el-button>
    </div>
  </header>
</template>
