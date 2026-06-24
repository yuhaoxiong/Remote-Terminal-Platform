<script setup lang="ts">
import { useRouter } from "vue-router";

import DevicesPanel from "../components/DevicesPanel.vue";
import { useDevicesStore, type Device } from "../stores/devices";
import { usePlatformOverviewStore } from "../stores/platformOverview";

const router = useRouter();
const devicesStore = useDevicesStore();
const platformOverviewStore = usePlatformOverviewStore();

function remoteUnavailableReason(device: Device, sessionType: "ssh" | "vnc"): string {
  if (sessionType === "ssh") {
    if (device.ssh_port === null) {
      return "缺少 SSH 端口";
    }
    if (!device.ssh_credential_configured) {
      return "缺少 SSH 凭据";
    }
  }
  if (sessionType === "vnc" && device.vnc_port === null) {
    return "缺少 VNC 端口";
  }
  return "";
}

async function openRemoteSession(device: Device, sessionType: "ssh" | "vnc") {
  devicesStore.requestRemoteSession(device, sessionType);
  await router.push({ name: "remote" });
}

async function openFiles(device: Device) {
  devicesStore.openFilePanel(device);
  await router.push({ name: "files" });
}
</script>

<template>
  <DevicesPanel
    :remote-unavailable-reason="remoteUnavailableReason"
    @changed="platformOverviewStore.refreshOverview"
    @ssh="(device: Device) => openRemoteSession(device, 'ssh')"
    @vnc="(device: Device) => openRemoteSession(device, 'vnc')"
    @open-files="openFiles"
  />
</template>
