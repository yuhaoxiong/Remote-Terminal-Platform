<script setup lang="ts">
import { Refresh } from "@element-plus/icons-vue";
import { computed, onMounted, reactive, ref } from "vue";

import {
  createAlertNotificationChannel,
  createAlertNotificationPolicy,
  deleteAlertNotificationChannel,
  deleteAlertNotificationPolicy,
  getAlertNotificationSummary,
  listAlertNotificationChannels,
  listAlertNotificationDeliveries,
  listAlertNotificationPolicies,
  retryAlertNotificationDelivery,
  testAlertNotificationChannel,
  updateAlertNotificationChannel,
  updateAlertNotificationPolicy,
  type AlertNotificationChannelRead,
  type AlertNotificationDeliveryRead,
  type AlertNotificationDeliveryStatus,
  type AlertNotificationEventType,
  type AlertNotificationPolicyRead,
  type AlertNotificationSummaryResponse,
  type AlertSeverity,
  type AlertSourceType,
  type AlertStatus,
} from "../api/platform";

interface ChannelFormState {
  id: number | null;
  name: string;
  enabled: boolean;
  webhookUrl: string;
  headersText: string;
  timeoutSeconds: number;
}

interface PolicyFormState {
  id: number | null;
  name: string;
  enabled: boolean;
  channelId: number | null;
  minSeverity: AlertSeverity;
  sourceTypes: AlertSourceType[];
  alertStatuses: AlertStatus[];
  eventTypes: AlertNotificationEventType[];
}

const channels = ref<AlertNotificationChannelRead[]>([]);
const policies = ref<AlertNotificationPolicyRead[]>([]);
const deliveries = ref<AlertNotificationDeliveryRead[]>([]);
const summary = ref<AlertNotificationSummaryResponse | null>(null);
const loading = ref(false);
const savingChannel = ref(false);
const savingPolicy = ref(false);
const actionKey = ref("");
const operationError = ref("");
const operationMessage = ref("");

const channelForm = reactive<ChannelFormState>({
  id: null,
  name: "",
  enabled: true,
  webhookUrl: "",
  headersText: "{}",
  timeoutSeconds: 5,
});

const policyForm = reactive<PolicyFormState>({
  id: null,
  name: "",
  enabled: true,
  channelId: null,
  minSeverity: "critical",
  sourceTypes: [],
  alertStatuses: ["open"],
  eventTypes: ["triggered"],
});

const severityText: Record<AlertSeverity, string> = {
  warning: "警告",
  critical: "严重",
};

const sourceText: Record<AlertSourceType, string> = {
  device: "设备状态",
  metric: "监控指标",
  scheduled_task: "定时任务",
  update_task: "批量更新",
};

const statusText: Record<AlertStatus, string> = {
  open: "未处理",
  acknowledged: "已确认",
  resolved: "已恢复",
};

const eventText: Record<AlertNotificationEventType, string> = {
  triggered: "触发",
  acknowledged: "确认",
  resolved: "手动恢复",
  auto_resolved: "自动恢复",
};

const deliveryStatusText: Record<AlertNotificationDeliveryStatus, string> = {
  pending: "待发送",
  success: "成功",
  failed: "失败",
  retrying: "待重试",
  skipped: "已跳过",
};

const channelOptions = computed(() =>
  channels.value.map((channel) => ({
    label: `${channel.name}${channel.enabled ? "" : "（停用）"}`,
    value: channel.id,
  })),
);

function formatTime(value: string | null): string {
  return value ? value.replace("T", " ").slice(0, 16) : "暂无";
}

function deliveryTagType(status: string): "success" | "warning" | "danger" | "info" {
  if (status === "success") {
    return "success";
  }
  if (status === "failed") {
    return "danger";
  }
  return status === "retrying" ? "warning" : "info";
}

function resetChannelForm() {
  channelForm.id = null;
  channelForm.name = "";
  channelForm.enabled = true;
  channelForm.webhookUrl = "";
  channelForm.headersText = "{}";
  channelForm.timeoutSeconds = 5;
}

function resetPolicyForm() {
  policyForm.id = null;
  policyForm.name = "";
  policyForm.enabled = true;
  policyForm.channelId = channels.value[0]?.id ?? null;
  policyForm.minSeverity = "critical";
  policyForm.sourceTypes = [];
  policyForm.alertStatuses = ["open"];
  policyForm.eventTypes = ["triggered"];
}

function editChannel(channel: AlertNotificationChannelRead) {
  operationError.value = "";
  operationMessage.value = "";
  channelForm.id = channel.id;
  channelForm.name = channel.name;
  channelForm.enabled = channel.enabled;
  channelForm.webhookUrl = "";
  channelForm.headersText = channel.header_keys.length ? "{}" : "{}";
  channelForm.timeoutSeconds = channel.timeout_seconds;
}

function editPolicy(policy: AlertNotificationPolicyRead) {
  operationError.value = "";
  operationMessage.value = "";
  policyForm.id = policy.id;
  policyForm.name = policy.name;
  policyForm.enabled = policy.enabled;
  policyForm.channelId = policy.channel_id;
  policyForm.minSeverity = policy.min_severity as AlertSeverity;
  policyForm.sourceTypes = policy.source_types as AlertSourceType[];
  policyForm.alertStatuses = policy.alert_statuses as AlertStatus[];
  policyForm.eventTypes = policy.event_types as AlertNotificationEventType[];
}

function parseHeaders(): Record<string, string> {
  const raw = channelForm.headersText.trim();
  if (!raw) {
    return {};
  }
  const parsed = JSON.parse(raw) as unknown;
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("请求头必须是 JSON 对象");
  }
  return Object.fromEntries(Object.entries(parsed).map(([key, value]) => [key, String(value)]));
}

async function loadNotificationData() {
  loading.value = true;
  operationError.value = "";
  try {
    const [channelResponse, policyResponse, deliveryResponse, summaryResponse] = await Promise.all([
      listAlertNotificationChannels(),
      listAlertNotificationPolicies(),
      listAlertNotificationDeliveries(),
      getAlertNotificationSummary(),
    ]);
    channels.value = channelResponse.items;
    policies.value = policyResponse.items;
    deliveries.value = deliveryResponse.items;
    summary.value = summaryResponse;
    if (!policyForm.channelId) {
      policyForm.channelId = channels.value[0]?.id ?? null;
    }
  } catch (error) {
    operationError.value = "无法加载告警通知配置，请检查后端服务和认证状态。";
  } finally {
    loading.value = false;
  }
}

async function saveChannel() {
  savingChannel.value = true;
  operationError.value = "";
  operationMessage.value = "";
  try {
    const headers = parseHeaders();
    if (channelForm.id) {
      const payload = {
        name: channelForm.name,
        enabled: channelForm.enabled,
        headers,
        timeout_seconds: channelForm.timeoutSeconds,
        ...(channelForm.webhookUrl.trim() ? { webhook_url: channelForm.webhookUrl.trim() } : {}),
      };
      await updateAlertNotificationChannel(channelForm.id, payload);
      operationMessage.value = "通知通道已更新。";
    } else {
      await createAlertNotificationChannel({
        name: channelForm.name,
        channel_type: "webhook",
        enabled: channelForm.enabled,
        webhook_url: channelForm.webhookUrl.trim(),
        headers,
        timeout_seconds: channelForm.timeoutSeconds,
      });
      operationMessage.value = "通知通道已创建。";
    }
    resetChannelForm();
    await loadNotificationData();
  } catch (error) {
    operationError.value = "保存通知通道失败，请检查 Webhook 地址、请求头 JSON 和加密配置。";
  } finally {
    savingChannel.value = false;
  }
}

async function removeChannel(channel: AlertNotificationChannelRead) {
  actionKey.value = `channel-delete-${channel.id}`;
  operationError.value = "";
  operationMessage.value = "";
  try {
    await deleteAlertNotificationChannel(channel.id);
    operationMessage.value = "通知通道已删除。";
    await loadNotificationData();
  } catch (error) {
    operationError.value = "删除通道失败，请先删除引用该通道的通知策略。";
  } finally {
    actionKey.value = "";
  }
}

async function sendTest(channel: AlertNotificationChannelRead) {
  actionKey.value = `channel-test-${channel.id}`;
  operationError.value = "";
  operationMessage.value = "";
  try {
    await testAlertNotificationChannel(channel.id);
    operationMessage.value = "测试通知已发送。";
    await loadNotificationData();
  } catch (error) {
    operationError.value = "测试通知失败，请检查 Webhook 地址和外部服务状态。";
  } finally {
    actionKey.value = "";
  }
}

async function savePolicy() {
  if (!policyForm.channelId) {
    operationError.value = "请先创建通知通道。";
    return;
  }
  savingPolicy.value = true;
  operationError.value = "";
  operationMessage.value = "";
  const payload = {
    name: policyForm.name,
    enabled: policyForm.enabled,
    channel_id: policyForm.channelId,
    min_severity: policyForm.minSeverity,
    source_types: policyForm.sourceTypes,
    alert_statuses: policyForm.alertStatuses,
    event_types: policyForm.eventTypes,
  };
  try {
    if (policyForm.id) {
      await updateAlertNotificationPolicy(policyForm.id, payload);
      operationMessage.value = "通知策略已更新。";
    } else {
      await createAlertNotificationPolicy(payload);
      operationMessage.value = "通知策略已创建。";
    }
    resetPolicyForm();
    await loadNotificationData();
  } catch (error) {
    operationError.value = "保存通知策略失败，请检查通道、级别和事件配置。";
  } finally {
    savingPolicy.value = false;
  }
}

async function removePolicy(policy: AlertNotificationPolicyRead) {
  actionKey.value = `policy-delete-${policy.id}`;
  operationError.value = "";
  operationMessage.value = "";
  try {
    await deleteAlertNotificationPolicy(policy.id);
    operationMessage.value = "通知策略已删除。";
    await loadNotificationData();
  } catch (error) {
    operationError.value = "删除通知策略失败，请确认没有外键引用或稍后重试。";
  } finally {
    actionKey.value = "";
  }
}

async function retryDelivery(delivery: AlertNotificationDeliveryRead) {
  actionKey.value = `delivery-retry-${delivery.id}`;
  operationError.value = "";
  operationMessage.value = "";
  try {
    await retryAlertNotificationDelivery(delivery.id);
    operationMessage.value = "通知投递已重试。";
    await loadNotificationData();
  } catch (error) {
    operationError.value = "重试通知投递失败，请检查通道配置。";
  } finally {
    actionKey.value = "";
  }
}

onMounted(() => {
  void loadNotificationData();
});
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <h3>外部通知</h3>
        <p class="panel-copy">Webhook 默认仅发送严重告警的触发事件，敏感配置使用后端加密密钥保存。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadNotificationData">刷新</el-button>
    </div>

    <div class="stat-grid notification-stats">
      <div class="stat-tile">
        <span>启用通道</span>
        <strong>{{ summary?.enabled_channel_count ?? 0 }}</strong>
      </div>
      <div class="stat-tile">
        <span>启用策略</span>
        <strong>{{ summary?.enabled_policy_count ?? 0 }}</strong>
      </div>
      <div class="stat-tile danger">
        <span>失败投递</span>
        <strong>{{ summary?.failed_delivery_count ?? 0 }}</strong>
      </div>
      <div class="stat-tile warning">
        <span>待重试</span>
        <strong>{{ summary?.retrying_delivery_count ?? 0 }}</strong>
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
    <el-alert
      v-if="operationMessage"
      class="validation-alert"
      type="success"
      show-icon
      :closable="false"
      :title="operationMessage"
    />
    <el-alert
      v-for="warning in summary?.warnings ?? []"
      :key="warning"
      class="validation-alert"
      type="warning"
      show-icon
      :closable="false"
      :title="warning"
    />

    <div class="notification-layout">
      <section class="sub-panel">
        <div class="sub-panel-header">
          <h4>{{ channelForm.id ? "编辑 Webhook 通道" : "新增 Webhook 通道" }}</h4>
          <el-button text @click="resetChannelForm">清空</el-button>
        </div>
        <el-form label-position="top" class="compact-form">
          <el-form-item label="通道名称">
            <el-input v-model="channelForm.name" placeholder="例如：生产告警 Webhook" />
          </el-form-item>
          <el-form-item label="Webhook 地址">
            <el-input v-model="channelForm.webhookUrl" :placeholder="channelForm.id ? '留空表示不更新地址' : 'https://example.com/webhook'" />
          </el-form-item>
          <el-form-item label="请求头 JSON">
            <el-input v-model="channelForm.headersText" type="textarea" :rows="3" placeholder='{"Authorization":"Bearer token"}' />
          </el-form-item>
          <div class="inline-fields">
            <el-form-item label="超时秒数">
              <el-input-number v-model="channelForm.timeoutSeconds" :min="1" :max="30" controls-position="right" />
            </el-form-item>
            <el-form-item label="启用">
              <el-switch v-model="channelForm.enabled" />
            </el-form-item>
          </div>
          <el-button type="primary" :loading="savingChannel" @click="saveChannel">
            {{ channelForm.id ? "保存通道" : "创建通道" }}
          </el-button>
        </el-form>
      </section>

      <section class="sub-panel">
        <div class="sub-panel-header">
          <h4>{{ policyForm.id ? "编辑通知策略" : "新增通知策略" }}</h4>
          <el-button text @click="resetPolicyForm">清空</el-button>
        </div>
        <el-form label-position="top" class="compact-form">
          <el-form-item label="策略名称">
            <el-input v-model="policyForm.name" placeholder="例如：严重告警触发通知" />
          </el-form-item>
          <el-form-item label="通知通道">
            <el-select v-model="policyForm.channelId" placeholder="请选择通道" class="full-width">
              <el-option v-for="item in channelOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <div class="inline-fields">
            <el-form-item label="最低级别">
              <select v-model="policyForm.minSeverity" class="native-select rule-select" aria-label="最低告警级别">
                <option value="critical">严重</option>
                <option value="warning">警告</option>
              </select>
            </el-form-item>
            <el-form-item label="启用">
              <el-switch v-model="policyForm.enabled" />
            </el-form-item>
          </div>
          <el-form-item label="触发事件">
            <el-checkbox-group v-model="policyForm.eventTypes">
              <el-checkbox value="triggered">触发</el-checkbox>
              <el-checkbox value="acknowledged">确认</el-checkbox>
              <el-checkbox value="resolved">手动恢复</el-checkbox>
              <el-checkbox value="auto_resolved">自动恢复</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          <el-form-item label="告警来源">
            <el-checkbox-group v-model="policyForm.sourceTypes">
              <el-checkbox value="device">设备状态</el-checkbox>
              <el-checkbox value="metric">监控指标</el-checkbox>
              <el-checkbox value="scheduled_task">定时任务</el-checkbox>
              <el-checkbox value="update_task">批量更新</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          <el-form-item label="告警状态">
            <el-checkbox-group v-model="policyForm.alertStatuses">
              <el-checkbox value="open">未处理</el-checkbox>
              <el-checkbox value="acknowledged">已确认</el-checkbox>
              <el-checkbox value="resolved">已恢复</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          <el-button type="primary" :loading="savingPolicy" @click="savePolicy">
            {{ policyForm.id ? "保存策略" : "创建策略" }}
          </el-button>
        </el-form>
      </section>
    </div>

    <section class="nested-panel">
      <div class="panel-header">
        <h4>通知通道</h4>
      </div>
      <el-table :data="channels" stripe class="table-panel" empty-text="暂无通知通道">
        <el-table-column prop="name" label="名称" min-width="170" />
        <el-table-column label="地址" min-width="220">
          <template #default="{ row }">
            {{ row.webhook_url_preview ?? "未配置" }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? "启用" : "停用" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近测试" width="150">
          <template #default="{ row }">
            {{ row.last_test_status ?? "暂无" }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editChannel(row)">编辑</el-button>
            <el-button size="small" :loading="actionKey === `channel-test-${row.id}`" @click="sendTest(row)">测试</el-button>
            <el-button
              size="small"
              type="danger"
              :loading="actionKey === `channel-delete-${row.id}`"
              @click="removeChannel(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="nested-panel">
      <div class="panel-header">
        <h4>通知策略</h4>
      </div>
      <el-table :data="policies" stripe class="table-panel" empty-text="暂无通知策略">
        <el-table-column prop="name" label="名称" min-width="170" />
        <el-table-column label="通道" width="160">
          <template #default="{ row }">
            {{ channels.find((channel) => channel.id === row.channel_id)?.name ?? row.channel_id }}
          </template>
        </el-table-column>
        <el-table-column label="最低级别" width="110">
          <template #default="{ row }">
            {{ severityText[row.min_severity as AlertSeverity] ?? row.min_severity }}
          </template>
        </el-table-column>
        <el-table-column label="事件" min-width="170">
          <template #default="{ row }">
            {{ row.event_types.map((item: AlertNotificationEventType) => eventText[item] ?? item).join("、") || "全部" }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? "启用" : "停用" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editPolicy(row)">编辑</el-button>
            <el-button size="small" type="danger" :loading="actionKey === `policy-delete-${row.id}`" @click="removePolicy(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="nested-panel">
      <div class="panel-header">
        <h4>最近投递</h4>
      </div>
      <el-table :data="deliveries" stripe class="table-panel" empty-text="暂无投递记录">
        <el-table-column label="告警" min-width="180">
          <template #default="{ row }">
            {{ row.alert_title ?? `告警 ${row.alert_id}` }}
          </template>
        </el-table-column>
        <el-table-column label="通道/策略" min-width="170">
          <template #default="{ row }">
            {{ row.channel_name ?? row.channel_id }} / {{ row.policy_name ?? row.policy_id }}
          </template>
        </el-table-column>
        <el-table-column label="事件" width="110">
          <template #default="{ row }">
            {{ eventText[row.event_type as AlertNotificationEventType] ?? row.event_type }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="deliveryTagType(row.status)">
              {{ deliveryStatusText[row.status as AlertNotificationDeliveryStatus] ?? row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="尝试" width="80" prop="attempt_count" />
        <el-table-column label="最近发送" width="150">
          <template #default="{ row }">
            {{ formatTime(row.last_attempt_at) }}
          </template>
        </el-table-column>
        <el-table-column label="错误" min-width="180">
          <template #default="{ row }">
            {{ row.error_message ?? row.response_summary ?? "-" }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              :disabled="row.status === 'success'"
              :loading="actionKey === `delivery-retry-${row.id}`"
              @click="retryDelivery(row)"
            >
              重试
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </section>
</template>

<style scoped>
.notification-stats {
  margin: 14px 0;
}

.notification-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.sub-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.sub-panel-header h4,
.nested-panel h4 {
  margin: 0;
}

.compact-form {
  display: grid;
  gap: 2px;
}

.inline-fields {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  align-items: end;
}

.full-width {
  width: 100%;
}

@media (max-width: 960px) {
  .notification-layout,
  .inline-fields {
    grid-template-columns: 1fr;
  }
}
</style>
