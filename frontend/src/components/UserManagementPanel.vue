<script setup lang="ts">
import { Refresh } from "@element-plus/icons-vue";
import { ElMessageBox } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import {
  createUser,
  listUsers,
  resetUserPassword,
  toggleUser,
  updateUser,
  type UserRead,
  type UserRole,
} from "../api/platform";

const users = ref<UserRead[]>([]);
const loading = ref(false);
const actionUserId = ref<number | null>(null);
const formOpen = ref(false);
const errorMessage = ref("");
const lastMessage = ref("");
const resetUserId = ref<number | null>(null);
const resetPasswordValue = ref("");

const createForm = reactive({
  username: "",
  password: "",
  role: "operator" as UserRole,
  is_active: true,
});

const sortedUsers = computed(() =>
  [...users.value].sort((left, right) => {
    if (left.role !== right.role) {
      return left.role === "admin" ? -1 : 1;
    }
    return left.username.localeCompare(right.username);
  }),
);

function formatTime(value: string | null): string {
  return value ? value.replace("T", " ").slice(0, 16) : "暂无";
}

function resetCreateForm() {
  createForm.username = "";
  createForm.password = "";
  createForm.role = "operator";
  createForm.is_active = true;
}

async function loadUserData() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await listUsers();
    users.value = response.items;
  } catch {
    errorMessage.value = "用户列表加载失败，请检查权限和后端服务。";
  } finally {
    loading.value = false;
  }
}

async function submitCreateUser() {
  errorMessage.value = "";
  lastMessage.value = "";
  const username = createForm.username.trim();
  if (!username) {
    errorMessage.value = "请输入用户名";
    return;
  }
  if (createForm.password.length < 8) {
    errorMessage.value = "初始密码至少 8 位";
    return;
  }

  loading.value = true;
  try {
    const created = await createUser({
      username,
      password: createForm.password,
      role: createForm.role,
      is_active: createForm.is_active,
    });
    users.value = [created, ...users.value];
    resetCreateForm();
    formOpen.value = false;
    lastMessage.value = "用户已创建";
  } catch {
    errorMessage.value = "创建用户失败，用户名可能已存在。";
  } finally {
    loading.value = false;
  }
}

async function saveUser(row: UserRead) {
  try {
    await ElMessageBox.confirm(`确认保存用户 ${row.username} 的角色和启用状态？`, "保存用户变更", { type: "warning" });
  } catch {
    return;
  }
  actionUserId.value = row.id;
  errorMessage.value = "";
  lastMessage.value = "";
  try {
    const updated = await updateUser(row.id, {
      role: row.role as UserRole,
      is_active: row.is_active,
    });
    users.value = users.value.map((user) => (user.id === updated.id ? updated : user));
    lastMessage.value = "用户已更新";
  } catch {
    errorMessage.value = "保存用户失败，请确认至少保留一个启用的管理员。";
    await loadUserData();
  } finally {
    actionUserId.value = null;
  }
}

async function switchUser(row: UserRead) {
  try {
    await ElMessageBox.confirm(`确认${row.is_active ? "停用" : "启用"}用户 ${row.username}？`, `${row.is_active ? "停用" : "启用"}用户`, {
      type: "warning",
    });
  } catch {
    return;
  }
  actionUserId.value = row.id;
  errorMessage.value = "";
  lastMessage.value = "";
  try {
    const updated = await toggleUser(row.id, !row.is_active);
    users.value = users.value.map((user) => (user.id === updated.id ? updated : user));
    lastMessage.value = updated.is_active ? "用户已启用" : "用户已停用";
  } catch {
    errorMessage.value = "切换用户状态失败，请确认至少保留一个启用的管理员。";
  } finally {
    actionUserId.value = null;
  }
}

function openResetPassword(row: UserRead) {
  resetUserId.value = row.id;
  resetPasswordValue.value = "";
}

async function submitResetPassword() {
  if (resetUserId.value === null) {
    return;
  }
  errorMessage.value = "";
  lastMessage.value = "";
  if (resetPasswordValue.value.length < 8) {
    errorMessage.value = "新密码至少 8 位";
    return;
  }

  const user = users.value.find((item) => item.id === resetUserId.value);
  try {
    await ElMessageBox.confirm(`确认重置用户 ${user?.username ?? resetUserId.value} 的密码？`, "重置密码", { type: "warning" });
  } catch {
    return;
  }

  actionUserId.value = resetUserId.value;
  try {
    const updated = await resetUserPassword(resetUserId.value, { new_password: resetPasswordValue.value });
    users.value = users.value.map((user) => (user.id === updated.id ? updated : user));
    resetUserId.value = null;
    resetPasswordValue.value = "";
    lastMessage.value = "密码已重置";
  } catch {
    errorMessage.value = "重置密码失败";
  } finally {
    actionUserId.value = null;
  }
}

onMounted(() => {
  void loadUserData();
});
</script>

<template>
  <section class="page-section">
    <div class="toolbar">
      <h3>用户管理</h3>
      <div class="topbar-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadUserData">刷新</el-button>
        <el-button data-testid="open-user-create" type="primary" @click="formOpen = true">新建用户</el-button>
      </div>
    </div>

    <el-alert v-if="errorMessage" class="validation-alert" type="error" :title="errorMessage" show-icon :closable="false" />
    <el-alert v-if="lastMessage" class="validation-alert" type="success" :title="lastMessage" show-icon :closable="false" />

    <section v-if="formOpen" class="form-panel" aria-label="创建用户">
      <div class="panel-header">
        <h3>创建用户</h3>
        <el-button text @click="formOpen = false">关闭</el-button>
      </div>
      <div class="form-grid">
        <div data-testid="user-username" class="input-wrap">
          <el-input v-model="createForm.username" placeholder="用户名" />
        </div>
        <div data-testid="user-password" class="input-wrap">
          <el-input v-model="createForm.password" type="password" show-password placeholder="初始密码，至少 8 位" />
        </div>
        <label class="field-label">
          <span>角色</span>
          <select data-testid="user-role" v-model="createForm.role" class="native-select">
            <option value="operator">运维人员</option>
            <option value="admin">管理员</option>
          </select>
        </label>
        <label class="field-label inline-field">
          <span>启用账号</span>
          <el-switch v-model="createForm.is_active" />
        </label>
      </div>
      <div class="form-actions">
        <el-button text @click="formOpen = false">取消</el-button>
        <el-button data-testid="user-create" type="primary" :loading="loading" @click="submitCreateUser">创建用户</el-button>
      </div>
    </section>

    <section v-if="resetUserId !== null" class="form-panel" aria-label="重置用户密码">
      <div class="panel-header">
        <h3>重置用户密码</h3>
        <el-button text @click="resetUserId = null">关闭</el-button>
      </div>
      <div class="form-grid">
        <div data-testid="user-reset-password" class="input-wrap">
          <el-input v-model="resetPasswordValue" type="password" show-password placeholder="新密码，至少 8 位" />
        </div>
      </div>
      <div class="form-actions">
        <el-button text @click="resetUserId = null">取消</el-button>
        <el-button data-testid="user-reset-submit" type="primary" :loading="actionUserId === resetUserId" @click="submitResetPassword">
          保存新密码
        </el-button>
      </div>
    </section>

    <section class="panel">
      <el-table :data="sortedUsers" row-key="id" empty-text="暂无用户">
        <el-table-column prop="username" label="用户" min-width="140" />
        <el-table-column label="角色" width="160">
          <template #default="{ row }">
            <select :data-testid="`user-role-${row.id}`" v-model="row.role" class="native-select table-select">
              <option value="operator">运维人员</option>
              <option value="admin">管理员</option>
            </select>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? "启用" : "停用" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近登录" min-width="150">
          <template #default="{ row }">
            <span>{{ formatTime(row.last_login_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="登录 IP" min-width="120">
          <template #default="{ row }">
            <span>{{ row.last_login_ip || "暂无" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="密码更新时间" min-width="150">
          <template #default="{ row }">
            <span>{{ formatTime(row.password_changed_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300">
          <template #default="{ row }">
            <el-button :data-testid="`save-user-${row.id}`" size="small" type="primary" :loading="actionUserId === row.id" @click="saveUser(row)">
              保存
            </el-button>
            <el-button :data-testid="`toggle-user-${row.id}`" size="small" :loading="actionUserId === row.id" @click="switchUser(row)">
              {{ row.is_active ? "停用" : "启用" }}
            </el-button>
            <el-button :data-testid="`reset-user-${row.id}`" size="small" @click="openResetPassword(row)">重置密码</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </section>
</template>

<style scoped>
.inline-field {
  align-items: center;
  display: flex;
  flex-direction: row;
  gap: 12px;
}

.table-select {
  min-width: 104px;
}
</style>
