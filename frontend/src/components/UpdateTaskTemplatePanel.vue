<script setup lang="ts">
import { ElMessageBox } from "element-plus";
import { onMounted, reactive, ref } from "vue";

import {
  createUpdateTaskTemplate,
  deleteUpdateTaskTemplate,
  listUpdateTaskTemplates,
  updateUpdateTaskTemplate,
  type UpdateTaskTemplateCreateRequest,
  type UpdateTaskTemplateRead,
} from "../api/platform";

const emit = defineEmits<{
  apply: [template: UpdateTaskTemplateRead];
}>();

const templates = ref<UpdateTaskTemplateRead[]>([]);
const loading = ref(false);
const formOpen = ref(false);
const editId = ref<number | null>(null);
const errorMessage = ref("");
const lastMessage = ref("");

const form = reactive({
  name: "",
  description: "",
  command: "hostname",
  task_type: "command",
  default_execution_mode: "dry_run" as "dry_run" | "ssh_command",
});

function resetForm() {
  editId.value = null;
  form.name = "";
  form.description = "";
  form.command = "hostname";
  form.task_type = "command";
  form.default_execution_mode = "dry_run";
}

async function loadTemplates() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await listUpdateTaskTemplates();
    templates.value = response.items;
  } catch {
    errorMessage.value = "命令模板加载失败";
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  resetForm();
  formOpen.value = true;
}

function openEdit(template: UpdateTaskTemplateRead) {
  editId.value = template.id;
  form.name = template.name;
  form.description = template.description ?? "";
  form.command = template.command;
  form.task_type = template.task_type;
  form.default_execution_mode = template.default_execution_mode;
  formOpen.value = true;
}

function buildPayload(): UpdateTaskTemplateCreateRequest {
  if (!form.name.trim()) {
    throw new Error("请输入模板名称");
  }
  if (!form.command.trim()) {
    throw new Error("请输入模板命令");
  }
  return {
    name: form.name.trim(),
    description: form.description.trim() || null,
    command: form.command.trim(),
    task_type: form.task_type.trim() || "command",
    default_execution_mode: form.default_execution_mode,
  };
}

async function saveTemplate() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const payload = buildPayload();
    if (editId.value === null) {
      const created = await createUpdateTaskTemplate(payload);
      templates.value.push(created);
      lastMessage.value = "命令模板已创建";
    } else {
      const updated = await updateUpdateTaskTemplate(editId.value, payload);
      templates.value = templates.value.map((template) => (template.id === updated.id ? updated : template));
      lastMessage.value = "命令模板已更新";
    }
    formOpen.value = false;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "命令模板保存失败";
  } finally {
    loading.value = false;
  }
}

async function removeTemplate(template: UpdateTaskTemplateRead) {
  await ElMessageBox.confirm(`确定删除命令模板 ${template.name}？`, "删除命令模板", { type: "warning" });
  loading.value = true;
  errorMessage.value = "";
  try {
    await deleteUpdateTaskTemplate(template.id);
    templates.value = templates.value.filter((item) => item.id !== template.id);
    lastMessage.value = "命令模板已删除";
  } catch {
    errorMessage.value = "命令模板删除失败";
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadTemplates();
});
</script>

<template>
  <section class="sub-panel" aria-label="命令模板">
    <div class="panel-header">
      <div>
        <h4>命令模板</h4>
        <p class="muted">模板只保存命令和说明，不保存设备凭据。</p>
      </div>
      <div class="topbar-actions">
        <el-button data-testid="refresh-update-templates" :loading="loading" @click="loadTemplates">刷新</el-button>
        <el-button data-testid="open-template-create" type="primary" @click="openCreate">新建模板</el-button>
      </div>
    </div>

    <el-alert v-if="errorMessage" class="validation-alert" type="error" :title="errorMessage" show-icon :closable="false" />
    <el-alert v-if="lastMessage" class="validation-alert" type="success" :title="lastMessage" show-icon :closable="false" />

    <section v-if="formOpen" class="nested-panel" aria-label="命令模板表单">
      <div class="form-grid compact-grid">
        <div data-testid="template-name" class="input-wrap"><el-input v-model="form.name" placeholder="模板名称" /></div>
        <div data-testid="template-type" class="input-wrap"><el-input v-model="form.task_type" placeholder="任务类型" /></div>
        <label class="field-label">
          <span>默认模式</span>
          <select data-testid="template-mode" v-model="form.default_execution_mode" class="native-select">
            <option value="dry_run">演练模式</option>
            <option value="ssh_command">真实 SSH 执行</option>
          </select>
        </label>
        <div data-testid="template-description" class="input-wrap textarea-wrap">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="说明" />
        </div>
        <div data-testid="template-command" class="input-wrap textarea-wrap">
          <el-input v-model="form.command" type="textarea" :rows="3" placeholder="命令" />
        </div>
      </div>
      <div class="form-actions">
        <el-button text @click="formOpen = false">取消</el-button>
        <el-button data-testid="save-template" type="primary" :loading="loading" @click="saveTemplate">保存模板</el-button>
      </div>
    </section>

    <el-table :data="templates" row-key="id" empty-text="暂无命令模板">
      <el-table-column prop="name" label="模板" min-width="150" />
      <el-table-column prop="command" label="命令" min-width="180" />
      <el-table-column label="默认模式" width="130">
        <template #default="{ row }">{{ row.default_execution_mode === "ssh_command" ? "真实 SSH" : "演练" }}</template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button :data-testid="`apply-template-${row.id}`" size="small" type="primary" @click="emit('apply', row)">套用</el-button>
          <el-button :data-testid="`edit-template-${row.id}`" size="small" @click="openEdit(row)">编辑</el-button>
          <el-button :data-testid="`delete-template-${row.id}`" size="small" type="danger" @click="removeTemplate(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>
