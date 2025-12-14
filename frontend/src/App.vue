<script setup>
import { ref } from 'vue'
import axios from 'axios'
import BatchImport from './components/BatchImport.vue'
import ProgressMonitor from './components/ProgressMonitor.vue'
import ResultsTable from './components/ResultsTable.vue'
import TaskManager from './components/TaskManager.vue'
import QualityReport from './components/QualityReport.vue'

// Active view: 'single', 'batch', 'manage', or 'quality'
const activeView = ref('single')

// Single search state
const term = ref('')
const loading = ref(false)
const error = ref(null)
const result = ref(null)

// Batch processing state
const currentTaskId = ref(null)
const showProgress = ref(false)
const showResults = ref(false)

// Single search functions
const search = async () => {
  if (!term.value.trim()) return
  
  loading.value = true
  error.value = null
  result.value = null
  
  try {
    const response = await axios.get(`http://localhost:8000/search?term=${encodeURIComponent(term.value)}`)
    result.value = response.data
  } catch (err) {
    if (err.response && err.response.data && err.response.data.detail) {
      error.value = err.response.data.detail
    } else {
      error.value = "An error occurred while fetching data."
    }
  } finally {
    loading.value = false
  }
}

const downloadJson = () => {
  if (!result.value) return
  const dataStr = JSON.stringify(result.value, null, 2)
  const blob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${result.value.term}_data.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

const handleKeyup = (e) => {
  if (e.key === 'Enter') search()
}

// Batch processing functions
const handleTaskCreated = async (taskData) => {
  currentTaskId.value = taskData.task_id
  
  // Start the task
  try {
    await axios.post(`http://localhost:8000/api/batch/${taskData.task_id}/start`)
    showProgress.value = true
  } catch (err) {
    console.error('Error starting task:', err)
  }
}

const handleTaskCompleted = (taskId) => {
  console.log('Task completed:', taskId)
}

const handleRetry = async (taskId) => {
  try {
    await axios.post(`http://localhost:8000/api/batch/${taskId}/retry-failed`)
    showResults.value = false
    showProgress.value = true
  } catch (err) {
    console.error('Error retrying:', err)
  }
}

const viewResults = () => {
  showProgress.value = false
  showResults.value = true
}

const closeProgress = () => {
  showProgress.value = false
}

const closeResults = () => {
  showResults.value = false
}

// Task Manager functions
const handleViewTask = (taskId) => {
  currentTaskId.value = taskId
  activeView.value = 'batch'
  showResults.value = true
}
</script>

<template>
  <div class="min-h-screen flex flex-col items-center py-12 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-blue-50 via-white to-purple-50">
    <div class="w-full max-w-6xl space-y-8">
      
      <!-- Header -->
      <div class="text-center">
        <h1 class="text-5xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-purple-600 tracking-tight">
          Term Corpus Generator
        </h1>
        <p class="mt-3 text-lg text-gray-600">
          Instantly fetch bilingual definitions from Wikipedia
        </p>
      </div>

      <!-- View Switcher -->
      <div class="flex justify-center gap-3">
        <button
          @click="activeView = 'single'"
          :class="[
            'px-8 py-3 rounded-xl font-semibold text-lg transition-all shadow-md',
            activeView === 'single'
              ? 'bg-gradient-to-r from-blue-600 to-blue-700 text-white shadow-blue-200'
              : 'bg-white text-gray-600 hover:bg-gray-50'
          ]"
        >
          🔍 Single Search
        </button>
        <button
          @click="activeView = 'batch'"
          :class="[
            'px-8 py-3 rounded-xl font-semibold text-lg transition-all shadow-md',
            activeView === 'batch'
              ? 'bg-gradient-to-r from-purple-600 to-purple-700 text-white shadow-purple-200'
              : 'bg-white text-gray-600 hover:bg-gray-50'
          ]"
        >
          📚 Batch Import
        </button>
        <button
          @click="activeView = 'manage'"
          :class="[
            'px-8 py-3 rounded-xl font-semibold text-lg transition-all shadow-md',
            activeView === 'manage'
              ? 'bg-gradient-to-r from-gray-700 to-gray-800 text-white shadow-gray-300'
              : 'bg-white text-gray-600 hover:bg-gray-50'
          ]"
        >
          ⚙️ Manage
        </button>
        <button
          @click="activeView = 'quality'"
          :class="[
            'px-8 py-3 rounded-xl font-semibold text-lg transition-all shadow-md',
            activeView === 'quality'
              ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white shadow-emerald-200'
              : 'bg-white text-gray-600 hover:bg-gray-50'
          ]"
        >
          📊 Quality
        </button>
      </div>

      <!-- Single Search View -->
      <div v-if="activeView === 'single'" class="space-y-8">
        <!-- Search Box -->
        <div class="mt-8 flex gap-2">
          <div class="relative flex-grow">
            <input 
              v-model="term" 
              @keyup="handleKeyup"
              type="text" 
              class="block w-full rounded-xl border-gray-300 shadow-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 sm:text-lg pl-4 py-4 border outline-none transition-all duration-200" 
              placeholder="Enter a term (e.g., Inflation)" 
            />
          </div>
          <button 
            @click="search" 
            :disabled="loading"
            class="inline-flex items-center px-8 py-4 border border-transparent text-base font-medium rounded-xl shadow-md text-white bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            <span v-if="loading" class="animate-spin mr-2">⟳</span>
            Search
          </button>
        </div>

        <!-- Error Message -->
        <div v-if="error" class="rounded-xl bg-red-50 p-4 border border-red-200 animate-fade-in-down shadow-md">
          <div class="flex">
            <div class="ml-3">
              <h3 class="text-sm font-medium text-red-800">Error</h3>
              <div class="mt-2 text-sm text-red-700">
                <p>{{ error }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Results Area -->
        <transition 
          enter-active-class="transition ease-out duration-300"
          enter-from-class="transform opacity-0 translate-y-4" 
          enter-to-class="transform opacity-100 translate-y-0"
          leave-active-class="transition ease-in duration-200"
          leave-from-class="transform opacity-100 translate-y-0"
          leave-to-class="transform opacity-0 translate-y-4"
        >
          <div v-if="result" class="bg-white shadow-xl rounded-2xl overflow-hidden border border-gray-100">
            <div class="px-6 py-4 flex justify-between items-center bg-gradient-to-r from-gray-50 to-blue-50 border-b border-gray-100">
              <h3 class="text-lg leading-6 font-medium text-gray-900">
                Results for: <span class="font-bold text-blue-600">{{ result.term }}</span>
              </h3>
              <button 
                @click="downloadJson" 
                class="inline-flex items-center px-3 py-1.5 border border-gray-300 shadow-sm text-sm font-medium rounded-lg text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition"
              >
                Export JSON
              </button>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-gray-100">
              <!-- English Section -->
              <div class="p-6">
                <div class="flex items-center justify-between mb-4">
                  <h4 class="text-lg font-bold text-gray-800 flex items-center">
                    🇺🇸 English
                  </h4>
                  <a :href="result.en_url" target="_blank" class="text-sm text-blue-500 hover:text-blue-700 font-medium transition">Wikipedia →</a>
                </div>
                <p class="text-gray-600 leading-relaxed text-sm h-80 overflow-y-auto pr-2 custom-scrollbar">
                  {{ result.en_summary }}
                </p>
              </div>

              <!-- Chinese Section -->
              <div class="p-6 bg-slate-50/50">
                <div class="flex items-center justify-between mb-4">
                  <h4 class="text-lg font-bold text-gray-800 flex items-center">
                    🇨🇳 Chinese
                  </h4>
                  <a v-if="result.zh_url" :href="result.zh_url" target="_blank" class="text-sm text-blue-500 hover:text-blue-700 font-medium transition">Wikipedia →</a>
                </div>
                <div v-if="result.zh_url">
                  <p class="text-gray-600 leading-relaxed text-sm h-80 overflow-y-auto pr-2 custom-scrollbar">
                    {{ result.zh_summary }}
                  </p>
                </div>
                <div v-else class="flex flex-col items-center justify-center h-80 text-gray-400">
                  <span>No Chinese translation found.</span>
                </div>
              </div>
            </div>
          </div>
        </transition>
      </div>

      <!-- Batch Import View -->
      <div v-if="activeView === 'batch'" class="space-y-6">
        <!-- Progress Monitor (if task is running) -->
        <div v-if="showProgress && currentTaskId">
          <ProgressMonitor 
            :taskId="currentTaskId" 
            @task-completed="viewResults"
            @close="closeProgress"
          />
        </div>

        <!-- Results Table (if viewing results) -->
        <div v-if="showResults && currentTaskId">
          <ResultsTable 
            :taskId="currentTaskId" 
            @close="closeResults"
            @retry="handleRetry"
          />
        </div>

        <!-- Batch Import Component (always visible when not showing progress/results) -->
        <div v-if="!showProgress && !showResults">
          <BatchImport @task-created="handleTaskCreated" />
        </div>

        <!-- Quick Access to Results (if task exists) -->
        <div v-if="currentTaskId && !showProgress && !showResults" class="bg-blue-50 border border-blue-200 rounded-xl p-4">
          <div class="flex justify-between items-center">
            <div>
              <p class="text-sm font-medium text-blue-900">Recent Task #{{ currentTaskId }}</p>
              <p class="text-xs text-blue-600 mt-1">Click to view progress or results</p>
            </div>
            <div class="flex gap-2">
              <button
                @click="showProgress = true"
                class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition"
              >
                View Progress
              </button>
              <button
                @click="showResults = true"
                class="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 transition"
              >
                View Results
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Manage View -->
      <div v-if="activeView === 'manage'" class="space-y-6">
        <TaskManager @view-task="handleViewTask" />
      </div>

      <!-- Quality View -->
      <div v-if="activeView === 'quality'" class="space-y-6">
        <QualityReport />
      </div>
    </div>
  </div>
</template>

<style>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
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
@keyframes fade-in-down {
    0% {
        opacity: 0;
        transform: translateY(-10px);
    }
    100% {
        opacity: 1;
        transform: translateY(0);
    }
}
.animate-fade-in-down {
    animation: fade-in-down 0.3s ease-out;
}
</style>
