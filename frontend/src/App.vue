<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

const projects = ref([])
const current = ref(null)
const busy = ref(false)
const error = ref('')
const reviewComment = ref('已核验企业资料与诊断依据，同意作为演示报告。')
const selectedFile = ref(null)
const uploadMessage = ref('')
const evidence = ref([])
const documents = ref([])
const knowledge = ref([])
const conflicts = ref([])
const metrics = ref({
  total_runs: 0,
  successful_runs: 0,
  degraded_runs: 0,
  failed_runs: 0,
  success_rate: 100,
  average_latency_ms: 0,
  current_mode: 'local',
  dify_configured: false,
  redis_available: false
})
const readiness = ref({ database: 'checking', redis: 'checking' })
const taskStatus = ref(null)
const evaluation = ref(null)
const evaluating = ref(false)
const projectSearch = ref('')
const projectStatusFilter = ref('all')
const showKnowledgeManager = ref(false)
const knowledgeSearch = ref('')
const knowledgeForm = reactive({
  title: '',
  authority: '',
  topic: '企业内部方法论',
  region: '中国',
  source_url: '',
  published_at: '',
  content: ''
})

const form = reactive({
  name: '英国市场绿色准备度诊断',
  company_name: '华东储能科技有限公司',
  industry: '储能设备制造',
  region: '浙江',
  target_market: '英国',
  goal: '识别绿色转型及进入英国市场前的主要准备缺口',
  profile: {
    annual_energy_data: true,
    carbon_inventory: false,
    reduction_target: false,
    green_certifications: ['ISO 14001'],
    lifecycle_assessment: false,
    eco_design: true,
    supplier_code: true,
    supplier_data: false,
    supplier_audit: false,
    esg_owner: '王经理',
    esg_policy: true,
    sustainability_report: false,
    target_market_requirements: false,
    compliance_owner: '',
    evidence_archive: false
  }
})

const statusText = {
  draft: '草稿',
  profile_ready: '画像已确认',
  pending_review: '待顾问审核',
  needs_revision: '待修改',
  completed: '已完成'
}

const fieldLabels = {
  annual_energy_data: '年度能源数据',
  carbon_inventory: '温室气体盘查',
  reduction_target: '量化减排目标',
  green_certifications: '绿色或环境认证',
  lifecycle_assessment: '产品生命周期评价',
  eco_design: '生态设计机制',
  supplier_code: '供应商环境准则',
  supplier_data: '供应商环境数据',
  supplier_audit: '供应商审核机制',
  esg_owner: 'ESG责任人',
  esg_policy: 'ESG或环境制度',
  sustainability_report: '可持续发展披露',
  target_market_requirements: '目标市场要求清单',
  compliance_owner: '海外合规责任人',
  evidence_archive: '合规证据归档'
}

const scoreLevel = computed(() => {
  const score = current.value?.assessment?.total_score ?? 0
  if (score >= 80) return '准备较充分'
  if (score >= 60) return '具备一定基础'
  return '需优先补强'
})

const filteredProjects = computed(() => {
  const keyword = projectSearch.value.trim().toLowerCase()
  return projects.value.filter(project => {
    const matchesKeyword = !keyword || `${project.name} ${project.company_name} ${project.target_market}`.toLowerCase().includes(keyword)
    const matchesStatus = projectStatusFilter.value === 'all' || project.status === projectStatusFilter.value
    return matchesKeyword && matchesStatus
  })
})

const filteredKnowledge = computed(() => {
  const keyword = knowledgeSearch.value.trim().toLowerCase()
  if (!keyword) return knowledge.value
  return knowledge.value.filter(item =>
    `${item.title} ${item.authority} ${item.topic} ${item.region}`.toLowerCase().includes(keyword)
  )
})

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `请求失败：${response.status}`)
  }
  if (response.status === 204) return null
  return response.json()
}

async function loadProjects() {
  try {
    projects.value = await api('/api/projects')
  } catch (e) {
    error.value = e.message
  }
}

async function loadKnowledge() {
  try {
    knowledge.value = await api('/api/knowledge')
  } catch (e) {
    error.value = e.message
  }
}

async function loadMetrics() {
  try {
    metrics.value = await api('/api/metrics/summary')
  } catch (e) {
    error.value = e.message
  }
}

async function loadReadiness() {
  try {
    readiness.value = await api('/api/health/ready')
  } catch (e) {
    readiness.value = { database: 'unavailable', redis: 'degraded' }
  }
}

async function runEvaluation() {
  evaluating.value = true
  error.value = ''
  try {
    evaluation.value = await api('/api/evaluations/run', { method: 'POST' })
  } catch (e) {
    error.value = e.message
  } finally {
    evaluating.value = false
  }
}

async function openProject(id) {
  error.value = ''
  const [project, projectEvidence, projectDocuments, projectConflicts, latestTask] = await Promise.all([
    api(`/api/projects/${id}`),
    api(`/api/projects/${id}/evidence`),
    api(`/api/projects/${id}/documents`),
    api(`/api/projects/${id}/conflicts`),
    api(`/api/projects/${id}/task-status`).catch(() => null)
  ])
  current.value = project
  evidence.value = projectEvidence
  documents.value = projectDocuments
  conflicts.value = projectConflicts
  taskStatus.value = latestTask
}

async function createAndAssess() {
  busy.value = true
  error.value = ''
  try {
    const payload = JSON.parse(JSON.stringify(form))
    for (const [key, value] of Object.entries(payload.profile)) {
      if (value === false || value === '') delete payload.profile[key]
    }
    const project = await api('/api/projects', { method: 'POST', body: JSON.stringify(payload) })
    await api(`/api/projects/${project.id}/assess`, { method: 'POST' })
    await loadProjects()
    await loadMetrics()
    await openProject(project.id)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function review(decision) {
  busy.value = true
  error.value = ''
  try {
    await api(`/api/projects/${current.value.id}/reviews`, {
      method: 'POST',
      body: JSON.stringify({ decision, comment: reviewComment.value, reviewer: '演示顾问' })
    })
    await loadProjects()
    await openProject(current.value.id)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function uploadDocument() {
  if (!selectedFile.value || !current.value) return
  busy.value = true
  error.value = ''
  uploadMessage.value = ''
  try {
    const data = new FormData()
    data.append('file', selectedFile.value)
    const response = await fetch(`/api/projects/${current.value.id}/documents`, { method: 'POST', body: data })
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || '上传失败')
    const extraction = await api(`/api/projects/${current.value.id}/extract`, { method: 'POST' })
    await api(`/api/projects/${current.value.id}/assess`, { method: 'POST' })
    uploadMessage.value = `已解析 ${result.filename}，识别 ${Object.keys(extraction.extracted_profile).length} 个画像字段`
    if (extraction.warnings?.length) uploadMessage.value += `；${extraction.warnings.join('；')}`
    if (extraction.conflicts?.length) uploadMessage.value += `；发现 ${extraction.conflicts.length} 个资料冲突，已从评分中隔离`
    await loadMetrics()
    await openProject(current.value.id)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function downloadReport() {
  if (!current.value) return
  const response = await fetch(`/api/projects/${current.value.id}/report.pdf`)
  if (!response.ok) {
    const result = await response.json().catch(() => ({}))
    error.value = result.detail || 'PDF生成失败'
    return
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${current.value.company_name}-绿色诊断报告.pdf`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

async function deleteProject(project) {
  const confirmed = window.confirm(`确认删除“${project.company_name}”吗？项目资料、评分、审核和运行记录都会一并删除。`)
  if (!confirmed) return
  busy.value = true
  error.value = ''
  try {
    await api(`/api/projects/${project.id}`, { method: 'DELETE' })
    if (current.value?.id === project.id) {
      current.value = null
      evidence.value = []
      documents.value = []
      conflicts.value = []
      taskStatus.value = null
    }
    await Promise.all([loadProjects(), loadMetrics()])
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function createKnowledge() {
  busy.value = true
  error.value = ''
  try {
    await api('/api/knowledge', { method: 'POST', body: JSON.stringify(knowledgeForm) })
    Object.assign(knowledgeForm, {
      title: '', authority: '', topic: '企业内部方法论', region: '中国',
      source_url: '', published_at: '', content: ''
    })
    await loadKnowledge()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function deleteKnowledge(item) {
  if (!window.confirm(`确认删除知识条目“${item.title}”吗？历史报告中的引用会保留。`)) return
  busy.value = true
  error.value = ''
  try {
    await api(`/api/knowledge/${item.id}`, { method: 'DELETE' })
    await loadKnowledge()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function resolveConflict(conflict, evidenceItem) {
  const label = evidenceItem.value === false ? '否定事实' : '肯定事实'
  if (!window.confirm(`确认采纳“${label}：${evidenceItem.excerpt}”吗？系统将写回企业画像并自动重新评分。`)) return
  busy.value = true
  error.value = ''
  try {
    await api(`/api/projects/${current.value.id}/conflicts/${conflict.id}/resolve`, {
      method: 'POST',
      body: JSON.stringify({
        selected_value: evidenceItem.value,
        reviewer: '演示顾问',
        comment: `采纳来自 ${evidenceItem.filename} 的证据`
      })
    })
    await Promise.all([openProject(current.value.id), loadMetrics()])
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

onMounted(() => Promise.all([loadProjects(), loadKnowledge(), loadMetrics(), loadReadiness()]))
</script>

<template>
  <div class="shell">
    <header>
      <button class="knowledge-toggle" @click="showKnowledgeManager = !showKnowledgeManager">知识库管理</button>
      <div class="brand-mark">绿</div>
      <div>
        <strong>绿智顾问</strong>
        <span>Green Intelligence Advisor</span>
      </div>
      <div class="header-tag">智库 + AI · {{ knowledge.length }} 个已核验来源</div>
    </header>

    <main>
      <section v-if="showKnowledgeManager" class="knowledge-manager">
        <div class="knowledge-heading">
          <div>
            <p class="eyebrow">KNOWLEDGE BASE</p>
            <h2>知识库管理</h2>
            <p>官方来源受保护；自定义知识可新增和删除，并立即参与后续风险检索。</p>
          </div>
          <button class="small" @click="showKnowledgeManager = false">关闭</button>
        </div>
        <div class="knowledge-layout">
          <div>
            <input v-model="knowledgeSearch" class="knowledge-search" placeholder="搜索标题、机构、主题或地区" />
            <div class="knowledge-items">
              <article v-for="item in filteredKnowledge" :key="item.id">
                <div>
                  <strong>{{ item.title }}</strong>
                  <span>{{ item.authority }} · {{ item.topic }} · {{ item.region }}</span>
                  <p>{{ item.content }}</p>
                  <a :href="item.source_url" target="_blank" rel="noreferrer">查看来源</a>
                </div>
                <div class="knowledge-actions">
                  <span v-if="item.protected" class="protected-badge">官方保护</span>
                  <button v-else class="knowledge-delete" :disabled="busy" @click="deleteKnowledge(item)">删除</button>
                </div>
              </article>
            </div>
          </div>
          <form class="knowledge-form" @submit.prevent="createKnowledge">
            <h3>新增自定义知识</h3>
            <label>标题<input v-model="knowledgeForm.title" required minlength="2" /></label>
            <label>来源机构<input v-model="knowledgeForm.authority" required minlength="2" /></label>
            <div class="knowledge-form-row">
              <label>主题<input v-model="knowledgeForm.topic" required /></label>
              <label>地区<input v-model="knowledgeForm.region" required /></label>
            </div>
            <label>来源链接<input v-model="knowledgeForm.source_url" required type="url" /></label>
            <label>发布日期<input v-model="knowledgeForm.published_at" placeholder="YYYY-MM-DD" /></label>
            <label>内容摘要<textarea v-model="knowledgeForm.content" required minlength="20" rows="6"></textarea></label>
            <button class="primary" :disabled="busy" type="submit">保存知识条目</button>
          </form>
        </div>
      </section>
      <section class="hero">
        <div>
          <p class="eyebrow">企业绿色转型与出海合规 AI 工作台</p>
          <h1>让企业资料变成<br><em>可解释的行动方案</em></h1>
          <p class="intro">结构化企业信息、识别资料缺口、评估绿色成熟度，并生成可供专业顾问审核的 90 天计划。</p>
        </div>
        <div class="hero-card">
          <span>演示场景</span>
          <strong>储能制造企业进入英国市场</strong>
          <p>系统不会把“资料缺失”误判为“不合规”，高风险结论均进入人工审核。</p>
        </div>
      </section>

      <p v-if="error" class="error">{{ error }}</p>

      <section class="monitor-strip">
        <div>
          <span>AI运行模式</span>
          <strong>{{ metrics.current_mode === 'dify' ? 'Dify 工作流' : '本地可解释模式' }}</strong>
          <small>MySQL {{ readiness.database }} · Redis {{ readiness.redis }}</small>
        </div>
        <div><span>累计运行</span><strong>{{ metrics.total_runs }}</strong><small>抽取与诊断任务</small></div>
        <div><span>成功率</span><strong>{{ metrics.success_rate }}%</strong><small>成功 {{ metrics.successful_runs }} 次</small></div>
        <div><span>平均耗时</span><strong>{{ metrics.average_latency_ms }} ms</strong><small>降级 {{ metrics.degraded_runs }} 次</small></div>
      </section>

      <section class="evaluation-panel">
        <div>
          <span>场景化质量评测</span>
          <strong>{{ evaluation ? `${evaluation.passed_cases}/${evaluation.total_cases} 通过` : '30条 · 5类场景' }}</strong>
          <small>覆盖抽取、检索、缺失信息、资料冲突和报告生成</small>
        </div>
        <div v-if="evaluation" class="evaluation-categories">
          <span v-for="(item, name) in evaluation.by_category" :key="name">
            {{ name }} {{ item.pass_rate }}%
          </span>
        </div>
        <div v-if="evaluation?.failures.length" class="evaluation-failures">
          待优化：{{ evaluation.failures.slice(0, 3).map(item => `${item.id} ${item.reason}`).join('；') }}
        </div>
        <button class="secondary" :disabled="evaluating" @click="runEvaluation">
          {{ evaluating ? '评测运行中…' : '运行30条评测' }}
        </button>
      </section>

      <div class="workspace">
        <aside>
          <div class="aside-title">
            <span>诊断项目</span>
            <button class="small" @click="current = null">＋ 新建</button>
          </div>
          <div class="project-filters">
            <input v-model="projectSearch" placeholder="搜索企业或项目" />
            <select v-model="projectStatusFilter">
              <option value="all">全部状态</option>
              <option value="draft">草稿</option>
              <option value="profile_ready">画像已确认</option>
              <option value="pending_review">待审核</option>
              <option value="needs_revision">待修改</option>
              <option value="completed">已完成</option>
            </select>
          </div>
          <div
            v-for="project in filteredProjects"
            :key="project.id"
            class="project-item"
            :class="{ active: current?.id === project.id }"
            @click="openProject(project.id)"
          >
            <div>
              <span>{{ project.company_name }}</span>
            <small>{{ project.target_market }} · {{ statusText[project.status] || project.status }}</small>
            </div>
            <button class="project-delete" title="删除项目" :disabled="busy" @click.stop="deleteProject(project)">×</button>
          </div>
          <p v-if="projects.length && !filteredProjects.length" class="empty">没有符合条件的项目</p>
          <p v-if="!projects.length" class="empty">还没有项目，先运行右侧演示诊断。</p>
        </aside>

        <section v-if="!current" class="panel form-panel">
          <div class="section-heading">
            <div>
              <p class="eyebrow">STEP 01</p>
              <h2>建立企业诊断项目</h2>
            </div>
            <span class="pill">已填入演示数据</span>
          </div>

          <div class="form-grid">
            <label>项目名称<input v-model="form.name" /></label>
            <label>企业名称<input v-model="form.company_name" /></label>
            <label>所属行业<input v-model="form.industry" /></label>
            <label>所在地区<input v-model="form.region" /></label>
            <label>目标市场<input v-model="form.target_market" /></label>
            <label class="wide">项目目标<textarea v-model="form.goal" rows="3"></textarea></label>
          </div>

          <h3>已有能力与资料</h3>
          <div class="checks">
            <label><input v-model="form.profile.annual_energy_data" type="checkbox" /> 年度能源数据</label>
            <label><input v-model="form.profile.carbon_inventory" type="checkbox" /> 温室气体盘查</label>
            <label><input v-model="form.profile.eco_design" type="checkbox" /> 生态设计机制</label>
            <label><input v-model="form.profile.supplier_code" type="checkbox" /> 供应商环境准则</label>
            <label><input v-model="form.profile.esg_policy" type="checkbox" /> ESG / 环境制度</label>
            <label><input v-model="form.profile.target_market_requirements" type="checkbox" /> 目标市场要求清单</label>
          </div>
          <button class="primary" :disabled="busy" @click="createAndAssess">
            {{ busy ? '正在生成诊断…' : '创建项目并运行诊断 →' }}
          </button>
        </section>

        <section v-else class="panel results">
          <div class="print-only report-cover">
            <span>GREEN INTELLIGENCE ADVISOR</span>
            <h1>{{ current.company_name }}<br />绿色转型与出海准备度诊断报告</h1>
            <p>{{ new Date().toLocaleDateString('zh-CN') }}</p>
          </div>
          <div class="section-heading">
            <div>
              <p class="eyebrow">DIAGNOSTIC REPORT</p>
              <h2>{{ current.company_name }}</h2>
              <p>{{ current.industry }} · {{ current.region }} → {{ current.target_market }}</p>
            </div>
            <div class="heading-actions">
              <span class="status">{{ statusText[current.status] || current.status }}</span>
              <button class="small print-button" @click="downloadReport">下载 PDF 报告</button>
            </div>
          </div>
          <p v-if="taskStatus" class="task-status">
            最近任务：{{ taskStatus.operation }} · {{ taskStatus.status }} · {{ taskStatus.latency_ms }}ms · 状态来源 {{ taskStatus.source.toUpperCase() }}
          </p>

          <template v-if="current.assessment">
            <div class="upload-strip">
              <div>
                <strong>补充企业材料</strong>
                <small>支持 TXT、Markdown、PDF、Word、Excel，单文件不超过 10MB</small>
              </div>
              <input type="file" accept=".txt,.md,.pdf,.docx,.xlsx" @change="selectedFile = $event.target.files[0]" />
              <button class="secondary" :disabled="busy || !selectedFile" @click="uploadDocument">上传并解析</button>
              <span v-if="uploadMessage">{{ uploadMessage }}</span>
            </div>
            <p v-if="documents.length" class="document-count">已纳入诊断资料：{{ documents.map(item => item.filename).join('、') }}</p>
            <div class="score-row">
              <div class="score-card main-score">
                <small>绿色成熟度</small>
                <strong>{{ current.assessment.total_score }}<i>/100</i></strong>
                <span>{{ scoreLevel }}</span>
              </div>
              <div class="score-card">
                <small>资料完整度</small>
                <strong>{{ current.assessment.completeness }}<i>%</i></strong>
                <span>待确认 {{ current.assessment.missing_fields.length }} 项</span>
              </div>
              <div class="score-card method">
                <small>评估方式</small>
                <strong>规则 v{{ current.assessment.rule_version }}</strong>
                <span>LLM 理解 · 代码评分 · 人工复核</span>
              </div>
            </div>

            <h3>五维诊断</h3>
            <div class="dimensions">
              <div v-for="item in current.assessment.dimensions" :key="item.key" class="dimension">
                <div><span>{{ item.name }}</span><strong>{{ item.score }}/{{ item.max_score }}</strong></div>
                <div class="bar"><i :style="{ width: `${item.score / item.max_score * 100}%` }"></i></div>
                <small>{{ item.pending.length ? `待确认：${item.pending.join('、')}` : '资料项已完整' }}</small>
              </div>
            </div>

            <template v-if="evidence.length">
              <template v-if="conflicts.length">
                <h3>资料冲突（需人工确认）</h3>
                <div class="conflict-list">
                  <article v-for="conflict in conflicts" :key="conflict.id">
                  <div class="conflict-title">
                    <strong>{{ fieldLabels[conflict.field] || conflict.field }}</strong>
                      <span>{{ conflict.status === 'resolved' ? '已人工解决并重新评分' : '已从评分画像中隔离' }}</span>
                    </div>
                    <div v-for="item in conflict.evidence" :key="`${item.filename}-${item.excerpt}`" class="conflict-evidence">
                      <b>{{ item.value === false ? '否定' : '肯定' }}</b>
                      <p>“{{ item.excerpt }}”</p>
                      <small>{{ item.filename }}</small>
                      <button
                        v-if="conflict.status === 'open' && conflict.field !== 'general_data_conflict'"
                        class="resolve-button"
                        :disabled="busy"
                        @click="resolveConflict(conflict, item)"
                      >采纳此事实</button>
                    </div>
                  </article>
                </div>
              </template>
              <h3>资料抽取证据</h3>
              <div class="evidence-list">
                <article v-for="item in evidence" :key="`${item.field}-${item.excerpt}`">
                  <div><strong>{{ item.field }}</strong><span>{{ Math.round(item.confidence * 100) }}% 置信度</span></div>
                  <p>“{{ item.excerpt }}”</p>
                  <small>{{ item.filename }} · {{ item.method }}</small>
                </article>
              </div>
            </template>

            <h3>优先风险</h3>
            <div class="risk-list">
              <article v-for="risk in current.assessment.risks" :key="risk.title">
                <span class="risk-level" :class="`level-${risk.level}`">{{ risk.level }}</span>
                <div>
                  <strong>{{ risk.title }}</strong>
                  <p>{{ risk.basis }}</p>
                  <small>建议：{{ risk.recommendation }}</small>
                  <div v-if="risk.citations?.length" class="citations">
                    <span>知识依据</span>
                    <a
                      v-for="citation in risk.citations"
                      :key="citation.id"
                      :href="citation.source_url"
                      target="_blank"
                      rel="noreferrer"
                    >
                      {{ citation.authority }}｜{{ citation.title }}（匹配 {{ citation.score }}）
                    </a>
                  </div>
                  <div v-else class="insufficient">知识库依据不足，必须由顾问确认</div>
                </div>
                <span v-if="risk.requires_review" class="review-flag">{{ risk.evidence_status === 'supported' ? '需人工确认' : '依据不足' }}</span>
              </article>
            </div>

            <h3>90 天行动计划</h3>
            <div class="timeline">
              <article v-for="item in current.assessment.action_plan" :key="item.phase">
                <span>{{ item.phase }}</span>
                <strong>{{ item.task }}</strong>
                <p>{{ item.owner }}</p>
                <small>交付物：{{ item.deliverable }}</small>
              </article>
            </div>

            <div class="review-box">
              <div>
                <p class="eyebrow">HUMAN IN THE LOOP</p>
                <h3>顾问审核</h3>
                <p>最终报告只使用已经审核或满足质量条件的内容。</p>
              </div>
              <textarea v-model="reviewComment" rows="3"></textarea>
              <div class="review-actions">
                <button class="secondary" :disabled="busy" @click="review('needs_revision')">退回修改</button>
                <button class="primary" :disabled="busy" @click="review('approved')">确认并完成报告</button>
              </div>
            </div>
            <p class="print-only disclaimer">本报告为 AI 辅助分析演示，不构成法律、审计、认证或投资意见，最终结论需由专业顾问复核。</p>
          </template>
        </section>
      </div>
    </main>

    <footer>AI 辅助分析演示，不构成法律、审计、认证或投资意见。</footer>
  </div>
</template>
