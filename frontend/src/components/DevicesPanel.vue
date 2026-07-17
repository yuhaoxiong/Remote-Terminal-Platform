<script setup lang="ts">
import { Plus, Refresh, Search } from "@element-plus/icons-vue";
import { ElMessageBox } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";
import { storeToRefs } from "pinia";

import {
  createDevice,
  deleteDevice,
  downloadDeviceBootstrapPackage,
  getApiErrorMessage,
  getDeviceBootstrapPackage,
  getDeviceStatus,
  importFrpsDevices,
  listHardwareProfiles,
  listProjects,
  prepareDeviceBootstrapPackage,
  syncDeviceConfig,
  updateDevice,
  type DeviceCreateRequest,
  type DeviceUpdateRequest,
  type FrpsDiscoveredDevice,
  type FrpsImportRequest,
  type HardwareProfileRead,
  type DeviceBootstrapPackageRead,
  type ProjectRead,
} from "../api/platform";
import { mapDevice, normalizeDeviceStatus, useDevicesStore, type Device, type DeviceStatus } from "../stores/devices";
import { groupNameFor, useGroupsStore } from "../stores/groups";
import { useLogsStore } from "../stores/logs";
import { usePlatformDataStore } from "../stores/platformData";
import { formatTime, parseTags } from "../utils/format";
import CommonDialog from "./CommonDialog.vue";
import DeviceDetailDrawer from "./DeviceDetailDrawer.vue";
import DeviceFilePanel from "./DeviceFilePanel.vue";

defineProps<{
  remoteUnavailableReason: (device: Device, sessionType: "ssh" | "vnc") => string;
}>();

const emit = defineEmits<{
  changed: [];
  ssh: [device: Device];
  vnc: [device: Device];
  "open-files": [device: Device];
}>();

const devicesStore = useDevicesStore();
const { devices, deviceSearch, selectedGroupId, deviceStatusFilter, deviceProjectFilter, deviceTagFilter, visibleDevices, filePanelDevice } = storeToRefs(devicesStore);
const groupsStore = useGroupsStore();
const { groups } = storeToRefs(groupsStore);
const { recalculateGroupCounts } = groupsStore;
const platformDataStore = usePlatformDataStore();
const { prependLocalLog } = useLogsStore();
const projects = ref<ProjectRead[]>([]);
const hardwareProfiles = ref<HardwareProfileRead[]>([]);

const statusType: Record<DeviceStatus, "success" | "warning" | "danger" | "info"> = {
  online: "success", offline: "danger", degraded: "warning", unknown: "info",
};
const deviceStatusText: Record<DeviceStatus, string> = {
  online: "在线", offline: "离线", degraded: "异常", unknown: "未知",
};

const deviceCreateOpen = ref(false);
const deviceEditId = ref<number | null>(null);
const deviceDetailOpen = ref(false);
const deviceDetail = ref<Device | null>(null);
const deviceForm = reactive({
  name: "", device_sn: "", project_id: null as number | null, expected_profile_id: null as number | null,
  is_test_device: false, group_id: null as number | null,
  location: "", tags: "", ssh_user: "ztl", ssh_auth_type: "password", ssh_password: "",
  ssh_port: null as number | null, vnc_port: null as number | null,
});
const deviceFormTitle = computed(() => (deviceEditId.value === null ? "创建设备" : "编辑设备"));
const selectedGroupName = computed(() => groupNameFor(selectedGroupId.value, groups.value));

const frpsImportOpen = ref(false);
const frpsImporting = ref(false);
const frpsImportResult = ref("");
const frpsImportItems = ref<FrpsDiscoveredDevice[]>([]);
const frpsForm = reactive({
  dashboard_url: "http://127.0.0.1:7000", username: "admin", password: "admin",
  ssh_port_start: 12001, ssh_port_end: 17000, vnc_port_start: 17001, vnc_port_end: 22000,
  project_id: null as number | null, location: "frps", overwrite_project_location: false,
});

const syncConfigOpen = ref(false);
const syncConfigTitle = ref("");
const syncConfigText = ref("");
const bootstrapOpen = ref(false);
const bootstrapDevice = ref<Device | null>(null);
const bootstrapPackage = ref<DeviceBootstrapPackageRead | null>(null);
const bootstrapBusy = ref(false);

function openDeviceCreate() {
  deviceEditId.value = null;
  Object.assign(deviceForm, { name: "", device_sn: "", project_id: null, expected_profile_id: null, is_test_device: false, group_id: selectedGroupId.value ?? groups.value[0]?.id ?? null, location: "", tags: "", ssh_user: "ztl", ssh_auth_type: "password", ssh_password: "", ssh_port: null, vnc_port: null });
  deviceCreateOpen.value = true;
}
function openDeviceEdit(device: Device) {
  deviceEditId.value = device.id;
  Object.assign(deviceForm, { name: device.name, device_sn: device.device_sn, project_id: device.project_id, expected_profile_id: device.expected_profile_id, is_test_device: device.is_test_device, group_id: device.group_id, location: device.location === "未分配" ? "" : device.location, tags: device.tags.join(","), ssh_user: device.ssh_user, ssh_auth_type: device.ssh_auth_type, ssh_password: "", ssh_port: device.ssh_port, vnc_port: device.vnc_port });
  deviceCreateOpen.value = true;
}
async function saveDevice() {
  if (!deviceForm.name || !deviceForm.device_sn) { prependLocalLog("设备校验", deviceEditId.value === null ? "新设备" : `设备：${deviceEditId.value}`, "blocked", "设备名称和序列号为必填项"); return; }
  platformDataStore.clearOperationError();
  const basePayload = { name: deviceForm.name, project_id: deviceForm.project_id, expected_profile_id: deviceForm.expected_profile_id, is_test_device: deviceForm.is_test_device, group_id: deviceForm.group_id, location: deviceForm.location || undefined, tags: parseTags(deviceForm.tags), ssh_user: deviceForm.ssh_user || "ztl", ssh_auth_type: deviceForm.ssh_auth_type || "password", ssh_port: deviceForm.ssh_port, vnc_port: deviceForm.vnc_port };
  const pwdPayload = deviceForm.ssh_password ? { ssh_password: deviceForm.ssh_password } : {};
  try {
    if (deviceEditId.value === null) { const payload: DeviceCreateRequest = { ...basePayload, ...pwdPayload, device_sn: deviceForm.device_sn }; devices.value.push(mapDevice(await createDevice(payload), groups.value)); }
    else { const payload: DeviceUpdateRequest = { ...basePayload, ...pwdPayload }; const updated = await updateDevice(deviceEditId.value, payload); const idx = devices.value.findIndex((d) => d.id === updated.id); if (idx >= 0) devices.value[idx] = mapDevice(updated, groups.value); }
    recalculateGroupCounts(devices.value); emit("changed"); deviceCreateOpen.value = false;
  } catch (error) {
    const message = getApiErrorMessage(error, "保存设备失败，请检查后端返回。");
    platformDataStore.setOperationError(message);
    prependLocalLog(deviceEditId.value === null ? "创建设备" : "编辑设备", "设备", "blocked", message);
  }
}
async function removeDevice(device: Device) {
  try { await ElMessageBox.confirm(`确定删除设备 ${device.name}（${device.device_sn}）？`, "删除设备", { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" }); } catch { return; }
  try { await deleteDevice(device.id); devices.value = devices.value.filter((d) => d.id !== device.id); recalculateGroupCounts(devices.value); emit("changed"); }
  catch { prependLocalLog("删除设备", `设备：${device.id}`, "blocked", "删除设备失败，请检查后端返回。"); }
}
async function refreshDeviceStatus(device: Device) {
  try { const s = await getDeviceStatus(device.id); const idx = devices.value.findIndex((d) => d.id === device.id); if (idx >= 0) devices.value[idx] = { ...devices.value[idx], status: normalizeDeviceStatus(s.status) }; }
  catch { prependLocalLog("刷新设备状态", `设备：${device.id}`, "blocked", "刷新状态失败，请检查后端返回。"); }
}
function openDeviceDetail(device: Device) { deviceDetail.value = device; deviceDetailOpen.value = true; }
async function showSyncConfig(device: Device) {
  syncConfigOpen.value = true; syncConfigTitle.value = `${device.name} 同步配置`; syncConfigText.value = "正在生成同步配置...";
  try { syncConfigText.value = (await syncDeviceConfig(device.id)).config; emit("changed"); }
  catch { syncConfigText.value = "生成同步配置失败，请检查设备远程端口配置。"; }
}
async function copySyncConfig() { if (!syncConfigText.value || syncConfigText.value.startsWith("正在")) return; try { await navigator.clipboard?.writeText(syncConfigText.value); prependLocalLog("复制同步配置", "frpc", "success", "已复制到剪贴板"); } catch { prependLocalLog("复制同步配置", "frpc", "blocked", "当前浏览器不支持自动复制，请手动选择配置内容"); } }
async function openBootstrap(device: Device) {
  bootstrapOpen.value = true; bootstrapDevice.value = device; bootstrapPackage.value = null; bootstrapBusy.value = true;
  try { bootstrapPackage.value = await getDeviceBootstrapPackage(device.id); }
  catch (error) { prependLocalLog("加载初始化包", `设备：${device.id}`, "blocked", getApiErrorMessage(error, "加载初始化包失败")); }
  bootstrapBusy.value = false;
}
async function prepareBootstrap() {
  if (!bootstrapDevice.value) return;
  bootstrapBusy.value = true;
  try {
    bootstrapPackage.value = await prepareDeviceBootstrapPackage(bootstrapDevice.value.id);
    prependLocalLog("生成初始化包", `设备：${bootstrapDevice.value.id}`, bootstrapPackage.value.status === "ready" ? "success" : "blocked", bootstrapPackage.value.status === "ready" ? "初始化包已就绪" : "初始化包仍有配置错误");
  } catch (error) { prependLocalLog("生成初始化包", `设备：${bootstrapDevice.value.id}`, "blocked", getApiErrorMessage(error, "生成初始化包失败")); }
  bootstrapBusy.value = false;
}
async function downloadBootstrap() {
  if (!bootstrapDevice.value || !bootstrapPackage.value || bootstrapPackage.value.status !== "ready") return;
  bootstrapBusy.value = true;
  try {
    const blob = await downloadDeviceBootstrapPackage(bootstrapDevice.value.id, bootstrapPackage.value.id);
    const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = `edge-bootstrap-${bootstrapDevice.value.device_sn}-g${bootstrapPackage.value.generation}.zip`; anchor.click(); URL.revokeObjectURL(url);
    prependLocalLog("下载初始化包", `设备：${bootstrapDevice.value.id}`, "success", "初始化包已下载");
  } catch (error) { prependLocalLog("下载初始化包", `设备：${bootstrapDevice.value.id}`, "blocked", getApiErrorMessage(error, "下载初始化包失败")); }
  bootstrapBusy.value = false;
}
async function importFromFrps() {
  frpsImporting.value = true; frpsImportResult.value = ""; frpsImportItems.value = [];
  try { const r = await importFrpsDevices({ dashboard_url: frpsForm.dashboard_url, username: frpsForm.username, password: frpsForm.password, ssh_port_start: Number(frpsForm.ssh_port_start), ssh_port_end: Number(frpsForm.ssh_port_end), vnc_port_start: Number(frpsForm.vnc_port_start), vnc_port_end: Number(frpsForm.vnc_port_end), project_id: frpsForm.project_id, location: frpsForm.location || "frps", overwrite_project_location: frpsForm.overwrite_project_location }); frpsImportItems.value = r.items; frpsImportResult.value = `发现 ${r.total} 台，新增 ${r.created} 台，同步 ${r.synced} 台，跳过 ${r.skipped} 台，冲突 ${r.conflicts} 台`; await platformDataStore.loadPlatformData(); emit("changed"); }
  catch { frpsImportResult.value = "frps 导入失败，请检查 Dashboard 地址、账号密码和后端网络"; }
  frpsImporting.value = false;
}

function projectLabel(projectId: number | null): string {
  if (projectId === null) return "未分配";
  const project = projects.value.find((item) => item.id === projectId);
  return project ? `${project.name} (${project.code})` : `项目 #${projectId}`;
}

onMounted(async () => {
  try {
    const [projectResponse, profileResponse] = await Promise.all([listProjects(), listHardwareProfiles()]);
    projects.value = projectResponse.items;
    hardwareProfiles.value = profileResponse.items;
  } catch {
    prependLocalLog("加载设备选项", "项目与硬件规格", "blocked", "无法加载项目或硬件规格列表");
  }
});
</script>

<template>
  <section class="page-section">
    <div class="page-title-row">
      <div><h3>设备管理</h3><p class="muted">按项目、分组、状态和标签快速定位边缘设备。</p></div>
      <div class="topbar-actions">
        <el-button data-testid="open-device-create" type="primary" :icon="Plus" @click="openDeviceCreate">创建设备</el-button>
        <el-button data-testid="open-frps-import" :icon="Refresh" @click="frpsImportOpen = !frpsImportOpen">导入 frps</el-button>
      </div>
    </div>

    <div class="filter-bar">
      <div class="filter-grid">
        <label class="field-label"><span>状态</span><el-select v-model="deviceStatusFilter" placeholder="全部状态" clearable><el-option v-for="(text,key) in deviceStatusText" :key="key" :label="text" :value="key" /></el-select></label>
        <label class="field-label"><span>分组</span><el-select v-model="selectedGroupId" placeholder="全部分组" clearable><el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" /></el-select></label>
        <label class="field-label"><span>标签</span><el-input v-model="deviceTagFilter" placeholder="请输入标签" /></label>
        <label class="field-label"><span>项目 ID</span><el-input v-model="deviceProjectFilter" placeholder="请输入项目 ID" /></label>
        <div class="filter-actions">
          <el-button @click="deviceSearch='';selectedGroupId=null;deviceStatusFilter='';deviceTagFilter='';deviceProjectFilter=''">重置</el-button>
          <el-button type="primary" :icon="Search">筛选</el-button>
        </div>
      </div>
      <el-alert v-if="selectedGroupId!==null" type="info" show-icon :closable="false" :title="`当前仅显示 ${selectedGroupName} 分组设备`">
        <template #default><el-button text @click="selectedGroupId=null">清除分组筛选</el-button></template>
      </el-alert>
    </div>

    <CommonDialog v-model:visible="frpsImportOpen" title="导入 frps 已有设备" width="900px">
      <div class="form-grid">
        <div data-testid="frps-url" class="input-wrap"><el-input v-model="frpsForm.dashboard_url" placeholder="Dashboard 地址" /></div>
        <div data-testid="frps-username" class="input-wrap"><el-input v-model="frpsForm.username" placeholder="用户名" /></div>
        <div data-testid="frps-password" class="input-wrap"><el-input v-model="frpsForm.password" type="password" show-password placeholder="密码" /></div>
        <el-select data-testid="frps-project" v-model="frpsForm.project_id" placeholder="导入后保持未分配" clearable>
          <el-option v-for="project in projects.filter((item) => item.status === 'active')" :key="project.id" :label="`${project.name} (${project.code})`" :value="project.id" />
        </el-select>
        <div data-testid="frps-location" class="input-wrap"><el-input v-model="frpsForm.location" placeholder="部署位置" /></div>
        <el-checkbox data-testid="frps-overwrite" v-model="frpsForm.overwrite_project_location">覆盖正式项目和位置</el-checkbox>
        <el-input-number v-model="frpsForm.ssh_port_start" :min="1" controls-position="right" />
        <el-input-number v-model="frpsForm.ssh_port_end" :min="1" controls-position="right" />
        <el-input-number v-model="frpsForm.vnc_port_start" :min="1" controls-position="right" />
        <el-input-number v-model="frpsForm.vnc_port_end" :min="1" controls-position="right" />
      </div>
      <p v-if="frpsImportResult" class="muted">{{ frpsImportResult }}</p>
      <el-table v-if="frpsImportItems.length" :data="frpsImportItems" size="small" row-key="device_sn" empty-text="暂无导入结果"><el-table-column prop="device_sn" label="设备 SN" min-width="130" /><el-table-column prop="ssh_port" label="SSH" width="90" /><el-table-column prop="vnc_port" label="VNC" width="90" /><el-table-column prop="import_status" label="结果" width="120" /><el-table-column prop="detail" label="详情" min-width="180" /></el-table>
      <template #footer>
        <el-button @click="frpsImportOpen=false">关闭</el-button>
        <el-button data-testid="import-frps" type="primary" :loading="frpsImporting" @click="importFromFrps">开始导入</el-button>
      </template>
    </CommonDialog>

    <div class="table-panel">
      <el-table :data="visibleDevices" row-key="id" empty-text="暂无设备">
        <el-table-column prop="name" label="设备" min-width="180" />
        <el-table-column prop="device_sn" label="序列号" min-width="150" />
        <el-table-column label="状态" width="110"><template #default="{row}"><el-tag :type="statusType[row.status as DeviceStatus]">{{ deviceStatusText[row.status as DeviceStatus] }}</el-tag></template></el-table-column>
        <el-table-column label="项目" min-width="180"><template #default="{row}">{{ projectLabel(row.project_id) }}</template></el-table-column>
        <el-table-column prop="group" label="分组" width="110" />
        <el-table-column prop="location" label="部署位置" min-width="130" />
        <el-table-column prop="ssh_port" label="SSH 端口" width="100" />
        <el-table-column prop="vnc_port" label="VNC 端口" width="100" />
        <el-table-column label="初始化" width="135"><template #default="{row}"><el-tag size="small" :type="row.initialization_status === 'ready' ? 'success' : row.initialization_status === 'hardware_mismatch' || row.initialization_status === 'failed' ? 'danger' : 'warning'">{{ row.initialization_status }}</el-tag></template></el-table-column>
        <el-table-column label="最近指标" min-width="150"><template #default="{row}"><span>{{ row.metricRecordedAt ? formatTime(row.metricRecordedAt) : "未上报" }}</span></template></el-table-column>
        <el-table-column label="标签" min-width="150"><template #default="{row}"><el-tag v-for="tag in row.tags" :key="tag" size="small" class="tag-chip">{{ tag }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="430" fixed="right">
          <template #default="{row}">
            <el-button size="small" type="primary" text @click="openDeviceDetail(row)">详情</el-button>
            <el-tooltip :content="remoteUnavailableReason(row,'ssh')||'SSH 连接'" placement="top"><el-button size="small" :disabled="Boolean(remoteUnavailableReason(row,'ssh'))" @click="$emit('ssh',row)">SSH</el-button></el-tooltip>
            <el-tooltip :content="remoteUnavailableReason(row,'vnc')||'VNC 连接'" placement="top"><el-button size="small" :disabled="Boolean(remoteUnavailableReason(row,'vnc'))" @click="$emit('vnc',row)">VNC</el-button></el-tooltip>
            <el-button :data-testid="`open-files-${row.id}`" size="small" @click="devicesStore.openFilePanel(row);$emit('open-files',row)">文件</el-button>
            <el-button :data-testid="`sync-device-${row.id}`" size="small" @click="showSyncConfig(row)">同步</el-button>
            <el-button :data-testid="`bootstrap-device-${row.id}`" size="small" @click="openBootstrap(row)">初始化</el-button>
            <el-button :data-testid="`refresh-device-${row.id}`" size="small" :icon="Refresh" @click="refreshDeviceStatus(row)">刷新</el-button>
            <el-button :data-testid="`edit-device-${row.id}`" size="small" @click="openDeviceEdit(row)">编辑</el-button>
            <el-button :data-testid="`delete-device-${row.id}`" size="small" type="danger" text @click="removeDevice(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <DeviceDetailDrawer v-model:visible="deviceDetailOpen" :device="deviceDetail" @ssh="(d) => $emit('ssh',d)" @vnc="(d) => $emit('vnc',d)" @files="(d) => { devicesStore.openFilePanel(d); $emit('open-files',d); }" @sync="(d) => showSyncConfig(d)" @edit="(d) => openDeviceEdit(d)" @remove="(d) => removeDevice(d)" />

    <CommonDialog v-model:visible="deviceCreateOpen" :title="deviceFormTitle" width="700px" @confirm="saveDevice" @cancel="deviceCreateOpen=false">
      <div class="form-grid">
        <div data-testid="device-name" class="input-wrap"><el-input v-model="deviceForm.name" placeholder="设备名称" /></div>
        <div data-testid="device-sn" class="input-wrap"><el-input v-model="deviceForm.device_sn" :disabled="deviceEditId!==null" placeholder="设备序列号" /></div>
        <el-select data-testid="device-project" v-model="deviceForm.project_id" placeholder="未分配项目" clearable>
          <el-option v-for="project in projects.filter((item) => item.status === 'active')" :key="project.id" :label="`${project.name} (${project.code})`" :value="project.id" />
        </el-select>
        <el-select data-testid="device-profile" v-model="deviceForm.expected_profile_id" placeholder="期望硬件规格" clearable>
          <el-option v-for="profile in hardwareProfiles" :key="profile.id" :label="profile.name" :value="profile.id" />
        </el-select>
        <label class="field-label inline-field"><span>测试设备</span><el-switch v-model="deviceForm.is_test_device" /></label>
        <el-select v-model="deviceForm.group_id" placeholder="选择分组" clearable><el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" /></el-select>
        <el-input v-model="deviceForm.location" placeholder="位置" />
        <div data-testid="device-tags" class="input-wrap"><el-input v-model="deviceForm.tags" placeholder="标签，用逗号分隔" /></div>
        <div data-testid="device-ssh-port" class="input-wrap"><el-input-number v-model="deviceForm.ssh_port" :min="1" :max="65535" placeholder="SSH 端口" controls-position="right" style="width: 100%" /></div>
        <div data-testid="device-vnc-port" class="input-wrap"><el-input-number v-model="deviceForm.vnc_port" :min="1" :max="65535" placeholder="VNC 端口" controls-position="right" style="width: 100%" /></div>
        <div data-testid="device-ssh-user" class="input-wrap"><el-input v-model="deviceForm.ssh_user" placeholder="SSH 用户" /></div>
        <div data-testid="device-ssh-auth-type" class="input-wrap"><el-input v-model="deviceForm.ssh_auth_type" placeholder="凭据类型" /></div>
        <div data-testid="device-ssh-password" class="input-wrap"><el-input v-model="deviceForm.ssh_password" type="password" show-password placeholder="SSH 密码" /></div>
      </div>
      <p class="muted">SSH 密码不会从接口回显；编辑设备时留空表示不修改已有凭据。端口留空表示不配置远程访问。</p>
      <template #footer>
        <el-button @click="deviceCreateOpen=false">取消</el-button>
        <el-button data-testid="save-device" type="primary" @click="saveDevice">保存设备</el-button>
      </template>
    </CommonDialog>

    <CommonDialog v-model:visible="syncConfigOpen" :title="syncConfigTitle" width="800px">
      <pre class="terminal-output">{{ syncConfigText }}</pre>
      <template #footer>
        <el-button data-testid="copy-sync-config" type="primary" @click="copySyncConfig">复制配置</el-button>
        <el-button @click="syncConfigOpen=false">关闭</el-button>
      </template>
    </CommonDialog>

    <CommonDialog v-model:visible="bootstrapOpen" :title="`${bootstrapDevice?.name || '设备'} 初始化包`" width="720px">
      <div v-loading="bootstrapBusy">
        <el-descriptions v-if="bootstrapPackage" :column="2" border>
          <el-descriptions-item label="代次">{{ bootstrapPackage.generation }}</el-descriptions-item>
          <el-descriptions-item label="状态"><el-tag :type="bootstrapPackage.status === 'ready' ? 'success' : 'warning'">{{ bootstrapPackage.status }}</el-tag></el-descriptions-item>
          <el-descriptions-item label="CA 指纹" :span="2"><code>{{ bootstrapPackage.ca_sha256 || '待生成' }}</code></el-descriptions-item>
        </el-descriptions>
        <el-alert v-if="bootstrapPackage?.validation_errors?.length" class="bootstrap-errors" type="warning" show-icon :closable="false" title="初始化包尚不可下载">
          <template #default><ul><li v-for="error in bootstrapPackage.validation_errors" :key="error">{{ error }}</li></ul></template>
        </el-alert>
        <p class="muted">该 ZIP 仅用于当前设备。复制到 Debian 11 设备后，以 root 执行 <code>bash install.sh</code>；脚本不会自动重启。</p>
      </div>
      <template #footer>
        <el-button @click="bootstrapOpen=false">关闭</el-button>
        <el-button data-testid="prepare-bootstrap" :loading="bootstrapBusy" @click="prepareBootstrap">生成/重新生成</el-button>
        <el-button data-testid="download-bootstrap" type="primary" :loading="bootstrapBusy" :disabled="bootstrapPackage?.status !== 'ready'" @click="downloadBootstrap">下载 ZIP</el-button>
      </template>
    </CommonDialog>

    <DeviceFilePanel v-if="filePanelDevice" :device="filePanelDevice" />
  </section>
</template>
