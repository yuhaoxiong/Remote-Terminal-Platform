<script setup lang="ts">
import { computed, onMounted, onUnmounted } from "vue";

const props = withDefaults(
  defineProps<{
    visible: boolean;
    title: string;
    width?: string;
    fullscreen?: boolean;
    showFooter?: boolean;
    confirmText?: string;
    cancelText?: string;
    confirmLoading?: boolean;
    closeOnClickModal?: boolean;
  }>(),
  {
    width: "700px",
    fullscreen: false,
    showFooter: true,
    confirmText: "确定",
    cancelText: "取消",
    confirmLoading: false,
    closeOnClickModal: false,
  },
);

const emit = defineEmits<{
  "update:visible": [value: boolean];
  confirm: [];
  cancel: [];
}>();

const dialogVisible = computed({
  get: () => props.visible,
  set: (value) => emit("update:visible", value),
});

function handleConfirm() {
  emit("confirm");
}

function handleCancel() {
  emit("cancel");
  dialogVisible.value = false;
}

function handleMaskClick() {
  if (props.closeOnClickModal) {
    handleCancel();
  }
}

function handleEscapeKey(event: KeyboardEvent) {
  if (event.key === "Escape" && dialogVisible.value) {
    handleCancel();
  }
}

onMounted(() => {
  document.addEventListener("keydown", handleEscapeKey);
});

onUnmounted(() => {
  document.removeEventListener("keydown", handleEscapeKey);
});
</script>

<template>
  <teleport to="body">
    <transition name="dialog-fade">
      <div v-if="dialogVisible" class="common-dialog-overlay" @click="handleMaskClick">
        <div class="common-dialog-wrapper">
          <section
            class="form-panel common-dialog"
            :class="{ 'common-dialog--fullscreen': fullscreen }"
            :aria-label="title"
            :style="{ width: fullscreen ? '100%' : width, maxWidth: fullscreen ? '100%' : '90vw' }"
            @click.stop
          >
            <div class="panel-header">
              <h3>{{ title }}</h3>
              <el-button text @click="handleCancel">{{ cancelText }}</el-button>
            </div>
            <slot></slot>
            <div v-if="showFooter" class="dialog-footer">
              <slot name="footer">
                <el-button @click="handleCancel">{{ cancelText }}</el-button>
                <el-button type="primary" :loading="confirmLoading" @click="handleConfirm">
                  {{ confirmText }}
                </el-button>
              </slot>
            </div>
          </section>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<style scoped>
.common-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: auto;
  padding: 20px;
}

.common-dialog-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  width: 100%;
}

.common-dialog {
  background: var(--el-bg-color);
  border-radius: var(--el-border-radius-base);
  box-shadow: var(--el-box-shadow-dark);
  margin: auto;
  max-height: calc(100vh - 40px);
  overflow: auto;
}

.common-dialog--fullscreen {
  width: 100%;
  height: 100%;
  max-height: 100vh;
  border-radius: 0;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: opacity 0.3s;
}

.dialog-fade-enter-from,
.dialog-fade-leave-to {
  opacity: 0;
}
</style>
