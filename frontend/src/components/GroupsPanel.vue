<script setup lang="ts">
import { Plus } from "@element-plus/icons-vue";
import { ElMessageBox } from "element-plus";
import { computed, reactive, ref } from "vue";
import { storeToRefs } from "pinia";

import {
  createGroup,
  deleteGroup,
  updateGroup,
  type GroupCreateRequest,
  type GroupUpdateRequest,
} from "../api/platform";
import { useDevicesStore } from "../stores/devices";
import { mapGroup, useGroupsStore, type Group } from "../stores/groups";
import { useLogsStore } from "../stores/logs";

const emit = defineEmits<{
  changed: [];
  "view-devices": [groupId: number];
}>();

const groupsStore = useGroupsStore();
const { groups } = storeToRefs(groupsStore);
const { recalculateGroupCounts } = groupsStore;
const devicesStore = useDevicesStore();
const { devices, selectedGroupId } = storeToRefs(devicesStore);
const { prependLocalLog } = useLogsStore();

const groupFormOpen = ref(false);
const groupEditId = ref<number | null>(null);
const groupForm = reactive({
  name: "",
  parent_id: null as number | null,
  description: "",
});
const groupFormTitle = computed(() => (groupEditId.value === null ? "创建分组" : "编辑分组"));

function openGroupCreate() {
  groupEditId.value = null;
  Object.assign(groupForm, {
    name: "",
    parent_id: null,
    description: "",
  });
  groupFormOpen.value = true;
}

function openGroupEdit(group: Group) {
  groupEditId.value = group.id;
  Object.assign(groupForm, {
    name: group.name,
    parent_id: group.parent_id,
    description: group.description === "暂无描述" ? "" : group.description,
  });
  groupFormOpen.value = true;
}

async function saveGroup() {
  if (!groupForm.name) {
    prependLocalLog("分组校验", "分组", "blocked", "分组名称为必填项");
    return;
  }
  try {
    if (groupEditId.value === null) {
      const payload: GroupCreateRequest = {
        name: groupForm.name,
        parent_id: groupForm.parent_id,
        description: groupForm.description || undefined,
      };
      const created = await createGroup(payload);
      groups.value.push(mapGroup(created, devices.value));
    } else {
      const payload: GroupUpdateRequest = {
        name: groupForm.name,
        parent_id: groupForm.parent_id,
        description: groupForm.description || undefined,
      };
      const updated = await updateGroup(groupEditId.value, payload);
      const index = groups.value.findIndex((group) => group.id === updated.id);
      if (index >= 0) {
        groups.value[index] = mapGroup(updated, devices.value);
      }
      devices.value = devices.value.map((device) =>
        device.group_id === updated.id ? { ...device, group: updated.name } : device,
      );
    }
    recalculateGroupCounts(devices.value);
    emit("changed");
    groupFormOpen.value = false;
  } catch (error) {
    prependLocalLog(groupEditId.value === null ? "创建分组" : "编辑分组", "分组", "blocked", "保存分组失败，请检查后端返回。");
  }
}

async function removeGroup(group: Group) {
  try {
    await ElMessageBox.confirm(`确定删除分组 ${group.name}？`, "删除分组", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  try {
    await deleteGroup(group.id);
    groups.value = groups.value.filter((item) => item.id !== group.id);
    if (selectedGroupId.value === group.id) {
      selectedGroupId.value = null;
    }
    devices.value = devices.value.map((device) =>
      device.group_id === group.id ? { ...device, group_id: null, group: "未分组" } : device,
    );
    emit("changed");
  } catch (error) {
    prependLocalLog("删除分组", `分组：${group.id}`, "blocked", "删除分组失败，请检查后端返回。");
  }
}
</script>

<template>
  <section class="page-section">
    <div class="toolbar">
      <div>
        <h3>分组管理</h3>
        <p class="muted">维护设备分组，并快速按分组进入设备列表。</p>
      </div>
      <el-button data-testid="open-group-create" type="primary" :icon="Plus" @click="openGroupCreate">新建分组</el-button>
    </div>

    <section v-if="groupFormOpen" class="form-panel" :aria-label="groupFormTitle">
      <div class="panel-header">
        <h3>{{ groupFormTitle }}</h3>
        <el-button text @click="groupFormOpen = false">关闭</el-button>
      </div>
      <div class="form-grid">
        <div data-testid="group-name" class="input-wrap"><el-input v-model="groupForm.name" placeholder="分组名称" /></div>
        <el-select v-model="groupForm.parent_id" placeholder="上级分组" clearable>
          <el-option
            v-for="group in groups.filter((item) => item.id !== groupEditId)"
            :key="group.id"
            :label="group.name"
            :value="group.id"
          />
        </el-select>
        <div data-testid="group-description" class="input-wrap textarea-wrap">
          <el-input v-model="groupForm.description" type="textarea" :rows="3" placeholder="分组描述" />
        </div>
      </div>
      <div class="form-actions">
        <el-button data-testid="save-group" type="primary" @click="saveGroup">保存分组</el-button>
      </div>
    </section>

    <div class="list-grid">
      <div v-for="group in groups" :key="group.id" class="item-card">
        <h3>{{ group.name }}</h3>
        <p>{{ group.description }}</p>
        <el-tag>{{ group.deviceCount }} 台设备</el-tag>
        <div class="form-actions">
          <el-button :data-testid="`filter-group-${group.id}`" size="small" @click="$emit('view-devices', group.id)">查看设备</el-button>
          <el-button :data-testid="`edit-group-${group.id}`" size="small" @click="openGroupEdit(group)">编辑</el-button>
          <el-button :data-testid="`delete-group-${group.id}`" size="small" type="danger" @click="removeGroup(group)">删除</el-button>
        </div>
      </div>
    </div>
  </section>
</template>
