<script setup lang="ts">
import { Refresh, Search } from "@element-plus/icons-vue";
import { storeToRefs } from "pinia";

import { useDevicesStore } from "../stores/devices";
import DeviceFilePanel from "./DeviceFilePanel.vue";

defineProps<{
  loading: boolean;
}>();

defineEmits<{
  refresh: [];
}>();

const devicesStore = useDevicesStore();
const { deviceSearch, visibleDevices, filePanelDevice } = storeToRefs(devicesStore);
const { openFilePanel } = devicesStore;
</script>

<template>
  <section class="page-section">
    <div class="page-title-row">
      <div>
        <h3>文件管理</h3>
        <p class="muted">选择设备后进行文件浏览、上传、下载和删除。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="$emit('refresh')">刷新设备</el-button>
    </div>
    <section class="panel">
      <div class="panel-header">
        <h3>选择设备</h3>
        <el-input v-model="deviceSearch" :prefix-icon="Search" placeholder="按设备名称、序列号、项目号搜索" />
      </div>
      <el-table :data="visibleDevices" row-key="id" empty-text="暂无可管理文件的设备">
        <el-table-column prop="name" label="设备名称" min-width="180" />
        <el-table-column prop="project_id" label="项目号" width="130" />
        <el-table-column prop="location" label="位置" min-width="130" />
        <el-table-column prop="ssh_port" label="SSH 端口" width="110" />
        <el-table-column label="凭据" width="110">
          <template #default="{ row }">
            <el-tag :type="row.ssh_credential_configured ? 'success' : 'warning'">
              {{ row.ssh_credential_configured ? "已配置" : "缺失" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button :data-testid="`open-files-${row.id}`" type="primary" text @click="openFilePanel(row)">打开文件</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
    <DeviceFilePanel v-if="filePanelDevice" :device="filePanelDevice" />
    <el-empty v-else description="请选择一台设备开始文件管理" />
  </section>
</template>
