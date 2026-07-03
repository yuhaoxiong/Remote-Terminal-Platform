<script setup lang="ts">
import { ref, computed } from "vue";
import { Folder, Document, Download, Delete, Edit, Refresh, Upload } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { Device } from "../stores/devices";

const props = defineProps<{
  device: Device | null;
  connected: boolean;
}>();

const emit = defineEmits<{
  upload: [path: string, files: File[]];
  download: [path: string, filename: string];
  delete: [path: string];
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

// Tree 配置
const treeProps = {
  label: "name",
  children: "children",
  isLeaf: "isLeaf",
};

// 加载根目录
const loadRootDirectory = async () => {
  if (!props.device || !props.connected) {
    fileTreeData.value = [];
    return;
  }

  loading.value = true;
  try {
    // TODO: 调用 API 获取根目录文件列表
    // const files = await listDeviceFiles(props.device.id, "/");

    // 模拟数据
    fileTreeData.value = [
      {
        id: "/root",
        name: "root",
        path: "/root",
        type: "directory",
        isLeaf: false,
      },
      {
        id: "/home",
        name: "home",
        path: "/home",
        type: "directory",
        isLeaf: false,
      },
      {
        id: "/etc",
        name: "etc",
        path: "/etc",
        type: "directory",
        isLeaf: false,
      },
      {
        id: "/var",
        name: "var",
        path: "/var",
        type: "directory",
        isLeaf: false,
      },
    ];
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

  try {
    // TODO: 调用 API 获取子目录文件列表
    // const files = await listDeviceFiles(props.device!.id, parentData.path);

    // 模拟数据
    const children: FileTreeNode[] = [
      {
        id: `${parentData.path}/file1.txt`,
        name: "file1.txt",
        path: `${parentData.path}/file1.txt`,
        type: "file",
        size: 1024,
        isLeaf: true,
      },
      {
        id: `${parentData.path}/subfolder`,
        name: "subfolder",
        path: `${parentData.path}/subfolder`,
        type: "directory",
        isLeaf: false,
      },
    ];

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
  switch (command) {
    case "download":
      emit("download", node.path, node.name);
      break;
    case "delete":
      try {
        await ElMessageBox.confirm(
          `确定删除 ${node.name}？`,
          "删除确认",
          {
            type: "warning",
            confirmButtonText: "删除",
            cancelButtonText: "取消",
          }
        );
        emit("delete", node.path);
      } catch {
        // 用户取消
      }
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

// 文件上传
const handleUploadClick = () => {
  const input = document.createElement("input");
  input.type = "file";
  input.multiple = true;
  input.onchange = (e) => {
    const files = Array.from((e.target as HTMLInputElement).files || []);
    if (files.length > 0) {
      emit("upload", currentPath.value, files);
    }
  };
  input.click();
};

// 拖拽上传
const handleDrop = (e: DragEvent) => {
  e.preventDefault();
  const files = Array.from(e.dataTransfer?.files || []);
  if (files.length > 0) {
    emit("upload", currentPath.value, files);
  }
};

const handleDragOver = (e: DragEvent) => {
  e.preventDefault();
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
