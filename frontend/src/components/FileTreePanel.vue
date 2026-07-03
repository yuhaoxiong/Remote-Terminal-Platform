<script setup lang="ts">
import { ref, computed } from "vue";
import { Folder, Document, Download, Delete, Edit, Refresh, Upload } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { Device } from "../stores/devices";
import {
  listDeviceFiles,
  uploadDeviceFile,
  downloadDeviceFile,
  deleteDeviceFile,
  type DeviceFileItem,
} from "../api/platform";

const props = defineProps<{
  device: Device | null;
  connected: boolean;
}>();

const emit = defineEmits<{
  refresh: [];
}>();

interface FileTreeNode {
  id: string;
  name: string;
  path: string;
  type: "file" | "directory";
  size?: number;
  modifiedAt?: string;
  permissions?: string;
  isLeaf?: boolean;
  children?: FileTreeNode[];
}

const loading = ref(false);
const fileTreeData = ref<FileTreeNode[]>([]);
const currentPath = ref("/");
const selectedNode = ref<FileTreeNode | null>(null);
const uploadingFiles = ref(new Set<string>());

// Tree 配置
const treeProps = {
  label: "name",
  children: "children",
  isLeaf: "isLeaf",
};

// 转换 API 数据为 Tree 节点
const mapFileItemToNode = (item: DeviceFileItem): FileTreeNode => {
  return {
    id: item.path,
    name: item.name,
    path: item.path,
    type: item.type === "directory" ? "directory" : "file",
    size: item.size,
    modifiedAt: item.modified_at || undefined,
    isLeaf: item.type !== "directory",
  };
};

// 加载根目录
const loadRootDirectory = async () => {
  if (!props.device || !props.connected) {
    fileTreeData.value = [];
    return;
  }

  loading.value = true;
  try {
    const response = await listDeviceFiles(props.device.id, "/");
    fileTreeData.value = response.items.map(mapFileItemToNode);
  } catch (error) {
    ElMessage.error("加载文件列表失败");
    fileTreeData.value = [];
  } finally {
    loading.value = false;
  }
};

// 懒加载子节点
const loadNode = async (node: any, resolve: any) => {
  if (node.level === 0) {
    // 根节点
    await loadRootDirectory();
    return resolve(fileTreeData.value);
  }

  // 加载子目录
  const parentData = node.data as FileTreeNode;

  if (!props.device) {
    return resolve([]);
  }

  try {
    const response = await listDeviceFiles(props.device.id, parentData.path);
    const children = response.items.map(mapFileItemToNode);
    resolve(children);
  } catch (error) {
    ElMessage.error(`加载 ${parentData.path} 失败`);
    resolve([]);
  }
};

// 点击节点
const handleNodeClick = (data: FileTreeNode) => {
  selectedNode.value = data;
  currentPath.value = data.path;
};

// 右键菜单命令
const handleCommand = async (command: string, node: FileTreeNode) => {
  if (!props.device) return;

  switch (command) {
    case "download":
      await handleDownload(node);
      break;
    case "delete":
      await handleDelete(node);
      break;
    case "rename":
      ElMessage.info("重命名功能开发中...");
      break;
    case "refresh":
      emit("refresh");
      loadRootDirectory();
      break;
  }
};

// 文件下载
const handleDownload = async (node: FileTreeNode) => {
  if (!props.device) return;

  try {
    ElMessage.info(`正在下载 ${node.name}...`);
    const blob = await downloadDeviceFile(props.device.id, node.path);

    // 创建下载链接
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = node.name;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    window.URL.revokeObjectURL(url);

    ElMessage.success(`${node.name} 下载成功`);
  } catch (error) {
    ElMessage.error(`下载 ${node.name} 失败`);
  }
};

// 文件删除
const handleDelete = async (node: FileTreeNode) => {
  if (!props.device) return;

  try {
    await ElMessageBox.confirm(
      `确定删除 ${node.name}？此操作不可恢复!`,
      "删除确认",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      }
    );

    await deleteDeviceFile(props.device.id, node.path);
    ElMessage.success(`${node.name} 删除成功`);

    // 刷新文件树
    emit("refresh");
    loadRootDirectory();
  } catch (error) {
    if (error !== "cancel") {
      ElMessage.error(`删除 ${node.name} 失败`);
    }
  }
};

// 文件上传
const handleUploadClick = () => {
  const input = document.createElement("input");
  input.type = "file";
  input.multiple = true;
  input.onchange = async (e) => {
    const files = Array.from((e.target as HTMLInputElement).files || []);
    if (files.length > 0) {
      await uploadFiles(currentPath.value, files);
    }
  };
  input.click();
};

// 拖拽上传
const handleDrop = async (e: DragEvent) => {
  e.preventDefault();
  const files = Array.from(e.dataTransfer?.files || []);
  if (files.length > 0) {
    await uploadFiles(currentPath.value, files);
  }
};

const handleDragOver = (e: DragEvent) => {
  e.preventDefault();
};

// 批量上传文件
const uploadFiles = async (targetPath: string, files: File[]) => {
  if (!props.device) return;

  const deviceId = props.device.id;

  for (const file of files) {
    const uploadKey = `${targetPath}/${file.name}`;
    uploadingFiles.value.add(uploadKey);

    try {
      ElMessage.info(`正在上传 ${file.name}...`);
      await uploadDeviceFile(deviceId, targetPath, file);
      ElMessage.success(`${file.name} 上传成功`);
    } catch (error) {
      ElMessage.error(`上传 ${file.name} 失败`);
    } finally {
      uploadingFiles.value.delete(uploadKey);
    }
  }

  // 上传完成后刷新文件树
  emit("refresh");
  loadRootDirectory();
};

// 刷新文件树
const refresh = () => {
  loadRootDirectory();
};

// 获取文件图标
const getFileIcon = (node: FileTreeNode) => {
  return node.type === "directory" ? Folder : Document;
};

// 格式化文件大小
const formatFileSize = (bytes?: number) => {
  if (!bytes) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};

// 暴露方法给父组件
defineExpose({
  refresh,
  loadRootDirectory,
});
</script>

<template>
  <div
    class="file-tree-panel"
    @drop="handleDrop"
    @dragover="handleDragOver"
  >
    <div class="panel-header">
      <h4>文件管理</h4>
      <div class="toolbar">
        <el-button
          size="small"
          :icon="Upload"
          :disabled="!connected"
          @click="handleUploadClick"
        >
          上传
        </el-button>
        <el-button
          size="small"
          :icon="Refresh"
          :disabled="!connected"
          @click="refresh"
        >
          刷新
        </el-button>
      </div>
    </div>

    <div class="current-path">
      <el-text size="small" type="info">{{ currentPath }}</el-text>
    </div>

    <div v-if="!device" class="empty-state">
      <el-empty description="请选择设备" />
    </div>

    <div v-else-if="!connected" class="empty-state">
      <el-empty description="请先连接 SSH" />
    </div>

    <div v-else class="tree-container" v-loading="loading">
      <el-tree
        :data="fileTreeData"
        :props="treeProps"
        :load="loadNode"
        lazy
        node-key="id"
        highlight-current
        @node-click="handleNodeClick"
      >
        <template #default="{ node, data }">
          <el-dropdown
            trigger="contextmenu"
            @command="(cmd: string) => handleCommand(cmd, data)"
          >
            <span class="tree-node">
              <el-icon><component :is="getFileIcon(data)" /></el-icon>
              <span class="node-label">{{ node.label }}</span>
              <span v-if="data.size" class="node-size">{{ formatFileSize(data.size) }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  command="download"
                  v-if="data.type === 'file'"
                >
                  <el-icon><Download /></el-icon> 下载
                </el-dropdown-item>
                <el-dropdown-item command="delete">
                  <el-icon><Delete /></el-icon> 删除
                </el-dropdown-item>
                <el-dropdown-item command="rename">
                  <el-icon><Edit /></el-icon> 重命名
                </el-dropdown-item>
                <el-dropdown-item
                  command="refresh"
                  v-if="data.type === 'directory'"
                  divided
                >
                  <el-icon><Refresh /></el-icon> 刷新
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-tree>

      <div class="drop-hint">
        <el-text size="small" type="info">
          💡 提示: 可将文件拖拽到此处上传
        </el-text>
      </div>
    </div>
  </div>
</template>

<style scoped>
.file-tree-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--el-bg-color);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--el-border-color);
}

.panel-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.toolbar {
  display: flex;
  gap: 8px;
}

.current-path {
  padding: 8px 16px;
  background: var(--el-fill-color-lighter);
  border-bottom: 1px solid var(--el-border-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tree-container {
  flex: 1;
  overflow: auto;
  padding: 8px;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  padding: 4px 0;
  user-select: none;
}

.node-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-size {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-left: auto;
}

.drop-hint {
  padding: 12px 16px;
  text-align: center;
  border-top: 1px solid var(--el-border-color);
  background: var(--el-fill-color-lighter);
}

:deep(.el-tree-node__content) {
  height: 32px;
}

:deep(.el-tree-node__content:hover) {
  background-color: var(--el-fill-color-light);
}
</style>
