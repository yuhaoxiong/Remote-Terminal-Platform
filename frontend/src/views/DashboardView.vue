<script setup lang="ts">
import { storeToRefs } from "pinia";
import { useRouter } from "vue-router";

import DashboardPanel from "../components/DashboardPanel.vue";
import { usePlatformDataStore } from "../stores/platformData";
import { usePlatformOverviewStore } from "../stores/platformOverview";

const router = useRouter();
const platformDataStore = usePlatformDataStore();
const { loading } = storeToRefs(platformDataStore);
const platformOverviewStore = usePlatformOverviewStore();
const { serverOverview, alertSummary, metricLoadWarning } = storeToRefs(platformOverviewStore);

async function navigate(section: string) {
  await router.push({ name: section });
}
</script>

<template>
  <DashboardPanel
    :server-overview="serverOverview"
    :alert-summary="alertSummary"
    :metric-load-warning="metricLoadWarning"
    :loading="loading"
    @refresh="platformDataStore.loadPlatformData"
    @navigate="navigate"
  />
</template>
