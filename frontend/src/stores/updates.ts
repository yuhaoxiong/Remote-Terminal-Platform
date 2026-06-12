import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { buildApiWebSocketUrl, getAccessToken, type UpdateTaskDeviceRead, type UpdateTaskRead } from "../api/platform";

export type UpdateStatus = "pending" | "running" | "completed" | "canceled" | "partial_failed";
export type ExecutionMode = "dry_run" | "ssh_command";

/**
 * 更新任务视图模型。由 mapUpdateTask 从后端 UpdateTaskRead 装配。
 */
export interface UpdateTask {
  id: number;
  name: string;
  command: string;
  target_filter: Record<string, unknown>;
  project_id: string;
  execution_mode: ExecutionMode;
  failure_strategy: "continue" | "pause" | "rollback";
  concurrency_limit: number;
  status: UpdateStatus;
  matched: number;
  completed: number;
  lastEvent: string;
  devices: UpdateTaskDeviceRead[];
}

export const updateStatusText: Record<UpdateStatus, string> = {
  pending: "待执行",
  running: "执行中",
  completed: "已完成",
  canceled: "已取消",
  partial_failed: "部分失败",
};

export const executionModeText: Record<ExecutionMode, string> = {
  dry_run: "演练模式",
  ssh_command: "真实 SSH 执行",
};

export function normalizeUpdateStatus(status: string): UpdateStatus {
  if (["pending", "running", "completed", "canceled", "partial_failed"].includes(status)) {
    return status as UpdateStatus;
  }
  return "pending";
}

export function statusTextForTask(status: string): string {
  return updateStatusText[normalizeUpdateStatus(status)] ?? status;
}

/**
 * 后端 UpdateTaskRead -> 前端 UpdateTask。
 */
export function mapUpdateTask(task: UpdateTaskRead): UpdateTask {
  const completed = task.devices.filter((device) => ["success", "completed", "failed", "skipped"].includes(device.status)).length;
  const targetFilter = task.target_filter ?? {};
  const projectId = typeof targetFilter.project_id === "string" ? targetFilter.project_id : "全部项目";
  const lastDevice = task.devices.at(-1);
  return {
    id: task.id,
    name: task.name,
    command: task.command,
    target_filter: targetFilter,
    project_id: projectId,
    execution_mode: task.execution_mode,
    failure_strategy: task.failure_strategy as "continue" | "pause" | "rollback",
    concurrency_limit: task.concurrency_limit,
    status: normalizeUpdateStatus(task.status),
    matched: task.device_count,
    completed,
    lastEvent:
      lastDevice?.error_message ||
      lastDevice?.stdout_summary ||
      lastDevice?.stderr_summary ||
      lastDevice?.output_summary ||
      statusTextForTask(task.status),
    devices: task.devices,
  };
}

/**
 * 更新任务 store。
 * 承载任务列表(仪表盘 overview / pendingTaskCount 与更新区共享, 并由 WebSocket 快照实时推送)
 * 及派生的 pendingTaskCount。类型/展示映射/mapUpdateTask 等纯逻辑随域导出, 供调用方复用。
 */
export const useUpdatesStore = defineStore("updates", () => {
  const updateTasks = ref<UpdateTask[]>([]);
  const pendingTaskCount = computed(
    () => updateTasks.value.filter((task) => ["pending", "running"].includes(task.status)).length,
  );

  // 每个任务一条 WebSocket 的实时进度连接。连接需跨 section 导航存活(执行任务后切走仍接收进度),
  // 故由 store 持有(而非随会卸载的视图组件),仅在应用卸载或任务结束时关闭。
  const progressSockets = new Map<number, WebSocket>();

  function updateTaskFromSnapshot(snapshot: UpdateTaskRead) {
    const mapped = mapUpdateTask(snapshot);
    const index = updateTasks.value.findIndex((item) => item.id === mapped.id);
    if (index >= 0) {
      updateTasks.value[index] = mapped;
    } else {
      updateTasks.value.push(mapped);
    }
    if (mapped.status !== "running") {
      stopUpdateProgress(mapped.id);
    }
  }

  function startUpdateProgress(taskId: number) {
    if (typeof WebSocket === "undefined") {
      return;
    }
    stopUpdateProgress(taskId);
    const token = getAccessToken();
    if (!token) {
      return;
    }
    const websocketUrl = buildApiWebSocketUrl(`/api/ws/update-tasks/${taskId}`, token);
    const socket = new WebSocket(websocketUrl);
    progressSockets.set(taskId, socket);
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(String(event.data)) as { type?: string; task?: UpdateTaskRead };
        if (payload.type === "task.snapshot" && payload.task) {
          updateTaskFromSnapshot(payload.task);
        }
      } catch {
        const task = updateTasks.value.find((item) => item.id === taskId);
        if (task) {
          task.lastEvent = "更新任务进度消息解析失败";
        }
      }
    };
    socket.onerror = () => {
      const task = updateTasks.value.find((item) => item.id === taskId);
      if (task && task.status === "running") {
        task.lastEvent = "实时进度连接异常，仍可刷新任务状态";
      }
    };
    socket.onclose = () => {
      if (progressSockets.get(taskId) === socket) {
        progressSockets.delete(taskId);
      }
    };
  }

  function stopUpdateProgress(taskId: number) {
    const socket = progressSockets.get(taskId);
    if (!socket) {
      return;
    }
    progressSockets.delete(taskId);
    socket.close();
  }

  function stopAllProgress() {
    for (const taskId of progressSockets.keys()) {
      stopUpdateProgress(taskId);
    }
  }

  return {
    updateTasks,
    pendingTaskCount,
    startUpdateProgress,
    stopUpdateProgress,
    updateTaskFromSnapshot,
    stopAllProgress,
  };
});
