<script setup lang="ts">
interface OperationLogDetail {
  id: number;
  action: string;
  target: string;
  status: string;
  detail: string;
  created_at: string;
}

defineProps<{
  modelValue: boolean;
  log: OperationLogDetail | null;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
}>();

function closeDrawer() {
  emit("update:modelValue", false);
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    title="操作详情"
    size="360px"
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-empty v-if="!log" description="暂无操作详情" />
    <section v-else class="log-detail">
      <el-tag :type="log.status === 'blocked' ? 'warning' : log.status === 'failed' ? 'danger' : 'success'">
        {{ log.status }}
      </el-tag>
      <dl>
        <dt>操作时间</dt>
        <dd>{{ log.created_at }}</dd>
        <dt>动作</dt>
        <dd>{{ log.action }}</dd>
        <dt>目标</dt>
        <dd>{{ log.target }}</dd>
        <dt>详情</dt>
        <dd class="log-detail-text">{{ log.detail || "暂无详情" }}</dd>
      </dl>
      <el-alert
        type="info"
        show-icon
        :closable="false"
        title="详情内容已按后端审计摘要展示，前端不展示密码、Token、私钥或 Webhook 明文密钥。"
      />
      <div class="drawer-actions">
        <el-button @click="closeDrawer">关闭</el-button>
      </div>
    </section>
  </el-drawer>
</template>
