<script setup lang="ts">
import type { Component } from "vue";

withDefaults(
  defineProps<{
    label: string;
    value: string | number;
    unit?: string;
    trend?: string;
    tone?: "primary" | "success" | "warning" | "danger" | "info";
    icon?: Component;
  }>(),
  {
    unit: "",
    trend: "",
    tone: "primary",
    icon: undefined,
  },
);
</script>

<template>
  <section class="metric-card" :class="`is-${tone}`">
    <span v-if="icon" class="metric-card-icon">
      <el-icon><component :is="icon" /></el-icon>
    </span>
    <div>
      <p>{{ label }}</p>
      <strong>{{ value }}<small v-if="unit">{{ unit }}</small></strong>
      <span v-if="trend">{{ trend }}</span>
    </div>
  </section>
</template>
