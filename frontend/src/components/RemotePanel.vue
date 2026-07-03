<script setup lang="ts">
import { Monitor, Search, VideoPlay } from "@element-plus/icons-vue";
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { storeToRefs } from "pinia";

import { buildApiWebSocketUrl, getAccessToken, openSshSession, openVncSession } from "../api/platform";
import { useDevicesStore, type Device, type DeviceStatus } from "../stores/devices";
import SplitLayout from "./SplitLayout.vue";
import FileTreePanel from "./FileTreePanel.vue";

const devicesStore = useDevicesStore();
const { devices, remoteSessionRequest } = storeToRefs(devicesStore);
const { clearRemoteSessionRequest } = devicesStore;

interface RemoteSessionUi { status: "idle" | "connecting" | "ready" | "connected" | "failed" | "disconnected"; message: string; websocketUrl: string; output: string; }
interface SshTerminalHandle { terminal: { cols: number; rows: number; loadAddon(addon: unknown): void; open(element: HTMLElement): void; focus(): void; write(data: string): void; writeln(data: string): void; onData(callback: (data: string) => void): { dispose: () => void }; dispose(): void }; fitAddon: { fit(): void; dispose?: () => void }; dataDisposable: { dispose: () => void }; resizeObserver: ResizeObserver | null; }
interface VncClient { showDotCursor?: boolean; focusOnClick?: boolean; scaleViewport?: boolean; clipViewport?: boolean; focus?(options?: FocusOptions): void; disconnect(): void; addEventListener(type: string, callback: (event: Event) => void): void; sendCredentials?(credentials: { password: string }): void; }

const statusType: Record<DeviceStatus, "success" | "warning" | "danger" | "info"> = { online: "success", offline: "danger", degraded: "warning", unknown: "info" };
const deviceStatusText: Record<DeviceStatus, string> = { online: "在线", offline: "离线", degraded: "异常", unknown: "未知" };

const remoteDeviceSearch = ref("");
const selectedRemoteDeviceId = ref<number | null>(null);
const sshTerminalHostRef = ref<HTMLElement | null>(null);
const vncCanvasHostRef = ref<HTMLElement | null>(null);
const vncPassword = ref("");
const vncLocalCursorVisible = ref(false);
const showFileTree = ref(true);
const fileTreePanelRef = ref<InstanceType<typeof FileTreePanel> | null>(null);
const remoteSessions = reactive<Record<string, RemoteSessionUi>>({});
const sshSockets = new Map<number, WebSocket>();
const sshTerminals = new Map<number, SshTerminalHandle>();
const vncClients = new Map<number, VncClient>();
const vncConnectionAttempts = new Map<number, number>();

const remoteVisibleDevices = computed(() => {
  const keyword = remoteDeviceSearch.value.trim().toLowerCase();
  return devices.value.filter((d) => !keyword || [d.name, d.device_sn, d.project_id, d.location, d.group, String(d.ssh_port ?? ""), String(d.vnc_port ?? "")].join(" ").toLowerCase().includes(keyword));
});
const selectedRemoteDevice = computed(() => devices.value.find((d) => d.id === selectedRemoteDeviceId.value) ?? null);
const selectedSshSession = computed(() => selectedRemoteDevice.value ? remoteSessionFor(selectedRemoteDevice.value.id, "ssh") : null);
const selectedVncSession = computed(() => selectedRemoteDevice.value ? remoteSessionFor(selectedRemoteDevice.value.id, "vnc") : null);
const isSshConnected = computed(() => selectedSshSession.value?.status === "connected");

// 文件操作处理已移至 FileTreePanel 组件内部
const handleFileTreeRefresh = () => {
  fileTreePanelRef.value?.refresh();
};

// 监听 SSH 连接状态,自动加载文件树
watch(isSshConnected, (connected) => {
  if (connected && showFileTree.value) {
    fileTreePanelRef.value?.loadRootDirectory();
  }
});

function remoteSessionKey(deviceId: number, sType: "ssh" | "vnc") { return `${sType}:${deviceId}`; }
function remoteSessionFor(deviceId: number, sType: "ssh" | "vnc"): RemoteSessionUi {
  const k = remoteSessionKey(deviceId, sType);
  if (!remoteSessions[k]) remoteSessions[k] = { status: "idle", message: "未连接", websocketUrl: "", output: "" };
  return remoteSessions[k];
}
function setRemoteSession(deviceId: number, sType: "ssh" | "vnc", update: Partial<RemoteSessionUi>) { Object.assign(remoteSessionFor(deviceId, sType), update); }
function remoteUnavailableReason(device: Device, sType: "ssh" | "vnc"): string {
  if (device.status === "offline") return "设备离线";
  if (!device.ssh_credential_configured) return "缺少 SSH 凭据";
  if (sType === "ssh" && device.ssh_port === null) return "缺少 SSH 端口";
  if (sType === "vnc" && device.vnc_port === null) return "缺少 VNC 端口";
  return "";
}
function canOpenRemote(device: Device, sType: "ssh" | "vnc"): boolean { return remoteUnavailableReason(device, sType) === ""; }
function selectRemoteDevice(device: Device) { selectedRemoteDeviceId.value = device.id; }

function disposeSshTerminal(deviceId: number) {
  const h = sshTerminals.get(deviceId); if (!h) return;
  h.dataDisposable.dispose(); h.resizeObserver?.disconnect(); h.terminal.dispose(); h.fitAddon.dispose?.();
  sshTerminals.delete(deviceId);
}
function focusSshTerminal(deviceId: number) { sshTerminals.get(deviceId)?.terminal.focus(); }
function writeSshOutput(deviceId: number, data: string, newline = false) {
  if (!data) return;
  const c = remoteSessionFor(deviceId, "ssh");
  c.output += newline ? `${data}\n` : data;
  const terminal = sshTerminals.get(deviceId)?.terminal;
  if (newline) terminal?.writeln(data);
  else terminal?.write(data);
}
async function prepareSshTerminal(deviceId: number) {
  await nextTick(); const host = sshTerminalHostRef.value; if (!host) return null;
  disposeSshTerminal(deviceId); host.replaceChildren();
  const [{ Terminal }, { FitAddon }] = await Promise.all([import("@xterm/xterm"), import("@xterm/addon-fit")]);
  const terminal = new Terminal({ cursorBlink: true, convertEol: true, fontFamily: "Consolas, 'Courier New', monospace", fontSize: 13, theme: { background: "#0f172a", foreground: "#d1fae5" } });
  const fit = new FitAddon(); terminal.loadAddon(fit); terminal.open(host); fit.fit(); terminal.focus();
  const dataDisposable = terminal.onData((data: string) => { const s = sshSockets.get(deviceId); if (s && s.readyState === WebSocket.OPEN) s.send(JSON.stringify({ type: "input", data })); });
  const resizeObserver = new ResizeObserver(() => { fit.fit(); const s = sshSockets.get(deviceId); if (s && typeof WebSocket !== "undefined" && s.readyState === WebSocket.OPEN) s.send(JSON.stringify({ type: "resize", columns: terminal.cols || 120, rows: terminal.rows || 32 })); });
  resizeObserver.observe(host);
  sshTerminals.set(deviceId, { terminal, fitAddon: fit, dataDisposable, resizeObserver });
  return terminal;
}

async function startSshSession(device: Device) {
  if (typeof WebSocket === "undefined") return;
  setRemoteSession(device.id, "ssh", { status: "connecting", message: "正在建立 SSH 连接", output: "" });
  try {
    const session = await openSshSession(device.id);
    const token = getAccessToken(); if (!token) { setRemoteSession(device.id, "ssh", { status: "failed", message: remoteUnavailableReason(device, "ssh") || "Token 不可用" }); return; }
    const terminal = await prepareSshTerminal(device.id); if (!terminal) { setRemoteSession(device.id, "ssh", { status: "failed", message: "终端初始化失败" }); return; }
    if (!session.websocket_url) { setRemoteSession(device.id, "ssh", { status: "failed", message: "SSH 初始化失败" }); return; }
    const wsUrl = buildApiWebSocketUrl(session.websocket_url, token!);
    sshSockets.get(device.id)?.close();
    const socket = new WebSocket(wsUrl);
    sshSockets.set(device.id, socket);
    socket.onopen = () => { setRemoteSession(device.id, "ssh", { status: "connected", message: `SSH 已连接 ${device.name}`, websocketUrl: wsUrl }); focusSshTerminal(device.id); };
    socket.onmessage = (e) => {
      try {
        const d = JSON.parse(String(e.data));
        if (d.type === "stdout" || d.type === "output") writeSshOutput(device.id, d.message ?? d.data ?? "");
        else if (d.type === "disconnect") { sshTerminals.get(device.id)?.terminal.writeln(d.message ?? "SSH 连接断开"); setRemoteSession(device.id, "ssh", { status: "disconnected", message: d.message ?? "SSH 已断开" }); }
        else if (d.message) writeSshOutput(device.id, d.message, true);
      } catch { sshTerminals.get(device.id)?.terminal.write(String(e.data)); }
    };
    socket.onerror = () => { sshTerminals.get(device.id)?.terminal.writeln("SSH WebSocket 连接失败"); setRemoteSession(device.id, "ssh", { status: "failed", message: "SSH WebSocket 错误" }); sshSockets.delete(device.id); };
    socket.onclose = () => { if (remoteSessionFor(device.id, "ssh").status !== "failed") setRemoteSession(device.id, "ssh", { status: "disconnected", message: "SSH 已断开" }); sshSockets.delete(device.id); };
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "SSH 连接失败";
    sshTerminals.get(device.id)?.terminal.writeln(msg);
    setRemoteSession(device.id, "ssh", { status: "failed", message: msg });
  }
}
function disconnectSshSession(deviceId: number) {
  const s = sshSockets.get(deviceId); if (s) { s.close(); sshSockets.delete(deviceId); }
  disposeSshTerminal(deviceId); setRemoteSession(deviceId, "ssh", { status: "disconnected", message: "SSH 已断开" });
}
function currentVncCredentials(defaultPassword?: string | null) {
  const password = vncPassword.value.trim() || defaultPassword?.trim();
  return password ? { password } : undefined;
}
function formatVncCredentialTypes(types: string[]) {
  const labels: Record<string, string> = { password: "密码", username: "用户名", target: "目标" };
  return types.map((type) => labels[type] ?? type).join("、") || "密码";
}
function configureVncDisplay(client: VncClient) {
  client.showDotCursor = true;
  client.focusOnClick = true;
  client.scaleViewport = true;
  client.clipViewport = false;
}
function nextVncConnectionAttempt(deviceId: number) {
  const attemptId = (vncConnectionAttempts.get(deviceId) ?? 0) + 1;
  vncConnectionAttempts.set(deviceId, attemptId);
  return attemptId;
}
function isCurrentVncConnectionAttempt(deviceId: number, attemptId: number) {
  return vncConnectionAttempts.get(deviceId) === attemptId;
}
async function startVncSession(device: Device) {
  const attemptId = nextVncConnectionAttempt(device.id);
  disconnectVncSession(device.id, false);
  setRemoteSession(device.id, "vnc", { status: "connecting", message: "正在连接 VNC", output: "" });
  try {
    const session = await openVncSession(device.id);
    if (!isCurrentVncConnectionAttempt(device.id, attemptId)) return;
    const token = getAccessToken(); if (!token) { setRemoteSession(device.id, "vnc", { status: "failed", message: "Token 不可用" }); return; }
    if (!session.websocket_url) { setRemoteSession(device.id, "vnc", { status: "failed", message: "VNC 初始化失败" }); return; }
    const wsUrl = buildApiWebSocketUrl(session.websocket_url, token!);
    if (!vncCanvasHostRef.value) { setRemoteSession(device.id, "vnc", { status: "failed", message: "VNC 初始化失败" }); return; }
    const RFB = (await import("@novnc/novnc")).default;
    if (!isCurrentVncConnectionAttempt(device.id, attemptId)) return;
    const credentials = currentVncCredentials(session.vnc_password);
    const client = new RFB(vncCanvasHostRef.value, wsUrl, credentials ? { credentials } : {}) as VncClient;
    configureVncDisplay(client);
    client.addEventListener("connect", () => {
      if (!isCurrentVncConnectionAttempt(device.id, attemptId)) return;
      setRemoteSession(device.id, "vnc", { status: "connected", message: `VNC 已连接 ${device.name}`, websocketUrl: wsUrl });
      configureVncDisplay(client);
      client.focus?.({ preventScroll: true });
    });
    client.addEventListener("credentialsrequired", (event: Event) => {
      if (!isCurrentVncConnectionAttempt(device.id, attemptId)) return;
      const credentials = currentVncCredentials(session.vnc_password);
      if (credentials && client.sendCredentials) { client.sendCredentials(credentials); return; }
      const required = formatVncCredentialTypes((event as CustomEvent<{ types?: string[] }>).detail?.types ?? []);
      setRemoteSession(device.id, "vnc", { status: "failed", message: `VNC 需要${required}，请输入 VNC 密码后重试` });
      client.disconnect();
    });
    client.addEventListener("securityfailure", (event: Event) => {
      if (!isCurrentVncConnectionAttempt(device.id, attemptId)) return;
      const reason = (event as CustomEvent<{ reason?: string }>).detail?.reason;
      setRemoteSession(device.id, "vnc", { status: "failed", message: reason ? `VNC 认证失败：${reason}` : "VNC 认证失败" });
      client.disconnect();
    });
    client.addEventListener("disconnect", (event: Event) => {
      if (!isCurrentVncConnectionAttempt(device.id, attemptId)) return;
      if (remoteSessionFor(device.id, "vnc").status !== "failed") {
        const wasConnecting = remoteSessionFor(device.id, "vnc").status === "connecting";
        const clean = (event as CustomEvent<{ clean?: boolean }>).detail?.clean;
        setRemoteSession(device.id, "vnc", wasConnecting || clean === false ? { status: "failed", message: "VNC 连接中断，请检查 VNC 服务、端口和密码" } : { status: "disconnected", message: "VNC 已断开" });
      }
      vncClients.delete(device.id);
    });
    vncClients.set(device.id, client);
    setRemoteSession(device.id, "vnc", { websocketUrl: wsUrl });
  } catch (e: unknown) {
    if (isCurrentVncConnectionAttempt(device.id, attemptId)) setRemoteSession(device.id, "vnc", { status: "failed", message: e instanceof Error ? e.message : "VNC 连接失败" });
  }
}
function disconnectVncSession(deviceId: number, updateStatus = true) {
  const c = vncClients.get(deviceId); if (c) { c.disconnect(); vncClients.delete(deviceId); }
  vncLocalCursorVisible.value = false;
  if (updateStatus) setRemoteSession(deviceId, "vnc", { status: "disconnected", message: "VNC 已断开" });
}
function refreshVncFullscreenState() {
  vncLocalCursorVisible.value = document.fullscreenElement === vncCanvasHostRef.value;
  if (!vncLocalCursorVisible.value) return;
  for (const client of vncClients.values()) {
    configureVncDisplay(client);
    client.focus?.({ preventScroll: true });
  }
}
async function requestVncFullscreen(deviceId: number) {
  await vncCanvasHostRef.value?.requestFullscreen?.();
  const client = vncClients.get(deviceId);
  if (!client) return;
  vncLocalCursorVisible.value = true;
  configureVncDisplay(client);
  client.focus?.({ preventScroll: true });
}

watch(
  remoteSessionRequest,
  async (request) => {
    if (!request) return;
    const device = devices.value.find((item) => item.id === request.deviceId);
    clearRemoteSessionRequest();
    if (!device) return;
    selectRemoteDevice(device);
    await nextTick();
    if (request.sessionType === "ssh") {
      await startSshSession(device);
      return;
    }
    await startVncSession(device);
  },
  { immediate: true },
);

onMounted(() => document.addEventListener("fullscreenchange", refreshVncFullscreenState));
onBeforeUnmount(() => { document.removeEventListener("fullscreenchange", refreshVncFullscreenState); for (const id of sshSockets.keys()) disconnectSshSession(id); for (const id of vncClients.keys()) disconnectVncSession(id, false); });
</script>

<template>
  <section class="page-section">
    <div class="remote-workspace">
      <aside class="remote-device-list" aria-label="远程设备列表">
        <div class="remote-list-header">
          <h3>远程设备</h3>
          <el-input v-model="remoteDeviceSearch" data-testid="remote-device-search" :prefix-icon="Search" placeholder="按名称、序列号或项目搜索" />
        </div>
        <button v-for="device in remoteVisibleDevices" :key="device.id" type="button" class="remote-device-row" :class="{ 'is-selected': selectedRemoteDeviceId === device.id }" :data-testid="`select-remote-device-${device.id}`" @click="selectRemoteDevice(device)">
          <span><strong>{{ device.name }}</strong><small>{{ device.device_sn }} · {{ device.project_id }}</small></span>
          <span class="remote-port-tags">
            <el-tag size="small" :type="device.ssh_port ? 'success' : 'info'">SSH {{ device.ssh_port ?? "缺失" }}</el-tag>
            <el-tag size="small" :type="device.vnc_port ? 'success' : 'info'">VNC {{ device.vnc_port ?? "缺失" }}</el-tag>
          </span>
        </button>
        <el-empty v-if="remoteVisibleDevices.length === 0" description="没有匹配的远程设备" />
      </aside>

      <section class="remote-console" aria-label="远程操作区">
        <el-empty v-if="!selectedRemoteDevice" description="请选择设备" />
        <template v-else>
          <div class="panel-header remote-console-header">
            <div><h3>{{ selectedRemoteDevice.name }}</h3><p class="muted">{{ selectedRemoteDevice.device_sn }} · {{ selectedRemoteDevice.location }} · {{ selectedRemoteDevice.group }}</p></div>
            <div class="remote-session-state">
              <el-tag :type="statusType[selectedRemoteDevice.status]">{{ deviceStatusText[selectedRemoteDevice.status] }}</el-tag>
              <el-tag :type="selectedRemoteDevice.ssh_credential_configured ? 'success' : 'warning'">{{ selectedRemoteDevice.ssh_credential_configured ? "凭据已配置" : "凭据未配置" }}</el-tag>
            </div>
          </div>
          <el-tabs class="remote-tabs">
            <el-tab-pane label="SSH 终端">
              <SplitLayout :default-width="280" :min-width="200" :max-width="500">
                <template #left>
                  <FileTreePanel
                    ref="fileTreePanelRef"
                    :device="selectedRemoteDevice"
                    :connected="isSshConnected"
                    @refresh="handleFileTreeRefresh"
                  />
                </template>
                <template #right>
                  <section class="remote-panel">
                    <div class="panel-header">
                      <div><h3>SSH 终端</h3><p class="muted">{{ selectedSshSession?.message ?? "未连接" }}</p></div>
                      <div class="remote-actions">
                        <el-button :data-testid="`open-ssh-${selectedRemoteDevice.id}`" type="primary" :icon="Monitor" :disabled="!canOpenRemote(selectedRemoteDevice, 'ssh')" :loading="selectedSshSession?.status === 'connecting'" @click="startSshSession(selectedRemoteDevice)">连接 SSH</el-button>
                        <el-button :data-testid="`disconnect-ssh-${selectedRemoteDevice.id}`" :disabled="selectedSshSession?.status !== 'connected'" @click="disconnectSshSession(selectedRemoteDevice.id)">断开 SSH</el-button>
                      </div>
                    </div>
                    <p v-if="remoteUnavailableReason(selectedRemoteDevice, 'ssh')" class="remote-warning">{{ remoteUnavailableReason(selectedRemoteDevice, "ssh") }}</p>
                    <div ref="sshTerminalHostRef" data-testid="ssh-terminal" class="ssh-terminal" @pointerdown="focusSshTerminal(selectedRemoteDevice.id)" @click="focusSshTerminal(selectedRemoteDevice.id)"></div>
                    <pre v-if="selectedSshSession?.output" data-testid="ssh-transcript" class="terminal-output">{{ selectedSshSession.output }}</pre>
                  </section>
                </template>
              </SplitLayout>
            </el-tab-pane>
            <el-tab-pane label="VNC 桌面">
              <section class="remote-panel">
                <div class="panel-header">
                  <div><h3>VNC 桌面</h3><p class="muted">{{ selectedVncSession?.message ?? "未连接" }}</p></div>
                  <div class="remote-actions">
                    <el-input v-model="vncPassword" data-testid="vnc-password" class="vnc-password-input" type="password" show-password placeholder="VNC 密码（如需要）" @keyup.enter="startVncSession(selectedRemoteDevice)" />
                    <el-button :data-testid="`open-vnc-${selectedRemoteDevice.id}`" :icon="VideoPlay" :disabled="!canOpenRemote(selectedRemoteDevice, 'vnc')" :loading="selectedVncSession?.status === 'connecting'" @click="startVncSession(selectedRemoteDevice)">连接 VNC</el-button>
                    <el-button :data-testid="`disconnect-vnc-${selectedRemoteDevice.id}`" :disabled="selectedVncSession?.status !== 'connected'" @click="disconnectVncSession(selectedRemoteDevice.id)">断开 VNC</el-button>
                    <el-button :data-testid="`fullscreen-vnc-${selectedRemoteDevice.id}`" :disabled="selectedVncSession?.status !== 'connected'" @click="requestVncFullscreen(selectedRemoteDevice.id)">全屏</el-button>
                  </div>
                </div>
                <p v-if="remoteUnavailableReason(selectedRemoteDevice, 'vnc')" class="remote-warning">{{ remoteUnavailableReason(selectedRemoteDevice, "vnc") }}</p>
                <div ref="vncCanvasHostRef" data-testid="vnc-screen" class="vnc-screen" :class="{ 'is-local-cursor-visible': vncLocalCursorVisible }"><span v-if="selectedVncSession?.status !== 'connected'">VNC 画面将在连接后显示</span></div>
              </section>
            </el-tab-pane>
            <el-tab-pane label="连接日志">
              <section class="remote-panel">
                <h3>连接日志</h3>
                <div class="connection-log">
                  <p>SSH：{{ selectedSshSession?.message ?? "未连接" }}</p>
                  <p>VNC：{{ selectedVncSession?.message ?? "未连接" }}</p>
                  <p>远程端口：SSH {{ selectedRemoteDevice.ssh_port ?? "缺失" }} / VNC {{ selectedRemoteDevice.vnc_port ?? "缺失" }}</p>
                </div>
              </section>
            </el-tab-pane>
          </el-tabs>
        </template>
      </section>
    </div>
  </section>
</template>
