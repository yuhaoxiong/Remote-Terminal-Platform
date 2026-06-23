<script setup lang="ts">
import { onMounted } from "vue";
import { storeToRefs } from "pinia";

import DiagnosticsPanel from "../components/DiagnosticsPanel.vue";
import { usePlatformOverviewStore } from "../stores/platformOverview";

const platformOverviewStore = usePlatformOverviewStore();
const { diagnosticsConfig, diagnosticsLoading } = storeToRefs(platformOverviewStore);
const { loadDiagnosticsConfig } = platformOverviewStore;

onMounted(() => {
  void loadDiagnosticsConfig();
});
</script>

<template>
  <DiagnosticsPanel
    :config="diagnosticsConfig"
    :loading="diagnosticsLoading"
    @refresh="loadDiagnosticsConfig"
  />
</template>
