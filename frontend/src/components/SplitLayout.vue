<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { DArrowLeft, DArrowRight } from "@element-plus/icons-vue";

const props = withDefaults(
  defineProps<{
    defaultWidth?: number;
    minWidth?: number;
    maxWidth?: number;
    collapsible?: boolean;
  }>(),
  {
    defaultWidth: 280,
    minWidth: 200,
    maxWidth: 500,
    collapsible: true,
  },
);

const emit = defineEmits<{
  "width-change": [width: number];
}>();

const leftPanelWidth = ref(`${props.defaultWidth}px`);
const collapsed = ref(false);
const isResizing = ref(false);

// 加载保存的宽度偏好
onMounted(() => {
  const savedWidth = localStorage.getItem("split-layout-width");
  if (savedWidth) {
    leftPanelWidth.value = `${savedWidth}px`;
  }

  const savedCollapsed = localStorage.getItem("split-layout-collapsed");
  if (savedCollapsed === "true") {
    collapsed.value = true;
  }
});

// 开始拖拽调整宽度
const startResize = (e: MouseEvent) => {
  isResizing.value = true;
  const startX = e.clientX;
  const startWidth = parseInt(leftPanelWidth.value);

  const handleMouseMove = (e: MouseEvent) => {
    const delta = e.clientX - startX;
    const newWidth = Math.max(props.minWidth, Math.min(props.maxWidth, startWidth + delta));
    leftPanelWidth.value = `${newWidth}px`;
    emit("width-change", newWidth);
  };

  const handleMouseUp = () => {
    isResizing.value = false;
    document.removeEventListener("mousemove", handleMouseMove);
    document.removeEventListener("mouseup", handleMouseUp);

    // 保存宽度偏好
    const width = parseInt(leftPanelWidth.value);
    localStorage.setItem("split-layout-width", width.toString());
  };

  document.addEventListener("mousemove", handleMouseMove);
  document.addEventListener("mouseup", handleMouseUp);
};

// 双击重置宽度
const resetWidth = () => {
  leftPanelWidth.value = `${props.defaultWidth}px`;
  localStorage.setItem("split-layout-width", props.defaultWidth.toString());
  emit("width-change", props.defaultWidth);
};

// 切换折叠状态
const toggleCollapse = () => {
  collapsed.value = !collapsed.value;
  localStorage.setItem("split-layout-collapsed", collapsed.value.toString());
};

// 清理事件监听
onUnmounted(() => {
  document.removeEventListener("mousemove", () => {});
  document.removeEventListener("mouseup", () => {});
});
</script>

<template>
  <div class="split-layout" :class="{ 'is-resizing': isResizing }">
    <transition name="slide">
      <div v-if="!collapsed" class="left-panel" :style="{ width: leftPanelWidth }">
        <slot name="left"></slot>
      </div>
    </transition>

    <div class="resize-handle" :class="{ collapsed }" @mousedown="startResize" @dblclick="resetWidth">
      <el-button v-if="collapsible" text circle size="small" @click="toggleCollapse">
        <el-icon><DArrowLeft v-if="!collapsed" /><DArrowRight v-else /></el-icon>
      </el-button>
    </div>

    <div class="right-panel">
      <slot name="right"></slot>
    </div>
  </div>
</template>

<style scoped>
.split-layout {
  display: flex;
  height: 100%;
  position: relative;
  overflow: hidden;
}

.split-layout.is-resizing {
  user-select: none;
  cursor: col-resize;
}

.left-panel {
  flex-shrink: 0;
  height: 100%;
  overflow: auto;
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color);
}

.resize-handle {
  width: 8px;
  flex-shrink: 0;
  cursor: col-resize;
  background: var(--el-fill-color-lighter);
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
}

.resize-handle:hover {
  background: var(--el-color-primary-light-7);
}

.resize-handle.collapsed {
  cursor: pointer;
}

.right-panel {
  flex: 1;
  height: 100%;
  overflow: auto;
  background: var(--el-bg-color);
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from {
  transform: translateX(-100%);
  opacity: 0;
}

.slide-leave-to {
  transform: translateX(-100%);
  opacity: 0;
}
</style>
