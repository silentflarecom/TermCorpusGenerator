<script setup>
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'

const props = defineProps({
  taskId: {
    type: Number,
    default: null
  }
})

const emit = defineEmits(['close', 'cleaned'])

const loading = ref(true)
const error = ref(null)
const qualityData = ref(null)
const cleaning = ref(false)
const cleanResult = ref(null)
const showCleanOptions = ref(false)

// Clean options
const cleanOptions = ref({
  removeFailed: true,
  removeMissingChinese: false,
  removeShortSummaries: false,
  minSummaryLength: 50
})

// Problematic terms filter
const issueFilter = ref('all')
const filteredTerms = ref([])
const loadingTerms = ref(false)

const loadQualityData = async () => {
  loading.value = true
  error.value = null
  
  try {
    const url = props.taskId 
      ? `http://localhost:8000/api/quality/analyze?task_id=${props.taskId}`
      : 'http://localhost:8000/api/quality/analyze'
    
    const response = await axios.get(url)
    qualityData.value = response.data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to load quality data'
  } finally {
    loading.value = false
  }
}

const loadFilteredTerms = async () => {
  loadingTerms.value = true
  
  try {
    const params = new URLSearchParams({
      issue_type: issueFilter.value,
      limit: '50'
    })
    
    if (props.taskId) {
      params.append('task_id', props.taskId)
    }
    
    const response = await axios.get(`http://localhost:8000/api/quality/issues?${params}`)
    filteredTerms.value = response.data.terms
  } catch (err) {
    console.error('Failed to load filtered terms:', err)
  } finally {
    loadingTerms.value = false
  }
}

const cleanData = async () => {
  if (!cleanOptions.value.removeFailed && 
      !cleanOptions.value.removeMissingChinese && 
      !cleanOptions.value.removeShortSummaries) {
    error.value = 'Please select at least one cleanup option'
    return
  }
  
  cleaning.value = true
  error.value = null
  
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
    
    // Reload quality data
    await loadQualityData()
    emit('cleaned', response.data)
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to clean data'
  } finally {
    cleaning.value = false
  }
}

const getScoreColor = (score) => {
  if (score >= 80) return 'text-green-600'
  if (score >= 60) return 'text-yellow-600'
  return 'text-red-600'
}

const getScoreBg = (score) => {
  if (score >= 80) return 'bg-green-100'
  if (score >= 60) return 'bg-yellow-100'
  return 'bg-red-100'
}

const getIssueLabel = (issue) => {
  const labels = {
    'missing_chinese': '缺少中文',
    'en_too_short': '英文过短',
    'zh_too_short': '中文过短',
    'failed': '爬取失败'
  }
  return labels[issue] || issue
}

const getIssueBadgeColor = (issue) => {
  const colors = {
    'missing_chinese': 'bg-orange-100 text-orange-800',
    'en_too_short': 'bg-blue-100 text-blue-800',
    'zh_too_short': 'bg-purple-100 text-purple-800',
    'failed': 'bg-red-100 text-red-800'
  }
  return colors[issue] || 'bg-gray-100 text-gray-800'
}

onMounted(() => {
  loadQualityData()
})
</script>

<template>
  <div class="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
    <!-- Header -->
    <div class="bg-gradient-to-r from-emerald-500 to-teal-600 px-6 py-4 flex justify-between items-center">
      <div>
        <h2 class="text-xl font-bold text-white">📊 Data Quality Report</h2>
        <p class="text-emerald-100 text-sm mt-1">
          {{ props.taskId ? `Task #${props.taskId}` : 'All Corpus Data' }}
        </p>
      </div>
      <div class="flex gap-2">
        <button
          @click="loadQualityData"
          class="px-3 py-1.5 bg-white/20 text-white rounded-lg hover:bg-white/30 transition text-sm"
        >
          🔄 Refresh
        </button>
        <button
          v-if="!showCleanOptions"
          @click="showCleanOptions = true"
          class="px-3 py-1.5 bg-red-500 text-white rounded-lg hover:bg-red-600 transition text-sm"
        >
          🧹 Clean Data
        </button>
      </div>
    </div>
    
    <!-- Loading -->
    <div v-if="loading" class="p-8 text-center">
      <div class="animate-spin inline-block w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full"></div>
      <p class="mt-2 text-gray-500">Analyzing data quality...</p>
    </div>
    
    <!-- Error -->
    <div v-else-if="error" class="p-6 bg-red-50 border-b border-red-200">
      <p class="text-red-700">{{ error }}</p>
    </div>
    
    <!-- Quality Data -->
    <div v-else-if="qualityData" class="p-6">
      <!-- Clean Result Banner -->
      <div v-if="cleanResult" class="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg">
        <p class="text-green-800 font-medium">✅ {{ cleanResult.message }}</p>
        <p class="text-green-600 text-sm mt-1">
          Failed: {{ cleanResult.failed_removed }} | 
          Missing Chinese: {{ cleanResult.missing_chinese_removed }} | 
          Short Summaries: {{ cleanResult.short_summaries_removed }} |
          Associations: {{ cleanResult.associations_removed }}
        </p>
      </div>
      
      <!-- Quality Score Circle -->
      <div class="flex items-center justify-center mb-6">
        <div :class="['w-32 h-32 rounded-full flex flex-col items-center justify-center', getScoreBg(qualityData.quality_score)]">
          <span :class="['text-4xl font-bold', getScoreColor(qualityData.quality_score)]">
            {{ qualityData.quality_score }}
          </span>
          <span class="text-gray-500 text-sm">Quality Score</span>
        </div>
      </div>
      
      <!-- Stats Grid -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div class="bg-gray-50 rounded-lg p-4 text-center">
          <p class="text-2xl font-bold text-gray-800">{{ qualityData.total_terms }}</p>
          <p class="text-sm text-gray-500">Total Terms</p>
        </div>
        <div class="bg-green-50 rounded-lg p-4 text-center">
          <p class="text-2xl font-bold text-green-600">{{ qualityData.complete_bilingual }}</p>
          <p class="text-sm text-gray-500">Complete Pairs</p>
        </div>
        <div class="bg-orange-50 rounded-lg p-4 text-center">
          <p class="text-2xl font-bold text-orange-600">{{ qualityData.missing_chinese }}</p>
          <p class="text-sm text-gray-500">Missing Chinese</p>
        </div>
        <div class="bg-red-50 rounded-lg p-4 text-center">
          <p class="text-2xl font-bold text-red-600">{{ qualityData.failed_terms }}</p>
          <p class="text-sm text-gray-500">Failed</p>
        </div>
      </div>
      
      <!-- Detailed Metrics -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div class="border border-gray-200 rounded-lg p-4">
          <h4 class="font-medium text-gray-700 mb-3">Summary Length Issues</h4>
          <div class="space-y-2">
            <div class="flex justify-between items-center">
              <span class="text-sm text-gray-600">English too short (&lt;{{ qualityData.min_summary_length }} chars)</span>
              <span class="font-medium text-blue-600">{{ qualityData.en_summary_too_short }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-sm text-gray-600">Chinese too short (&lt;{{ qualityData.min_summary_length }} chars)</span>
              <span class="font-medium text-purple-600">{{ qualityData.zh_summary_too_short }}</span>
            </div>
          </div>
        </div>
        
        <div class="border border-gray-200 rounded-lg p-4">
          <h4 class="font-medium text-gray-700 mb-3">Status Breakdown</h4>
          <div class="space-y-2">
            <div class="flex justify-between items-center">
              <span class="text-sm text-gray-600">Completed</span>
              <span class="font-medium text-green-600">{{ qualityData.completed_terms }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-sm text-gray-600">Pending</span>
              <span class="font-medium text-yellow-600">{{ qualityData.pending_terms }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-sm text-gray-600">Failed</span>
              <span class="font-medium text-red-600">{{ qualityData.failed_terms }}</span>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Problematic Terms Preview -->
      <div v-if="qualityData.problematic_terms && qualityData.problematic_terms.length > 0" class="border border-gray-200 rounded-lg overflow-hidden">
        <div class="bg-gray-50 px-4 py-3 border-b border-gray-200 flex justify-between items-center">
          <h4 class="font-medium text-gray-700">⚠️ Problematic Terms ({{ qualityData.problematic_terms.length }})</h4>
          <select 
            v-model="issueFilter"
            @change="loadFilteredTerms"
            class="text-sm border border-gray-300 rounded-lg px-2 py-1"
          >
            <option value="all">All Issues</option>
            <option value="missing_chinese">Missing Chinese</option>
            <option value="short_en">Short English</option>
            <option value="short_zh">Short Chinese</option>
            <option value="failed">Failed</option>
          </select>
        </div>
        <div class="max-h-48 overflow-y-auto divide-y divide-gray-100">
          <div
            v-for="term in qualityData.problematic_terms"
            :key="term.id"
            class="px-4 py-2 flex items-center justify-between hover:bg-gray-50"
          >
            <span class="text-sm text-gray-800">{{ term.term }}</span>
            <span :class="['px-2 py-0.5 rounded-full text-xs', getIssueBadgeColor(term.issue)]">
              {{ getIssueLabel(term.issue) }}
            </span>
          </div>
        </div>
      </div>
      
      <!-- No Issues -->
      <div v-else class="text-center py-8 text-gray-500">
        <span class="text-4xl">🎉</span>
        <p class="mt-2">No quality issues found!</p>
      </div>
      
      <!-- Clean Options Modal -->
      <div v-if="showCleanOptions" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div class="bg-white rounded-xl shadow-2xl p-6 max-w-md mx-4">
          <h3 class="text-xl font-bold text-gray-800 mb-4">🧹 Clean Data Options</h3>
          
          <div class="space-y-4 mb-6">
            <label class="flex items-start gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
              <input type="checkbox" v-model="cleanOptions.removeFailed" class="mt-1" />
              <div>
                <p class="font-medium text-gray-800">Remove Failed Terms</p>
                <p class="text-sm text-gray-500">Delete all terms that failed to crawl ({{ qualityData.failed_terms }})</p>
              </div>
            </label>
            
            <label class="flex items-start gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
              <input type="checkbox" v-model="cleanOptions.removeMissingChinese" class="mt-1" />
              <div>
                <p class="font-medium text-gray-800">Remove Missing Chinese</p>
                <p class="text-sm text-gray-500">Delete terms without Chinese translation ({{ qualityData.missing_chinese }})</p>
              </div>
            </label>
            
            <label class="flex items-start gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
              <input type="checkbox" v-model="cleanOptions.removeShortSummaries" class="mt-1" />
              <div>
                <p class="font-medium text-gray-800">Remove Short Summaries</p>
                <p class="text-sm text-gray-500">
                  Delete terms with summaries &lt; {{ cleanOptions.minSummaryLength }} chars
                  (EN: {{ qualityData.en_summary_too_short }}, ZH: {{ qualityData.zh_summary_too_short }})
                </p>
              </div>
            </label>
            
            <div class="p-3 border rounded-lg">
              <label class="block text-sm font-medium text-gray-700 mb-2">
                Minimum Summary Length
              </label>
              <input 
                type="number" 
                v-model.number="cleanOptions.minSummaryLength"
                min="10"
                max="200"
                class="w-24 px-3 py-1.5 border border-gray-300 rounded-lg"
              />
              <span class="text-sm text-gray-500 ml-2">characters</span>
            </div>
          </div>
          
          <div class="flex gap-3">
            <button
              @click="cleanData"
              :disabled="cleaning"
              class="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition"
            >
              {{ cleaning ? 'Cleaning...' : 'Clean Now' }}
            </button>
            <button
              @click="showCleanOptions = false"
              :disabled="cleaning"
              class="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
