<script setup lang="ts">
import { ElMessageBox } from "element-plus";
import { computed, onMounted, ref, watch } from "vue";

import {
  deleteDeviceFile,
  downloadDeviceFile,
  listDeviceFiles,
  uploadDeviceFile,
  type DeviceFileItem,
} from "../api/platform";

interface FileDevice {
  id: number;
  name: string;
  device_sn: string;
  ssh_port: number | null;
  ssh_credential_configured: boolean;
}

const props = defineProps<{
  device: FileDevice;
}>();

const currentPath = ref("/");
const pathInput = ref("/");
const files = ref<DeviceFileItem[]>([]);
const loading = ref(false);
const errorMessage = ref("");
const uploadRemotePath = ref("");
const selectedFile = ref<File | null>(null);
const lastMessage = ref("");

const deviceWarning = computed(() => {
  if (props.device.ssh_port === null) {
    return "设备缺少 SSH 端口，SFTP 文件后端可能不可用";
  }
  if (!props.device.ssh_credential_configured) {
    return "设备凭据未配置，SFTP 文件后端可能不可用";
  }
  return "";
});

function parentPath(path: string): string {
  const normalized = path.trim() || "/";
  if (normalized === "/") {
    return "/";
  }
  const parts = normalized.split("/").filter(Boolean);
  parts.pop();
  return parts.length ? `/${parts.join("/")}` : "/";
}

function filenameFor(path: string): string {
  return path.split("/").filter(Boolean).at(-1) || "download";
}

function formatSize(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function formatTime(value: string | null): string {
  return value ? value.replace("T", " ").slice(0, 16) : "-";
}

async function loadFiles(path = currentPath.value) {
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await listDeviceFiles(props.device.id, path || "/");
    currentPath.value = response.path || "/";
    pathInput.value = currentPath.value;
    files.value = response.items;
  } catch {
    errorMessage.value = "文件列表加载失败";
  } finally {
    loading.value = false;
  }
}

function openDirectory(item: DeviceFileItem) {
  if (item.type !== "directory") {
    return;
  }
  void loadFiles(item.path);
}

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] ?? null;
  if (selectedFile.value && !uploadRemotePath.value) {
    const basePath = currentPath.value === "/" ? "" : currentPath.value.replace(/\/$/, "");
    uploadRemotePath.value = `${basePath}/${selectedFile.value.name}`;
  }
}

async function uploadSelectedFile() {
  if (!selectedFile.value) {
    errorMessage.value = "请选择要上传的文件";
    return;
  }
  if (!uploadRemotePath.value.trim()) {
    errorMessage.value = "请输入远程目标路径";
    return;
  }
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await uploadDeviceFile(props.device.id, uploadRemotePath.value.trim(), selectedFile.value);
    lastMessage.value = `上传成功：${response.remote_path}`;
    await loadFiles(currentPath.value);
  } catch {
    errorMessage.value = "文件上传失败";
  } finally {
    loading.value = false;
  }
}

async function downloadFile(item: DeviceFileItem) {
  loading.value = true;
  errorMessage.value = "";
  try {
    const blob = await downloadDeviceFile(props.device.id, item.path);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filenameFor(item.path);
    link.click();
    window.URL.revokeObjectURL(url);
    lastMessage.value = `已下载：${item.name}`;
  } catch {
    errorMessage.value = "文件下载失败";
  } finally {
    loading.value = false;
  }
}

async function removeFile(item: DeviceFileItem) {
  await ElMessageBox.confirm(`确认删除 ${item.path}？`, "确认删除文件", { type: "warning" });
  loading.value = true;
  errorMessage.value = "";
  try {
    await deleteDeviceFile(props.device.id, item.path);
    lastMessage.value = `已删除：${item.name}`;
    await loadFiles(currentPath.value);
  } catch {
    errorMessage.value = "文件删除失败";
  } finally {
    loading.value = false;
  }
}

watch(
  () => props.device.id,
  () => {
    currentPath.value = "/";
    pathInput.value = "/";
    files.value = [];
    selectedFile.value = null;
    uploadRemotePath.value = "";
    void loadFiles("/");
  },
);

onMounted(() => {
  void loadFiles("/");
});
</script>

<template>
  <section class="form-panel" aria-label="设备文件管理">
    <div class="panel-header">
      <div>
        <h3>文件管理</h3>
        <p class="muted">{{ device.name }} / {{ device.device_sn }}</p>
      </div>
      <el-button data-testid="refresh-files" :loading="loading" @click="loadFiles(pathInput)">刷新</el-button>
    </div>

    <el-alert v-if="deviceWarning" class="validation-alert" type="warning" :title="deviceWarning" show-icon :closable="false" />
    <el-alert v-if="errorMessage" class="validation-alert" type="error" :title="errorMessage" show-icon :closable="false" />
    <el-alert v-if="lastMessage" class="validation-alert" type="success" :title="lastMessage" show-icon :closable="false" />

    <div class="file-toolbar">
      <div data-testid="file-path" class="input-wrap">
        <el-input v-model="pathInput" placeholder="远程目录路径，例如 /opt/app" />
      </div>
      <el-button data-testid="load-files" type="primary" :loading="loading" @click="loadFiles(pathInput)">打开目录</el-button>
      <el-button data-testid="file-parent" :disabled="currentPath === '/'" @click="loadFiles(parentPath(currentPath))">返回上级</el-button>
    </div>

    <div class="file-toolbar">
      <input data-testid="file-upload-input" type="file" @change="handleFileChange" />
      <div data-testid="file-upload-path" class="input-wrap">
        <el-input v-model="uploadRemotePath" placeholder="远程目标路径，例如 /opt/app/file.bin" />
      </div>
      <el-button data-testid="upload-file" type="primary" :loading="loading" @click="uploadSelectedFile">上传文件</el-button>
    </div>

    <el-table :data="files" row-key="path" empty-text="暂无文件">
      <el-table-column prop="name" label="名称" min-width="180">
        <template #default="{ row }">
          <button v-if="row.type === 'directory'" class="link-button" type="button" @click="openDirectory(row)">
            {{ row.name }}
          </button>
          <span v-else>{{ row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="type" label="类型" width="100">
        <template #default="{ row }">{{ row.type === "directory" ? "目录" : "文件" }}</template>
      </el-table-column>
      <el-table-column label="大小" width="110">
        <template #default="{ row }">{{ row.type === "directory" ? "-" : formatSize(row.size) }}</template>
      </el-table-column>
      <el-table-column label="修改时间" width="170">
        <template #default="{ row }">{{ formatTime(row.modified_at) }}</template>
      </el-table-column>
      <el-table-column prop="path" label="路径" min-width="220" />
      <el-table-column label="操作" width="170">
        <template #default="{ row }">
          <el-button v-if="row.type !== 'directory'" :data-testid="`download-file-${row.name}`" size="small" @click="downloadFile(row)">
            下载
          </el-button>
          <el-button v-if="row.type !== 'directory'" :data-testid="`delete-file-${row.name}`" size="small" type="danger" @click="removeFile(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>
