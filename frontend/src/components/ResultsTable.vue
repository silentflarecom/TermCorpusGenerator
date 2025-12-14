<script setup>
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import VisualGraph from './VisualGraph.vue'

const props = defineProps({
  taskId: {
    type: Number,
    required: true
  }
})

const emit = defineEmits(['close', 'retry'])

const terms = ref([])
const loading = ref(true)
const filterStatus = ref('all')
const expandedTerm = ref(null)
const activeTab = ref('table')

// Quality state
const qualityData = ref(null)
const loadingQuality = ref(false)
const showCleanOptions = ref(false)
const cleaning = ref(false)
const cleanResult = ref(null)
const cleanOptions = ref({
  removeFailed: true,
  removeMissingChinese: false,
  removeShortSummaries: false,
  minSummaryLength: 50
})

// Export state
const showExportDialog = ref(false)

const filteredTerms = computed(() => {
  if (filterStatus.value === 'all') return terms.value
  return terms.value.filter(t => t.status === filterStatus.value)
})

const completedCount = computed(() => terms.value.filter(t => t.status === 'completed').length)
const failedCount = computed(() => terms.value.filter(t => t.status === 'failed').length)
const pendingCount = computed(() => terms.value.filter(t => t.status === 'pending').length)

const fetchTerms = async () => {
  try {
    const response = await axios.get(`http://localhost:8000/api/batch/${props.taskId}/terms`)
    terms.value = response.data
  } catch (error) {
    console.error('Error fetching terms:', error)
  } finally {
    loading.value = false
  }
}

const fetchQuality = async () => {
  loadingQuality.value = true
  try {
    const response = await axios.get(`http://localhost:8000/api/quality/analyze?task_id=${props.taskId}`)
    qualityData.value = response.data
  } catch (error) {
    console.error('Error fetching quality:', error)
  } finally {
    loadingQuality.value = false
  }
}

const cleanData = async () => {
  if (!cleanOptions.value.removeFailed && 
      !cleanOptions.value.removeMissingChinese && 
      !cleanOptions.value.removeShortSummaries) {
    return
  }
  
  cleaning.value = true
  try {
    const response = await axios.post('http://localhost:8000/api/quality/clean', {
      task_id: props.taskId,
      remove_failed: cleanOptions.value.removeFailed,
      remove_missing_chinese: cleanOptions.value.removeMissingChinese,
      remove_short_summaries: cleanOptions.value.removeShortSummaries,
      min_summary_length: cleanOptions.value.minSummaryLength
    })
    
    cleanResult.value = response.data
    showCleanOptions.value = false
    
    // Reload data
    await fetchTerms()
    await fetchQuality()
  } catch (error) {
    console.error('Error cleaning:', error)
  } finally {
    cleaning.value = false
  }
}

const exportResults = async (format) => {
  try {
    const url = `http://localhost:8000/api/batch/${props.taskId}/export?format=${format}`
    window.open(url, '_blank')
  } catch (error) {
    console.error('Error exporting results:', error)
  }
}

const retryFailed = async () => {
  emit('retry', props.taskId)
}

const toggleExpand = (termId) => {
  expandedTerm.value = expandedTerm.value === termId ? null : termId
}

const getStatusColor = (status) => {
  switch (status) {
    case 'completed': return 'text-green-600 bg-green-50'
    case 'failed': return 'text-red-600 bg-red-50'
    case 'pending': return 'text-yellow-600 bg-yellow-50'
    case 'crawling': return 'text-blue-600 bg-blue-50'
    default: return 'text-gray-600 bg-gray-50'
  }
}

const getScoreColor = (score) => {
  if (score >= 80) return 'text-green-600'
  if (score >= 60) return 'text-yellow-600'
  return 'text-red-600'
}

const getScoreBg = (score) => {
  if (score >= 80) return 'bg-green-100 border-green-300'
  if (score >= 60) return 'bg-yellow-100 border-yellow-300'
  return 'bg-red-100 border-red-300'
}

const isExportReady = computed(() => {
  return qualityData.value && 
         qualityData.value.completed_terms > 0 && 
         pendingCount.value === 0
})

onMounted(async () => {
  await fetchTerms()
  await fetchQuality()
})
</script>

<template>
  <div class="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
    <!-- Header -->
    <div class="bg-gradient-to-r from-purple-500 to-purple-600 px-6 py-4 flex justify-between items-center">
      <div>
        <h2 class="text-xl font-bold text-white">📦 Task #{{ taskId }} Results</h2>
        <p class="text-purple-100 text-sm mt-1">Quality check → Clean → Export</p>
      </div>
      <button
        @click="emit('close')"
        class="text-white hover:text-gray-200 transition text-2xl"
      >
        ×
      </button>
    </div>
    
    <div class="p-6">
      <div v-if="loading">
        <div class="text-center py-8">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto"></div>
          <p class="text-gray-500 mt-4">Loading results...</p>
        </div>
      </div>
      
      <div v-else>
        <!-- Step 1: Quality Check Panel -->
        <div class="mb-6 p-4 border-2 rounded-xl" :class="qualityData ? getScoreBg(qualityData.quality_score) : 'border-gray-200 bg-gray-50'">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-4">
              <div v-if="loadingQuality" class="animate-spin w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full"></div>
              <div v-else-if="qualityData" class="w-16 h-16 rounded-full flex flex-col items-center justify-center bg-white border-2" :class="getScoreBg(qualityData.quality_score)">
                <span :class="['text-xl font-bold', getScoreColor(qualityData.quality_score)]">
                  {{ qualityData.quality_score }}
                </span>
                <span class="text-xs text-gray-500">分</span>
              </div>
              <div>
                <h3 class="font-bold text-gray-800">Step 1: 质量检测</h3>
                <div v-if="qualityData" class="text-sm text-gray-600 mt-1">
                  <span class="text-green-600">✓ {{ qualityData.complete_bilingual }}</span> 完整 |
                  <span class="text-orange-600">⚠ {{ qualityData.missing_chinese }}</span> 缺中文 |
                  <span class="text-red-600">✗ {{ qualityData.failed_terms }}</span> 失败
                </div>
                <p v-else class="text-sm text-gray-500">加载中...</p>
              </div>
            </div>
            
            <div class="flex gap-2">
              <button
                @click="fetchQuality"
                class="px-3 py-1.5 bg-white border border-gray-300 rounded-lg text-sm hover:bg-gray-50 transition"
              >
                🔄 刷新
              </button>
              <button
                v-if="qualityData && (qualityData.failed_terms > 0 || qualityData.missing_chinese > 0)"
                @click="showCleanOptions = true"
                class="px-3 py-1.5 bg-red-500 text-white rounded-lg text-sm hover:bg-red-600 transition"
              >
                🧹 清洗数据
              </button>
            </div>
          </div>
          
          <!-- Clean Result -->
          <div v-if="cleanResult" class="mt-3 p-3 bg-white rounded-lg border border-green-300">
            <p class="text-green-700 text-sm">✅ 已清理 {{ cleanResult.total_removed }} 条数据</p>
          </div>
        </div>
        
        <!-- Step 2: Export Panel -->
        <div class="mb-6 p-4 rounded-xl border-2" :class="isExportReady ? 'border-blue-300 bg-blue-50' : 'border-gray-200 bg-gray-100'">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="font-bold" :class="isExportReady ? 'text-gray-800' : 'text-gray-400'">Step 2: 导出数据</h3>
              <p v-if="!isExportReady && pendingCount > 0" class="text-sm text-gray-500 mt-1">
                ⏳ 还有 {{ pendingCount }} 个术语待处理
              </p>
              <p v-else-if="!isExportReady && completedCount === 0" class="text-sm text-gray-500 mt-1">
                暂无可导出数据
              </p>
              <p v-else class="text-sm text-gray-600 mt-1">
                可导出 {{ completedCount }} 条数据，支持多种格式
              </p>
            </div>
            
            <div v-if="isExportReady" class="flex gap-2">
              <button
                @click="exportResults('json')"
                class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition"
              >
                📄 JSON
              </button>
              <button
                @click="exportResults('csv')"
                class="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition"
              >
                📊 CSV
              </button>
            </div>
            <div v-else class="text-gray-400">
              🔒 需要先完成质量检测
            </div>
          </div>
        </div>
        
        <!-- Tabs -->
        <div class="flex gap-4 border-b border-gray-200 mb-4">
          <button
            @click="activeTab = 'table'"
            class="py-2 text-sm font-medium border-b-2 transition-colors"
            :class="activeTab === 'table' ? 'border-purple-600 text-purple-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
          >
            📋 数据列表
          </button>
          <button
            @click="activeTab = 'graph'"
            class="py-2 text-sm font-medium border-b-2 transition-colors"
            :class="activeTab === 'graph' ? 'border-purple-600 text-purple-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
          >
            🕸️ 知识图谱
          </button>
        </div>

        <!-- Table Tab -->
        <div v-if="activeTab === 'table'">
        <!-- Filter Toolbar -->
        <div class="flex justify-between items-center mb-4">
          <div class="flex gap-2">
            <button
              @click="filterStatus = 'all'"
              :class="[
                'px-4 py-2 rounded-lg text-sm font-medium transition',
                filterStatus === 'all' 
                  ? 'bg-purple-600 text-white' 
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              ]"
            >
              全部 ({{ terms.length }})
            </button>
            <button
              @click="filterStatus = 'completed'"
              :class="[
                'px-4 py-2 rounded-lg text-sm font-medium transition',
                filterStatus === 'completed' 
                  ? 'bg-green-600 text-white' 
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              ]"
            >
              ✓ 完成 ({{ completedCount }})
            </button>
            <button
              @click="filterStatus = 'failed'"
              :class="[
                'px-4 py-2 rounded-lg text-sm font-medium transition',
                filterStatus === 'failed' 
                  ? 'bg-red-600 text-white' 
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              ]"
            >
              ✗ 失败 ({{ failedCount }})
            </button>
          </div>
          
          <button
            v-if="failedCount > 0"
            @click="retryFailed"
            class="px-4 py-2 bg-orange-600 text-white rounded-lg text-sm font-medium hover:bg-orange-700 transition"
          >
            🔄 重试失败
          </button>
        </div>
        
        <!-- Results Table -->
        <div class="border border-gray-200 rounded-lg overflow-hidden">
          <div class="max-h-80 overflow-y-auto custom-scrollbar">
            <table class="w-full">
              <thead class="bg-gray-50 sticky top-0">
                <tr>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    #
                  </th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    术语
                  </th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    状态
                  </th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-200">
                <template v-for="(term, index) in filteredTerms" :key="term.id">
                  <!-- Main Row -->
                  <tr class="hover:bg-gray-50 transition">
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {{ index + 1 }}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                      <span class="text-sm font-medium text-gray-900">{{ term.term }}</span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                      <span :class="['px-2 py-1 rounded-full text-xs font-medium capitalize', getStatusColor(term.status)]">
                        {{ term.status }}
                      </span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm">
                      <button
                        v-if="term.status === 'completed'"
                        @click="toggleExpand(term.id)"
                        class="text-blue-600 hover:text-blue-700 font-medium"
                      >
                        {{ expandedTerm === term.id ? '收起' : '查看' }}
                      </button>
                      <span v-else-if="term.status === 'failed'" class="text-red-600 text-xs">
                        {{ term.error_message }}
                      </span>
                    </td>
                  </tr>
                  
                  <!-- Expanded Details Row -->
                  <tr v-if="expandedTerm === term.id" class="bg-gray-50">
                    <td colspan="4" class="px-6 py-4">
                      <div class="grid grid-cols-2 gap-4">
                        <!-- English Section -->
                        <div>
                          <h4 class="text-sm font-bold text-gray-800 mb-2 flex items-center gap-2">
                            🇺🇸 English
                            <a v-if="term.en_url" :href="term.en_url" target="_blank" class="text-xs text-blue-500 hover:text-blue-700">
                              查看 →
                            </a>
                          </h4>
                          <p class="text-xs text-gray-600 max-h-32 overflow-y-auto custom-scrollbar bg-white p-3 rounded border border-gray-200">
                            {{ term.en_summary || 'N/A' }}
                          </p>
                        </div>
                        
                        <!-- Chinese Section -->
                        <div>
                          <h4 class="text-sm font-bold text-gray-800 mb-2 flex items-center gap-2">
                            🇨🇳 Chinese
                            <a v-if="term.zh_url" :href="term.zh_url" target="_blank" class="text-xs text-blue-500 hover:text-blue-700">
                              查看 →
                            </a>
                          </h4>
                          <p class="text-xs text-gray-600 max-h-32 overflow-y-auto custom-scrollbar bg-white p-3 rounded border border-gray-200">
                            {{ term.zh_summary || '未找到翻译' }}
                          </p>
                        </div>
                      </div>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </div>
        
        <!-- Empty State -->
        <div v-if="filteredTerms.length === 0" class="text-center py-12">
          <p class="text-gray-500">没有找到状态为 <span class="font-medium">{{ filterStatus }}</span> 的术语</p>
        </div>
        </div>
        
        <!-- Graph Tab -->
        <div v-if="activeTab === 'graph'">
          <VisualGraph :task-id="taskId" />
        </div>
      </div>
    </div>
    
    <!-- Clean Options Modal -->
    <div v-if="showCleanOptions" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-2xl p-6 max-w-md mx-4">
        <h3 class="text-xl font-bold text-gray-800 mb-4">🧹 清洗 Task #{{ taskId }} 数据</h3>
        
        <div class="space-y-4 mb-6">
          <label class="flex items-start gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
            <input type="checkbox" v-model="cleanOptions.removeFailed" class="mt-1" />
            <div>
              <p class="font-medium text-gray-800">删除失败的术语</p>
              <p class="text-sm text-gray-500">共 {{ qualityData?.failed_terms || 0 }} 条</p>
            </div>
          </label>
          
          <label class="flex items-start gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
            <input type="checkbox" v-model="cleanOptions.removeMissingChinese" class="mt-1" />
            <div>
              <p class="font-medium text-gray-800">删除缺少中文翻译的术语</p>
              <p class="text-sm text-gray-500">共 {{ qualityData?.missing_chinese || 0 }} 条</p>
            </div>
          </label>
          
          <label class="flex items-start gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
            <input type="checkbox" v-model="cleanOptions.removeShortSummaries" class="mt-1" />
            <div>
              <p class="font-medium text-gray-800">删除摘要过短的术语</p>
              <p class="text-sm text-gray-500">
                英文: {{ qualityData?.en_summary_too_short || 0 }} | 
                中文: {{ qualityData?.zh_summary_too_short || 0 }}
              </p>
            </div>
          </label>
        </div>
        
        <div class="flex gap-3">
          <button
            @click="cleanData"
            :disabled="cleaning"
            class="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition"
          >
            {{ cleaning ? '清理中...' : '确认清理' }}
          </button>
          <button
            @click="showCleanOptions = false"
            :disabled="cleaning"
            class="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: #f1f1f1;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
</style>
