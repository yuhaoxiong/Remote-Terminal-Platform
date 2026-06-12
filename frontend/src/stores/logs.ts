import { ref } from "vue";
import { defineStore } from "pinia";

import { type OperationLogRead } from "../api/platform";
import { formatTime } from "../utils/format";

/**
 * 操作日志视图模型。
 */
export interface AuditLog {
  id: number;
  action: string;
  target: string;
  status: string;
  detail: string;
  created_at: string;
}

/**
 * 操作日志 store。
 *
 * 承载审计日志列表(此前散落在 App.vue),并提供两项全局公共能力:
 * - mapLog: 后端 OperationLogRead -> 前端 AuditLog 的映射
 * - prependLocalLog: 各业务动作在校验失败/异常时本地插入一条日志
 *   (全项目 ~25 处调用,是各"执行动作"型 section 的公共依赖)
 * 日志的筛选/分页/拉取仍由调用方(App.vue,以及后续的 LogsPanel)负责编排。
 */
export const useLogsStore = defineStore("logs", () => {
  const auditLogs = ref<AuditLog[]>([]);
  const auditLogsTotal = ref(0);

  function mapLog(log: OperationLogRead): AuditLog {
    const target = log.target_type && log.target_id !== null ? `${log.target_type}:${log.target_id}` : log.target_type || "-";
    return {
      id: log.id,
      action: log.action,
      target,
      status: log.status,
      detail: log.detail || "",
      created_at: formatTime(log.created_at),
    };
  }

  function prependLocalLog(action: string, target: string, status: string, detail: string) {
    auditLogs.value.unshift({
      id: Date.now(),
      action,
      target,
      status,
      detail,
      created_at: new Date().toLocaleString("sv-SE").slice(0, 16),
    });
  }

  return { auditLogs, auditLogsTotal, mapLog, prependLocalLog };
});
