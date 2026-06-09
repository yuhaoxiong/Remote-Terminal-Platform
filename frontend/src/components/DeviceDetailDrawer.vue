<script setup lang="ts">
import { Close, Connection, Delete, Document, Edit, FolderOpened, VideoPlay } from "@element-plus/icons-vue";

import StatusBadge from "./StatusBadge.vue";

interface DeviceDetail {
  id: number;
  name: string;
  device_sn: string;
  project_id: string;
  group: string;
  group_id: number | null;
  location: string;
  tags: string[];
  status: "online" | "offline" | "degraded" | "unknown";
  ssh_port: number | null;
  vnc_port: number | null;
  ssh_user: string;
  ssh_auth_type: string;
  ssh_credential_configured: boolean;
  cpu: number | null;
  memory: number | null;
  disk: number | null;
  metricRecordedAt: string | null;
  metricStale: boolean;
  metricLoadFailed: boolean;
}

const props = defineProps<{
  visible: boolean;
  device: DeviceDetail | null;
}>();

const emit = defineEmits<{
  "update:visible": [visible: boolean];
  ssh: [device: DeviceDetail];
  vnc: [device: DeviceDetail];
  files: [device: DeviceDetail];
  sync: [device: DeviceDetail];
  edit: [device: DeviceDetail];
  remove: [device: DeviceDetail];
}>();

const statusText = {
  online: "在线",
  offline: "离线",
  degraded: "异常",
  unknown: "未知",
};

const statusState = {
  online: "success",
  offline: "danger",
  degraded: "warning",
  unknown: "info",
} as const;

function formatTime(value: string | null): string {
  return value ? value.replace("T", " ").slice(0, 16) : "未上报";
}

function metricText(value: number | null): string {
  return value === null ? "暂无" : `${value}%`;
}

function sshReason(device: DeviceDetail): string {
  if (device.ssh_port === null) return "缺少 SSH 端口";
  if (!device.ssh_credential_configured) return "缺少 SSH 凭据";
  return "";
}

function vncReason(device: DeviceDetail): string {
  return device.vnc_port === null ? "缺少 VNC 端口" : "";
}
</script>

<template>
  <el-drawer
    :model-value="visible"
    size="380px"
    class="device-detail-drawer"
    :with-header="false"
    @update:model-value="emit('update:visible', $event)"
  >
    <template v-if="props.device">
      <div class="drawer-header">
        <div>
          <h3>{{ props.device.name }}</h3>
          <p>{{ props.device.device_sn }} · {{ props.device.project_id }}</p>
        </div>
        <el-button :icon="Close" circle text @click="emit('update:visible', false)" />
      </div>

      <section class="drawer-block">
        <StatusBadge :label="statusText[props.device.status]" :state="statusState[props.device.status]" />
        <div class="detail-grid">
          <span>分组</span><strong>{{ props.device.group }}</strong>
          <span>位置</span><strong>{{ props.device.location }}</strong>
          <span>SSH 端口</span><strong>{{ props.device.ssh_port ?? "缺失" }}</strong>
          <span>VNC 端口</span><strong>{{ props.device.vnc_port ?? "缺失" }}</strong>
        </div>
      </section>

      <section class="drawer-block">
        <h4>SSH 凭据状态</h4>
        <div class="detail-grid">
          <span>用户</span><strong>{{ props.device.ssh_user }}</strong>
          <span>认证方式</span><strong>{{ props.device.ssh_auth_type }}</strong>
          <span>凭据</span><strong>{{ props.device.ssh_credential_configured ? "已配置" : "未配置" }}</strong>
        </div>
      </section>

      <section class="drawer-block">
        <h4>最近指标</h4>
        <div class="metric-mini-grid">
          <div><span>CPU</span><strong>{{ metricText(props.device.cpu) }}</strong></div>
          <div><span>内存</span><strong>{{ metricText(props.device.memory) }}</strong></div>
          <div><span>磁盘</span><strong>{{ metricText(props.device.disk) }}</strong></div>
        </div>
        <p class="muted">{{ formatTime(props.device.metricRecordedAt) }}</p>
        <el-alert v-if="props.device.metricLoadFailed" type="warning" title="最新指标加载失败" show-icon :closable="false" />
        <el-alert v-else-if="props.device.metricStale" type="warning" title="指标超过 10 分钟未更新" show-icon :closable="false" />
      </section>

      <section class="drawer-block">
        <h4>快速操作</h4>
        <div class="quick-action-grid">
          <el-tooltip :content="sshReason(props.device) || '打开 SSH 连接'" placement="top">
            <el-button :icon="Connection" :disabled="Boolean(sshReason(props.device))" @click="emit('ssh', props.device)">SSH</el-button>
          </el-tooltip>
          <el-tooltip :content="vncReason(props.device) || '打开 VNC 连接'" placement="top">
            <el-button :icon="VideoPlay" :disabled="Boolean(vncReason(props.device))" @click="emit('vnc', props.device)">VNC</el-button>
          </el-tooltip>
          <el-button :icon="FolderOpened" @click="emit('files', props.device)">文件</el-button>
          <el-button :icon="Document" @click="emit('sync', props.device)">同步配置</el-button>
          <el-button :icon="Edit" @click="emit('edit', props.device)">编辑</el-button>
          <el-button type="danger" :icon="Delete" @click="emit('remove', props.device)">删除</el-button>
        </div>
      </section>
    </template>
  </el-drawer>
</template>
