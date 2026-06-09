<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    tone?: "success" | "warning" | "danger" | "info";
    tag?: string;
    details?: string[];
  }>(),
  {
    tone: "info",
    tag: "",
    details: () => [],
  },
);
</script>

<template>
  <article class="diagnostic-card" :class="`is-${tone}`">
    <div class="diagnostic-card-header">
      <h3>{{ title }}</h3>
      <el-tag v-if="tag" :type="tone === 'danger' ? 'danger' : tone">{{ tag }}</el-tag>
    </div>
    <slot>
      <p v-for="detail in details" :key="detail">{{ detail }}</p>
    </slot>
  </article>
</template>
