<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import {
  getEffectiveSystemSettings,
  getSystemSettingSchema,
  listSystemSettingChanges,
  resetSystemSetting,
  restartSystemService,
  updateSystemSettingGroup,
  type SystemSettingChangeRead,
  type SystemSettingEffectiveItem,
  type SystemSettingEffectiveResponse,
  type SystemSettingSchemaItem,
  type SystemSettingSchemaResponse,
} from "../api/platform";

const schema = ref<SystemSettingSchemaResponse | null>(null);
const effective = ref<SystemSettingEffectiveResponse | null>(null);
const changes = ref<SystemSettingChangeRead[]>([]);
const loading = ref(false);
const savingGroup = ref("");
const restartLoading = ref(false);
const restartConfirmText = ref("");
const formValues = reactive<Record<string, Record<string, string | number | boolean | null>>>({});

const editableGroups = computed(() => {
  if (!schema.value) {
    return [];
  }
  return Object.entries(schema.value.groups)
    .filter(([key]) => key !== "readonly_status")
    .map(([key, label]) => ({
      key,
      label,
      items: schema.value?.items.filter((item) => item.category === key && item.editable) ?? [],
    }))
    .filter((group) => group.items.length > 0);
});

const readonlyItems = computed(() => schema.value?.items.filter((item) => !item.editable) ?? []);
const effectiveByKey = computed(() => {
  const items = effective.value?.items ?? [];
  return Object.fromEntries(items.map((item) => [item.key, item]));
});

function sourceLabel(source: string): string {
  if (source === "database") {
    return "数据库覆盖";
  }
  if (source === "system") {
    return "系统配置";
  }
  return "默认值";
}

function sourceTag(source: string): "success" | "warning" | "info" {
  if (source === "database") {
    return "success";
  }
  if (source === "system") {
    return "warning";
  }
  return "info";
}

function effectiveItem(key: string): SystemSettingEffectiveItem | undefined {
  return effectiveByKey.value[key];
}

function displayValue(item: SystemSettingSchemaItem): string {
  const current = effectiveItem(item.key);
  if (item.secret) {
    return current?.configured ? "已配置" : "未配置";
  }
  const value = current?.value;
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "boolean") {
    return value ? "启用" : "停用";
  }
  return String(value);
}

function initializeForms() {
  for (const group of editableGroups.value) {
    formValues[group.key] = {};
    for (const item of group.items) {
      const current = effectiveItem(item.key);
      formValues[group.key][item.key] = item.secret ? "" : (current?.value ?? "");
    }
  }
}

async function loadSystemSettings() {
  loading.value = true;
  try {
    const [schemaResponse, effectiveResponse, changeResponse] = await Promise.all([
      getSystemSettingSchema(),
      getEffectiveSystemSettings(),
      listSystemSettingChanges(),
    ]);
    schema.value = schemaResponse;
    effective.value = effectiveResponse;
    changes.value = changeResponse.items;
    initializeForms();
  } catch {
    ElMessage.error("无法加载系统设置，请检查后端服务或当前账号权限。");
  } finally {
    loading.value = false;
  }
}

function groupNeedsRestart(groupKey: string): boolean {
  const group = editableGroups.value.find((item) => item.key === groupKey);
  return Boolean(group?.items.some((item) => item.requires_restart && formValues[groupKey]?.[item.key] !== undefined));
}

async function saveGroup(groupKey: string) {
  const group = editableGroups.value.find((item) => item.key === groupKey);
  if (!group) {
    return;
  }
  if (groupNeedsRestart(groupKey)) {
    await ElMessageBox.confirm(
      "当前分组包含重启后生效配置，保存后不会立即按新值运行。请在合适时间点击“重启服务”完成生效。",
      "配置需重启后生效",
      { type: "warning", confirmButtonText: "继续保存", cancelButtonText: "取消" },
    );
  }
  savingGroup.value = groupKey;
  try {
    const payload: Record<string, unknown> = {};
    for (const item of group.items) {
      const value = formValues[groupKey]?.[item.key];
      if (item.secret && (value === "" || value === null || value === undefined)) {
        continue;
      }
      payload[item.key] = value;
    }
    const response = await updateSystemSettingGroup(groupKey, payload);
    effective.value = {
      ...(effective.value ?? {
        database_override_count: 0,
        pending_restart_count: 0,
        credential_encryption_configured: false,
        systemd_managed: false,
      }),
      items: response.items,
      pending_restart_count: response.pending_restart_count,
    };
    const changeResponse = await listSystemSettingChanges();
    changes.value = changeResponse.items;
    initializeForms();
    ElMessage.success(response.requires_restart ? "配置已保存，重启服务后生效。" : "配置已保存并立即生效。");
  } catch (error) {
    const message = error instanceof Error ? error.message : "系统设置保存失败";
    ElMessage.error(message);
  } finally {
    savingGroup.value = "";
  }
}

async function resetItem(item: SystemSettingSchemaItem) {
  await ElMessageBox.confirm(
    `将删除 ${item.name} 的数据库覆盖值，并回退到系统配置或默认值。`,
    "恢复默认值",
    { type: "warning", confirmButtonText: "恢复", cancelButtonText: "取消" },
  );
  await resetSystemSetting(item.key);
  await loadSystemSettings();
  ElMessage.success("已恢复默认值。");
}

async function restartService() {
  if (restartConfirmText.value !== "确认重启") {
    ElMessage.warning("请输入“确认重启”后再执行。");
    return;
  }
  await ElMessageBox.confirm(
    "服务将短暂不可用，远程连接、批量任务进度刷新和告警投递可能受到影响。请确认后端已由 systemd 托管。",
    "确认重启服务",
    { type: "warning", confirmButtonText: "确认重启", cancelButtonText: "取消" },
  );
  restartLoading.value = true;
  try {
    const response = await restartSystemService(restartConfirmText.value);
    ElMessage.success(response.message || "服务正在重启。");
  } catch (error) {
    const message = error instanceof Error ? error.message : "重启服务失败";
    ElMessage.error(message);
  } finally {
    restartLoading.value = false;
  }
}

onMounted(() => {
  void loadSystemSettings();
});
</script>

<template>
  <section class="page-section system-settings-page" data-testid="system-settings-page">
    <div class="toolbar">
      <h3>系统设置</h3>
      <el-button :loading="loading" @click="loadSystemSettings">刷新设置</el-button>
    </div>

    <el-skeleton v-if="loading && !schema" :rows="8" animated />

    <template v-else-if="schema && effective">
      <section class="panel settings-status-panel">
        <el-alert
          v-if="effective.pending_restart_count > 0"
          type="warning"
          show-icon
          :closable="false"
          title="存在待重启后生效的配置，请在合适时间重启服务。"
        />
        <div class="settings-status-grid">
          <div class="item-card">
            <h3>数据库覆盖</h3>
            <strong>{{ effective.database_override_count }}</strong>
            <p>当前覆盖项数量</p>
          </div>
          <div class="item-card">
            <h3>待重启配置</h3>
            <strong>{{ effective.pending_restart_count }}</strong>
            <p>重启后自动清除</p>
          </div>
          <div class="item-card">
            <h3>凭据加密</h3>
            <el-tag :type="effective.credential_encryption_configured ? 'success' : 'warning'">
              {{ effective.credential_encryption_configured ? "已配置" : "未配置" }}
            </el-tag>
            <p>未配置时禁止保存敏感配置</p>
          </div>
          <div class="item-card">
            <h3>systemd 托管</h3>
            <el-tag :type="effective.systemd_managed ? 'success' : 'warning'">
              {{ effective.systemd_managed ? "已检测到" : "未确认" }}
            </el-tag>
            <p>未确认时后端会拒绝重启</p>
          </div>
        </div>
        <div class="restart-row">
          <el-input
            v-model="restartConfirmText"
            data-testid="restart-confirm-text"
            placeholder="输入 确认重启"
            clearable
          />
          <el-button
            data-testid="restart-service"
            type="danger"
            :loading="restartLoading"
            @click="restartService"
          >
            重启服务
          </el-button>
        </div>
      </section>

      <section v-for="group in editableGroups" :key="group.key" class="panel">
        <div class="panel-header">
          <h3>{{ group.label }}</h3>
          <el-button
            :data-testid="`save-settings-${group.key}`"
            type="primary"
            :loading="savingGroup === group.key"
            @click="saveGroup(group.key)"
          >
            保存分组
          </el-button>
        </div>
        <div class="settings-grid">
          <div v-for="item in group.items" :key="item.key" class="setting-field">
            <div class="setting-field__header">
              <strong>{{ item.name }}</strong>
              <span>
                <el-tag size="small" :type="sourceTag(effectiveItem(item.key)?.source ?? 'default')">
                  {{ sourceLabel(effectiveItem(item.key)?.source ?? "default") }}
                </el-tag>
                <el-tag v-if="item.requires_restart" size="small" type="warning">重启后生效</el-tag>
                <el-tag v-if="effectiveItem(item.key)?.pending_restart" size="small" type="danger">待重启</el-tag>
              </span>
            </div>
            <p>{{ item.description }}</p>
            <el-input-number
              v-if="item.value_type === 'int'"
              v-model="formValues[group.key][item.key]"
              :min="item.min_value ?? undefined"
              :max="item.max_value ?? undefined"
            />
            <el-switch v-else-if="item.value_type === 'bool'" v-model="formValues[group.key][item.key]" />
            <el-select v-else-if="item.value_type === 'enum'" v-model="formValues[group.key][item.key]">
              <el-option v-for="option in item.options ?? []" :key="option" :label="option" :value="option" />
            </el-select>
            <el-input
              v-else
              v-model="formValues[group.key][item.key]"
              :data-testid="`setting-${item.key}`"
              :type="item.secret ? 'password' : 'text'"
              :placeholder="item.secret ? displayValue(item) : item.name"
              :disabled="item.secret && !effective.credential_encryption_configured"
              show-password
            />
            <div class="setting-field__footer">
              <span>当前值：{{ displayValue(item) }}</span>
              <el-button
                v-if="effectiveItem(item.key)?.source === 'database'"
                link
                type="primary"
                :data-testid="`reset-setting-${item.key}`"
                @click="resetItem(item)"
              >
                恢复默认值
              </el-button>
            </div>
            <el-alert
              v-if="item.secret && !effective.credential_encryption_configured"
              type="warning"
              show-icon
              :closable="false"
              title="未配置凭据加密密钥，不能保存该敏感配置。"
            />
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <h3>只读状态</h3>
          <el-tag type="info">不可由数据库覆盖</el-tag>
        </div>
        <div class="list-grid">
          <div v-for="item in readonlyItems" :key="item.key" class="item-card">
            <h3>{{ item.name }}</h3>
            <el-tag :type="effectiveItem(item.key)?.configured ? 'success' : 'warning'">
              {{ displayValue(item) }}
            </el-tag>
            <p>{{ item.description }}</p>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <h3>变更历史</h3>
          <el-button @click="loadSystemSettings">刷新历史</el-button>
        </div>
        <el-table :data="changes" empty-text="暂无系统设置变更记录">
          <el-table-column prop="created_at" label="时间" min-width="180" />
          <el-table-column prop="actor_username" label="操作者" min-width="120" />
          <el-table-column prop="setting_key" label="配置项" min-width="220" />
          <el-table-column prop="action" label="动作" min-width="100" />
          <el-table-column prop="old_value_snapshot" label="旧值" min-width="140" />
          <el-table-column prop="new_value_snapshot" label="新值" min-width="140" />
          <el-table-column label="状态" min-width="130">
            <template #default="{ row }">
              <el-tag v-if="row.requires_restart" type="warning" size="small">需重启</el-tag>
              <el-tag v-else type="success" size="small">立即生效</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </template>

    <el-empty v-else description="暂无系统设置数据" />
  </section>
</template>

<style scoped>
.system-settings-page {
  display: grid;
  gap: 16px;
}

.settings-status-panel {
  display: grid;
  gap: 16px;
}

.settings-status-grid,
.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
}

.restart-row {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto;
  gap: 12px;
  align-items: center;
}

.setting-field {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid #e5eaf3;
  border-radius: 8px;
  background: #ffffff;
}

.setting-field__header,
.setting-field__footer {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.setting-field__header span {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.setting-field p,
.item-card p {
  margin: 0;
  color: #64748b;
  line-height: 1.6;
}

.setting-field__footer {
  color: #64748b;
  font-size: 13px;
}

@media (max-width: 760px) {
  .restart-row {
    grid-template-columns: 1fr;
  }

  .setting-field__header,
  .setting-field__footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
