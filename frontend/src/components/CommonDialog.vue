<script setup lang="ts">
import { computed } from "vue";

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

</script>

<template>
  <section
    v-if="dialogVisible"
    class="form-panel common-dialog"
    :class="{ 'common-dialog--fullscreen': fullscreen }"
    :aria-label="title"
    :style="{ maxWidth: fullscreen ? undefined : width }"
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
</template>

<style scoped>
.common-dialog {
  width: 100%;
}

.common-dialog--fullscreen {
  max-width: none;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
