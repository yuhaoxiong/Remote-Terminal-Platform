<script setup lang="ts">
import { computed } from "vue";

import type { UpdateTaskDeviceRead } from "../api/platform";

const props = defineProps<{
  devices: UpdateTaskDeviceRead[];
}>();

const emit = defineEmits<{
  retryFailed: [deviceIds: number[]];
}>();

const failedDeviceIds = computed(() => props.devices.filter((device) => device.status === "failed").map((device) => device.device_id));

const statusText: Record<string, string> = {
  pending: "等待执行",
  running: "执行中",
  success: "成功",
  failed: "失败",
  skipped: "已跳过",
  canceled: "已取消",
  completed: "已完成",
};

function resultSummary(device: UpdateTaskDeviceRead): string {
  return device.error_message || device.stderr_summary || device.stdout_summary || device.output_summary || "-";
}
</script>

<template>
  <section class="sub-panel" aria-label="任务设备结果">
    <div class="panel-header">
      <div>
        <h4>设备执行结果</h4>
        <p class="muted">失败 {{ failedDeviceIds.length }} 台 / 总计 {{ devices.length }} 台</p>
      </div>
      <el-button
        data-testid="retry-failed-devices"
        :disabled="failedDeviceIds.length === 0"
        type="warning"
        @click="emit('retryFailed', failedDeviceIds)"
      >
        以失败设备新建任务
      </el-button>
    </div>

    <el-table :data="devices" row-key="id" empty-text="暂无设备结果">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="result-detail">
            <p><strong>标准输出：</strong>{{ row.stdout_summary || "-" }}</p>
            <p><strong>错误输出：</strong>{{ row.stderr_summary || "-" }}</p>
            <p><strong>失败原因：</strong>{{ row.error_message || "-" }}</p>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="device_id" label="设备 ID" width="90" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'info'">
            {{ statusText[row.status] ?? row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="退出码" width="90">
        <template #default="{ row }">{{ row.exit_code ?? "-" }}</template>
      </el-table-column>
      <el-table-column label="摘要" min-width="220">
        <template #default="{ row }">{{ resultSummary(row) }}</template>
      </el-table-column>
    </el-table>
  </section>
</template>
