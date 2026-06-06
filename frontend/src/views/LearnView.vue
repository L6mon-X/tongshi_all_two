<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getCourses, type Course } from '@/api/course'

const router = useRouter()
const courses = ref<Course[]>([])
const loading = ref(true)
const keyword = ref('')

async function loadCourses() {
  loading.value = true
  try {
    courses.value = await getCourses()
  } finally {
    loading.value = false
  }
}

onMounted(loadCourses)

const filteredCourses = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return courses.value
  return courses.value.filter(c => c.name.toLowerCase().includes(q))
})
</script>

<template>
  <div class="learn-page">
    <section class="page-hero">
      <div class="container">
        <div class="hero-inner">
          <div class="hero-icon">学</div>
          <h1>学 · 积累知识</h1>
          <p>浏览课程资料、课件和题库，按自己的节奏学习。</p>
        </div>
      </div>
    </section>

    <section class="courses-section">
      <div class="container">
        <div class="search-bar">
          <input
            v-model="keyword"
            type="text"
            placeholder="搜索课程名称"
            @keyup.enter="loadCourses"
          />
          <button @click="loadCourses">搜索</button>
        </div>
        <div v-if="loading" class="empty-state">课程加载中...</div>
        <div v-else-if="filteredCourses.length > 0" class="course-grid">
          <div
            v-for="course in filteredCourses"
            :key="course.id"
            class="course-card"
          >
            <h3>{{ course.name }}</h3>
            <p>{{ course.material_count }} 份学习资料 · {{ course.question_count }} 道练习题</p>
            <div class="card-links">
              <button class="card-link materials" @click="router.push(`/learn/course/${course.id}`)">
                资料
              </button>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          {{ keyword ? '未找到匹配的课程' : '暂无课程内容。' }}
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.learn-page {
  padding-top: 60px;
}

.page-hero {
  padding: var(--space-3xl) 0 var(--space-2xl);
  background: var(--color-learn-bg);
  border-bottom: 1px solid var(--color-border-light);
}

.hero-inner {
  text-align: center;
}

.hero-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  background: var(--color-learn);
  border-radius: var(--radius-md);
  color: white;
  font-family: var(--font-serif);
  font-size: 1.3rem;
  font-weight: 900;
  margin-bottom: var(--space-lg);
  box-shadow: 0 4px 14px rgba(45, 106, 122, 0.2);
}

.hero-inner h1 {
  font-family: var(--font-serif);
  font-size: 1.8rem;
  font-weight: 900;
  color: var(--color-text);
  margin-bottom: var(--space-sm);
  letter-spacing: 0.05em;
}

.hero-inner p {
  font-size: 0.92rem;
  color: var(--color-text-secondary);
}

.courses-section {
  padding: var(--space-2xl) 0 var(--space-3xl);
}

.search-bar {
  display: flex;
  gap: 8px;
  margin-bottom: var(--space-xl);
}

.search-bar input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 0.9rem;
}

.search-bar button {
  padding: 10px 20px;
  background: var(--color-learn);
  color: white;
  border-radius: var(--radius-md);
  font-weight: 700;
  font-size: 0.85rem;
}

.course-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-lg);
}

.course-card {
  text-align: left;
  display: flex;
  flex-direction: column;
  padding: var(--space-xl);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  transition: all var(--duration-normal) var(--ease-out);
  position: relative;
  overflow: hidden;
}

.course-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 3px;
  height: 100%;
  background: var(--color-learn);
  opacity: 0;
  transition: opacity var(--duration-normal);
}

.course-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-lg);
  border-color: rgba(45, 106, 122, 0.2);
}

.course-card:hover::before {
  opacity: 1;
}

.course-card h3 {
  font-family: var(--font-serif);
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: var(--space-sm);
  letter-spacing: 0.03em;
}

.course-card p {
  color: var(--color-text-secondary);
  font-size: 0.88rem;
  margin-bottom: var(--space-lg);
}

.card-links {
  display: flex;
  gap: var(--space-sm);
}

.card-link {
  padding: 6px 18px;
  font-size: 0.85rem;
  font-weight: 600;
  border-radius: var(--radius-full);
  transition: all var(--duration-fast);
}

.card-link.materials {
  color: white;
  background: var(--color-learn);
}

.card-link.materials:hover {
  opacity: 0.9;
}

.empty-state {
  text-align: center;
  padding: var(--space-4xl) 0;
  color: var(--color-text-muted);
  font-size: 0.9rem;
}

@media (max-width: 768px) {
  .course-grid {
    grid-template-columns: 1fr;
  }
}
</style>
