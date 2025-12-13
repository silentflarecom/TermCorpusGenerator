<script setup>
import { ref } from 'vue'
import axios from 'axios'

const term = ref('')
const loading = ref(false)
const error = ref(null)
const result = ref(null)

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
</script>

<template>
  <div class="min-h-screen flex flex-col items-center py-12 px-4 sm:px-6 lg:px-8">
    <div class="w-full max-w-4xl space-y-8">
      
      <!-- Header -->
      <div class="text-center">
        <h1 class="text-4xl font-extrabold text-gray-900 tracking-tight">
          Term Corpus Generator
        </h1>
        <p class="mt-2 text-lg text-gray-600">
          Instantly fetch bilingual economic definitions.
        </p>
      </div>

      <!-- Search Box -->
      <div class="mt-8 flex gap-2">
        <div class="relative flex-grow">
          <input 
            v-model="term" 
            @keyup="handleKeyup"
            type="text" 
            class="block w-full rounded-lg border-gray-300 shadow-sm focus:ring-primary focus:border-primary sm:text-lg pl-4 py-3 border outline-none transition-all duration-200" 
            placeholder="Enter a term (e.g., Inflation)" 
          />
        </div>
        <button 
          @click="search" 
          :disabled="loading"
          class="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-lg shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition"
        >
          <span v-if="loading" class="animate-spin mr-2">⟳</span>
          Search
        </button>
      </div>

      <!-- Error Message -->
      <div v-if="error" class="rounded-md bg-red-50 p-4 border border-red-200 animate-fade-in-down">
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
        <div v-if="result" class="bg-white shadow-xl rounded-xl overflow-hidden border border-gray-100">
          <div class="px-6 py-4 flex justify-between items-center bg-gray-50 border-b border-gray-100">
            <h3 class="text-lg leading-6 font-medium text-gray-900">
              Results for: <span class="font-bold text-blue-600">{{ result.term }}</span>
            </h3>
            <button 
              @click="downloadJson" 
              class="inline-flex items-center px-3 py-1.5 border border-gray-300 shadow-sm text-sm font-medium rounded text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary transition"
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
