<script setup lang="ts">
import { ElMessageBox } from "element-plus";
import { onMounted, reactive, ref } from "vue";

import {
  createScheduledTask,
  deleteScheduledTask,
  executeScheduledTask,
  listScheduledTaskLogs,
  listScheduledTasks,
  toggleScheduledTask,
  updateScheduledTask,
  type OperationLogRead,
  type ScheduledTaskCreateRequest,
  type ScheduledTaskRead,
} from "../api/platform";

const tasks = ref<ScheduledTaskRead[]>([]);
const logs = ref<OperationLogRead[]>([]);
const total = ref(0);
const loading = ref(false);
const formOpen = ref(false);
const editId = ref<number | null>(null);
const errorMessage = ref("");
const lastMessage = ref("");

const form = reactive({
  name: "",
  task_type: "command",
  schedule: "interval:300",
  command: "hostname",
  target_filter: '{\n  "project_id": "frps-import"\n}',
  enabled: true,
});

function resetForm() {
  editId.value = null;
  form.name = "";
  form.task_type = "command";
  form.schedule = "interval:300";
  form.command = "hostname";
  form.target_filter = '{\n  "project_id": "frps-import"\n}';
  form.enabled = true;
}

function formatTime(value: string): string {
  return value ? value.replace("T", " ").slice(0, 16) : "-";
}

function parseTargetFilter(): Record<string, unknown> | null {
  const text = form.target_filter.trim();
  if (!text) {
    return null;
  }
  const parsed = JSON.parse(text);
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("目标筛选必须是 JSON 对象");
  }
  return parsed as Record<string, unknown>;
}

function buildPayload(): ScheduledTaskCreateRequest {
  if (!form.name.trim()) {
    throw new Error("请输入任务名称");
  }
  if (!form.task_type.trim()) {
    throw new Error("请输入任务类型");
  }
  if (!form.schedule.startsWith("cron:") && !form.schedule.startsWith("interval:")) {
    throw new Error("调度表达式必须以 cron: 或 interval: 开头");
  }
  return {
    name: form.name.trim(),
    task_type: form.task_type.trim(),
    schedule: form.schedule.trim(),
    command: form.command.trim() || null,
    target_filter: parseTargetFilter(),
    enabled: form.enabled,
  };
}

async function loadTasks() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await listScheduledTasks();
    total.value = response.total;
    tasks.value = response.items;
  } catch {
    errorMessage.value = "定时任务加载失败";
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  resetForm();
  formOpen.value = true;
}

function openEdit(task: ScheduledTaskRead) {
  editId.value = task.id;
  form.name = task.name;
  form.task_type = task.task_type;
  form.schedule = task.schedule;
  form.command = task.command ?? "";
  form.target_filter = task.target_filter ? JSON.stringify(task.target_filter, null, 2) : "";
  form.enabled = task.enabled;
  formOpen.value = true;
}

async function saveTask() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const payload = buildPayload();
    if (editId.value === null) {
      const created = await createScheduledTask(payload);
      tasks.value.push(created);
      total.value += 1;
      lastMessage.value = "定时任务已创建";
    } else {
      const updated = await updateScheduledTask(editId.value, payload);
      tasks.value = tasks.value.map((task) => (task.id === updated.id ? updated : task));
      lastMessage.value = "定时任务已更新";
    }
    formOpen.value = false;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "定时任务保存失败";
  } finally {
    loading.value = false;
  }
}

async function removeTask(task: ScheduledTaskRead) {
  await ElMessageBox.confirm(`确认删除定时任务 ${task.name}？`, "确认删除定时任务", { type: "warning" });
  loading.value = true;
  errorMessage.value = "";
  try {
    await deleteScheduledTask(task.id);
    tasks.value = tasks.value.filter((item) => item.id !== task.id);
    total.value = Math.max(0, total.value - 1);
    lastMessage.value = "定时任务已删除";
  } catch {
    errorMessage.value = "定时任务删除失败";
  } finally {
    loading.value = false;
  }
}

async function toggleTask(task: ScheduledTaskRead) {
  loading.value = true;
  errorMessage.value = "";
  try {
    const updated = await toggleScheduledTask(task.id);
    tasks.value = tasks.value.map((item) => (item.id === updated.id ? updated : item));
    lastMessage.value = updated.enabled ? "定时任务已启用" : "定时任务已停用";
  } catch {
    errorMessage.value = "定时任务启停失败";
  } finally {
    loading.value = false;
  }
}

async function executeTask(task: ScheduledTaskRead) {
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await executeScheduledTask(task.id);
    lastMessage.value = response.output_summary;
  } catch {
    errorMessage.value = "定时任务执行失败";
  } finally {
    loading.value = false;
  }
}

async function showLogs(task: ScheduledTaskRead) {
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await listScheduledTaskLogs(task.id);
    logs.value = response.items;
    lastMessage.value = `已加载 ${response.total} 条执行日志`;
  } catch {
    errorMessage.value = "定时任务日志加载失败";
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadTasks();
});
</script>

<template>
  <section class="page-section">
    <div class="toolbar">
      <div>
        <h3>定时任务</h3>
        <p class="muted">管理已有定时任务 API，当前不接入真实后台调度器。</p>
      </div>
      <div class="topbar-actions">
        <el-button data-testid="refresh-scheduled-tasks" :loading="loading" @click="loadTasks">刷新</el-button>
        <el-button data-testid="open-scheduled-create" type="primary" @click="openCreate">新建定时任务</el-button>
      </div>
    </div>

    <el-alert v-if="errorMessage" class="validation-alert" type="error" :title="errorMessage" show-icon :closable="false" />
    <el-alert v-if="lastMessage" class="validation-alert" type="success" :title="lastMessage" show-icon :closable="false" />

    <section v-if="formOpen" class="form-panel" aria-label="定时任务表单">
      <div class="panel-header">
        <h3>{{ editId === null ? "创建定时任务" : "编辑定时任务" }}</h3>
        <el-button text @click="formOpen = false">关闭</el-button>
      </div>
      <div class="form-grid">
        <div data-testid="scheduled-name" class="input-wrap"><el-input v-model="form.name" placeholder="任务名称" /></div>
        <div data-testid="scheduled-type" class="input-wrap"><el-input v-model="form.task_type" placeholder="任务类型，例如 command" /></div>
        <div data-testid="scheduled-schedule" class="input-wrap"><el-input v-model="form.schedule" placeholder="interval:300 或 cron:0 * * * *" /></div>
        <label class="field-label">
          <span>启用状态</span>
          <select data-testid="scheduled-enabled" v-model="form.enabled" class="native-select">
            <option :value="true">启用</option>
            <option :value="false">停用</option>
          </select>
        </label>
        <div data-testid="scheduled-command" class="input-wrap textarea-wrap">
          <el-input v-model="form.command" type="textarea" :rows="2" placeholder="命令或任务参数" />
        </div>
        <div data-testid="scheduled-target-filter" class="input-wrap textarea-wrap">
          <el-input v-model="form.target_filter" type="textarea" :rows="4" placeholder="目标筛选 JSON" />
        </div>
      </div>
      <div class="form-actions">
        <el-button data-testid="save-scheduled-task" type="primary" :loading="loading" @click="saveTask">保存定时任务</el-button>
      </div>
    </section>

    <div class="table-panel">
      <el-table :data="tasks" row-key="id" empty-text="暂无定时任务">
        <el-table-column prop="name" label="任务" min-width="170" />
        <el-table-column prop="task_type" label="类型" width="120" />
        <el-table-column prop="schedule" label="调度" min-width="150" />
        <el-table-column prop="command" label="命令" min-width="180" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? "启用" : "停用" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="160">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="360">
          <template #default="{ row }">
            <el-button :data-testid="`edit-scheduled-${row.id}`" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button :data-testid="`toggle-scheduled-${row.id}`" size="small" @click="toggleTask(row)">
              {{ row.enabled ? "停用" : "启用" }}
            </el-button>
            <el-button :data-testid="`execute-scheduled-${row.id}`" size="small" type="primary" @click="executeTask(row)">立即执行</el-button>
            <el-button :data-testid="`logs-scheduled-${row.id}`" size="small" @click="showLogs(row)">日志</el-button>
            <el-button :data-testid="`delete-scheduled-${row.id}`" size="small" type="danger" @click="removeTask(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <section class="panel">
      <div class="panel-header">
        <h3>执行日志</h3>
        <el-tag>{{ logs.length }} 条</el-tag>
      </div>
      <el-table :data="logs" row-key="id" empty-text="暂无定时任务日志">
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="action" label="动作" min-width="160" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="detail" label="详情" min-width="220" />
      </el-table>
    </section>
  </section>
</template>
