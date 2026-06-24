<script setup lang="ts">
import { storeToRefs } from "pinia";

import ScheduledTaskPanel from "../components/ScheduledTaskPanel.vue";
import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();
const { isAdmin } = storeToRefs(authStore);
</script>

<template>
  <ScheduledTaskPanel :can-manage="isAdmin" />
</template>
