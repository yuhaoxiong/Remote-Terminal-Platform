<script setup lang="ts">
import FilesPanel from "../components/FilesPanel.vue";
import { usePlatformDataStore } from "../stores/platformData";
import { storeToRefs } from "pinia";

const platformDataStore = usePlatformDataStore();
const { loading } = storeToRefs(platformDataStore);
</script>

<template>
  <FilesPanel :loading="loading" @refresh="platformDataStore.loadPlatformData" />
</template>
