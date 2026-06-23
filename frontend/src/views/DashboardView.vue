<script setup lang="ts">
import { storeToRefs } from "pinia";

import DashboardPanel from "../components/DashboardPanel.vue";
import { usePlatformOverviewStore } from "../stores/platformOverview";

defineProps<{
  loading: boolean;
}>();

const emit = defineEmits<{
  refresh: [];
  navigate: [section: string];
}>();

const platformOverviewStore = usePlatformOverviewStore();
const { serverOverview, alertSummary, metricLoadWarning } = storeToRefs(platformOverviewStore);
</script>

<template>
  <DashboardPanel
    :server-overview="serverOverview"
    :alert-summary="alertSummary"
    :metric-load-warning="metricLoadWarning"
    :loading="loading"
    @refresh="emit('refresh')"
    @navigate="(section: string) => emit('navigate', section)"
  />
</template>
