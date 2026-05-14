<template>
  <section>
    <h1>仪表盘</h1>
    <div class="dashboard-grid">
      <el-card class="metric-card" shadow="never">
        <template #header>设备</template>
        <strong>0</strong>
      </el-card>
      <el-card class="metric-card" shadow="never">
        <template #header>在线</template>
        <strong>0</strong>
      </el-card>
      <el-card class="metric-card" shadow="never">
        <template #header>远程会话</template>
        <strong>0</strong>
      </el-card>
    </div>
  </section>
</template>
