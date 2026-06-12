import { ref } from "vue";
import { defineStore } from "pinia";

/**
 * 分组视图模型。deviceCount 由 App.vue 的 mapGroup 依据当前设备列表装配。
 */
export interface Group {
  id: number;
  name: string;
  parent_id: number | null;
  description: string;
  deviceCount: number;
}

/**
 * 分组 store。
 * 作为分组列表的单一数据源(此前散落在 App.vue 内)。
 * 分组与设备的交叉映射(mapGroup 计数 / mapDevice 取分组名)仍由调用方(App.vue)编排。
 */
export const useGroupsStore = defineStore("groups", () => {
  const groups = ref<Group[]>([]);
  return { groups };
});
