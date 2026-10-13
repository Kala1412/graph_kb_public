<template>
  <div class="workspace-page">
    <el-card class="workspace-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">工作台</span>
        </div>
      </template>
      <el-empty description="该页面待建设" />
    </el-card>
  </div>
</template>

<script setup></script>

<style scoped>
.workspace-page {
  padding: 16px;
}

.workspace-card {
  min-height: 360px;
}

.card-header .title {
  font-size: 16px;
  font-weight: 600;
  color: #334155;
}
</style>
