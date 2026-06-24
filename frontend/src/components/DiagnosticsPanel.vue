<script setup lang="ts">
import { Refresh } from "@element-plus/icons-vue";
import { storeToRefs } from "pinia";

import { type DiagnosticsConfigResponse } from "../api/platform";
import { useDevicesStore } from "../stores/devices";
import { formatTime } from "../utils/format";
import DiagnosticCard from "./DiagnosticCard.vue";

defineProps<{
  config: DiagnosticsConfigResponse | null;
  loading: boolean;
}>();

defineEmits<{
  refresh: [];
}>();

const { monitoringAvailability } = storeToRefs(useDevicesStore());
</script>

<template>
  <section class="page-section">
    <div class="toolbar">
      <h3>系统诊断</h3>
      <el-button :icon="Refresh" :loading="loading" @click="$emit('refresh')">刷新诊断</el-button>
    </div>
    <section class="panel">
      <div v-if="config" class="list-grid">
        <DiagnosticCard title="服务" :tag="config.api_prefix">
          <p>{{ config.service_name }} · {{ config.version }}</p>
        </DiagnosticCard>
        <DiagnosticCard title="数据" :tag="config.file_backend">
          <p>{{ config.database }}</p>
        </DiagnosticCard>
        <DiagnosticCard title="远程网关">
          <p>SSH {{ config.remote_gateway_host }}</p>
          <p>VNC {{ config.vnc_gateway_host }}</p>
        </DiagnosticCard>
        <DiagnosticCard title="默认 SSH 用户" :tag="`${config.ssh_timeout_seconds} 秒超时`">
          <p>{{ config.default_device_ssh_user }}</p>
        </DiagnosticCard>
        <DiagnosticCard
          title="数据库迁移"
          :tone="config.migration.has_pending_migrations ? 'warning' : 'success'"
          :tag="config.migration.has_pending_migrations ? '待迁移' : '已同步'"
        >
          <p>{{ config.migration.current_revision ?? "未初始化" }}</p>
        </DiagnosticCard>
        <DiagnosticCard
          title="SSH 主机密钥"
          :tone="config.ssh_host_key.known_hosts_configured ? 'success' : 'warning'"
          :tag="config.ssh_host_key.known_hosts_configured ? '已配置 known_hosts' : '未配置 known_hosts'"
        >
          <p>{{ config.ssh_host_key.policy }}</p>
        </DiagnosticCard>
        <DiagnosticCard title="认证有效期">
          <p>访问 {{ config.auth_lifetime.access_expire_minutes }} 分钟</p>
          <p>刷新 {{ config.auth_lifetime.refresh_expire_minutes }} 分钟</p>
        </DiagnosticCard>
        <DiagnosticCard
          title="数据库状态"
          :tone="config.database_status.sqlite_backup_recommended ? 'warning' : 'success'"
          :tag="config.database_status.sqlite_backup_recommended ? '建议备份' : '无需 SQLite 备份'"
        >
          <p>{{ config.database_status.summary }}</p>
        </DiagnosticCard>
        <DiagnosticCard
          title="定时调度器"
          :tone="config.scheduler.running ? 'success' : 'warning'"
          :tag="config.scheduler.running ? '运行中' : '未运行'"
        >
          <p>{{ config.scheduler.enabled ? "已启用" : "已关闭" }}</p>
        </DiagnosticCard>
        <DiagnosticCard title="调度摘要">
          <p>启用任务 {{ config.scheduler.enabled_task_count }} 个</p>
          <p>失败执行 {{ config.scheduler.failed_run_count }} 次</p>
        </DiagnosticCard>
        <DiagnosticCard
          title="告警中心"
          :tone="config.alerts.critical_count ? 'danger' : 'success'"
          :tag="config.alerts.critical_count ? `严重 ${config.alerts.critical_count} 条` : '无严重告警'"
        >
          <p>活跃告警 {{ config.alerts.active_count }} 条</p>
        </DiagnosticCard>
        <DiagnosticCard
          title="告警通知"
          :tone="config.notifications.failed_delivery_count ? 'danger' : 'success'"
          :tag="config.notifications.failed_delivery_count ? `失败 ${config.notifications.failed_delivery_count} 条` : '投递正常'"
        >
          <p>启用通道 {{ config.notifications.enabled_channel_count }} 个</p>
          <p>启用策略 {{ config.notifications.enabled_policy_count }} 个</p>
        </DiagnosticCard>
        <DiagnosticCard
          title="用户与权限"
          :tone="config.users.disabled_count ? 'warning' : 'success'"
          :tag="config.users.disabled_count ? `停用 ${config.users.disabled_count} 个` : '无停用用户'"
        >
          <p>启用用户 {{ config.users.active_count }} / {{ config.users.total_count }}</p>
          <p>管理员 {{ config.users.admin_count }} 个，运维 {{ config.users.operator_count }} 个</p>
        </DiagnosticCard>
        <DiagnosticCard
          title="系统设置"
          :tone="config.system_settings.pending_restart_count ? 'warning' : 'success'"
          :tag="config.system_settings.pending_restart_count ? `待重启 ${config.system_settings.pending_restart_count} 项` : '配置已应用'"
        >
          <p>数据库覆盖 {{ config.system_settings.database_override_count }} 项</p>
          <p>systemd {{ config.system_settings.systemd_managed ? "已检测到" : "未确认" }}</p>
        </DiagnosticCard>
      </div>
      <el-empty v-else description="暂无诊断数据" />
    </section>
    <section class="panel">
      <div class="panel-header">
        <h3>监控可用性</h3>
        <el-tag :type="monitoringAvailability.withoutMetrics ? 'warning' : 'success'">
          {{ monitoringAvailability.withoutMetrics ? "存在未上报" : "指标正常" }}
        </el-tag>
      </div>
      <div class="list-grid">
        <div class="item-card">
          <h3>有指标设备</h3>
          <p>有指标设备：{{ monitoringAvailability.withMetrics }}</p>
        </div>
        <div class="item-card">
          <h3>无指标设备</h3>
          <p>无指标设备：{{ monitoringAvailability.withoutMetrics }}</p>
        </div>
        <div class="item-card">
          <h3>最近指标时间</h3>
          <p>{{ monitoringAvailability.latestRecordedAt ? formatTime(monitoringAvailability.latestRecordedAt) : "未上报" }}</p>
        </div>
      </div>
    </section>
    <section v-if="config" class="panel">
      <div class="panel-header">
        <h3>安全检查</h3>
        <el-tag :type="config.security.warnings.length ? 'warning' : 'success'">
          {{ config.security.warnings.length ? "存在提醒" : "配置正常" }}
        </el-tag>
      </div>
      <div class="list-grid">
        <div class="item-card">
          <h3>凭据加密</h3>
          <el-tag :type="config.security.credential_encryption_configured ? 'success' : 'warning'">
            {{ config.security.credential_encryption_configured ? "已配置" : "未配置" }}
          </el-tag>
        </div>
        <div class="item-card">
          <h3>JWT 密钥</h3>
          <el-tag :type="config.security.jwt_secret_configured ? 'success' : 'warning'">
            {{ config.security.jwt_secret_configured ? "已配置" : "默认值" }}
          </el-tag>
        </div>
        <div class="item-card">
          <h3>默认密码</h3>
          <p>管理员：{{ config.security.default_admin_password_in_use ? "仍为默认值" : "已修改" }}</p>
          <p>设备 SSH：{{ config.security.default_device_ssh_password_in_use ? "仍为默认值" : "已修改" }}</p>
        </div>
      </div>
      <el-alert
        v-for="warning in config.security.warnings"
        :key="warning"
        class="validation-alert"
        type="warning"
        show-icon
        :closable="false"
        :title="warning"
      />
      <el-alert
        v-for="warning in config.ssh_host_key.warnings"
        :key="warning"
        class="validation-alert"
        type="warning"
        show-icon
        :closable="false"
        :title="warning"
      />
      <el-alert
        v-for="warning in config.scheduler.warnings"
        :key="warning"
        class="validation-alert"
        type="warning"
        show-icon
        :closable="false"
        :title="warning"
      />
      <el-alert
        v-for="warning in config.alerts.warnings"
        :key="warning"
        class="validation-alert"
        type="warning"
        show-icon
        :closable="false"
        :title="warning"
      />
      <el-alert
        v-for="warning in config.notifications.warnings"
        :key="warning"
        class="validation-alert"
        type="warning"
        show-icon
        :closable="false"
        :title="warning"
      />
      <el-alert
        v-for="warning in config.users.warnings"
        :key="warning"
        class="validation-alert"
        type="warning"
        show-icon
        :closable="false"
        :title="warning"
      />
      <el-alert
        v-for="warning in config.system_settings.warnings"
        :key="warning"
        class="validation-alert"
        type="warning"
        show-icon
        :closable="false"
        :title="warning"
      />
    </section>
  </section>
</template>
