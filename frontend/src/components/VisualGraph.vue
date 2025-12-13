<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'
import axios from 'axios'

const props = defineProps({
  taskId: {
    type: Number,
    required: true
  }
})

const container = ref(null)
const loading = ref(false)
const graphData = ref({ nodes: [], edges: [] })
let simulation = null

const fetchGraphData = async () => {
  if (!props.taskId) return
  loading.value = true
  try {
    const response = await axios.get(`http://localhost:8000/api/batch/${props.taskId}/graph`)
    graphData.value = response.data
    renderGraph()
  } catch (e) {
    console.error("Error fetching graph:", e)
  } finally {
    loading.value = false
  }
}

const renderGraph = () => {
  if (!container.value || !graphData.value.nodes.length) return

  // Clear previous SVG
  d3.select(container.value).selectAll("*").remove()

  const width = container.value.clientWidth
  const height = 600
  
  const svg = d3.select(container.value)
    .append("svg")
    .attr("width", width)
    .attr("height", height)
    .attr("viewBox", [0, 0, width, height])
    .attr("style", "max-width: 100%; height: auto;")

  // Create a set of valid node IDs
  const nodeIds = new Set(graphData.value.nodes.map(n => n.id))
  
  // Filter edges and convert from {from, to} to {source, target} for D3
  const validEdges = graphData.value.edges
    .filter(e => nodeIds.has(e.from) && nodeIds.has(e.to))
    .map(e => ({
      source: e.from,
      target: e.to,
      type: e.type,
      value: e.value
    }))

  // Limit edges to reduce density (show max 100 edges)
  const displayEdges = validEdges.slice(0, 100)

  // Simulation setup with better spacing
  simulation = d3.forceSimulation(graphData.value.nodes)
    .force("link", d3.forceLink(displayEdges).id(d => d.id).distance(150))  // Increased distance
    .force("charge", d3.forceManyBody().strength(-500))  // Stronger repulsion
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collide", d3.forceCollide(50))  // Larger collision radius
    .force("x", d3.forceX(width / 2).strength(0.05))  // Keep nodes centered
    .force("y", d3.forceY(height / 2).strength(0.05))

  // Render links with lower opacity
  const link = svg.append("g")
    .attr("class", "links")
    .attr("stroke", "#999")
    .attr("stroke-opacity", 0.3)  // Reduced opacity
    .selectAll("line")
    .data(displayEdges)
    .join("line")
    .attr("stroke-width", 1)  // Thinner lines

  // Render nodes with varying sizes
  const node = svg.append("g")
    .attr("class", "nodes")
    .attr("stroke", "#fff")
    .attr("stroke-width", 2)
    .selectAll("circle")
    .data(graphData.value.nodes)
    .join("circle")
    .attr("r", d => {
      // Larger nodes for root terms (depth 0)
      if (d.depth === 0) return 12
      if (d.depth === 1) return 8
      return 5
    })
    .attr("fill", d => {
        // Color by depth
        const colors = ["#ef4444", "#3b82f6", "#10b981", "#f59e0b"]
        return colors[d.depth % colors.length] || "#888"
    })
    .call(d3.drag()
      .on("start", dragstarted)
      .on("drag", dragged)
      .on("end", dragended))

  node.append("title")
    .text(d => d.label)
    
  // Labels - ONLY show for depth 0 and 1 nodes to reduce clutter
  const labels = svg.append("g")
    .attr("class", "labels")
    .selectAll("text")
    .data(graphData.value.nodes.filter(n => n.depth <= 1))  // Only root and first layer
    .enter()
    .append("text")
    .attr("dx", 14)
    .attr("dy", ".35em")
    .text(d => d.label.length > 20 ? d.label.substring(0, 18) + '...' : d.label)  // Truncate long labels
    .style("font-size", d => d.depth === 0 ? "12px" : "9px")
    .style("font-weight", d => d.depth === 0 ? "bold" : "normal")
    .style("pointer-events", "none")
    .style("fill", "#333")
    .style("text-shadow", "1px 1px 2px white, -1px -1px 2px white")  // Better readability

  simulation.on("tick", () => {
    link
      .attr("x1", d => d.source.x)
      .attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x)
      .attr("y2", d => d.target.y)

    node
      .attr("cx", d => d.x)
      .attr("cy", d => d.y)
      
    labels
      .attr("x", d => d.x)
      .attr("y", d => d.y)
  })

  // Zoom behavior
  const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on("zoom", (event) => {
          svg.selectAll("g").attr("transform", event.transform);
      });
      
  svg.call(zoom);

  function dragstarted(event) {
    if (!event.active) simulation.alphaTarget(0.3).restart()
    event.subject.fx = event.subject.x
    event.subject.fy = event.subject.y
  }

  function dragged(event) {
    event.subject.fx = event.x
    event.subject.fy = event.y
  }

  function dragended(event) {
    if (!event.active) simulation.alphaTarget(0)
    event.subject.fx = null
    event.subject.fy = null
  }
}

watch(() => props.taskId, () => {
  fetchGraphData()
})

onMounted(() => {
  fetchGraphData()
})

onUnmounted(() => {
  if (simulation) simulation.stop()
})

// Export functions - capture full graph regardless of zoom state
const getFullGraphSVG = () => {
  if (!container.value) return null
  const svgElement = container.value.querySelector('svg')
  if (!svgElement) return null
  
  // Clone SVG to avoid modifying the displayed one
  const clonedSvg = svgElement.cloneNode(true)
  
  // Remove any transform from groups (zoom/pan state)
  const groups = clonedSvg.querySelectorAll('g')
  groups.forEach(g => {
    g.removeAttribute('transform')
  })
  
  // Calculate bounding box of all nodes
  const nodes = graphData.value.nodes
  if (nodes.length === 0) return null
  
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  nodes.forEach(n => {
    if (n.x !== undefined && n.y !== undefined) {
      minX = Math.min(minX, n.x - 50)
      minY = Math.min(minY, n.y - 50)
      maxX = Math.max(maxX, n.x + 150)  // Extra space for labels
      maxY = Math.max(maxY, n.y + 50)
    }
  })
  
  // Add padding
  const padding = 50
  minX -= padding
  minY -= padding
  maxX += padding
  maxY += padding
  
  const width = maxX - minX
  const height = maxY - minY
  
  // Update viewBox to show all content
  clonedSvg.setAttribute('viewBox', `${minX} ${minY} ${width} ${height}`)
  clonedSvg.setAttribute('width', width)
  clonedSvg.setAttribute('height', height)
  
  return clonedSvg
}

const exportAsSVG = () => {
  const clonedSvg = getFullGraphSVG()
  if (!clonedSvg) return
  
  const serializer = new XMLSerializer()
  const svgString = serializer.serializeToString(clonedSvg)
  const blob = new Blob([svgString], { type: 'image/svg+xml' })
  const url = URL.createObjectURL(blob)
  
  const a = document.createElement('a')
  a.href = url
  a.download = `knowledge_graph_task_${props.taskId}.svg`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

const exportAsPNG = () => {
  const clonedSvg = getFullGraphSVG()
  if (!clonedSvg) return
  
  const serializer = new XMLSerializer()
  const svgString = serializer.serializeToString(clonedSvg)
  
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  const img = new Image()
  
  const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(svgBlob)
  
  img.onload = () => {
    // Use original size * 2 for high resolution
    const scale = 2
    canvas.width = img.width * scale
    canvas.height = img.height * scale
    ctx.fillStyle = '#f9fafb'  // Background color
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.scale(scale, scale)
    ctx.drawImage(img, 0, 0)
    
    const pngUrl = canvas.toDataURL('image/png')
    const a = document.createElement('a')
    a.href = pngUrl
    a.download = `knowledge_graph_task_${props.taskId}.png`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }
  img.src = url
}

const exportAsJSON = () => {
  const data = {
    nodes: graphData.value.nodes,
    edges: graphData.value.edges
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  
  const a = document.createElement('a')
  a.href = url
  a.download = `knowledge_graph_task_${props.taskId}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="border rounded-lg bg-white p-4 shadow-sm">
    <div class="flex justify-between items-center mb-4 border-b pb-2">
        <h3 class="font-bold text-gray-700">Knowledge Graph</h3>
        <div class="flex gap-2">
            <button @click="exportAsPNG" class="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 transition">
                🖼️ PNG
            </button>
            <button @click="exportAsSVG" class="text-sm px-3 py-1 bg-purple-600 text-white rounded hover:bg-purple-700 transition">
                📝 SVG
            </button>
            <button @click="exportAsJSON" class="text-sm px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700 transition">
                📄 JSON
            </button>
            <button @click="fetchGraphData" class="text-sm px-3 py-1 bg-gray-500 text-white rounded hover:bg-gray-600 transition">
                🔄 Refresh
            </button>
        </div>
    </div>
    
    <div v-if="loading" class="flex justify-center py-12">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
    </div>
    
    <div ref="container" class="w-full h-[600px] bg-gray-50 rounded overflow-hidden relative">
      <div v-if="!loading && graphData.nodes.length === 0" class="absolute inset-0 flex items-center justify-center text-gray-400">
        No graph data available
      </div>
    </div>
    
    <div class="mt-2 flex gap-4 text-xs text-gray-600">
        <div class="flex items-center gap-1">
            <span class="w-3 h-3 rounded-full bg-red-500 block"></span> Depth 0 (Root)
        </div>
        <div class="flex items-center gap-1">
            <span class="w-3 h-3 rounded-full bg-blue-500 block"></span> Depth 1
        </div>
        <div class="flex items-center gap-1">
            <span class="w-3 h-3 rounded-full bg-green-500 block"></span> Depth 2
        </div>
    </div>
  </div>
</template>
