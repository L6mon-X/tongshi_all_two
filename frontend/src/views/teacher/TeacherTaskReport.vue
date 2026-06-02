<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getAnnouncements, getCompletionReport, type Announcement, type CompletionReport } from '@/api/announcement'

const route = useRoute()
const announcements = ref<Announcement[]>([])
const loading = ref(true)

const selectedAnnouncementId = ref<number | null>(null)
const reportData = ref<CompletionReport | null>(null)
const reportLoading = ref(false)

async function loadReport(id: number) {
  reportLoading.value = true
  try {
    reportData.value = await getCompletionReport(id)
  } catch {
    ElMessage.error('任务完成情况加载失败，请稍后重试')
  } finally {
    reportLoading.value = false
  }
}

function handleAnnouncementChange(val: number | null) {
  if (val) loadReport(val)
  else reportData.value = null
}

onMounted(async () => {
  try {
    announcements.value = await getAnnouncements()
    // 支持从 URL query 直接定位到某个任务
    const taskId = Number(route.query.task_id)
    if (Number.isFinite(taskId) && taskId > 0) {
      selectedAnnouncementId.value = taskId
      await loadReport(taskId)
    }
  } catch {
    ElMessage.error('任务数据加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="task-report-page">
    <div class="page-header">
      <h1>任务完成</h1>
    </div>

    <div class="filter-bar">
      <el-select
        v-model="selectedAnnouncementId"
        placeholder="选择任务查看完成情况"
        size="default"
        style="width: 320px"
        clearable
        @change="handleAnnouncementChange"
      >
        <el-option
          v-for="a in announcements.filter(a => a.type === 'quiz')"
          :key="a.id"
          :label="a.title"
          :value="a.id"
        />
      </el-select>
    </div>

    <div v-if="loading" class="loading-state">加载中...</div>

    <div v-else-if="announcements.filter(a => a.type === 'quiz').length === 0" class="empty-state">
      暂无可查看的题目任务。
    </div>

    <template v-else>
      <div v-if="reportLoading" class="loading-state">加载中...</div>

      <div v-else-if="reportData" class="report-content">
        <div class="report-header">
          <h3>{{ reportData.announcement_title }}</h3>
          <el-tag v-if="reportData.is_expired" type="warning" size="small">已过截止时间</el-tag>
        </div>
        <div class="report-stats">
          <div class="report-stat">
            <span class="stat-num">{{ reportData.completed_count }}</span>
            <span class="stat-label">已完成</span>
          </div>
          <div class="report-stat">
            <span class="stat-num warn">{{ reportData.total_students - reportData.completed_count }}</span>
            <span class="stat-label">未完成</span>
          </div>
          <div class="report-stat">
            <span class="stat-num">{{ reportData.total_students }}</span>
            <span class="stat-label">总人数</span>
          </div>
        </div>
        <el-progress
          :percentage="reportData.total_students > 0 ? Math.round(reportData.completed_count / reportData.total_students * 100) : 0"
          :stroke-width="10"
          color="var(--color-primary)"
          style="margin-bottom: var(--space-lg)"
        />
        <div v-if="reportData.incomplete_students.length > 0">
          <h4 class="section-title">未完成学生名单</h4>
          <el-table :data="reportData.incomplete_students" stripe style="width: 100%">
            <el-table-column prop="id" label="学号" width="120" />
            <el-table-column prop="name" label="姓名" width="120" />
            <el-table-column prop="class_name" label="班级" min-width="140" />
          </el-table>
        </div>
        <div v-if="reportData.per_class?.length" class="per-class">
          <h4 class="section-title">分班小计</h4>
          <el-table :data="reportData.per_class" stripe style="width: 100%">
            <el-table-column prop="class_name" label="班级" min-width="140" />
            <el-table-column prop="total" label="总人数" width="100" />
            <el-table-column prop="completed" label="已完成" width="100" />
          </el-table>
        </div>
        <div v-if="reportData.incomplete_students.length === 0" class="all-done">所有学生已完成</div>
      </div>

      <div v-else class="empty-state">
        请选择一个任务查看完成情况
      </div>
    </template>
  </div>
</template>

<style scoped>
.task-report-page {
  /* 沿用教师端页面间距 */
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-xl);
}

.page-header h1 {
  font-size: 1.5rem;
  font-weight: 800;
  color: var(--color-text);
  font-family: var(--font-serif);
  letter-spacing: 0.05em;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  margin-bottom: var(--space-lg);
}

.loading-state {
  text-align: center;
  padding: var(--space-3xl) 0;
  color: var(--color-text-muted);
}

.empty-state {
  text-align: center;
  padding: var(--space-3xl) 0;
  color: var(--color-text-muted);
  font-size: 0.9rem;
}

.report-content {
  max-width: 600px;
}

.report-header {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  margin-bottom: var(--space-lg);
}

.report-header h3 {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--color-text);
}

.report-stats {
  display: flex;
  gap: var(--space-xl);
  margin-bottom: var(--space-lg);
}

.report-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-num {
  font-size: 2rem;
  font-weight: 800;
  color: var(--color-primary);
}

.stat-num.warn {
  color: #ef4444;
}

.stat-label {
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.section-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--space-md);
}

.all-done {
  text-align: center;
  padding: var(--space-xl);
  color: #10b981;
  font-weight: 600;
  font-size: 1rem;
}

.per-class {
  margin-top: var(--space-lg);
}
</style>
