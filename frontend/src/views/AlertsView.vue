<script setup lang="ts">
import { storeToRefs } from "pinia";

import AlertCenterPanel from "../components/AlertCenterPanel.vue";
import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();
const { isAdmin } = storeToRefs(authStore);
</script>

<template>
  <AlertCenterPanel :can-manage="isAdmin" />
</template>
