<template>
  <div class="about-page">
    <el-card class="about-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">关于</span>
        </div>
      </template>
      <el-empty description="该页面待建设" />
    </el-card>
  </div>
</template>

<script setup></script>

<style scoped>
.about-page {
  padding: 16px;
}

.about-card {
  min-height: 360px;
}

.card-header .title {
  font-size: 16px;
  font-weight: 600;
  color: #334155;
}
</style>
