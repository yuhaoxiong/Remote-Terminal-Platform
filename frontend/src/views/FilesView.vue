<script setup lang="ts">
import FilesPanel from "../components/FilesPanel.vue";

defineProps<{
  loading: boolean;
}>();

const emit = defineEmits<{
  refresh: [];
}>();
</script>

<template>
  <FilesPanel :loading="loading" @refresh="emit('refresh')" />
</template>
