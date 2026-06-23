import { ref } from "vue";
import { defineStore } from "pinia";

import { type GroupRead } from "../api/platform";
import { type Device } from "./devices";

/**
 * 分组视图模型。deviceCount 由 mapGroup 依据当前设备列表装配。
 */
export interface Group {
  id: number;
  name: string;
  parent_id: number | null;
  description: string;
  deviceCount: number;
}

/**
 * 在后端 GroupRead -> 前端 Group 的映射中,以及目标筛选展示中
 * 按 group_id 查找分组名称。若未找到则返回 "未分组" 或 "分组 ${id}"。
 */
export function groupNameFor(
  groupId: number | null,
  sourceGroups: Array<{ id: number; name: string }> = [],
): string {
  if (groupId === null) {
    return "未分组";
  }
  return sourceGroups.find((group) => group.id === groupId)?.name ?? `分组 ${groupId}`;
}

/**
 * 后端 GroupRead -> 前端 Group。deviceCount 依据传入的设备列表实时算出。
 */
export function mapGroup(group: GroupRead, devices: Device[]): Group {
  return {
    id: group.id,
    name: group.name,
    parent_id: group.parent_id,
    description: group.description || "暂无描述",
    deviceCount: devices.filter((device) => device.group_id === group.id).length,
  };
}

/**
 * 分组 store。
 * 作为分组列表的单一数据源(此前散落在 App.vue 内),并提供依赖设备列表的
 * recalculateGroupCounts(分组/设备增删改后重算各分组设备数)。
 */
export const useGroupsStore = defineStore("groups", () => {
  const groups = ref<Group[]>([]);

  function recalculateGroupCounts(deviceList: Device[]) {
    groups.value = groups.value.map((group) => ({
      ...group,
      deviceCount: deviceList.filter((device) => device.group_id === group.id).length,
    }));
  }

  return { groups, recalculateGroupCounts };
});
