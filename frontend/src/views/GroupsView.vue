<script setup lang="ts">
import { useRouter } from "vue-router";
import { storeToRefs } from "pinia";

import GroupsPanel from "../components/GroupsPanel.vue";
import { useDevicesStore } from "../stores/devices";
import { usePlatformOverviewStore } from "../stores/platformOverview";

const router = useRouter();
const devicesStore = useDevicesStore();
const { selectedGroupId } = storeToRefs(devicesStore);
const platformOverviewStore = usePlatformOverviewStore();

async function viewGroupDevices(groupId: number | null) {
  selectedGroupId.value = groupId;
  await router.push({ name: "devices" });
}
</script>

<template>
  <GroupsPanel
    @changed="platformOverviewStore.refreshOverview"
    @view-devices="viewGroupDevices"
  />
</template>
