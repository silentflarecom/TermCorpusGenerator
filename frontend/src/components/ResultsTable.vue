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

const filteredTerms = computed(() => {
  if (filterStatus.value === 'all') return terms.value
  return terms.value.filter(t => t.status === filterStatus.value)
})

const completedCount = computed(() => terms.value.filter(t => t.status === 'completed').length)
const failedCount = computed(() => terms.value.filter(t => t.status === 'failed').length)

const fetchTerms = async () => {
  try {
    const response = await axios.get(`http://localhost:8000/api/batch/${props.taskId}/terms`)
    terms.value = response.data
    loading.value = false
  } catch (error) {
    console.error('Error fetching terms:', error)
    loading.value = false
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

onMounted(() => {
  fetchTerms()
})
</script>

<template>
  <div class="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
    <!-- Header -->
    <div class="bg-gradient-to-r from-purple-500 to-purple-600 px-6 py-4 flex justify-between items-center">
      <div>
        <h2 class="text-xl font-bold text-white">📦 Task #{{ taskId }} Results</h2>
        <p class="text-purple-100 text-sm mt-1">View and export crawled data</p>
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
        <!-- Tabs -->
        <div class="flex gap-4 border-b border-gray-200 mb-4">
          <button
            @click="activeTab = 'table'"
            class="py-2 text-sm font-medium border-b-2 transition-colors"
            :class="activeTab === 'table' ? 'border-purple-600 text-purple-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
          >
            📋 Results Table
          </button>
          <button
            @click="activeTab = 'graph'"
            class="py-2 text-sm font-medium border-b-2 transition-colors"
            :class="activeTab === 'graph' ? 'border-purple-600 text-purple-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
          >
            🕸️ Knowledge Graph
          </button>
        </div>

        <!-- Table Tab -->
        <div v-if="activeTab === 'table'">
        <!-- Toolbar -->
        <div class="flex justify-between items-center mb-6">
          <!-- Filter Tabs -->
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
              All ({{ terms.length }})
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
              ✓ Completed ({{ completedCount }})
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
              ✗ Failed ({{ failedCount }})
            </button>
          </div>
          
          <!-- Export Buttons -->
          <div class="flex gap-2">
            <button
              v-if="failedCount > 0"
              @click="retryFailed"
              class="px-4 py-2 bg-orange-600 text-white rounded-lg text-sm font-medium hover:bg-orange-700 transition"
            >
              🔄 Retry Failed
            </button>
            <button
              @click="exportResults('json')"
              class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition"
            >
              Export JSON
            </button>
            <button
              @click="exportResults('csv')"
              class="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition"
            >
              Export CSV
            </button>
          </div>
        </div>
        
        <!-- Results Table -->
        <div class="border border-gray-200 rounded-lg overflow-hidden">
          <div class="max-h-96 overflow-y-auto custom-scrollbar">
            <table class="w-full">
              <thead class="bg-gray-50 sticky top-0">
                <tr>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    #
                  </th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Term
                  </th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Action
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
                        {{ expandedTerm === term.id ? 'Hide' : 'View' }}
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
                              View →
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
                              View →
                            </a>
                          </h4>
                          <p class="text-xs text-gray-600 max-h-32 overflow-y-auto custom-scrollbar bg-white p-3 rounded border border-gray-200">
                            {{ term.zh_summary || 'Translation not found' }}
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
        <div v-if="activeTab === 'table' && filteredTerms.length === 0" class="text-center py-12">
          <p class="text-gray-500">No terms found with status: <span class="font-medium">{{ filterStatus }}</span></p>
        </div>
        </div>
        
        <!-- Graph Tab -->
        <div v-if="activeTab === 'graph'">
          <VisualGraph :task-id="taskId" />
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
