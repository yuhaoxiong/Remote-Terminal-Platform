<script setup lang="ts">
import { Cpu, Finished, Monitor, Refresh, WarningFilled } from "@element-plus/icons-vue";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { storeToRefs } from "pinia";

import { type AlertSummaryResponse, type MonitoringOverviewResponse } from "../api/platform";
import { useDevicesStore, type Device, type DeviceStatus } from "../stores/devices";
import { useLogsStore } from "../stores/logs";
import { useUpdatesStore } from "../stores/updates";
import { formatTime } from "../utils/format";
import MetricCard from "./MetricCard.vue";

const props = defineProps<{
  serverOverview: MonitoringOverviewResponse | null;
  alertSummary: AlertSummaryResponse | null;
  metricLoadWarning: string;
  loading: boolean;
}>();

const emit = defineEmits<{
  refresh: [];
  navigate: [section: string];
}>();

const devicesStore = useDevicesStore();
const { devices } = storeToRefs(devicesStore);
const updatesStore = useUpdatesStore();
const { pendingTaskCount } = storeToRefs(updatesStore);
const logsStore = useLogsStore();
const { auditLogs } = storeToRefs(logsStore);

const CPU_HIGH_THRESHOLD = 90;
const MEMORY_HIGH_THRESHOLD = 85;
const DISK_HIGH_THRESHOLD = 90;

const statusType: Record<DeviceStatus, "success" | "warning" | "danger" | "info"> = {
  online: "success",
  offline: "danger",
  degraded: "warning",
  unknown: "info",
};

const deviceStatusText: Record<DeviceStatus, string> = {
  online: "在线",
  offline: "离线",
  degraded: "异常",
  unknown: "未知",
};

const logStatusText: Record<string, string> = {
  success: "成功",
  completed: "已完成",
  blocked: "已阻止",
  generated: "已生成",
  ready: "就绪",
};

const statusChartRef = ref<HTMLElement | null>(null);
const riskChartRef = ref<HTMLElement | null>(null);
let statusChart: { setOption: (options: unknown) => void; resize: () => void; dispose: () => void } | null = null;
let riskChart: { setOption: (options: unknown) => void; resize: () => void; dispose: () => void } | null = null;
let chartReady = false;

const overview = computed(() => {
  if (props.serverOverview) {
    return {
      devices: props.serverOverview.total_devices,
      online: props.serverOverview.online_devices,
      degraded: props.serverOverview.offline_devices + props.serverOverview.unknown_devices,
      updates: pendingTaskCount.value === 0 ? 0 : props.serverOverview.total_devices,
    };
  }
  const online = devices.value.filter((device) => device.status === "online").length;
  const degraded = devices.value.filter((device) => device.status !== "online").length;
  return {
    devices: devices.value.length,
    online,
    degraded,
    updates: pendingTaskCount.value,
  };
});

const abnormalDevices = computed(() => {
  const items: Array<{ key: string; device: Device; type: string; description: string; tagType: "danger" | "warning" | "info" }> = [];
  for (const device of devices.value) {
    if (device.status === "offline") {
      items.push({ key: `${device.id}-offline`, device, type: "离线", description: "设备当前处于离线状态", tagType: "danger" });
    } else if (device.status === "unknown") {
      items.push({ key: `${device.id}-unknown`, device, type: "未知", description: "设备状态暂不可确认", tagType: "info" });
    }
    if (device.metricLoadFailed) {
      items.push({ key: `${device.id}-metric-failed`, device, type: "指标失败", description: "最新指标读取失败", tagType: "warning" });
      continue;
    }
    if (device.metricStale) {
      items.push({ key: `${device.id}-stale`, device, type: "指标过期", description: "最新指标超过 10 分钟未更新", tagType: "warning" });
    }
    if (device.cpu !== null && device.cpu >= CPU_HIGH_THRESHOLD) {
      items.push({ key: `${device.id}-cpu`, device, type: "高负载", description: `CPU ${device.cpu}%`, tagType: "danger" });
    }
    if (device.memory !== null && device.memory >= MEMORY_HIGH_THRESHOLD) {
      items.push({ key: `${device.id}-memory`, device, type: "高内存", description: `内存 ${device.memory}%`, tagType: "warning" });
    }
    if (device.disk !== null && device.disk >= DISK_HIGH_THRESHOLD) {
      items.push({ key: `${device.id}-disk`, device, type: "磁盘紧张", description: `磁盘 ${device.disk}%`, tagType: "danger" });
    }
  }
  return items.slice(0, 8);
});

const statusDistribution = computed(() => {
  const online = devices.value.filter((device) => device.status === "online").length;
  const offline = devices.value.filter((device) => device.status === "offline").length;
  const unknown = devices.value.filter((device) => device.status === "unknown").length;
  return [
    { name: "在线", value: online },
    { name: "离线", value: offline },
    { name: "未知", value: unknown },
    { name: "异常", value: abnormalDevices.value.length },
  ];
});

const resourceRiskDistribution = computed(() => {
  let normal = 0;
  let highCpu = 0;
  let highMemory = 0;
  let highDisk = 0;
  let noMetric = 0;
  for (const device of devices.value) {
    if (device.metricLoadFailed || device.metricRecordedAt === null) {
      noMetric += 1;
      continue;
    }
    if (device.cpu !== null && device.cpu >= CPU_HIGH_THRESHOLD) {
      highCpu += 1;
    }
    if (device.memory !== null && device.memory >= MEMORY_HIGH_THRESHOLD) {
      highMemory += 1;
    }
    if (device.disk !== null && device.disk >= DISK_HIGH_THRESHOLD) {
      highDisk += 1;
    }
    if (
      (device.cpu === null || device.cpu < CPU_HIGH_THRESHOLD) &&
      (device.memory === null || device.memory < MEMORY_HIGH_THRESHOLD) &&
      (device.disk === null || device.disk < DISK_HIGH_THRESHOLD)
    ) {
      normal += 1;
    }
  }
  return [
    { name: "正常", value: normal },
    { name: "高CPU", value: highCpu },
    { name: "高内存", value: highMemory },
    { name: "高磁盘", value: highDisk },
    { name: "无指标", value: noMetric },
  ];
});

function metricPercent(value: number | null): number {
  if (value === null || Number.isNaN(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(value)));
}

function metricText(value: number | null): string {
  return value === null ? "暂无指标" : `${metricPercent(value)}%`;
}

function hasMetric(device: Device): boolean {
  return device.cpu !== null || device.memory !== null || device.disk !== null;
}

function pieChartOptions(title: string, data: Array<{ name: string; value: number }>) {
  return {
    title: {
      text: title,
      left: "center",
      top: 0,
      textStyle: {
        fontSize: 13,
        fontWeight: 600,
        color: "#334155",
      },
    },
    tooltip: {
      trigger: "item",
    },
    legend: {
      bottom: 0,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: {
        color: "#64748b",
      },
    },
    series: [
      {
        type: "pie",
        radius: ["42%", "68%"],
        center: ["50%", "48%"],
        avoidLabelOverlap: true,
        label: {
          formatter: "{b}: {c}",
        },
        data,
      },
    ],
  };
}

async function renderCharts() {
  if (import.meta.env.MODE === "test") {
    return;
  }
  await nextTick();
  if (!statusChartRef.value || !riskChartRef.value) {
    return;
  }
  if (!chartReady) {
    const echarts = await import("echarts");
    statusChart = echarts.init(statusChartRef.value);
    riskChart = echarts.init(riskChartRef.value);
    chartReady = true;
  }
  statusChart!.setOption(pieChartOptions("设备状态分布", statusDistribution.value));
  riskChart!.setOption(pieChartOptions("资源风险分布", resourceRiskDistribution.value));
}

onMounted(() => {
  void renderCharts();
});

watch([() => devices.value.length, () => props.serverOverview], () => {
  void renderCharts();
});

onBeforeUnmount(() => {
  statusChart?.dispose();
  riskChart?.dispose();
  chartReady = false;
});
</script>

<template>
  <section class="page-section">
    <div class="stat-grid">
      <MetricCard label="设备总数" :value="overview.devices" unit="台" trend="统一纳管设备" :icon="Cpu" />
      <MetricCard label="在线设备" :value="overview.online" unit="台" tone="success" trend="可远程连接" :icon="Monitor" />
      <MetricCard label="离线/未知" :value="overview.degraded" unit="台" tone="warning" trend="需优先排查" :icon="WarningFilled" />
      <MetricCard label="活跃告警" :value="alertSummary?.active_count ?? 0" unit="条" tone="danger" trend="待确认或恢复" :icon="WarningFilled" />
      <MetricCard label="待执行任务" :value="pendingTaskCount" unit="个" tone="info" trend="批量或定时任务" :icon="Finished" />
    </div>

    <div class="two-column">
      <section class="panel">
        <div class="panel-header">
          <h3>资源快照</h3>
          <el-button :icon="Refresh" text :loading="loading" @click="$emit('refresh')">刷新</el-button>
        </div>
        <el-alert
          v-if="metricLoadWarning"
          class="validation-alert"
          type="warning"
          show-icon
          :closable="false"
          :title="metricLoadWarning"
        />
        <div v-for="device in devices" :key="device.id" class="metric-row">
          <div class="metric-title">
            <div>
              <strong>{{ device.name }}</strong>
              <span>{{ device.project_id }}</span>
            </div>
            <div class="metric-tags">
              <el-tag size="small" :type="statusType[device.status]">{{ deviceStatusText[device.status] }}</el-tag>
              <el-tag v-if="device.metricLoadFailed" size="small" type="warning">指标加载失败</el-tag>
              <el-tag v-else-if="device.metricStale" size="small" type="warning">指标过期</el-tag>
              <el-tag v-else-if="!hasMetric(device)" size="small" type="info">暂无指标</el-tag>
            </div>
          </div>
          <div v-if="device.metricLoadFailed" class="metric-empty">指标加载失败</div>
          <div v-else-if="!hasMetric(device)" class="metric-empty">暂无指标</div>
          <div v-else class="metric-bars">
            <div class="metric-bar">
              <span>CPU {{ metricText(device.cpu) }}</span>
              <el-progress :percentage="metricPercent(device.cpu)" :stroke-width="10" />
            </div>
            <div class="metric-bar">
              <span>内存 {{ metricText(device.memory) }}</span>
              <el-progress :percentage="metricPercent(device.memory)" :stroke-width="10" color="#4f46e5" />
            </div>
            <div class="metric-bar">
              <span>磁盘 {{ metricText(device.disk) }}</span>
              <el-progress :percentage="metricPercent(device.disk)" :stroke-width="10" color="#dc2626" />
            </div>
          </div>
          <small>{{ device.metricRecordedAt ? `最近指标 ${formatTime(device.metricRecordedAt)}` : "未上报" }}</small>
        </div>
        <el-empty v-if="!devices.length" description="暂无设备" />
      </section>

      <section class="panel">
        <div class="panel-header">
          <h3>异常设备</h3>
          <el-button text @click="$emit('navigate', 'devices')">进入设备管理</el-button>
        </div>
        <div v-if="abnormalDevices.length" class="alert-list">
          <div v-for="item in abnormalDevices" :key="item.key" class="alert-row">
            <el-tag size="small" :type="item.tagType">{{ item.type }}</el-tag>
            <div>
              <strong>{{ item.device.name }}</strong>
              <span>{{ item.device.project_id }} · {{ item.description }}</span>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无异常设备" />
      </section>
    </div>

    <div class="two-column chart-row">
      <section class="panel">
        <div class="panel-header">
          <h3>监控分布</h3>
        </div>
        <div v-if="devices.length" class="chart-grid">
          <div ref="statusChartRef" class="chart-box" aria-label="设备状态分布"></div>
          <div ref="riskChartRef" class="chart-box" aria-label="资源风险分布"></div>
          <div class="chart-summary">
            <div v-for="item in statusDistribution" :key="item.name">
              <span>{{ item.name }}</span>
              <strong>{{ item.value }}</strong>
            </div>
            <div v-for="item in resourceRiskDistribution" :key="item.name">
              <span>{{ item.name }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无监控数据" />
      </section>

      <section class="panel">
        <div class="panel-header">
          <h3>最近审计</h3>
          <el-button text @click="$emit('navigate', 'logs')">查看全部</el-button>
        </div>
        <div v-for="log in auditLogs.slice(0, 5)" :key="log.id" class="log-row">
          <el-tag size="small" :type="log.status === 'success' || log.status === 'completed' ? 'success' : 'warning'">
            {{ logStatusText[log.status] ?? log.status }}
          </el-tag>
          <span>{{ log.action }}</span>
          <small>{{ log.detail }}</small>
        </div>
      </section>
    </div>
  </section>
</template>
