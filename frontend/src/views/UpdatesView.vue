<script setup lang="ts">
import { ElMessageBox } from "element-plus";
import { storeToRefs } from "pinia";

import UpdatesPanel from "../components/UpdatesPanel.vue";
import { normalizeDeviceStatus } from "../stores/devices";
import { groupNameFor, useGroupsStore } from "../stores/groups";
import { usePlatformOverviewStore } from "../stores/platformOverview";
import { type UpdateTask } from "../stores/updates";

const groupsStore = useGroupsStore();
const { groups } = storeToRefs(groupsStore);
const platformOverviewStore = usePlatformOverviewStore();

const deviceStatusText: Record<string, string> = {
  online: "在线",
  offline: "离线",
  degraded: "异常",
  unknown: "未知",
};

function targetSummaryForFilter(targetFilter: Record<string, unknown>): string {
  const deviceIds = Array.isArray(targetFilter.device_ids) ? targetFilter.device_ids : [];
  if (deviceIds.length > 0) {
    return `手动选择 ${deviceIds.length} 台设备`;
  }
  const parts: string[] = [];
  if (typeof targetFilter.project_id === "number" && targetFilter.project_id) {
    parts.push(`项目 ${targetFilter.project_id}`);
  }
  if (typeof targetFilter.group_id === "number") {
    parts.push(`分组 ${groupNameFor(targetFilter.group_id, groups.value)}`);
  }
  if (typeof targetFilter.status === "string" && targetFilter.status) {
    parts.push(`状态 ${deviceStatusText[normalizeDeviceStatus(targetFilter.status)]}`);
  }
  const tags = Array.isArray(targetFilter.tags) ? targetFilter.tags.filter((tag): tag is string => typeof tag === "string") : [];
  if (tags.length > 0) {
    parts.push(`标签 ${tags.join(", ")}`);
  }
  return parts.length > 0 ? parts.join("，") : "全部设备";
}

function targetSummaryForTask(task: UpdateTask): string {
  return `${targetSummaryForFilter(task.target_filter)}，匹配 ${task.matched} 台`;
}

async function confirmRealSshTask(command: string, target: string): Promise<boolean> {
  try {
    await ElMessageBox.confirm(
      `将通过 SSH 在目标设备上真实执行命令。\n目标：${target}\n命令：${command}\n建议先使用演练模式确认范围。`,
      "确认真实 SSH 执行",
      {
        type: "warning",
        confirmButtonText: "确认执行",
        cancelButtonText: "取消",
      },
    );
    return true;
  } catch {
    return false;
  }
}
</script>

<template>
  <UpdatesPanel
    :confirm-real-ssh-task="confirmRealSshTask"
    :target-summary-for-filter="targetSummaryForFilter"
    :target-summary-for-task="targetSummaryForTask"
    @changed="platformOverviewStore.refreshOverview"
  />
</template>
