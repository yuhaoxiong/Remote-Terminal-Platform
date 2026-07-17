<script setup lang="ts">
import { Plus, Refresh } from "@element-plus/icons-vue";
import { ElMessageBox } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import {
  createFunction,
  createFunctionRelease,
  createFunctionVariant,
  createProject,
  getApiErrorMessage,
  listFunctionReleases,
  listFunctions,
  listHardwareProfiles,
  listProjectFunctions,
  listProjects,
  markProjectFunctionPendingUninstall,
  publishFunctionRelease,
  setProjectFunction,
  updateProject,
  type FunctionRead,
  type FunctionReleaseRead,
  type HardwareProfileRead,
  type ProjectFunctionRead,
  type ProjectRead,
} from "../api/platform";
import { formatTime } from "../utils/format";
import CommonDialog from "./CommonDialog.vue";

const projects = ref<ProjectRead[]>([]);
const functions = ref<FunctionRead[]>([]);
const hardwareProfiles = ref<HardwareProfileRead[]>([]);
const releases = ref<Record<number, FunctionReleaseRead[]>>({});
const assignments = ref<Record<number, ProjectFunctionRead[]>>({});
const loading = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

const projectDialogOpen = ref(false);
const functionDialogOpen = ref(false);
const releaseDialogOpen = ref(false);
const variantDialogOpen = ref(false);
const assignmentDialogOpen = ref(false);

const projectForm = reactive({ code: "", name: "", description: "" });
const functionForm = reactive({ code: "", name: "", description: "" });
const releaseForm = reactive({ function_id: null as number | null, version: "", release_notes: "" });
const variantForm = reactive({
  function_id: null as number | null,
  release_id: null as number | null,
  hardware_profile_id: null as number | null,
  artifact_uri: "",
  artifact_sha256: "",
  artifact_size: 0,
});
const assignmentForm = reactive({
  project_id: null as number | null,
  function_id: null as number | null,
  desired_release_id: null as number | null,
  config_json: "{}",
});

const activeProjects = computed(() => projects.value.filter((item) => item.status === "active"));
const activeFunctions = computed(() => functions.value.filter((item) => item.status === "active"));
const assignmentReleases = computed(() =>
  assignmentForm.function_id === null
    ? []
    : (releases.value[assignmentForm.function_id] ?? []).filter((item) => item.status === "published"),
);

function functionName(functionId: number): string {
  const item = functions.value.find((candidate) => candidate.id === functionId);
  return item ? `${item.name} (${item.code})` : `功能 #${functionId}`;
}

function releaseName(releaseId: number): string {
  for (const items of Object.values(releases.value)) {
    const item = items.find((candidate) => candidate.id === releaseId);
    if (item) return item.version;
  }
  return `#${releaseId}`;
}

async function loadAll() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const [projectResponse, functionResponse, profileResponse] = await Promise.all([
      listProjects(),
      listFunctions(),
      listHardwareProfiles(),
    ]);
    projects.value = projectResponse.items;
    functions.value = functionResponse.items;
    hardwareProfiles.value = profileResponse.items;
    await Promise.all([
      ...functions.value.map((item) => loadReleases(item.id)),
      ...projects.value.map((item) => loadAssignments(item.id)),
    ]);
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "项目与功能数据加载失败");
  } finally {
    loading.value = false;
  }
}

async function loadReleases(functionId: number) {
  releases.value[functionId] = (await listFunctionReleases(functionId)).items;
}

async function loadAssignments(projectId: number) {
  assignments.value[projectId] = (await listProjectFunctions(projectId)).items;
}

async function submitProject() {
  if (!projectForm.code || !projectForm.name) {
    errorMessage.value = "项目代码和名称为必填项";
    return;
  }
  try {
    const created = await createProject({ ...projectForm });
    projects.value.push(created);
    assignments.value[created.id] = [];
    Object.assign(projectForm, { code: "", name: "", description: "" });
    projectDialogOpen.value = false;
    successMessage.value = "项目已创建";
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "创建项目失败");
  }
}

async function toggleProject(project: ProjectRead) {
  const nextStatus = project.status === "active" ? "archived" : "active";
  try {
    await ElMessageBox.confirm(
      `确认${nextStatus === "archived" ? "归档" : "恢复"}项目 ${project.name}？`,
      "项目状态确认",
      { type: "warning" },
    );
  } catch {
    return;
  }
  const updated = await updateProject(project.id, { status: nextStatus });
  projects.value = projects.value.map((item) => (item.id === updated.id ? updated : item));
}

async function submitFunction() {
  if (!functionForm.code || !functionForm.name) {
    errorMessage.value = "功能代码和名称为必填项";
    return;
  }
  try {
    const created = await createFunction({ ...functionForm });
    functions.value.push(created);
    releases.value[created.id] = [];
    Object.assign(functionForm, { code: "", name: "", description: "" });
    functionDialogOpen.value = false;
    successMessage.value = "功能已创建";
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "创建功能失败");
  }
}

async function submitRelease() {
  if (releaseForm.function_id === null || !releaseForm.version) {
    errorMessage.value = "请选择功能并填写版本";
    return;
  }
  try {
    await createFunctionRelease(releaseForm.function_id, {
      version: releaseForm.version,
      release_notes: releaseForm.release_notes || undefined,
      manifest_json: { schema_version: 1 },
    });
    await loadReleases(releaseForm.function_id);
    Object.assign(releaseForm, { function_id: null, version: "", release_notes: "" });
    releaseDialogOpen.value = false;
    successMessage.value = "草稿版本已创建";
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "创建版本失败");
  }
}

async function submitVariant() {
  if (
    variantForm.function_id === null ||
    variantForm.release_id === null ||
    variantForm.hardware_profile_id === null ||
    !variantForm.artifact_uri ||
    !/^[0-9a-f]{64}$/.test(variantForm.artifact_sha256) ||
    variantForm.artifact_size <= 0
  ) {
    errorMessage.value = "请完整填写变体信息，SHA-256 必须为 64 位小写十六进制";
    return;
  }
  try {
    await createFunctionVariant(variantForm.function_id, variantForm.release_id, {
      hardware_profile_id: variantForm.hardware_profile_id,
      artifact_uri: variantForm.artifact_uri,
      artifact_sha256: variantForm.artifact_sha256,
      artifact_size: variantForm.artifact_size,
    });
    variantDialogOpen.value = false;
    successMessage.value = "硬件变体已登记";
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "登记变体失败");
  }
}

async function publishRelease(item: FunctionReleaseRead) {
  try {
    await ElMessageBox.confirm(`发布后版本 ${item.version} 将不可修改，确认发布？`, "发布版本", {
      type: "warning",
    });
  } catch {
    return;
  }
  try {
    await publishFunctionRelease(item.function_id, item.id);
    await loadReleases(item.function_id);
    successMessage.value = "版本已发布并冻结";
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "发布失败，请先登记至少一个硬件变体");
  }
}

async function prepareAssignment(projectId: number) {
  Object.assign(assignmentForm, {
    project_id: projectId,
    function_id: null,
    desired_release_id: null,
    config_json: "{}",
  });
  assignmentDialogOpen.value = true;
}

async function selectAssignmentFunction(functionId: number | null) {
  assignmentForm.function_id = functionId;
  assignmentForm.desired_release_id = null;
  if (functionId !== null && releases.value[functionId] === undefined) await loadReleases(functionId);
}

async function submitAssignment() {
  if (
    assignmentForm.project_id === null ||
    assignmentForm.function_id === null ||
    assignmentForm.desired_release_id === null
  ) {
    errorMessage.value = "请选择功能和已发布版本";
    return;
  }
  let config: Record<string, unknown>;
  try {
    config = JSON.parse(assignmentForm.config_json) as Record<string, unknown>;
  } catch {
    errorMessage.value = "项目默认配置必须是合法 JSON";
    return;
  }
  try {
    await setProjectFunction(assignmentForm.project_id, assignmentForm.function_id, {
      desired_release_id: assignmentForm.desired_release_id,
      config_json: config,
    });
    await loadAssignments(assignmentForm.project_id);
    assignmentDialogOpen.value = false;
    successMessage.value = "项目功能已保存";
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, "项目功能保存失败");
  }
}

async function pendingUninstall(item: ProjectFunctionRead) {
  try {
    await ElMessageBox.confirm("此操作只标记待卸载，不会立即修改设备，确认继续？", "待卸载确认", {
      type: "warning",
    });
  } catch {
    return;
  }
  await markProjectFunctionPendingUninstall(item.project_id, item.function_id);
  await loadAssignments(item.project_id);
}

onMounted(() => void loadAll());
</script>

<template>
  <section class="page-section">
    <div class="page-title-row">
      <div>
        <h3>项目与功能</h3>
        <p class="muted">正式项目、不可变功能版本及硬件变体；部署计划将在后续阶段接入。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
    </div>

    <el-alert v-if="errorMessage" class="validation-alert" type="error" :title="errorMessage" show-icon closable @close="errorMessage = ''" />
    <el-alert v-if="successMessage" class="validation-alert" type="success" :title="successMessage" show-icon closable @close="successMessage = ''" />

    <el-tabs>
      <el-tab-pane label="项目">
        <div class="toolbar"><h4>业务项目</h4><el-button data-testid="open-project-create" type="primary" :icon="Plus" @click="projectDialogOpen = true">新建项目</el-button></div>
        <section class="panel">
          <el-table :data="projects" row-key="id" empty-text="暂无项目">
            <el-table-column prop="code" label="代码" min-width="150" />
            <el-table-column prop="name" label="名称" min-width="180" />
            <el-table-column prop="description" label="说明" min-width="220" />
            <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ row.status === "active" ? "启用" : "归档" }}</el-tag></template></el-table-column>
            <el-table-column label="功能" min-width="260"><template #default="{ row }"><span v-if="!(assignments[row.id] ?? []).length" class="muted">尚未分配</span><el-tag v-for="item in assignments[row.id] ?? []" :key="item.id" class="tag-chip" :type="item.status === 'active' ? 'success' : 'warning'">{{ functionName(item.function_id) }} · {{ releaseName(item.desired_release_id) }}</el-tag></template></el-table-column>
            <el-table-column label="操作" width="260"><template #default="{ row }"><el-button size="small" :disabled="row.status !== 'active'" @click="prepareAssignment(row.id)">配置功能</el-button><el-button size="small" @click="toggleProject(row)">{{ row.status === "active" ? "归档" : "恢复" }}</el-button></template></el-table-column>
          </el-table>
        </section>
        <section v-for="project in activeProjects" :key="`assignment-${project.id}`" class="panel compact-panel">
          <div class="panel-header"><h4>{{ project.name }} · 已配置功能</h4></div>
          <el-table :data="assignments[project.id] ?? []" size="small" row-key="id" empty-text="暂无功能">
            <el-table-column label="功能"><template #default="{ row }">{{ functionName(row.function_id) }}</template></el-table-column>
            <el-table-column label="版本"><template #default="{ row }">{{ releaseName(row.desired_release_id) }}</template></el-table-column>
            <el-table-column prop="status" label="状态" width="150" />
            <el-table-column label="操作" width="130"><template #default="{ row }"><el-button size="small" type="danger" text :disabled="row.status === 'pending_uninstall'" @click="pendingUninstall(row)">标记待卸载</el-button></template></el-table-column>
          </el-table>
        </section>
      </el-tab-pane>

      <el-tab-pane label="功能与版本">
        <div class="toolbar"><h4>可复用功能</h4><div><el-button :icon="Plus" @click="functionDialogOpen = true">新建功能</el-button><el-button type="primary" :icon="Plus" @click="releaseDialogOpen = true">新建版本</el-button><el-button :icon="Plus" @click="variantDialogOpen = true">登记变体</el-button></div></div>
        <section v-for="item in functions" :key="item.id" class="panel compact-panel">
          <div class="panel-header"><div><h4>{{ item.name }}</h4><p class="muted">{{ item.code }} · {{ item.description || "暂无说明" }}</p></div><el-tag :type="item.status === 'active' ? 'success' : 'info'">{{ item.status }}</el-tag></div>
          <el-table :data="releases[item.id] ?? []" size="small" row-key="id" empty-text="暂无版本">
            <el-table-column prop="version" label="版本" width="150" />
            <el-table-column prop="status" label="状态" width="120" />
            <el-table-column prop="release_notes" label="说明" min-width="220" />
            <el-table-column label="发布时间" width="180"><template #default="{ row }">{{ formatTime(row.published_at, "未发布") }}</template></el-table-column>
            <el-table-column label="操作" width="120"><template #default="{ row }"><el-button v-if="row.status === 'draft'" size="small" type="primary" @click="publishRelease(row)">发布</el-button><el-tag v-else type="success">已冻结</el-tag></template></el-table-column>
          </el-table>
        </section>
      </el-tab-pane>
    </el-tabs>

    <CommonDialog v-model:visible="projectDialogOpen" title="新建正式项目" width="620px" @confirm="submitProject"><div class="form-grid"><el-input data-testid="project-code" v-model="projectForm.code" placeholder="项目代码，例如 site-a" /><el-input data-testid="project-name" v-model="projectForm.name" placeholder="项目名称" /><el-input v-model="projectForm.description" type="textarea" placeholder="项目说明" /></div><template #footer><el-button @click="projectDialogOpen = false">取消</el-button><el-button data-testid="project-create" type="primary" @click="submitProject">创建项目</el-button></template></CommonDialog>
    <CommonDialog v-model:visible="functionDialogOpen" title="新建功能" width="620px" @confirm="submitFunction"><div class="form-grid"><el-input v-model="functionForm.code" placeholder="功能代码，例如 outside-rubbish-bag" /><el-input v-model="functionForm.name" placeholder="功能名称" /><el-input v-model="functionForm.description" type="textarea" placeholder="功能说明" /></div></CommonDialog>
    <CommonDialog v-model:visible="releaseDialogOpen" title="新建版本草稿" width="620px" @confirm="submitRelease"><div class="form-grid"><el-select v-model="releaseForm.function_id" placeholder="选择功能"><el-option v-for="item in activeFunctions" :key="item.id" :label="`${item.name} (${item.code})`" :value="item.id" /></el-select><el-input v-model="releaseForm.version" placeholder="版本，例如 0.1.0" /><el-input v-model="releaseForm.release_notes" type="textarea" placeholder="版本说明" /></div></CommonDialog>
    <CommonDialog v-model:visible="variantDialogOpen" title="登记硬件变体" width="720px" @confirm="submitVariant"><div class="form-grid"><el-select v-model="variantForm.function_id" placeholder="选择功能" @change="variantForm.release_id = null"><el-option v-for="item in activeFunctions" :key="item.id" :label="item.name" :value="item.id" /></el-select><el-select v-model="variantForm.release_id" placeholder="选择草稿版本"><el-option v-for="item in (variantForm.function_id === null ? [] : releases[variantForm.function_id] ?? []).filter((release) => release.status === 'draft')" :key="item.id" :label="item.version" :value="item.id" /></el-select><el-select v-model="variantForm.hardware_profile_id" placeholder="硬件规格"><el-option v-for="profile in hardwareProfiles" :key="profile.id" :label="profile.name" :value="profile.id" /></el-select><el-input v-model="variantForm.artifact_uri" placeholder="制品 URI（阶段 1 人工登记）" /><el-input v-model="variantForm.artifact_sha256" placeholder="SHA-256" /><el-input-number v-model="variantForm.artifact_size" :min="1" placeholder="制品字节数" style="width: 100%" /></div></CommonDialog>
    <CommonDialog v-model:visible="assignmentDialogOpen" title="配置项目功能" width="700px" @confirm="submitAssignment"><div class="form-grid"><el-select :model-value="assignmentForm.function_id" placeholder="选择功能" @change="selectAssignmentFunction"><el-option v-for="item in activeFunctions" :key="item.id" :label="`${item.name} (${item.code})`" :value="item.id" /></el-select><el-select v-model="assignmentForm.desired_release_id" placeholder="选择已发布版本"><el-option v-for="item in assignmentReleases" :key="item.id" :label="item.version" :value="item.id" /></el-select><el-input v-model="assignmentForm.config_json" type="textarea" :rows="6" placeholder="项目默认配置 JSON" /></div></CommonDialog>
  </section>
</template>

<style scoped>
.compact-panel { margin-top: 16px; }
.tag-chip { margin: 2px 6px 2px 0; }
</style>
