<script setup lang="ts">
import { Document } from "@element-plus/icons-vue";
import { reactive, ref } from "vue";
import { storeToRefs } from "pinia";

import { exportLogs } from "../api/platform";
import { useLogsStore, type AuditLog } from "../stores/logs";
import OperationLogDetailDrawer from "./OperationLogDetailDrawer.vue";

const logsStore = useLogsStore();
const { auditLogs, auditLogsTotal } = storeToRefs(logsStore);
const { loadLogs, prependLocalLog } = logsStore;

const logFilters = reactive({
  action: "",
  target_type: "",
  status: "",
});

const logPagination = reactive({
  offset: 0,
  limit: 50,
});

const selectedAuditLog = ref<AuditLog | null>(null);
const auditLogDetailOpen = ref(false);

const logStatusText: Record<string, string> = {
  success: "成功",
  completed: "已完成",
  blocked: "已阻止",
  generated: "已生成",
  ready: "就绪",
};

async function applyLogFilters() {
  logPagination.offset = 0;
  await loadLogs({
    offset: logPagination.offset,
    limit: logPagination.limit,
    action: logFilters.action || undefined,
    target_type: logFilters.target_type || undefined,
    status: logFilters.status || undefined,
  });
}

async function handleLogPageChange(page: number) {
  logPagination.offset = (page - 1) * logPagination.limit;
  await loadLogs({
    offset: logPagination.offset,
    limit: logPagination.limit,
    action: logFilters.action || undefined,
    target_type: logFilters.target_type || undefined,
    status: logFilters.status || undefined,
  });
}

async function downloadLogs() {
  try {
    const blob = await exportLogs({
      action: logFilters.action || undefined,
      target_type: logFilters.target_type || undefined,
      status: logFilters.status || undefined,
    });
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "operation_logs.csv";
    anchor.click();
    window.URL.revokeObjectURL(url);
  } catch {
    prependLocalLog("导出操作日志", "操作日志", "blocked", "导出 CSV 失败，请检查后端服务。");
  }
}

function openAuditLogDetail(log: AuditLog) {
  selectedAuditLog.value = log;
  auditLogDetailOpen.value = true;
}
</script>

<template>
  <section class="page-section">
    <div class="toolbar">
      <h3>操作日志</h3>
      <el-button data-testid="export-logs" :icon="Document" @click="downloadLogs">导出 CSV</el-button>
    </div>
    <div class="form-panel">
      <div class="form-grid">
        <div data-testid="log-action" class="input-wrap"><el-input v-model="logFilters.action" placeholder="操作，例如 device.create" /></div>
        <div data-testid="log-target-type" class="input-wrap"><el-input v-model="logFilters.target_type" placeholder="目标类型，例如 device" /></div>
        <div data-testid="log-status" class="input-wrap"><el-input v-model="logFilters.status" placeholder="状态，例如 success" /></div>
      </div>
      <div class="form-actions">
        <el-button data-testid="apply-log-filters" type="primary" @click="applyLogFilters">筛选</el-button>
      </div>
    </div>
    <div class="table-panel">
      <el-table :data="auditLogs" row-key="id" empty-text="暂无日志">
        <el-table-column prop="created_at" label="时间" width="160" />
        <el-table-column prop="action" label="操作" min-width="150" />
        <el-table-column prop="target" label="目标" min-width="130" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'blocked' ? 'warning' : 'success'">{{ logStatusText[row.status] ?? row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="detail" label="详情" min-width="220" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button :data-testid="`open-log-detail-${row.id}`" size="small" text @click="openAuditLogDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <el-pagination
      layout="prev, pager, next, total"
      :total="auditLogsTotal"
      :page-size="logPagination.limit"
      :current-page="Math.floor(logPagination.offset / logPagination.limit) + 1"
      @current-change="handleLogPageChange"
    />
    <OperationLogDetailDrawer v-model="auditLogDetailOpen" :log="selectedAuditLog" />
    <span v-if="auditLogDetailOpen && selectedAuditLog" data-testid="selected-log-detail" class="visually-hidden">
      操作详情 {{ selectedAuditLog.detail }}
    </span>
  </section>
</template>
