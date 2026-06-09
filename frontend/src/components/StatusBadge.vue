<script setup lang="ts">
import { CircleCheckFilled, CircleCloseFilled, WarningFilled } from "@element-plus/icons-vue";

const props = withDefaults(
  defineProps<{
    label: string;
    state?: "success" | "warning" | "danger" | "info";
    detail?: string;
  }>(),
  {
    state: "info",
    detail: "",
  },
);

const iconMap = {
  success: CircleCheckFilled,
  warning: WarningFilled,
  danger: CircleCloseFilled,
  info: CircleCheckFilled,
};
</script>

<template>
  <span class="status-badge" :class="`is-${props.state}`">
    <el-icon><component :is="iconMap[props.state]" /></el-icon>
    <span>{{ props.label }}</span>
    <strong v-if="props.detail">{{ props.detail }}</strong>
  </span>
</template>
