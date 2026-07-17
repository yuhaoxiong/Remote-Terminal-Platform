<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import {
  previewUpdateTaskTargets,
  type UpdateTaskTargetDeviceRead,
  type UpdateTaskTargetPreviewResponse,
} from "../api/platform";

interface TargetDevice {
  id: number;
  name: string;
  device_sn: string;
  project_id: number | null;
  group_id: number | null;
  group: string;
  location: string;
  tags: string[];
  status: string;
  ssh_port: number | null;
  ssh_credential_configured: boolean;
}

interface TargetGroup {
  id: number;
  name: string;
}

const props = defineProps<{
  devices: TargetDevice[];
  groups: TargetGroup[];
  executionMode: "dry_run" | "ssh_command";
  initialProjectId?: number | null;
  initialDeviceIds?: number[];
}>();

const emit = defineEmits<{
  "target-change": [targetFilter: Record<string, unknown>];
  "preview-change": [preview: UpdateTaskTargetPreviewResponse | null];
}>();

const filters = reactive({
  search: "",
  project_id: props.initialProjectId ?? "",
  group_id: "" as string,
  status: "",
  tag: "",
});
const selectedDeviceIds = ref<number[]>(props.initialDeviceIds ? [...props.initialDeviceIds] : []);
const preview = ref<UpdateTaskTargetPreviewResponse | null>(null);
const loading = ref(false);
const errorMessage = ref("");

const visibleDevices = computed(() => {
  const keyword = filters.search.trim().toLowerCase();
  return props.devices.filter((device) => {
    const matchesKeyword =
      !keyword ||
      [device.name, device.device_sn, device.project_id, device.location, device.tags.join(",")]
        .join(" ")
        .toLowerCase()
        .includes(keyword);
    const matchesProject = !filters.project_id || device.project_id === filters.project_id;
    const matchesGroup = !filters.group_id || device.group_id === Number(filters.group_id);
    const matchesStatus = !filters.status || device.status === filters.status;
    const matchesTag = !filters.tag || device.tags.includes(filters.tag);
    return matchesKeyword && matchesProject && matchesGroup && matchesStatus && matchesTag;
  });
});

const selectedSet = computed(() => new Set(selectedDeviceIds.value));
const projectIds = computed(() =>
  Array.from(
    new Set(props.devices.map((device) => device.project_id).filter((value): value is number => value !== null)),
  ),
);

function buildTargetFilter(): Record<string, unknown> {
  if (selectedDeviceIds.value.length > 0) {
    return { device_ids: [...selectedDeviceIds.value] };
  }
  const targetFilter: Record<string, unknown> = {};
  if (filters.project_id) {
    targetFilter.project_id = filters.project_id;
  }
  if (filters.group_id) {
    targetFilter.group_id = Number(filters.group_id);
  }
  if (filters.status) {
    targetFilter.status = filters.status;
  }
  if (filters.tag) {
    targetFilter.tags = [filters.tag];
  }
  return targetFilter;
}

function emitTarget() {
  emit("target-change", buildTargetFilter());
}

function toggleDevice(deviceId: number) {
  selectedDeviceIds.value = selectedSet.value.has(deviceId)
    ? selectedDeviceIds.value.filter((id) => id !== deviceId)
    : [...selectedDeviceIds.value, deviceId];
  emitTarget();
}

function selectVisibleDevices() {
  selectedDeviceIds.value = Array.from(new Set([...selectedDeviceIds.value, ...visibleDevices.value.map((device) => device.id)]));
  emitTarget();
}

function clearSelectedDevices() {
  selectedDeviceIds.value = [];
  emitTarget();
}

async function previewTargets() {
  loading.value = true;
  errorMessage.value = "";
  try {
    preview.value = await previewUpdateTaskTargets({
      target_filter: buildTargetFilter(),
      execution_mode: props.executionMode,
    });
    emit("preview-change", preview.value);
  } catch {
    errorMessage.value = "目标设备预览失败";
    emit("preview-change", null);
  } finally {
    loading.value = false;
  }
}

function previewDeviceLabel(device: UpdateTaskTargetDeviceRead): string {
  return `${device.name} / ${device.device_sn} / ${device.project_id}`;
}

watch(
  () => [filters.project_id, filters.group_id, filters.status, filters.tag],
  () => {
    emitTarget();
    preview.value = null;
    emit("preview-change", null);
  },
);

watch(
  () => props.initialProjectId,
  (value) => {
    filters.project_id = value ?? "";
  },
);

emitTarget();
</script>

<template>
  <section class="sub-panel" aria-label="目标设备选择">
    <div class="panel-header">
      <div>
        <h4>目标设备</h4>
        <p class="muted">可按条件筛选，也可手动勾选设备；手动勾选优先。</p>
      </div>
      <el-button data-testid="preview-update-targets" :loading="loading" @click="previewTargets">预览目标</el-button>
    </div>

    <el-alert v-if="errorMessage" class="validation-alert" type="error" :title="errorMessage" show-icon :closable="false" />

    <div class="form-grid compact-grid">
      <div data-testid="target-search" class="input-wrap"><el-input v-model="filters.search" placeholder="搜索名称、序列号、项目号" /></div>
      <label class="field-label">
        <span>项目</span>
        <select data-testid="target-project" v-model="filters.project_id" class="native-select">
          <option value="">全部项目</option>
          <option v-for="projectId in projectIds" :key="projectId" :value="projectId">项目 #{{ projectId }}</option>
        </select>
      </label>
      <label class="field-label">
        <span>分组</span>
        <select data-testid="target-group" v-model="filters.group_id" class="native-select">
          <option value="">全部分组</option>
          <option v-for="group in groups" :key="group.id" :value="String(group.id)">{{ group.name }}</option>
        </select>
      </label>
      <label class="field-label">
        <span>状态</span>
        <select data-testid="target-status" v-model="filters.status" class="native-select">
          <option value="">全部状态</option>
          <option value="online">在线</option>
          <option value="offline">离线</option>
          <option value="unknown">未知</option>
          <option value="degraded">异常</option>
        </select>
      </label>
      <div data-testid="target-tag" class="input-wrap"><el-input v-model="filters.tag" placeholder="标签" /></div>
    </div>

    <div class="inline-actions">
      <el-button data-testid="select-visible-targets" size="small" @click="selectVisibleDevices">全选当前筛选结果</el-button>
      <el-button data-testid="clear-targets" size="small" @click="clearSelectedDevices">清空选择</el-button>
      <el-tag>已选 {{ selectedDeviceIds.length }} 台</el-tag>
      <el-tag type="info">当前显示 {{ visibleDevices.length }} 台</el-tag>
    </div>

    <div class="target-list">
      <label v-for="device in visibleDevices" :key="device.id" class="target-row">
        <input
          type="checkbox"
          :data-testid="`target-device-${device.id}`"
          :checked="selectedSet.has(device.id)"
          @change="toggleDevice(device.id)"
        />
        <span>{{ device.name }}</span>
        <small>{{ device.device_sn }}</small>
        <small>{{ device.project_id }}</small>
        <el-tag size="small">{{ device.status }}</el-tag>
        <el-tag size="small" :type="device.ssh_credential_configured ? 'success' : 'warning'">
          {{ device.ssh_credential_configured ? "凭据已配置" : "缺少凭据" }}
        </el-tag>
      </label>
    </div>

    <section v-if="preview" class="preview-box">
      <div class="panel-header">
        <h4>目标预览：{{ preview.total }} 台</h4>
      </div>
      <el-alert
        v-for="warning in preview.warnings"
        :key="warning"
        class="validation-alert"
        type="warning"
        :title="warning"
        show-icon
        :closable="false"
      />
      <ul class="compact-list">
        <li v-for="device in preview.items" :key="device.id">{{ previewDeviceLabel(device) }}</li>
      </ul>
    </section>
  </section>
</template>
