<script setup lang="ts">
import { Plus } from "@element-plus/icons-vue";
import { ElMessageBox } from "element-plus";
import { computed, reactive, ref } from "vue";
import { storeToRefs } from "pinia";

import {
  cancelUpdateTask,
  createUpdateTask,
  executeUpdateTask,
  exportUpdateTaskResults,
  type UpdateTaskCreateRequest,
  type UpdateTaskTargetPreviewResponse,
  type UpdateTaskTemplateRead,
} from "../api/platform";
import { useAuthStore } from "../stores/auth";
import { useDevicesStore } from "../stores/devices";
import { useGroupsStore } from "../stores/groups";
import { useLogsStore } from "../stores/logs";
import { useUpdatesStore, mapUpdateTask, updateStatusText, executionModeText, type UpdateStatus, type ExecutionMode, type UpdateTask } from "../stores/updates";
import CommonDialog from "./CommonDialog.vue";
import DeviceTargetSelector from "./DeviceTargetSelector.vue";
import UpdateTaskResultTable from "./UpdateTaskResultTable.vue";
import UpdateTaskTemplatePanel from "./UpdateTaskTemplatePanel.vue";

const props = defineProps<{
  confirmRealSshTask: (command: string, target: string) => Promise<boolean>;
  targetSummaryForFilter: (targetFilter: Record<string, unknown>) => string;
  targetSummaryForTask: (task: UpdateTask) => string;
}>();

const emit = defineEmits<{
  changed: [];
}>();

const authStore = useAuthStore();
const { isAdmin } = storeToRefs(authStore);
const devicesStore = useDevicesStore();
const { devices } = storeToRefs(devicesStore);
const groupsStore = useGroupsStore();
const { groups } = storeToRefs(groupsStore);
const { prependLocalLog } = useLogsStore();
const updatesStore = useUpdatesStore();
const { updateTasks } = storeToRefs(updatesStore);

const updateCreateOpen = ref(false);
const updateForm = reactive({
  name: "",
  command: "",
  project_id: "",
  target_filter: {} as Record<string, unknown>,
  execution_mode: "dry_run" as ExecutionMode,
  failure_strategy: "continue" as "continue" | "pause" | "rollback",
  concurrency_limit: 5,
});
const updateTargetPreview = ref<UpdateTaskTargetPreviewResponse | null>(null);

const updateInitialDeviceIds = computed(() => {
  const deviceIds = updateForm.target_filter.device_ids;
  return Array.isArray(deviceIds) ? deviceIds.filter((id): id is number => typeof id === "number") : [];
});

function openUpdateCreate() {
  const defaultProjectId = devices.value[0]?.project_id ?? "";
  Object.assign(updateForm, {
    name: "",
    command: "hostname",
    project_id: defaultProjectId,
    target_filter: defaultProjectId ? { project_id: defaultProjectId } : {},
    execution_mode: "dry_run" as ExecutionMode,
    failure_strategy: "continue" as "continue" | "pause" | "rollback",
    concurrency_limit: 5,
  });
  updateTargetPreview.value = null;
  updateCreateOpen.value = true;
}

function handleUpdateTargetChange(targetFilter: Record<string, unknown>) {
  updateForm.target_filter = targetFilter;
  updateForm.project_id = typeof targetFilter.project_id === "string" ? targetFilter.project_id : "";
}

function handleUpdateTargetPreview(preview: UpdateTaskTargetPreviewResponse | null) {
  updateTargetPreview.value = preview;
}

function applyUpdateTemplate(template: UpdateTaskTemplateRead) {
  if (!isAdmin.value && template.default_execution_mode === "ssh_command") {
    prependLocalLog("套用命令模板", `模板：${template.id}`, "blocked", "当前账号无权限套用真实 SSH 命令模板。");
    return;
  }
  updateForm.command = template.command;
  updateForm.execution_mode = template.default_execution_mode;
  if (!updateForm.name) {
    updateForm.name = template.name;
  }
}

async function saveUpdate() {
  if (!updateForm.name || !updateForm.command) {
    prependLocalLog("更新任务校验", "新任务", "blocked", "任务名称和命令为必填项");
    return;
  }
  if (!isAdmin.value && updateForm.execution_mode === "ssh_command") {
    updateForm.execution_mode = "dry_run";
    prependLocalLog("更新任务校验", "新任务", "blocked", "当前账号无权创建真实 SSH 任务，已切换为演练模式。");
    return;
  }
  const targetFilter = updateForm.target_filter && Object.keys(updateForm.target_filter).length > 0
    ? updateForm.target_filter
    : updateForm.project_id
      ? { project_id: updateForm.project_id }
      : {};
  if (updateForm.execution_mode === "ssh_command" && updateTargetPreview.value?.total === 0) {
    prependLocalLog("更新任务校验", "新任务", "blocked", "目标预览为空，未创建真实 SSH 任务。");
    return;
  }
  const payload: UpdateTaskCreateRequest = {
    name: updateForm.name,
    task_type: "command",
    command: updateForm.command,
    target_filter: targetFilter,
    execution_mode: updateForm.execution_mode,
    failure_strategy: updateForm.failure_strategy,
    concurrency_limit: Number(updateForm.concurrency_limit) || 1,
  };
  if (payload.execution_mode === "ssh_command") {
    const targetSummary = `${props.targetSummaryForFilter(targetFilter)}，预览 ${updateTargetPreview.value?.total ?? "未确认"} 台`;
    const confirmed = await props.confirmRealSshTask(updateForm.command, targetSummary);
    if (!confirmed) {
      return;
    }
  }
  try {
    const created = await createUpdateTask(payload);
    updateTasks.value.push(mapUpdateTask(created));
    emit("changed");
    updateCreateOpen.value = false;
  } catch (error) {
    prependLocalLog("创建更新任务", "新任务", "blocked", "创建更新任务失败，请检查后端返回。");
  }
}

async function executeUpdate(task: UpdateTask) {
  if (task.execution_mode === "ssh_command") {
    const confirmed = await props.confirmRealSshTask(task.command, props.targetSummaryForTask(task));
    if (!confirmed) {
      return;
    }
  }
  task.status = "running";
  task.lastEvent = "正在请求后端执行";
  updatesStore.startUpdateProgress(task.id);
  try {
    const executed = await executeUpdateTask(task.id);
    const mapped = mapUpdateTask(executed);
    const index = updateTasks.value.findIndex((item) => item.id === task.id);
    if (index >= 0) {
      updateTasks.value[index] = mapped;
    }
    updatesStore.startUpdateProgress(task.id);
    emit("changed");
  } catch (error) {
    task.status = "partial_failed";
    task.lastEvent = "后端执行失败";
    updatesStore.stopUpdateProgress(task.id);
    prependLocalLog("执行更新任务", `更新任务：${task.id}`, "blocked", "执行失败，请检查后端任务状态。");
  }
}

async function cancelUpdate(task: UpdateTask) {
  try {
    await ElMessageBox.confirm(`确定取消更新任务 ${task.name}？`, "取消更新任务", {
      type: "warning",
      confirmButtonText: "取消任务",
      cancelButtonText: "返回",
    });
  } catch {
    return;
  }
  try {
    const canceled = await cancelUpdateTask(task.id);
    const mapped = mapUpdateTask(canceled);
    const index = updateTasks.value.findIndex((item) => item.id === task.id);
    if (index >= 0) {
      updateTasks.value[index] = mapped;
    }
    updatesStore.stopUpdateProgress(task.id);
    emit("changed");
  } catch (error) {
    prependLocalLog("取消更新任务", `更新任务：${task.id}`, "blocked", "取消任务失败，请检查后端任务状态。");
  }
}

function openRetryFailedTask(task: UpdateTask, deviceIds: number[]) {
  if (deviceIds.length === 0) {
    prependLocalLog("更新任务重试", `更新任务：${task.id}`, "blocked", "当前任务没有失败设备。");
    return;
  }
  Object.assign(updateForm, {
    name: `${task.name} 失败重试`,
    command: task.command,
    project_id: "",
    target_filter: { device_ids: deviceIds },
    execution_mode: task.execution_mode,
    failure_strategy: task.failure_strategy,
    concurrency_limit: task.concurrency_limit,
  });
  updateTargetPreview.value = null;
  updateCreateOpen.value = true;
}

async function downloadUpdateTaskResults(task: UpdateTask) {
  try {
    const blob = await exportUpdateTaskResults(task.id);
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `update_task_${task.id}_results.csv`;
    anchor.click();
    window.URL.revokeObjectURL(url);
  } catch {
    prependLocalLog("导出更新结果", `更新任务：${task.id}`, "blocked", "导出失败，请检查后端服务。");
  }
}
</script>

<template>
  <section class="page-section">
    <div class="toolbar">
      <div>
        <h3>更新任务</h3>
        <p class="muted">创建按条件筛选的任务，并跟踪每台设备的执行进度。</p>
      </div>
      <el-button data-testid="open-update-create" type="primary" :icon="Plus" @click="openUpdateCreate">
        新建更新
      </el-button>
    </div>

    <CommonDialog v-model:visible="updateCreateOpen" title="创建更新任务" width="900px" @confirm="saveUpdate" @cancel="updateCreateOpen = false">
      <div class="form-grid">
        <div data-testid="update-name" class="input-wrap"><el-input v-model="updateForm.name" placeholder="任务名称" /></div>
        <label class="field-label">
          <span>执行模式</span>
          <select data-testid="update-execution-mode" v-model="updateForm.execution_mode" class="native-select">
            <option value="dry_run">演练模式</option>
            <option v-if="isAdmin" value="ssh_command">真实 SSH 执行</option>
          </select>
        </label>
        <label class="field-label">
          <span>失败策略</span>
          <select data-testid="update-failure-strategy" v-model="updateForm.failure_strategy" class="native-select">
            <option value="continue">继续执行</option>
            <option value="pause">暂停后续</option>
            <option value="rollback">预留回滚</option>
          </select>
        </label>
        <div data-testid="update-concurrency" class="input-wrap">
          <el-input v-model.number="updateForm.concurrency_limit" type="number" min="1" placeholder="并发数量" />
        </div>
        <div data-testid="update-command" class="input-wrap textarea-wrap">
          <el-input v-model="updateForm.command" type="textarea" :rows="3" placeholder="命令或脚本" />
        </div>
      </div>
      <UpdateTaskTemplatePanel :can-manage="isAdmin" @apply="applyUpdateTemplate" />
      <DeviceTargetSelector
        :devices="devices"
        :groups="groups"
        :execution-mode="updateForm.execution_mode"
        :initial-project-id="updateForm.project_id"
        :initial-device-ids="updateInitialDeviceIds"
        @target-change="handleUpdateTargetChange"
        @preview-change="handleUpdateTargetPreview"
      />
      <el-alert
        v-if="!isAdmin"
        class="validation-alert"
        type="info"
        show-icon
        :closable="false"
        title="当前账号为运维人员，仅允许创建和执行演练任务。"
      />
      <p v-if="updateForm.execution_mode === 'ssh_command'" class="risk-note">
        真实 SSH 执行会连接目标设备。建议先使用 hostname、whoami、uptime 等只读命令验收。
      </p>
      <template #footer>
        <el-button @click="updateCreateOpen = false">取消</el-button>
        <el-button data-testid="save-update" type="primary" @click="saveUpdate">保存更新任务</el-button>
      </template>
    </CommonDialog>

    <div class="table-panel">
      <el-table :data="updateTasks" row-key="id" empty-text="暂无更新任务">
        <el-table-column prop="name" label="任务" min-width="190" />
        <el-table-column prop="project_id" label="目标" width="130" />
        <el-table-column label="模式" width="130">
          <template #default="{ row }">{{ executionModeText[row.execution_mode as ExecutionMode] }}</template>
        </el-table-column>
        <el-table-column label="进度" width="140">
          <template #default="{ row }">{{ row.completed }}/{{ row.matched }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : 'info'">{{ updateStatusText[row.status as UpdateStatus] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="lastEvent" label="最新事件" min-width="190" />
        <el-table-column label="设备结果" min-width="260">
          <template #default="{ row }">
            <UpdateTaskResultTable :devices="row.devices" @retry-failed="(deviceIds) => openRetryFailedTask(row, deviceIds)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250">
          <template #default="{ row }">
            <el-button
              :data-testid="`execute-update-${row.id}`"
              size="small"
              type="primary"
              :disabled="row.status === 'completed'"
              @click="executeUpdate(row)"
            >
              执行
            </el-button>
            <el-button :data-testid="`export-update-${row.id}`" size="small" @click="downloadUpdateTaskResults(row)">
              导出
            </el-button>
            <el-button
              v-if="row.status === 'pending' || row.status === 'running'"
              :data-testid="`cancel-update-${row.id}`"
              size="small"
              type="warning"
              @click="cancelUpdate(row)"
            >
              取消
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </section>
</template>
