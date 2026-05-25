<script setup lang="ts">
import { Refresh } from "@element-plus/icons-vue";
import { computed, onMounted, reactive, ref } from "vue";

import {
  acknowledgeAlert,
  getAlertSummary,
  listAlertRules,
  listAlerts,
  resolveAlert,
  updateAlertRule,
  type AlertRead,
  type AlertRuleRead,
  type AlertSeverity,
  type AlertSourceType,
  type AlertStatus,
  type AlertSummaryResponse,
} from "../api/platform";

const alerts = ref<AlertRead[]>([]);
const alertTotal = ref(0);
const rules = ref<AlertRuleRead[]>([]);
const summary = ref<AlertSummaryResponse | null>(null);
const loading = ref(false);
const savingRuleId = ref<number | null>(null);
const actionAlertId = ref<number | null>(null);
const operationError = ref("");

const filters = reactive({
  status: "open" as AlertStatus | "",
  severity: "" as AlertSeverity | "",
  source_type: "" as AlertSourceType | "",
});

const sourceText: Record<AlertSourceType, string> = {
  device: "设备状态",
  metric: "监控指标",
  scheduled_task: "定时任务",
  update_task: "批量更新",
};

const severityText: Record<AlertSeverity, string> = {
  warning: "警告",
  critical: "严重",
};

const statusText: Record<AlertStatus, string> = {
  open: "未处理",
  acknowledged: "已确认",
  resolved: "已恢复",
};

const ruleText: Record<string, string> = {
  device_status: "设备离线/未知",
  cpu_high: "CPU 高负载",
  memory_high: "内存高负载",
  disk_high: "磁盘高占用",
  metrics_stale: "指标冻结",
  scheduled_task_failed: "定时任务失败",
  update_task_failed: "批量更新失败",
};

const hasActiveAlerts = computed(() => (summary.value?.active_count ?? 0) > 0);

function severityTagType(severity: AlertSeverity): "danger" | "warning" {
  return severity === "critical" ? "danger" : "warning";
}

function statusTagType(status: AlertStatus): "success" | "warning" | "info" {
  if (status === "resolved") {
    return "success";
  }
  return status === "acknowledged" ? "warning" : "info";
}

function formatTime(value: string | null): string {
  return value ? value.replace("T", " ").slice(0, 16) : "暂无";
}

async function loadAlertsData() {
  loading.value = true;
  operationError.value = "";
  try {
    const [alertResponse, summaryResponse, ruleResponse] = await Promise.all([
      listAlerts({
        limit: 50,
        status: filters.status || undefined,
        severity: filters.severity || undefined,
        source_type: filters.source_type || undefined,
      }),
      getAlertSummary(),
      listAlertRules(),
    ]);
    alerts.value = alertResponse.items;
    alertTotal.value = alertResponse.total;
    summary.value = summaryResponse;
    rules.value = ruleResponse.items;
  } catch (error) {
    operationError.value = "无法加载告警数据，请检查后端服务和认证状态。";
  } finally {
    loading.value = false;
  }
}

async function acknowledge(row: AlertRead) {
  actionAlertId.value = row.id;
  operationError.value = "";
  try {
    await acknowledgeAlert(row.id, { note: "前端确认" });
    await loadAlertsData();
  } catch (error) {
    operationError.value = "确认告警失败，请稍后重试。";
  } finally {
    actionAlertId.value = null;
  }
}

async function resolve(row: AlertRead) {
  actionAlertId.value = row.id;
  operationError.value = "";
  try {
    await resolveAlert(row.id, { note: "前端手动恢复" });
    await loadAlertsData();
  } catch (error) {
    operationError.value = "恢复告警失败，请稍后重试。";
  } finally {
    actionAlertId.value = null;
  }
}

async function saveRule(rule: AlertRuleRead) {
  savingRuleId.value = rule.id;
  operationError.value = "";
  try {
    await updateAlertRule(rule.id, {
      enabled: rule.enabled,
      severity: rule.severity,
      threshold_value: rule.threshold_value,
      window_minutes: rule.window_minutes,
    });
    await loadAlertsData();
  } catch (error) {
    operationError.value = "保存告警规则失败，请检查阈值设置。";
  } finally {
    savingRuleId.value = null;
  }
}

onMounted(() => {
  void loadAlertsData();
});
</script>

<template>
  <section class="page-section">
    <div class="stat-grid">
      <div class="stat-tile warning">
        <span>活跃告警</span>
        <strong>{{ summary?.active_count ?? 0 }}</strong>
      </div>
      <div class="stat-tile danger">
        <span>严重告警</span>
        <strong>{{ summary?.critical_count ?? 0 }}</strong>
      </div>
      <div class="stat-tile info">
        <span>未确认</span>
        <strong>{{ summary?.unacknowledged_count ?? 0 }}</strong>
      </div>
      <div class="stat-tile">
        <span>最近告警</span>
        <strong class="stat-time">{{ formatTime(summary?.latest_alert_at ?? null) }}</strong>
      </div>
    </div>

    <el-alert
      v-if="operationError"
      class="validation-alert"
      type="warning"
      show-icon
      :closable="false"
      :title="operationError"
    />

    <section class="panel">
      <div class="panel-header">
        <div>
          <h3>告警列表</h3>
          <p class="panel-copy">{{ hasActiveAlerts ? "优先处理严重与未确认告警" : "当前暂无活跃告警" }}</p>
        </div>
        <el-button :icon="Refresh" :loading="loading" @click="loadAlertsData">刷新</el-button>
      </div>
      <div class="toolbar alert-toolbar">
        <select v-model="filters.status" class="native-select" aria-label="告警状态" @change="loadAlertsData">
          <option value="">全部状态</option>
          <option value="open">未处理</option>
          <option value="acknowledged">已确认</option>
          <option value="resolved">已恢复</option>
        </select>
        <select v-model="filters.severity" class="native-select" aria-label="告警级别" @change="loadAlertsData">
          <option value="">全部级别</option>
          <option value="warning">警告</option>
          <option value="critical">严重</option>
        </select>
        <select v-model="filters.source_type" class="native-select" aria-label="告警来源" @change="loadAlertsData">
          <option value="">全部来源</option>
          <option value="device">设备状态</option>
          <option value="metric">监控指标</option>
          <option value="scheduled_task">定时任务</option>
          <option value="update_task">批量更新</option>
        </select>
      </div>
      <el-table :data="alerts" stripe class="table-panel" :empty-text="loading ? '加载中' : '暂无告警'">
        <el-table-column prop="title" label="告警" min-width="220">
          <template #default="{ row }">
            <strong>{{ row.title }}</strong>
            <p class="table-subtitle">{{ row.message }}</p>
          </template>
        </el-table-column>
        <el-table-column label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="severityTagType(row.severity)">{{ severityText[row.severity as AlertSeverity] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="120">
          <template #default="{ row }">
            {{ sourceText[row.source_type as AlertSourceType] ?? row.source_type }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusText[row.status as AlertStatus] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="阈值" width="130">
          <template #default="{ row }">
            {{ row.metric_value ?? "-" }} / {{ row.threshold_value ?? "-" }}
          </template>
        </el-table-column>
        <el-table-column label="时间" width="150">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              :disabled="row.status !== 'open'"
              :loading="actionAlertId === row.id"
              @click="acknowledge(row)"
            >
              确认
            </el-button>
            <el-button
              size="small"
              type="success"
              :disabled="row.status === 'resolved'"
              :loading="actionAlertId === row.id"
              @click="resolve(row)"
            >
              恢复
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <p class="table-footnote">共 {{ alertTotal }} 条告警，列表默认显示最近 50 条。</p>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h3>告警规则</h3>
      </div>
      <el-table :data="rules" stripe class="table-panel" empty-text="暂无规则">
        <el-table-column label="规则" min-width="180">
          <template #default="{ row }">
            {{ ruleText[row.rule_type] ?? row.rule_type }}
          </template>
        </el-table-column>
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" />
          </template>
        </el-table-column>
        <el-table-column label="级别" width="130">
          <template #default="{ row }">
            <select v-model="row.severity" class="native-select rule-select" aria-label="规则级别">
              <option value="warning">警告</option>
              <option value="critical">严重</option>
            </select>
          </template>
        </el-table-column>
        <el-table-column label="阈值" width="140">
          <template #default="{ row }">
            <el-input-number v-model="row.threshold_value" :min="0" :max="100" :step="1" controls-position="right" />
          </template>
        </el-table-column>
        <el-table-column label="窗口/分钟" width="140">
          <template #default="{ row }">
            <el-input-number v-model="row.window_minutes" :min="1" :max="1440" :step="1" controls-position="right" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" :loading="savingRuleId === row.id" @click="saveRule(row)">保存</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </section>
</template>
