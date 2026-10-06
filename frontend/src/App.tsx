import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  AlertTriangle, ArrowRight, Building2,
  CalendarDays, ChevronDown, Clock3, CreditCard, Database, FileCheck2, Pencil,
  FileText, Filter, LayoutDashboard, Menu, Search, Settings2,
  ShieldCheck, SlidersHorizontal, Wallet, X,
} from 'lucide-react'
import {
  Area, AreaChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

type Page = 'Dashboard' | 'Faturas' | 'Faturas pendentes' | 'Documentos importados' | 'Processos SEI' | 'Alertas' | 'Saldos' | 'Auditoria' | 'Configurações'
type SettingsTab = 'Geral' | 'Regras administrativas'
type ApiHealth = { status: string; database: string; database_engine: string }
type MonitorHealth = { enabled: boolean; running: boolean; indexed?: number; parsed?: number; refreshed?: number; skipped?: number; errors?: number }
type ProcessRow = { id: string; process_number: string; verification_state: string; object_description: string | null; created_at: string }
type AlertRow = { id: string; alert_type: string; severity: string; status: string; summary: string; created_at: string }
type CatalogSummary = {
  organization_count: number
  material_count: number
  service_count: number
  supplier_count: number
  organizations: { id: number; sigla: string; nome: string }[]
  materials: { id: number; nome: string; categoria: string }[]
  services: { id: number; nome: string }[]
  fornecedores: { id: number; nome: string; servico_associado: string }[]
  catalog_source: string
  catalog_verified: boolean
}
type MoneyAggregate = { name: string; amount: string; documents: number }
type MonthlyAggregate = { month: string; month_number: number; amount: string; documents: number }
type FinancialCandidateSummary = {
  confirmed_spending: boolean
  included_term_documents: number
  total_candidate_amount: string
  ambiguous_term_documents: number
  documents_without_term_amount: number
  unassigned_organization_documents: number
  by_organization: MoneyAggregate[]
  by_month: MonthlyAggregate[]
  by_service: MoneyAggregate[]
  by_material: MoneyAggregate[]
  by_supplier?: MoneyAggregate[]
}

const navItems: { label: Page; icon: typeof LayoutDashboard; section?: string }[] = [
  { label: 'Dashboard', icon: LayoutDashboard, section: 'VISÃO GERAL' },
  { label: 'Faturas', icon: FileText },
  { label: 'Documentos importados', icon: Database },
  { label: 'Processos SEI', icon: FileCheck2, section: 'GESTÃO' },
  { label: 'Alertas', icon: AlertTriangle },
  { label: 'Saldos', icon: Wallet },
  { label: 'Auditoria', icon: ShieldCheck, section: 'SISTEMA' },
  { label: 'Configurações', icon: Settings2 },
]

type AppRoute = { page: Page; settingsTab: SettingsTab }

const routesByPath: Record<string, AppRoute> = {
  '/dashboard': { page: 'Dashboard', settingsTab: 'Geral' },
  '/faturas': { page: 'Faturas', settingsTab: 'Geral' },
  '/faturas/pendentes': { page: 'Faturas pendentes', settingsTab: 'Geral' },
  '/documentos-importados': { page: 'Documentos importados', settingsTab: 'Geral' },
  '/processos-sei': { page: 'Processos SEI', settingsTab: 'Geral' },
  '/alertas': { page: 'Alertas', settingsTab: 'Geral' },
  '/saldos': { page: 'Saldos', settingsTab: 'Geral' },
  '/auditoria': { page: 'Auditoria', settingsTab: 'Geral' },
  '/configuracoes': { page: 'Configurações', settingsTab: 'Geral' },
  '/configuracoes/regras-administrativas': { page: 'Configurações', settingsTab: 'Regras administrativas' },
}

function resolveAppRoute(pathname: string): AppRoute {
  const normalizedPath = pathname.toLowerCase().replace(/\/+$/, '') || '/'
  return routesByPath[normalizedPath] ?? routesByPath['/dashboard']
}

function pathForPage(page: Page, settingsTab: SettingsTab): string {
  if (page === 'Configurações' && settingsTab === 'Regras administrativas') {
    return '/configuracoes/regras-administrativas'
  }
  if (page === 'Faturas pendentes') return '/faturas/pendentes'
  const pagePaths: Record<Exclude<Page, 'Faturas pendentes'>, string> = {
    Dashboard: '/dashboard',
    Faturas: '/faturas',
    'Documentos importados': '/documentos-importados',
    'Processos SEI': '/processos-sei',
    Alertas: '/alertas',
    Saldos: '/saldos',
    Auditoria: '/auditoria',
    Configurações: '/configuracoes',
  }
  return pagePaths[page]
}

const money = (value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value)
const formatMoney = (value: number) => money(value)
const formatCompactMoney = (value: number) => new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 }).format(value)

function App() {
  const initialRoute = resolveAppRoute(window.location.pathname)
  const [page, setPage] = useState<Page>(initialRoute.page)
  const [settingsTab, setSettingsTab] = useState<SettingsTab>(initialRoute.settingsTab)
  const [expandedMenus, setExpandedMenus] = useState({ invoices: initialRoute.page === 'Faturas pendentes', settings: initialRoute.page === 'Configurações' })
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [apiHealth, setApiHealth] = useState<ApiHealth | null>(null)
  const [monitorHealth, setMonitorHealth] = useState<MonitorHealth | null>(null)
  const [catalogSummary, setCatalogSummary] = useState<CatalogSummary | null>(null)

  const navigateToPage = (nextPage: Page, nextSettingsTab = settingsTab) => {
    const nextPath = pathForPage(nextPage, nextSettingsTab)
    if (window.location.pathname !== nextPath) window.history.pushState({}, '', nextPath)
    setPage(nextPage)
    if (nextPage === 'Configurações') setSettingsTab(nextSettingsTab)
  }

  useEffect(() => {
    const syncRoute = () => {
      const route = resolveAppRoute(window.location.pathname)
      const canonicalPath = pathForPage(route.page, route.settingsTab)
      if (window.location.pathname !== canonicalPath) window.history.replaceState({}, '', canonicalPath)
      setPage(route.page)
      setSettingsTab(route.settingsTab)
      setExpandedMenus((current) => ({
        invoices: route.page === 'Faturas pendentes' || current.invoices,
        settings: route.page === 'Configurações' || current.settings,
      }))
    }
    syncRoute()
    window.addEventListener('popstate', syncRoute)
    return () => window.removeEventListener('popstate', syncRoute)
  }, [])

  useEffect(() => {
    let active = true
    const checkApi = async () => {
      try {
        const [healthResponse, monitorResponse, catalogResponse] = await Promise.all([
          fetch('/api/v1/health'),
          fetch('/api/v1/monitor/status'),
          fetch('/api/v1/catalog/summary'),
        ])
        if (!healthResponse.ok) throw new Error('API indisponível')
        if (!monitorResponse.ok) throw new Error('Monitor indisponível')
        if (!catalogResponse.ok) throw new Error('Catálogo indisponível')

        const health = await healthResponse.json() as ApiHealth
        const monitor = await monitorResponse.json() as MonitorHealth
        const catalog = await catalogResponse.json() as CatalogSummary

        if (active) {
          setApiHealth(health)
          setMonitorHealth(monitor)
          setCatalogSummary(catalog)
        }
      } catch {
        if (active) {
          setApiHealth(null)
          setMonitorHealth(null)
          setCatalogSummary(null)
        }
      }
    }
    void checkApi()
    const timer = window.setInterval(checkApi, 30_000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])

  const greeting = new Intl.DateTimeFormat('pt-BR', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' }).format(new Date())

  return (
    <div className="app-shell">
      {sidebarOpen && <button className="mobile-scrim" aria-label="Fechar menu" onClick={() => setSidebarOpen(false)} />}
      <aside className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="brand-lockup">
          <div className="brand-mark"><span>S</span><i /></div>
          <div className="brand-copy"><strong>SIG<span>·</span>ES</strong><small>GESTÃO INTELIGENTE</small></div>
          <button className="icon-button sidebar-close" aria-label="Fechar menu" onClick={() => setSidebarOpen(false)}><X size={18} /></button>
        </div>
        <div className="workspace-switcher"><div className="workspace-seal"><Building2 size={17} /></div><div><strong>Instância local</strong><span>{apiHealth ? 'Banco conectado' : 'Banco indisponível'}</span></div></div>
        <nav className="main-nav" aria-label="Navegação principal">
          {navItems.map(({ label, icon: Icon, section }, index) => <div key={label}>
            {section && <div className={`nav-section ${index ? 'nav-section-spaced' : ''}`}>{section}</div>}
            <button className={`nav-link ${page === label || (label === 'Faturas' && page === 'Faturas pendentes') ? 'nav-link-active' : ''}`} aria-expanded={label === 'Faturas' ? expandedMenus.invoices : label === 'Configurações' ? expandedMenus.settings : undefined} onClick={() => {
              navigateToPage(label)
              if (label === 'Faturas') setExpandedMenus((current) => ({ ...current, invoices: page === 'Faturas' ? !current.invoices : true }))
              if (label === 'Configurações') setExpandedMenus((current) => ({ ...current, settings: page === 'Configurações' ? !current.settings : true }))
              setSidebarOpen(false)
            }}>
              <Icon size={18} strokeWidth={page === label ? 2.2 : 1.8} /><span>{label}</span>
              {(label === 'Faturas' || label === 'Configurações') && <ChevronDown className={((label === 'Faturas' && expandedMenus.invoices) || (label === 'Configurações' && expandedMenus.settings)) ? 'nav-chevron-open' : ''} size={14} />}
            </button>
            {label === 'Faturas' && expandedMenus.invoices && <button className={`nav-link nav-link-nested ${page === 'Faturas pendentes' ? 'nav-link-active' : ''}`} onClick={() => { navigateToPage('Faturas pendentes'); setExpandedMenus((current) => ({ ...current, invoices: true })); setSidebarOpen(false) }}><Clock3 size={16} /><span>Pendentes</span></button>}
            {label === 'Configurações' && expandedMenus.settings && <div className="nav-submenu" aria-label="Abas de configurações">
              {(['Geral', 'Regras administrativas'] as const).map((tab) => <button key={tab} className={`nav-link nav-link-nested ${page === 'Configurações' && settingsTab === tab ? 'nav-link-active' : ''}`} onClick={() => { navigateToPage('Configurações', tab); setSidebarOpen(false) }}>{tab === 'Geral' ? <Settings2 size={14} /> : <SlidersHorizontal size={14} />}<span>{tab}</span></button>)}
            </div>}
          </div>)}
        </nav>
        <div className="sidebar-bottom">
          <div className="environment-access-note"><ShieldCheck size={15} /><span>Ambiente local · sem autenticação de usuário</span></div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <button className="icon-button mobile-menu" aria-label="Abrir menu" onClick={() => setSidebarOpen(true)}><Menu size={20} /></button>
          <div className="breadcrumbs"><span>Ambiente local</span><span className="crumb-slash">/</span><strong>{page}</strong></div>
        </header>

        <div className="page-content">
          <div className="environment-banner"><span className="environment-dot" /><strong>Ambiente local · não homologado</strong><span>Dados extraídos são candidatos; pagamento, saldo e existência no SEI não estão confirmados.</span><span className={`api-connection ${apiHealth ? 'api-online' : 'api-offline'}`}><i />{apiHealth ? `API + ${apiHealth.database_engine}: conectados` : 'API/banco: desconectados'}</span>{monitorHealth?.running && <span className="api-connection api-online"><i />Monitor ativo · {monitorHealth.parsed ?? 0} arquivos processados desde a inicialização</span>}</div>
          <div className="page-heading">
            <div><div className="eyebrow"><CalendarDays size={14} /> {greeting}</div><h1>{page === 'Dashboard' ? 'Visão geral' : page}</h1><p>{page === 'Configurações' && settingsTab === 'Regras administrativas' ? 'Rascunhos de regras por fornecedor e material; não são oficiais nem aplicados automaticamente.' : pageDescriptions[page]}</p></div>
          </div>

          {page === 'Dashboard' ? <Dashboard catalogSummary={catalogSummary} /> : page === 'Faturas' || page === 'Faturas pendentes' ? <InvoiceDocumentsPage pendingOnly={page === 'Faturas pendentes'} catalogSummary={catalogSummary} /> : page === 'Documentos importados' ? <ImportedDataPage /> : page === 'Configurações' ? <SettingsPage activeTab={settingsTab} onChangeTab={(tab) => navigateToPage('Configurações', tab)} catalogSummary={catalogSummary} /> : <SectionPage page={page} />}

          <footer className="page-footer"><span><i /> {apiHealth ? `API e ${apiHealth.database_engine} conectados` : 'API não conectada'}</span><span>{page === 'Dashboard' ? 'Valores candidatos · sem confirmação financeira' : page === 'Documentos importados' ? 'Campos extraídos com proveniência · revisão humana necessária' : 'Consulte a origem e o estado de verificação de cada registro'}{monitorHealth?.running ? ` · ${monitorHealth.indexed ?? 0} novos/alterados indexados` : ''}</span></footer>
        </div>
      </main>

    </div>
  )
}

const pageDescriptions: Record<Page, string> = {
  Dashboard: 'Indicadores e atividade recente.', Faturas: 'PDFs locais organizados por fornecedor, material, órgão ou serviço; valores permanecem candidatos.',
  'Faturas pendentes': 'Documentos em quarentena aguardando revisão dos candidatos e conclusão do checklist.',
  'Documentos importados': 'Arquivos e campos candidatos lidos localmente para conferência humana.',
  'Processos SEI': 'Processos registrados localmente; o SIG-ES não consulta nem valida o SEI.',
  Alertas: 'Alertas persistidos na base; geração e reconhecimento automático dependem de regras aprovadas.', Saldos: 'Fonte de saldos ainda não configurada.',
  Auditoria: 'Ações selecionadas são persistidas; consulta completa e identidade do responsável ainda não estão disponíveis.', Configurações: 'Estado do ambiente e rascunhos de regras administrativas.',
}

type DashboardProps = {
  catalogSummary: CatalogSummary | null
}

function Dashboard({ catalogSummary }: DashboardProps) {
  const [financial, setFinancial] = useState<FinancialCandidateSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const financialResponse = await fetch('/api/v1/dashboard/financial-candidates')
        if (!financialResponse.ok) throw new Error('API indisponível')
        const nextFinancial = await financialResponse.json() as FinancialCandidateSummary
        if (active) {
          setFinancial(nextFinancial)
          setError('')
        }
      } catch {
        if (active) setError('Não foi possível carregar a ingestão local; confira a API.')
      } finally {
        if (active) setLoading(false)
      }
    }
    void load()
    const timer = window.setInterval(load, 30_000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])

  const organizationChart = (financial?.by_organization ?? [])
    .map((item) => ({ ...item, value: Number(item.amount) }))
    .filter((item) => item.value > 0)
  const organizationTotal = organizationChart.reduce((total, item) => total + item.value, 0)
  const monthChart = (financial?.by_month ?? []).map((item) => ({ ...item, value: Number(item.amount) }))
  const organizationColors = ['#4268e8', '#22ae91', '#8d7be6', '#efa93d', '#51a3d5', '#d27683', '#7ca35a', '#c36bab', '#3e9eae', '#bd8050', '#778398']

  return <>
    <section className="kpi-grid" aria-label="Resumo financeiro candidato">
      <LiveKpi title="Total identificado nos termos" value={financial ? formatMoney(Number(financial.total_candidate_amount)) : '—'} detail="valor candidato · não confirmado" icon={CreditCard} tone="blue" />
      <LiveKpi title="Documentos com valor único" value={financial?.included_term_documents} detail="termo de recebimento" icon={FileText} tone="purple" />
      <LiveKpi title="Termos ambíguos excluídos" value={financial?.ambiguous_term_documents} detail="mais de um valor distinto" icon={AlertTriangle} tone="amber" />
      <LiveKpi title="Sem órgão único" value={financial?.unassigned_organization_documents} detail="fora do gráfico por órgão" icon={Building2} tone="green" />
    </section>

    <div className="filter-row live-filter-row">
      <div className="filter-label"><Filter size={15} /><span>ANÁLISE DOS TERMOS</span></div>
      <span className="live-filter-pill"><Database size={14} /> Fonte local</span>
      <span className="live-filter-pill"><ShieldCheck size={14} /> Estimativa candidata · não é gasto confirmado</span>
      <span className="live-filter-summary">Catálogo de referência não verificado · {catalogSummary?.organization_count ?? '—'} órgãos · {catalogSummary?.service_count ?? '—'} serviços · {catalogSummary?.material_count ?? '—'} materiais</span>
    </div>

    {error && <div className="financial-load-error" role="alert">{error} · Os gráficos financeiros não foram atualizados.</div>}
    {loading && <div className="financial-loading">Atualizando os valores extraídos dos termos…</div>}
    <section className="finance-summary-grid" aria-label="Valores candidatos por órgão e por mês">
      <article className="panel live-chart-panel">
        <div className="panel-heading"><div><h2>Valor por órgão</h2><p>Soma de termos únicos por documento</p></div><span className="chart-action">Termo SEI</span></div>
        <div className="organization-spend-wrap">
          <div className="organization-spend-donut"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={organizationChart} dataKey="value" nameKey="name" innerRadius={49} outerRadius={71} paddingAngle={2} stroke="none">{organizationChart.map((item) => <Cell key={item.name} fill={organizationColors[(financial?.by_organization.findIndex((org) => org.name === item.name) ?? 0) % organizationColors.length]} />)}</Pie><Tooltip formatter={(value) => [formatMoney(Number(value)), 'Valor candidato']} contentStyle={{ border: '1px solid #edf0f5', borderRadius: 10, fontSize: 11 }} /></PieChart></ResponsiveContainer><div className="donut-center"><strong>{formatCompactMoney(organizationTotal)}</strong><span>órgãos associados</span></div></div>
          <div className="organization-spend-legend">{(financial?.by_organization ?? []).map((item, index) => <div key={item.name}><span><i style={{ background: organizationColors[index % organizationColors.length] }} />{item.name}</span><strong>{formatMoney(Number(item.amount))}</strong></div>)}</div>
        </div>
        <div className="chart-footnote"><span>Exclui documentos sem órgão único</span></div>
      </article>
      <article className="panel live-chart-panel monthly-trend-panel">
        <div className="panel-heading"><div><h2>Evolução mensal</h2><p>Competência inferida do caminho relativo do arquivo</p></div><span className="chart-action">Inferida</span></div>
        <div className="area-chart monthly-chart-area"><ResponsiveContainer width="100%" height="100%"><AreaChart data={monthChart} margin={{ top: 12, right: 16, bottom: 4, left: 0 }}>
          <defs><linearGradient id="monthlyCandidateFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#22ae91" stopOpacity={0.2} /><stop offset="100%" stopColor="#22ae91" stopOpacity={0.02} /></linearGradient></defs>
          <CartesianGrid vertical={false} stroke="#edf0f5" strokeDasharray="4 5" />
          <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: '#929caf', fontSize: 10 }} interval={0} />
          <YAxis axisLine={false} tickLine={false} tick={{ fill: '#929caf', fontSize: 9 }} tickFormatter={(value: number) => formatCompactMoney(value)} />
          <Tooltip formatter={(value) => [formatMoney(Number(value)), 'Valor candidato do termo']} contentStyle={{ border: '1px solid #edf0f5', borderRadius: 10, fontSize: 11 }} />
          <Area type="monotone" dataKey="value" stroke="#22ae91" strokeWidth={2.5} fill="url(#monthlyCandidateFill)" activeDot={{ r: 4, strokeWidth: 2, stroke: '#fff' }} />
        </AreaChart></ResponsiveContainer></div>
        <div className="chart-footnote"><span>{financial?.included_term_documents ?? 0} documentos únicos · mês pelo nome do arquivo</span></div>
      </article>
    </section>

    <section className="finance-category-grid" aria-label="Valores candidatos por serviço, material e fornecedor">
      <article className="panel live-chart-panel finance-category-panel">
        <div className="panel-heading"><div><h2>Serviços</h2><p>{financial?.by_service.length ?? catalogSummary?.service_count ?? 0} itens no catálogo/agregação</p></div><span className="chart-action">BRL</span></div>
        <CandidateBars items={financial?.by_service ?? []} emptyLabel="Sem associações seguras" />
        <div className="chart-footnote"><span>Valor zero = sem associação segura, não gasto zero</span></div>
      </article>
      <article className="panel live-chart-panel finance-category-panel">
        <div className="panel-heading"><div><h2>Materiais</h2><p>{financial?.by_material.length ?? catalogSummary?.material_count ?? 0} itens no catálogo/agregação</p></div><span className="chart-action">BRL</span></div>
        <CandidateBars items={financial?.by_material ?? []} compact emptyLabel="Sem associações seguras" />
        <div className="chart-footnote"><span>Valor zero = sem associação segura, não gasto zero</span></div>
      </article>
      <article className="panel live-chart-panel finance-category-panel">
        <div className="panel-heading"><div><h2>Fornecedores</h2><p>{financial?.by_supplier?.length ?? catalogSummary?.supplier_count ?? 0} itens no catálogo/agregação</p></div><span className="chart-action">BRL</span></div>
        <CandidateBars items={financial?.by_supplier ?? []} compact emptyLabel="Sem associações seguras" />
        <div className="chart-footnote"><span>Valor zero = sem associação segura, não gasto zero</span></div>
      </article>
    </section>
  </>
}

function LiveKpi({ title, value, detail, icon: Icon, tone }: { title: string; value: number | string | undefined; detail: string; icon: typeof FileText; tone: string }) {
  const formattedValue = typeof value === 'number' ? value.toLocaleString('pt-BR') : value ?? '—'
  return <article className="kpi-card"><div className="kpi-top"><div className={`kpi-icon ${tone}`}><Icon size={17} /></div></div><span className="kpi-title">{title}</span><strong className="kpi-value">{formattedValue}</strong><div className="kpi-bottom"><span className="kpi-note">{detail}</span></div></article>
}

function CandidateBars({ items, compact = false, emptyLabel }: { items: MoneyAggregate[]; compact?: boolean; emptyLabel: string }) {
  const maximum = Math.max(0, ...items.map((item) => Number(item.amount)))
  if (items.length === 0) return <div className="candidate-bars-empty">{emptyLabel}</div>

  return <div className={`candidate-bars-list ${compact ? 'candidate-bars-compact' : ''}`}>
    {items.map((item) => {
      const amount = Number(item.amount)
      const width = maximum > 0 ? Math.max(amount > 0 ? 2 : 0, amount / maximum * 100) : 0
      return <div className="candidate-bar-row" key={item.name} title={`${item.name}: ${formatMoney(amount)} · ${item.documents} documentos`}>
        <span className="candidate-bar-name">{item.name}</span>
        <span className="candidate-bar-track"><i style={{ width: `${width}%` }} /></span>
        <strong className="candidate-bar-value">{formatMoney(amount)}</strong>
      </div>
    })}
  </div>
}

type ImportSummary = {
  source_key: string
  documents: number
  candidates: number
  pending_review: number
  document_states: Record<string, number>
  candidate_fields: Record<string, number>
  directory_hints: { relative_path: string; documents: number }[]
  extensions: Record<string, number>
  all_extractions_unconfirmed: boolean
}

type CandidateRecord = {
  id: string
  relative_path: string
  field_name: string
  raw_value: string
  normalized_value: string | null
  amount_basis: 'gross' | 'net' | 'unspecified' | null
  amount_role: AmountRole | null
  extraction_method: string
  evidence_location: string | null
  review_state: string
}

type InvoiceDocumentCard = {
  id: string
  relative_path: string
  filename: string
  processing_state: string
  group_by: 'supplier' | 'material' | 'organization' | 'service'
  group_name: string
  supplier: string | null
  organization: string | null
  service_associated: string | null
  material: string | null
  process_number: string | null
  process_ambiguous: boolean
  due_date: string | null
  amount: string | null
  amount_source: string | null
  amount_ambiguous: boolean
  amount_evidence_location: string | null
  amount_candidates: InvoiceAmountCandidate[]
  invoice_amount_candidates: InvoiceAmountCandidate[]
  term_amount_candidates: InvoiceAmountCandidate[]
  amount_comparison: 'different' | 'basis_conflict' | 'same' | 'incomplete' | 'ambiguous'
  editable_candidates: CandidateRecord[]
  pending_review: boolean
  invoice_workflow_state: 'quarantined' | 'invoices'
  release_ready: boolean
  release_checks: { key: string; label: string; complete: boolean; remaining?: number }[]
  pdf_url: string
}

type InvoiceAmountCandidate = {
  id: string
  field_name: string
  raw_value: string
  normalized_value: string | null
  amount_basis: 'gross' | 'net' | 'unspecified' | null
  amount_role: AmountRole | null
  evidence_location: string | null
  review_state: string
}

type AmountRole = 'unspecified' | 'total_amount' | 'installment_amount' | 'percentage' | 'interest' | 'penalty' | 'fine' | 'discount' | 'tax' | 'fee' | 'unit_price' | 'quantity' | 'other_numeric'

const amountRoleOptions: { value: AmountRole; label: string }[] = [
  { value: 'unspecified', label: 'Ainda não classificado' },
  { value: 'total_amount', label: 'Valor total da fatura ou documento' },
  { value: 'installment_amount', label: 'Valor de parcela' },
  { value: 'percentage', label: 'Percentual ou alíquota (%)' },
  { value: 'interest', label: 'Juros' },
  { value: 'penalty', label: 'Encargo por atraso' },
  { value: 'fine', label: 'Multa' },
  { value: 'discount', label: 'Desconto ou abatimento' },
  { value: 'tax', label: 'Imposto ou tributo' },
  { value: 'fee', label: 'Tarifa ou taxa em dinheiro' },
  { value: 'unit_price', label: 'Preço unitário' },
  { value: 'quantity', label: 'Quantidade ou medida' },
  { value: 'other_numeric', label: 'Outro número (não somar como total)' },
]

type InvoiceDocumentPage = {
  items: InvoiceDocumentCard[]
  page: { limit: number; offset: number; total: number }
  group_by: 'supplier' | 'material' | 'organization' | 'service'
  all_cards_are_unconfirmed_candidates: boolean
}

function normalizeInvoiceDocumentPage(page: InvoiceDocumentPage): InvoiceDocumentPage {
  return {
    ...page,
    items: page.items.map((card) => ({
      ...card,
      amount_candidates: card.amount_candidates ?? [],
      invoice_amount_candidates: card.invoice_amount_candidates ?? card.amount_candidates?.filter((candidate) => candidate.field_name === 'invoice_amount_brl') ?? [],
      term_amount_candidates: card.term_amount_candidates ?? card.amount_candidates?.filter((candidate) => candidate.field_name === 'reimbursement_term_amount_brl') ?? [],
      amount_comparison: card.amount_comparison ?? 'incomplete',
      editable_candidates: card.editable_candidates ?? [],
    })),
  }
}

type ManualFieldDraft = {
  id: string
  fieldName: string
  value: string
  initialValue: string
  sourceCandidateIds: string[]
  allSourceCandidateIds: string[]
  sourceCount: number
  distinctCount: number
  detectedValues: { value: string; normalizedValue: string | null; count: number; evidence: string[]; candidateIds: string[]; amountBasis: 'gross' | 'net' | 'unspecified'; amountRole: AmountRole }[]
  applyToAll: boolean
  amountBasis: 'gross' | 'net' | 'unspecified'
  initialAmountBasis: 'gross' | 'net' | 'unspecified'
  amountRole: AmountRole
  initialAmountRole: AmountRole
}

function InvoiceDocumentsPage({ pendingOnly = false, catalogSummary }: { pendingOnly?: boolean; catalogSummary: CatalogSummary | null }) {
  const [groupBy, setGroupBy] = useState<'supplier' | 'material' | 'organization' | 'service'>('supplier')
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [pageOffset, setPageOffset] = useState(0)
  const [data, setData] = useState<InvoiceDocumentPage | null>(null)
  const [detailCard, setDetailCard] = useState<InvoiceDocumentCard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedCard, setSelectedCard] = useState<InvoiceDocumentCard | null>(null)
  const [manualFieldDrafts, setManualFieldDrafts] = useState<ManualFieldDraft[]>([])
  const [correctionReason, setCorrectionReason] = useState('')
  const [savingCorrection, setSavingCorrection] = useState(false)
  const [savingWorkflow, setSavingWorkflow] = useState(false)
  const [correctionMessage, setCorrectionMessage] = useState('')
  const [revision, setRevision] = useState(0)
  const pageSize = 24

  useEffect(() => {
    let active = true
    const load = async () => {
      setLoading(true)
      try {
        const params = new URLSearchParams({ group_by: groupBy, limit: String(pageSize), offset: String(pageOffset), pending_only: String(pendingOnly) })
        if (search) params.set('search', search)
        const response = await fetch(`/api/v1/invoice-documents?${params.toString()}`)
        if (!response.ok) throw new Error('A API não conseguiu listar os PDFs')
        const result = normalizeInvoiceDocumentPage(await response.json() as InvoiceDocumentPage)
        if (active) {
          setData(result)
          setError('')
        }
      } catch {
        if (active) setError('Não foi possível carregar os PDFs locais. Confira se a API está ativa e com a pasta 2026 configurada.')
      } finally {
        if (active) setLoading(false)
      }
    }
    void load()
    return () => { active = false }
  }, [groupBy, pageOffset, search, pendingOnly, revision])

  const groupedCards = useMemo(() => {
    const groups = new Map<string, InvoiceDocumentCard[]>()
    for (const card of data?.items ?? []) {
      const group = groups.get(card.group_name) ?? []
      group.push(card)
      groups.set(card.group_name, group)
    }
    return [...groups.entries()]
  }, [data])

  const applySearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setPageOffset(0)
    setSearch(searchInput.trim())
  }

  const startCorrection = (card: InvoiceDocumentCard) => {
    setSelectedCard(card)
    const fallbacks: Partial<Record<string, string | null>> = {
      process_number: card.process_ambiguous ? null : card.process_number,
      due_date: card.due_date,
      organization_reference: card.organization,
      service_reference: card.service_associated,
      material_reference: card.material,
      supplier_reference: card.supplier,
    }
    const drafts = INVOICE_REVIEW_FIELDS.map((fieldName): ManualFieldDraft => {
      const candidates = card.editable_candidates.filter((candidate) => candidate.field_name === fieldName)
      const distinctValues = new Map<string, CandidateRecord[]>()
      for (const candidate of candidates) {
        const key = `${candidate.normalized_value ?? candidate.raw_value}|${candidate.amount_basis ?? 'unspecified'}`
        distinctValues.set(key, [...(distinctValues.get(key) ?? []), candidate])
      }
      const detectedValues = [...distinctValues.values()].map((matching) => ({
        value: matching[0].raw_value,
        normalizedValue: matching[0].normalized_value,
        count: matching.length,
        evidence: [...new Set(matching.map((candidate) => candidate.evidence_location ?? 'evidência não localizada'))],
        candidateIds: matching.map((candidate) => candidate.id),
        amountBasis: matching[0].amount_basis ?? 'unspecified',
        amountRole: matching[0].amount_role ?? 'unspecified',
      }))
      const isReferenceField = isCatalogReferenceField(fieldName)
      const candidateValue = detectedValues.length === 1
        ? isReferenceField ? detectedValues[0].normalizedValue ?? detectedValues[0].value : detectedValues[0].value
        : ''
      const initialValue = candidateValue || (candidates.length === 0 ? fallbacks[fieldName] ?? '' : '')
      const amountRoles = new Set(candidates.map((candidate) => candidate.amount_role ?? 'unspecified'))
      const amountBases = new Set(candidates.map((candidate) => candidate.amount_basis ?? 'unspecified'))
      const initialAmountRole = amountRoles.size === 1 ? [...amountRoles][0] : 'unspecified'
      const initialAmountBasis = amountBases.size === 1 ? [...amountBases][0] : 'unspecified'
      const editValue = candidateValueForEdit(fieldName, initialValue, catalogSummary)
      const initialSourceIds = detectedValues.length === 1 ? detectedValues[0].candidateIds : []
      return {
        id: crypto.randomUUID(),
        fieldName,
        value: editValue,
        initialValue: editValue,
        sourceCandidateIds: initialSourceIds,
        allSourceCandidateIds: candidates.map((candidate) => candidate.id),
        sourceCount: candidates.length,
        distinctCount: distinctValues.size,
        detectedValues,
        applyToAll: distinctValues.size === 1 && detectedValues.length === 1,
        amountBasis: initialAmountBasis,
        initialAmountBasis,
        amountRole: initialAmountRole,
        initialAmountRole,
      }
    })
    setManualFieldDrafts(drafts)
    setCorrectionReason('')
    setCorrectionMessage('')
  }

  const reviewFieldsToSave = () => manualFieldDrafts.flatMap((draft) => {
    const valueChanged = draft.value.trim() !== draft.initialValue.trim()
    const amountField = isAmountFieldName(draft.fieldName)
    const classificationEnabled = !amountField || draft.sourceCount <= 1 || draft.applyToAll
    const roleChanged = amountField && classificationEnabled && draft.amountRole !== draft.initialAmountRole
    const basisChanged = amountField && classificationEnabled && draft.amountBasis !== draft.initialAmountBasis
    if (!valueChanged && !roleChanged && !basisChanged) return []
    if (draft.sourceCount === 0 && !draft.value.trim()) return []
    if (draft.sourceCount > 0 && draft.distinctCount > 1 && valueChanged && !draft.applyToAll) return []
    if (draft.sourceCount > 1 && (valueChanged || roleChanged || basisChanged) && !draft.applyToAll) return []
    return [{
      field_name: draft.fieldName,
      ...(draft.value.trim() ? { corrected_value: draft.value.trim() } : {}),
      source_candidate_ids: draft.applyToAll ? draft.allSourceCandidateIds : draft.sourceCandidateIds,
      ...(amountField && classificationEnabled ? { amount_role: draft.amountRole, amount_basis: draft.amountBasis } : {}),
      replace_all: draft.applyToAll,
    }]
  })

  const saveCorrection = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const fields = reviewFieldsToSave()
    if (!selectedCard || fields.length === 0) {
      setCorrectionMessage('Nenhuma alteração pronta para salvar. Confira os campos ambíguos e as opções de aplicação em grupo.')
      return
    }
    setSavingCorrection(true)
    setCorrectionMessage('')
    try {
      const response = await fetch(`/api/v1/source-documents/${selectedCard.id}/propose-review-batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fields, reason: correctionReason }),
      })
      const payload = await response.json() as { detail?: string; created?: number; duplicates?: number; confirmed?: boolean }
      if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : 'Não foi possível salvar as alterações')
      const successMessage = `${payload.created ?? 0} proposta(s) registrada(s); ${payload.duplicates ?? 0} já existia(m). Os dados originais foram preservados e nada foi confirmado.`
      if (pendingOnly) {
        try {
          const params = new URLSearchParams({ group_by: groupBy, limit: String(pageSize), offset: String(pageOffset), pending_only: 'true' })
          if (search) params.set('search', search)
          const refreshResponse = await fetch(`/api/v1/invoice-documents?${params.toString()}`)
          if (!refreshResponse.ok) throw new Error('As propostas foram salvas, mas não foi possível atualizar o checklist.')
          const refreshedPage = normalizeInvoiceDocumentPage(await refreshResponse.json() as InvoiceDocumentPage)
          setData(refreshedPage)
          const refreshedCard = refreshedPage.items.find((card) => card.id === selectedCard.id)
          if (!refreshedCard) throw new Error('As propostas foram salvas, mas o documento não apareceu na fila atualizada.')
          const savedReason = correctionReason
          startCorrection(refreshedCard)
          setCorrectionReason(savedReason)
          setCorrectionMessage(successMessage)
        } catch (refreshError) {
          setCorrectionMessage(refreshError instanceof Error ? refreshError.message : successMessage)
          setRevision((current) => current + 1)
        }
      } else {
        setSelectedCard(null)
        setManualFieldDrafts([])
        setCorrectionMessage(successMessage)
        setRevision((current) => current + 1)
      }
    } catch (saveError) {
      setCorrectionMessage(saveError instanceof Error ? saveError.message : 'Falha ao registrar proposta.')
    } finally {
      setSavingCorrection(false)
    }
  }

  const transitionWorkflow = async (transition: 'release-to-invoices' | 'return-to-review') => {
    if (!selectedCard || correctionReason.trim().length < 5) return
    setSavingWorkflow(true)
    setCorrectionMessage('')
    try {
      const response = await fetch(`/api/v1/source-documents/${selectedCard.id}/${transition}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: correctionReason.trim() }),
      })
      const payload = await response.json() as { detail?: string | { message?: string; missing?: string[] } }
      if (!response.ok) {
        const detail = typeof payload.detail === 'string' ? payload.detail : payload.detail?.missing?.join(' · ') ?? payload.detail?.message
        throw new Error(detail ?? 'Não foi possível atualizar o fluxo da fatura')
      }
      setSelectedCard(null)
      setCorrectionReason('')
      setCorrectionMessage(transition === 'release-to-invoices'
        ? 'Fatura liberada para Faturas após validação dos campos.'
        : 'Fatura devolvida à revisão; os candidatos e o documento foram preservados.')
      setRevision((current) => current + 1)
    } catch (transitionError) {
      setCorrectionMessage(transitionError instanceof Error ? transitionError.message : 'Falha ao atualizar o fluxo da fatura.')
    } finally {
      setSavingWorkflow(false)
    }
  }

  const total = data?.page.total ?? 0
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const currentPage = Math.floor(pageOffset / pageSize) + 1
  const fieldsToSave = reviewFieldsToSave()
  const hasUnconfirmedBulkChoice = manualFieldDrafts.some((draft) => {
    const valueChanged = draft.value.trim() !== draft.initialValue.trim()
    const classificationChanged = draft.amountRole !== draft.initialAmountRole || draft.amountBasis !== draft.initialAmountBasis
    return draft.sourceCount > 1 && (valueChanged || classificationChanged) && !draft.applyToAll
  })
  const updateManualField = (id: string, changes: Partial<ManualFieldDraft>) => {
    setManualFieldDrafts((current) => current.map((draft) => draft.id === id ? { ...draft, ...changes } : draft))
  }

  return <div className="invoice-documents-page">
    <section className="invoice-library-hero">
      <div><span className="eyebrow"><FileCheck2 size={14} /> BIBLIOTECA LOCAL · PDF</span><h2>{pendingOnly ? 'Faturas pendentes de revisão' : 'Faturas por fornecedor, material, órgão ou serviço'}</h2><p>{pendingOnly ? 'Todos os documentos importados aguardam conferência. Correções preservam os candidatos originais e não confirmam valores.' : 'Classifique números como total, parcela, percentual, juros, multa ou outros componentes. A proposta preserva o original e não confirma valores.'}</p></div>
      <div className="invoice-library-count"><strong>{total.toLocaleString('pt-BR')}</strong><span>PDFs encontrados</span></div>
    </section>

    <section className="invoice-library-toolbar">
      <div className="invoice-group-switch" role="group" aria-label="Agrupar PDFs">
        <button className={groupBy === 'supplier' ? 'active' : ''} onClick={() => { setGroupBy('supplier'); setPageOffset(0) }}>Por fornecedor</button>
        <button className={groupBy === 'material' ? 'active' : ''} onClick={() => { setGroupBy('material'); setPageOffset(0) }}>Por material</button>
        <button className={groupBy === 'organization' ? 'active' : ''} onClick={() => { setGroupBy('organization'); setPageOffset(0) }}>Por órgão</button>
        <button className={groupBy === 'service' ? 'active' : ''} onClick={() => { setGroupBy('service'); setPageOffset(0) }}>Por serviço</button>
      </div>
      <form className="invoice-library-search" onSubmit={applySearch}><Search size={16} /><input aria-label="Buscar PDFs" placeholder="Fornecedor, material, SEI ou nome de arquivo" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} /><button type="submit">Buscar</button></form>
      <span className="unverified-note"><ShieldCheck size={15} /> Candidatos · não confirmados</span>
    </section>

    {error ? <section className="panel import-state import-error">{error}</section>
      : loading ? <section className="panel import-state">Carregando PDFs do banco local…</section>
        : groupedCards.length === 0 ? <section className="panel import-state">Nenhum PDF encontrado com esse filtro.</section>
          : <div className="invoice-group-list">{groupedCards.map(([group, cards]) => <section className="invoice-group" key={group}>
            <header className="invoice-group-header"><div><span className="invoice-group-icon">{groupBy === 'supplier' || groupBy === 'organization' ? <Building2 size={16} /> : groupBy === 'material' ? <Database size={16} /> : <Settings2 size={16} />}</span><div><h3>{group}</h3>{groupBy === 'supplier' && cards[0]?.service_associated && <p>{cards[0].service_associated}</p>}</div></div><span>{cards.length} PDF{cards.length === 1 ? '' : 's'}</span></header>
            <div className="invoice-card-grid">{cards.map((card) => {
              const termAmountValues = new Set(card.term_amount_candidates.map((candidate) => candidate.normalized_value ?? candidate.raw_value))
              const termAmount = termAmountValues.size === 1
                ? card.term_amount_candidates.find((candidate) => (candidate.normalized_value ?? candidate.raw_value) === [...termAmountValues][0])?.raw_value ?? 'Identificado no termo'
                : termAmountValues.size > 1
                  ? `${termAmountValues.size} valores no termo · revisar`
                  : 'Não identificado no termo'
              return <article className="invoice-pdf-card" key={card.id}>
                <button type="button" className="invoice-card-summary" onClick={() => setDetailCard(card)} aria-label={`Ver todos os dados da fatura ${card.filename}`}>
                  <div className="invoice-pdf-card-top"><span className="pdf-card-icon"><FileText size={17} /></span><span className="candidate-badge"><i /> {pendingOnly ? 'Em quarentena' : 'Em Faturas'}</span></div>
                  <h4 title={card.filename}>{card.filename}</h4>
                  <div className="invoice-card-primary-value"><span>Valor de referência do termo</span><strong>{termAmount}</strong><small>Termo prioritário · candidato não confirmado</small></div>
                  <div className="invoice-card-keyfacts">
                    <div><span>Processo SEI</span><strong>{card.process_ambiguous ? 'Múltiplos · revisar' : card.process_number ?? 'Não identificado'}</strong></div>
                    <div><span>Vencimento</span><strong>{card.due_date ?? 'Não identificado'}</strong></div>
                  </div>
                  <span className="invoice-card-detail-hint">Selecionar para ver todos os dados <ArrowRight size={13} /></span>
                </button>
              </article>
            })}</div>
          </section>)}</div>}

    {!loading && !error && total > pageSize && <nav className="invoice-pagination" aria-label="Paginação de PDFs"><span>Página {currentPage} de {pageCount} · {total.toLocaleString('pt-BR')} documentos</span><div><button disabled={pageOffset === 0} onClick={() => setPageOffset(Math.max(0, pageOffset - pageSize))}>Anterior</button><button disabled={pageOffset + pageSize >= total} onClick={() => setPageOffset(pageOffset + pageSize)}>Próxima</button></div></nav>}
    {correctionMessage && <div className="correction-feedback" role="status">{correctionMessage}</div>}
    <p className="invoice-library-footnote">Todas as faturas permanecem pendentes até conferência. Os agrupamentos por fornecedor, órgão e serviço dependem de associações únicas no catálogo, candidatos ou caminho do arquivo; materiais vêm das subpastas MATERIAL. Propostas de correção são auditadas e anexadas, nunca sobrescrevem os valores originais.</p>
    {detailCard && <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setDetailCard(null) }}><section className="invoice-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="invoice-detail-title">
      <header className="dialog-top"><div><span className="eyebrow">FATURA · DADOS LOCAIS</span><h2 id="invoice-detail-title">Detalhes da fatura</h2></div><button type="button" className="icon-button" aria-label="Fechar detalhes" onClick={() => setDetailCard(null)}><X size={18} /></button></header>
      <p className="dialog-lead invoice-detail-filename">{detailCard.filename}</p>
      <section className="invoice-detail-facts" aria-label="Informações da fatura">
        <div><span>Agrupamento atual</span><strong>{detailCard.group_name}</strong></div>
        <div><span>Fornecedor reconhecido no catálogo</span><strong>{detailCard.supplier ?? 'Não identificado'}</strong></div>
        <div><span>Órgão</span><strong>{detailCard.organization ?? 'Não identificado'}</strong></div>
        <div><span>Serviço associado</span><strong>{detailCard.service_associated ?? 'Não identificado'}</strong></div>
        <div><span>Material</span><strong>{detailCard.material ?? 'Não identificado'}</strong></div>
        <div><span>Processo SEI candidato</span><strong>{detailCard.process_ambiguous ? 'Múltiplos · revisar' : detailCard.process_number ?? 'Não identificado'}</strong></div>
        <div><span>Vencimento candidato</span><strong>{detailCard.due_date ?? 'Não identificado'}</strong></div>
        <div><span>Estado do processamento</span><strong>{detailCard.processing_state === 'error' ? 'Erro de leitura' : detailCard.processing_state}</strong></div>
        <div><span>Fluxo da fatura</span><strong>{detailCard.invoice_workflow_state === 'quarantined' ? 'Em quarentena · revisão pendente' : 'Na lista Faturas · não é aprovação'}</strong></div>
        <div className="invoice-detail-path"><span>Caminho relativo da origem</span><strong>{detailCard.relative_path}</strong></div>
      </section>
      <section className="invoice-detail-section"><h3>Extrações brutas</h3>{detailCard.amount_candidates.length ? <details className="invoice-candidate-archive"><summary>Ver {detailCard.amount_candidates.length.toLocaleString('pt-BR')} candidatos monetários com página e classificação</summary><div className="invoice-detail-candidate-list">{detailCard.amount_candidates.map((candidate) => <article key={candidate.id}>
        <div><span>{fieldLabel(candidate.field_name)}</span><strong>{candidate.raw_value}</strong></div>
        <small>{amountRoleLabel(candidate.amount_role)}{isNonCurrencyAmountRole(candidate.amount_role) ? '' : ` · ${amountBasisLabel(candidate.amount_basis)}`}{candidate.normalized_value ? ` · normalizado: ${candidate.normalized_value}` : ''}</small>
        <small>Evidência: {candidate.evidence_location ?? 'não localizada'} · Estado: {candidate.review_state}</small>
      </article>)}</div></details> : <p className="invoice-detail-empty">Nenhum candidato numérico disponível.</p>}</section>
      {detailCard.editable_candidates.some((candidate) => !detailCard.amount_candidates.some((amount) => amount.id === candidate.id)) && <section className="invoice-detail-section"><details className="invoice-candidate-archive"><summary>Ver outros {detailCard.editable_candidates.filter((candidate) => !detailCard.amount_candidates.some((amount) => amount.id === candidate.id)).length} campos extraídos</summary><div className="invoice-detail-candidate-list">{detailCard.editable_candidates.filter((candidate) => !detailCard.amount_candidates.some((amount) => amount.id === candidate.id)).map((candidate) => <article key={candidate.id}>
        <div><span>{fieldLabel(candidate.field_name)}</span><strong>{candidate.raw_value}</strong></div><small>Evidência: {candidate.evidence_location ?? 'não localizada'} · Estado: {candidate.review_state}</small>
      </article>)}</div></details></section>}
      <section className="invoice-detail-section"><h3>Resumo de valor e conferência</h3><p className="invoice-detail-note">Valor agregado: {detailCard.amount ?? 'não identificado'} · fonte: {detailCard.amount_source ?? 'não identificada'} · {detailCard.amount_ambiguous ? 'ambíguo' : 'sem ambiguidade detectada'}.</p><p className="invoice-detail-note">Comparação fatura/termo: {detailCard.amount_comparison === 'different' ? 'valores diferentes' : detailCard.amount_comparison === 'basis_conflict' ? 'natureza bruto/líquido divergente' : detailCard.amount_comparison === 'ambiguous' ? 'valores ambíguos' : detailCard.amount_comparison === 'same' ? 'valores iguais' : 'incompleta'} · evidência do valor: {detailCard.amount_evidence_location ?? 'não localizada'}.</p></section>
      {pendingOnly && <section className="workflow-release-checks" aria-label="Requisitos para liberar fatura"><strong>Requisitos para sair da quarentena</strong>{detailCard.release_checks.map((check) => <span key={check.key} className={check.complete ? 'workflow-check-complete' : 'workflow-check-pending'}>{check.complete ? '✓' : '○'} {check.label}{check.remaining ? ` · ${check.remaining} restante(s)` : ''}</span>)}<small>A situação da lista não representa aprovação institucional.</small></section>}
      <div className="invoice-detail-actions"><button type="button" className="button button-secondary" onClick={() => { startCorrection(detailCard); setDetailCard(null) }}><Pencil size={14} /> Editar todos os campos</button><a className="button button-primary invoice-open-pdf" href={detailCard.pdf_url} target="_blank" rel="noreferrer"><FileCheck2 size={15} /> Abrir PDF original <ArrowRight size={14} /></a></div>
    </section></div>}
    {selectedCard && <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !savingCorrection) setSelectedCard(null) }}><form className="candidate-correction-dialog invoice-review-dialog" role="dialog" aria-modal="true" aria-labelledby="correction-title" onSubmit={saveCorrection}>
      <div className="dialog-top"><div><span className="eyebrow">REVISÃO CONSOLIDADA · PROPOSTA NÃO CONFIRMADA</span><h2 id="correction-title">Editar campos da fatura</h2></div><button type="button" className="icon-button" aria-label="Fechar revisão" onClick={() => setSelectedCard(null)}><X size={18} /></button></div>
      <p className="dialog-lead">Documento: {selectedCard.filename}. Os campos identificados vêm preenchidos. O único campo de valor usa o termo como fonte prioritária; valores da fatura ficam apenas para comparação. Este arquivo pode conter várias faturas/termos: o sistema ainda não associa cada termo à respectiva fatura nem calcula rateio automaticamente. O original é preservado.</p>
      {catalogSummary && !catalogSummary.catalog_verified && <div className="catalog-review-note"><ShieldCheck size={14} /> As opções são referências locais não verificadas; selecione apenas quando houver evidência no documento.</div>}
      <div className="invoice-review-fields" aria-label="Campos encontrados para revisão">{manualFieldDrafts.map((draft) => {
        const blocksRelease = reviewFieldBlocksRelease(draft.fieldName, selectedCard.release_checks)
        return <section className={`invoice-review-field ${blocksRelease ? 'invoice-review-field-blocking' : ''}`} key={draft.id} aria-invalid={blocksRelease}>
        <header><div><strong>{draft.fieldName === 'reimbursement_term_amount_brl' ? 'Valor de referência do termo' : fieldLabel(draft.fieldName)}</strong><span>{draft.sourceCount ? `${draft.sourceCount} ocorrência(s) · ${draft.distinctCount} valor(es) distinto(s)` : draft.value ? 'Sugestão do caminho/catálogo · não confirmada' : 'Não identificado'}</span>{blocksRelease && <span className="invoice-review-required">Pendente para mover para Faturas</span>}</div></header>
        {draft.distinctCount > 1 && <label className="correction-field"><span>{draft.fieldName === 'reimbursement_term_amount_brl' ? 'Valores de termo encontrados · selecione um para revisar' : 'Valores diferentes encontrados · selecione um ou digite abaixo'}</span><select value={draft.detectedValues.some((option) => candidateValueForEdit(draft.fieldName, option.normalizedValue ?? option.value, catalogSummary) === draft.value) ? draft.value : ''} onChange={(event) => {
          const selected = draft.detectedValues.find((option) => candidateValueForEdit(draft.fieldName, option.normalizedValue ?? option.value, catalogSummary) === event.target.value)
          if (!selected) return
          updateManualField(draft.id, {
            value: candidateValueForEdit(draft.fieldName, selected.normalizedValue ?? selected.value, catalogSummary),
            sourceCandidateIds: selected.candidateIds,
            amountBasis: selected.amountBasis,
            amountRole: selected.amountRole,
          })
        }}><option value="">Selecione o valor do documento…</option>{draft.detectedValues.map((option) => <option key={`${option.normalizedValue}-${option.amountBasis}`} value={candidateValueForEdit(draft.fieldName, option.normalizedValue ?? option.value, catalogSummary)}>{option.value} · {option.count} ocorrência(s) · {option.evidence.join(', ')}</option>)}</select></label>}
        <label className="correction-field"><span>{draft.distinctCount > 1 ? 'Valor revisado para este campo' : 'Valor do campo'}</span>{draft.fieldName === 'billing_mode' ? <select value={draft.value} onChange={(event) => updateManualField(draft.id, { value: event.target.value })}><option value="">Selecione o tipo de cobrança…</option><option value="exclusive">Exclusiva · uma unidade/serviço</option><option value="rateio">Rateio · compartilhada entre unidades</option></select> : isCatalogReferenceField(draft.fieldName) ? <select value={draft.value} onChange={(event) => updateManualField(draft.id, { value: event.target.value })}><option value="">Não identificado · selecione se houver evidência</option>{catalogOptionsForField(draft.fieldName, catalogSummary).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select> : <input type={draft.fieldName === 'due_date' ? 'date' : 'text'} value={draft.value} onChange={(event) => updateManualField(draft.id, { value: event.target.value })} maxLength={2000} placeholder={draft.fieldName === 'process_number' ? '00000.000000/0000-00' : isAmountFieldName(draft.fieldName) ? 'Ex.: 1.250,00' : 'Não identificado'} />}</label>
        {draft.distinctCount > 1 && <p className="invoice-review-ambiguity">Foram encontrados {draft.distinctCount} valores diferentes. Confira os registros abaixo; preencher este campo substitui o grupo pela informação revisada.</p>}
        {draft.distinctCount > 1 && <label className="invoice-review-bulk-check"><input type="checkbox" checked={draft.applyToAll} onChange={(event) => updateManualField(draft.id, { applyToAll: event.target.checked })} /><span>{draft.fieldName === 'reimbursement_term_amount_brl' ? `Usar este como o único valor de referência do termo neste PDF e substituir os ${draft.sourceCount} candidatos do termo. Se o PDF reunir várias faturas, confirme antes: o sistema não identifica automaticamente qual termo pertence a cada fatura.` : `Aplicar o valor escolhido a todos os ${draft.sourceCount} candidatos deste campo.`}</span></label>}
        {isAmountFieldName(draft.fieldName) && <div className="invoice-review-amount-classification">
          <label className="correction-field"><span>Classificação do número</span><select value={draft.amountRole} onChange={(event) => { const role = event.target.value as AmountRole; updateManualField(draft.id, { amountRole: role, ...(isNonCurrencyAmountRole(role) ? { amountBasis: 'unspecified' as const } : {}) }) }}>{amountRoleOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          {!isNonCurrencyAmountRole(draft.amountRole) && <label className="correction-field"><span>Natureza contábil</span><select value={draft.amountBasis} onChange={(event) => updateManualField(draft.id, { amountBasis: event.target.value as ManualFieldDraft['amountBasis'] })}><option value="unspecified">Ainda não sei</option><option value="gross">Valor bruto</option><option value="net">Valor líquido</option></select></label>}
        </div>}
        {draft.detectedValues.length > 0 && <details className="invoice-review-source-values"><summary>Ver {draft.sourceCount} ocorrência(s) e evidências</summary><ul>{draft.detectedValues.map((detected) => <li key={`${draft.fieldName}-${detected.normalizedValue}-${detected.amountBasis}`}><strong>{detected.value}</strong><span>{detected.count} ocorrência(s) · {detected.evidence.join(', ')}</span></li>)}</ul></details>}
      </section>
      })}</div>
      <label className="correction-field"><span>Justificativa (obrigatória)</span><textarea value={correctionReason} onChange={(event) => setCorrectionReason(event.target.value)} required minLength={5} maxLength={1000} rows={3} placeholder="Ex.: termo informa o valor líquido; fatura mostra o valor bruto." /></label>
      <div className="correction-warning"><ShieldCheck size={15} /><span>A correção será salva como novo candidato pendente e registrada na trilha de auditoria. Não confirma pagamento, autenticidade nem altera o PDF.</span></div>
      {pendingOnly && <section className="workflow-release-checks" aria-label="Requisitos para liberar fatura"><strong>Requisitos para sair da quarentena</strong>{selectedCard.release_checks.map((check) => <span key={check.key} className={check.complete ? 'workflow-check-complete' : 'workflow-check-pending'}>{check.complete ? '✓' : '○'} {check.label}{check.remaining ? ` · ${check.remaining} restante(s)` : ''}</span>)}<small>Preencha/corrija os candidatos, classifique todos os números e informe uma justificativa para mover. A transição ainda não é aprovação institucional.</small></section>}
      {correctionMessage && <div className="correction-feedback" role="status">{correctionMessage}</div>}
      <div className="correction-actions"><button type="button" className="button button-secondary" onClick={() => setSelectedCard(null)} disabled={savingCorrection || savingWorkflow}>Cancelar</button><button type="submit" className="button button-primary" disabled={savingCorrection || savingWorkflow || fieldsToSave.length === 0 || hasUnconfirmedBulkChoice}>{savingCorrection ? 'Salvando…' : `Salvar ${fieldsToSave.length} alteração(ões)`}</button>{pendingOnly ? <button type="button" className="button button-primary" disabled={!selectedCard.release_ready || correctionReason.trim().length < 5 || savingCorrection || savingWorkflow || fieldsToSave.length > 0 || hasUnconfirmedBulkChoice} onClick={() => void transitionWorkflow('release-to-invoices')}>{savingWorkflow ? 'Movendo…' : 'Mover para Faturas'}</button> : <button type="button" className="button button-secondary" disabled={correctionReason.trim().length < 5 || savingCorrection || savingWorkflow || fieldsToSave.length > 0 || hasUnconfirmedBulkChoice} onClick={() => void transitionWorkflow('return-to-review')}>{savingWorkflow ? 'Devolvendo…' : 'Devolver à revisão'}</button>}</div>
    </form></div>}
  </div>
}

function ImportedDataPage() {
  const [summary, setSummary] = useState<ImportSummary | null>(null)
  const [items, setItems] = useState<CandidateRecord[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const [summaryResponse, candidatesResponse] = await Promise.all([
          fetch('/api/v1/ingestion/summary'),
          fetch('/api/v1/extraction-candidates?limit=100&offset=0'),
        ])
        if (!summaryResponse.ok || !candidatesResponse.ok) throw new Error('API indisponível')
        const nextSummary = await summaryResponse.json() as ImportSummary
        const page = await candidatesResponse.json() as { items: CandidateRecord[]; page: { total: number } }
        if (active) {
          setSummary(nextSummary)
          setItems(page.items)
          setTotal(page.page.total)
          setError('')
        }
      } catch {
        if (active) setError('Não foi possível carregar os documentos e candidatos da API local.')
      } finally {
        if (active) setLoading(false)
      }
    }
    void load()
    return () => { active = false }
  }, [])

  if (loading) return <section className="panel import-state">Carregando a ingestão local…</section>
  if (error) return <section className="panel import-state import-error">{error}</section>
  if (!summary) return <section className="panel import-state">Resumo de ingestão indisponível.</section>

  return <div className="import-page">
    <div className="import-caution"><ShieldCheck size={17} /><div><strong>Todos os campos são candidatos, não fatos confirmados.</strong><span>Valor do termo de recebimento tem precedência sobre fatura quando identificado; fonte, página e revisão permanecem explícitas.</span></div></div>
    <section className="import-kpis"><article><span>Documentos</span><strong>{summary.documents.toLocaleString('pt-BR')}</strong></article><article><span>Candidatos</span><strong>{summary.candidates.toLocaleString('pt-BR')}</strong></article><article><span>Pendentes de revisão</span><strong>{summary.pending_review.toLocaleString('pt-BR')}</strong></article><article><span>Documentos com erro</span><strong>{summary.document_states.error ?? 0}</strong></article></section>
    <section className="panel imported-candidates"><div className="panel-heading"><div><h2>Fila de conferência</h2><p>{total.toLocaleString('pt-BR')} candidatos · exibindo {items.length}</p></div></div><div className="candidate-table-wrap"><table className="candidate-table"><thead><tr><th>CAMPO</th><th>VALOR LIDO</th><th>ARQUIVO / EVIDÊNCIA</th><th>ESTADO</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td><strong>{fieldLabel(item.field_name)}</strong></td><td><strong>{item.raw_value}</strong>{item.normalized_value && <small>Normalizado: {item.normalized_value}</small>}</td><td><span>{item.relative_path}</span><small>{item.evidence_location ?? 'Localização não disponível'}</small></td><td>{item.review_state === 'candidate' ? 'Pendente · não confirmado' : item.review_state}</td></tr>)}</tbody></table>{items.length === 0 && <div className="empty-state">Nenhum campo candidato nesta página.</div>}</div></section>
  </div>
}

function SettingsPage({ activeTab, onChangeTab, catalogSummary }: { activeTab: SettingsTab; onChangeTab: (tab: SettingsTab) => void; catalogSummary: CatalogSummary | null }) {
  return <div className="settings-workspace">
    <header className="settings-page-header">
      <span className="settings-page-mark"><Settings2 size={20} /></span>
      <div><span className="eyebrow">SISTEMA · PREFERÊNCIAS</span><h2>Configurações</h2><p>Preferências do ambiente e regras administrativas de classificação.</p></div>
      <span className="settings-environment-badge"><i /> Ambiente local</span>
    </header>
    <div className="settings-subtabs" role="tablist" aria-label="Abas de configurações">
      {(['Geral', 'Regras administrativas'] as const).map((tab) => <button key={tab} type="button" role="tab" aria-selected={activeTab === tab} className={activeTab === tab ? 'active' : ''} onClick={() => onChangeTab(tab)}>{tab === 'Regras administrativas' ? <SlidersHorizontal size={15} /> : <Settings2 size={15} />}{tab}<span className="settings-tab-indicator" /></button>)}
    </div>
    {activeTab === 'Regras administrativas' ? <AdministrativeRulesPage catalogSummary={catalogSummary} /> : <div className="settings-general-grid">
      <section className="panel settings-general-panel">
        <div className="settings-section-heading"><span className="settings-section-icon"><Settings2 size={17} /></span><div><h2>Estado desta instância</h2><p>Informações operacionais consultadas da API; não representam homologação de produção.</p></div></div>
        <div className="setting-row setting-row-static"><span><strong>Catálogo</strong><small>Referências carregadas, pendentes de validação institucional</small></span><span>{catalogSummary?.catalog_verified ? 'Verificado' : 'Não verificado'}</span></div>
        <div className="setting-row setting-row-static"><span><strong>Autenticação</strong><small>Identidade e perfis de acesso</small></span><span>Não configurada</span></div>
        <div className="setting-row setting-row-static"><span><strong>Fontes oficiais</strong><small>SEI, pagamentos e planilha de saldos</small></span><span>Não conectadas</span></div>
      </section>
      <aside className="settings-status-column">
        <section className="settings-status-card"><span className="settings-status-icon"><ShieldCheck size={17} /></span><div><span className="settings-status-label">INTEGRAÇÕES INSTITUCIONAIS</span><strong>SEI, identidade, e-mail e saldos desconectados</strong><p>O monitor local de arquivos é configurado separadamente. A instância ainda não está homologada para produção.</p></div></section>
        <section className="settings-status-card"><span className="settings-status-icon settings-status-draft"><SlidersHorizontal size={17} /></span><div><span className="settings-status-label">REGRAS DE NEGÓCIO</span><strong>Rascunhos não aplicados</strong><p>{catalogSummary?.supplier_count ?? '—'} fornecedores · {catalogSummary?.material_count ?? '—'} materiais</p><button type="button" onClick={() => onChangeTab('Regras administrativas')}>Abrir regras administrativas <ArrowRight size={13} /></button></div></section>
      </aside>
    </div>}
  </div>
}

type AdministrativeRuleScope = 'supplier' | 'material'
type BillingMode = 'unclassified' | 'exclusive' | 'rateio'
type RateioMethod = 'not_defined' | 'equal_shares' | 'contractual_percentages' | 'consumption' | 'manual'
type AmountBasisRule = 'unspecified' | 'gross' | 'net'
type AdministrativeRuleValues = {
  billing_mode: BillingMode
  rateio_method: RateioMethod
  invoice_amount_basis: AmountBasisRule
  term_amount_basis: AmountBasisRule
  difference_policy: 'manual_review'
  status: 'draft'
}
type AdministrativeRuleItem = {
  scope_type: AdministrativeRuleScope
  scope_id: number
  name: string
  subtitle: string
  rule: AdministrativeRuleValues
  version: number
  saved: boolean
}

const RATEIO_METHODS: { value: RateioMethod; label: string }[] = [
  { value: 'not_defined', label: 'Ainda não definido' },
  { value: 'equal_shares', label: 'Divisão em partes iguais' },
  { value: 'contractual_percentages', label: 'Percentuais previstos em contrato' },
  { value: 'consumption', label: 'Consumo/medição por unidade' },
  { value: 'manual', label: 'Valor informado manualmente' },
]

function AdministrativeRulesPage({ catalogSummary }: { catalogSummary: CatalogSummary | null }) {
  const [items, setItems] = useState<AdministrativeRuleItem[]>([])
  const [scope, setScope] = useState<AdministrativeRuleScope>('supplier')
  const [selectedKey, setSelectedKey] = useState('')
  const [draft, setDraft] = useState<AdministrativeRuleValues | null>(null)
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [feedback, setFeedback] = useState('')

  useEffect(() => {
    let active = true
    fetch('/api/v1/administrative-rules')
      .then(async (response) => {
        if (!response.ok) throw new Error('API indisponível ou migração das regras ainda não aplicada')
        return await response.json() as { items: AdministrativeRuleItem[] }
      })
      .then((result) => { if (active) { setItems(result.items); setError('') } })
      .catch((loadError) => { if (active) setError(loadError instanceof Error ? loadError.message : 'Não foi possível carregar as regras.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const visibleItems = items.filter((item) => item.scope_type === scope)
  const selectedItem = items.find((item) => `${item.scope_type}:${item.scope_id}` === selectedKey) ?? null

  const openRule = (item: AdministrativeRuleItem) => {
    setSelectedKey(`${item.scope_type}:${item.scope_id}`)
    setDraft({ ...item.rule })
    setReason('')
    setFeedback('')
  }

  const saveRule = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selectedItem || !draft) return
    setSaving(true)
    setFeedback('')
    try {
      const response = await fetch(`/api/v1/administrative-rules/${selectedItem.scope_type}/${selectedItem.scope_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...draft, reason }),
      })
      const payload = await response.json() as { detail?: string; rule?: AdministrativeRuleValues; version?: number; unchanged?: boolean }
      if (!response.ok) throw new Error(payload.detail ?? 'Não foi possível salvar o rascunho')
      const savedRule = payload.rule ?? draft
      const savedVersion = payload.version ?? selectedItem.version
      setItems((current) => current.map((item) => item.scope_type === selectedItem.scope_type && item.scope_id === selectedItem.scope_id
        ? { ...item, rule: savedRule, version: savedVersion, saved: true }
        : item))
      setDraft({ ...savedRule })
      setReason('')
      setFeedback(payload.unchanged ? `Nenhuma mudança; rascunho permanece na versão ${savedVersion}.` : `Rascunho v${savedVersion} salvo e auditado. Não foi aplicado às extrações.`)
    } catch (saveError) {
      setFeedback(saveError instanceof Error ? saveError.message : 'Falha ao salvar o rascunho.')
    } finally {
      setSaving(false)
    }
  }

  const totalForScope = scope === 'supplier' ? catalogSummary?.supplier_count ?? 0 : catalogSummary?.material_count ?? 0

  return <div className="administrative-rules-page">
    <section className="invoice-library-hero"><div><span className="eyebrow"><SlidersHorizontal size={14} /> CONFIGURAÇÃO · RASCUNHOS ADMINISTRATIVOS</span><h2>Regras por fornecedor e material</h2><p>Defina o tipo de cobrança e a natureza dos valores sem misturar o valor da fatura com o valor do termo de recebimento.</p></div><div className="invoice-library-count"><strong>{totalForScope || visibleItems.length}</strong><span>{scope === 'supplier' ? 'fornecedores' : 'materiais'}</span></div></section>
    <div className="import-caution admin-rule-caution"><ShieldCheck size={17} /><div><strong>Rascunhos locais; não são regras oficiais nem estão ativos.</strong><span>Não há autenticação administrativa configurada. Alterações ficam versionadas, não modificam PDFs nem candidatos e não escolhem automaticamente entre fatura e termo.</span></div></div>
    <div className="rule-principles"><article><strong>1 · Fontes separadas</strong><span>Guardar e exibir invoice_amount_brl e reimbursement_term_amount_brl como campos independentes, cada um com evidência.</span></article><article><strong>2 · Divergência explícita</strong><span>Quando os valores diferirem, manter ambos e encaminhar para revisão humana; não substituir um pelo outro.</span></article><article><strong>3 · Rateio sem pressuposição</strong><span>Registrar se é exclusivo ou rateio. O critério fica “não definido” até aprovação administrativa.</span></article></div>
    <div className="admin-rule-scope-switch" role="tablist" aria-label="Tipo de regra">
      <button role="tab" aria-selected={scope === 'supplier'} className={scope === 'supplier' ? 'active' : ''} onClick={() => { setScope('supplier'); setSelectedKey(''); setDraft(null) }}><Building2 size={15} /> Fornecedores <span>{catalogSummary?.supplier_count ?? '—'}</span></button>
      <button role="tab" aria-selected={scope === 'material'} className={scope === 'material' ? 'active' : ''} onClick={() => { setScope('material'); setSelectedKey(''); setDraft(null) }}><Database size={15} /> Materiais <span>{catalogSummary?.material_count ?? '—'}</span></button>
    </div>
    {loading ? <section className="panel import-state">Carregando regras administrativas…</section> : error ? <section className="panel import-state import-error">{error}. A tela continua sem ativar nenhuma regra.</section> : <>
      <section className="admin-rule-card-grid" aria-label={scope === 'supplier' ? 'Regras por fornecedor' : 'Regras por material'}>{visibleItems.map((item) => <button type="button" className={`admin-rule-card ${selectedKey === `${item.scope_type}:${item.scope_id}` ? 'admin-rule-card-selected' : ''}`} key={`${item.scope_type}:${item.scope_id}`} onClick={() => openRule(item)}>
        <span className="admin-rule-card-top"><span className="invoice-group-icon">{scope === 'supplier' ? <Building2 size={16} /> : <Database size={16} />}</span><span className={`admin-rule-status ${item.saved ? 'admin-rule-status-saved' : ''}`}>{item.saved ? `Rascunho v${item.version}` : 'Sem regra salva'}</span></span>
        <strong>{item.name}</strong><small>{item.subtitle}</small><span className="admin-rule-card-summary">{billingModeLabel(item.rule.billing_mode)}<ArrowRight size={14} /></span>
      </button>)}</section>
      {selectedItem && draft && <section className="admin-rule-editor" id="administrative-rule-editor">
        <header><div><span className="eyebrow">{selectedItem.scope_type === 'supplier' ? 'REGRA DO FORNECEDOR' : 'REGRA DO MATERIAL'} · {selectedItem.saved ? `VERSÃO ${selectedItem.version}` : 'NOVA'}</span><h2>{selectedItem.name}</h2><p>{selectedItem.subtitle}</p></div><button type="button" className="button button-secondary compact" onClick={() => { setSelectedKey(''); setDraft(null) }}>Fechar seção</button></header>
        <form onSubmit={saveRule}>
          <div className="admin-rule-form-grid">
            <label className="correction-field"><span>Tipo de cobrança</span><select value={draft.billing_mode} onChange={(event) => { const mode = event.target.value as BillingMode; setDraft((current) => current ? { ...current, billing_mode: mode, rateio_method: mode === 'rateio' ? current.rateio_method : 'not_defined' } : current) }}><option value="unclassified">Ainda não classificada</option><option value="exclusive">Exclusiva · uma unidade/serviço</option><option value="rateio">Rateio · compartilhada entre unidades</option></select></label>
            {draft.billing_mode === 'rateio' && <label className="correction-field"><span>Critério de rateio</span><select value={draft.rateio_method} onChange={(event) => setDraft((current) => current ? { ...current, rateio_method: event.target.value as RateioMethod } : current)}>{RATEIO_METHODS.map((method) => <option key={method.value} value={method.value}>{method.label}</option>)}</select></label>}
            <label className="correction-field"><span>Natureza do valor da fatura</span><select value={draft.invoice_amount_basis} onChange={(event) => setDraft((current) => current ? { ...current, invoice_amount_basis: event.target.value as AmountBasisRule } : current)}><option value="unspecified">Não definida</option><option value="gross">Bruto</option><option value="net">Líquido</option></select><small>Campo independente: valor lido da fatura.</small></label>
            <label className="correction-field"><span>Natureza do valor do termo</span><select value={draft.term_amount_basis} onChange={(event) => setDraft((current) => current ? { ...current, term_amount_basis: event.target.value as AmountBasisRule } : current)}><option value="unspecified">Não definida</option><option value="gross">Bruto</option><option value="net">Líquido</option></select><small>Campo independente: valor lido do termo de recebimento.</small></label>
          </div>
          <div className="admin-rule-difference"><AlertTriangle size={16} /><div><strong>Divergência entre fatura e termo: revisão humana obrigatória</strong><span>Os dois valores e suas evidências permanecem visíveis; esta regra não define precedência nem contabiliza diferença como saldo/pagamento.</span></div></div>
          <label className="correction-field"><span>Justificativa da alteração (obrigatória)</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} minLength={5} maxLength={1000} rows={3} required placeholder="Ex.: contrato prevê cobrança rateada entre as unidades indicadas no termo." /></label>
          <div className="admin-rule-editor-footer"><span><ShieldCheck size={14} /> Apenas rascunho · não aplicado · alterações registradas no histórico</span><button type="submit" className="button button-primary" disabled={saving}>{saving ? 'Salvando…' : 'Salvar rascunho'}</button></div>
        </form>
      </section>}
      {feedback && <div role="status" className="correction-feedback">{feedback}</div>}
    </>}
  </div>
}

function billingModeLabel(mode: BillingMode) {
  if (mode === 'exclusive') return 'Cobrança exclusiva'
  if (mode === 'rateio') return 'Cobrança rateada'
  return 'Classificação pendente'
}

const INVOICE_REVIEW_FIELDS = [
  'reimbursement_term_amount_brl', 'billing_mode', 'process_number',
  'due_date', 'organization_reference', 'service_reference', 'material_reference', 'supplier_reference',
]

function isAmountFieldName(field: string) {
  return ['amount_brl', 'invoice_amount_brl', 'reimbursement_term_amount_brl'].includes(field)
}

function amountBasisLabel(basis: CandidateRecord['amount_basis']) {
  if (basis === 'gross') return 'bruto'
  if (basis === 'net') return 'líquido'
  return 'natureza não informada'
}

function amountRoleLabel(role: AmountRole | null) {
  const option = amountRoleOptions.find((item) => item.value === (role ?? 'unspecified'))
  return option?.label ?? 'Classificação pendente'
}

function isNonCurrencyAmountRole(role: AmountRole | null) {
  return role === 'percentage' || role === 'quantity' || role === 'other_numeric'
}

function fieldLabel(field: string) {
  const labels: Record<string, string> = {
    process_number: 'Número de processo (formato)', amount_brl: 'Valor sem classificação de origem',
    invoice_amount_brl: 'Valor candidato da fatura',
    reimbursement_term_amount_brl: 'Valor candidato do termo de recebimento · preferencial',
    due_date: 'Data de vencimento',
    organization_reference: 'Órgão reconhecido no catálogo',
    material_reference: 'Material reconhecido no catálogo',
    service_reference: 'Serviço reconhecido no catálogo',
    supplier_reference: 'Fornecedor reconhecido no catálogo',
    directory_classification_hint: 'Pista do caminho da pasta', parser_warning: 'Aviso de leitura',
  }
  return labels[field] ?? field
}

function isCatalogReferenceField(field: string) {
  return ['organization_reference', 'service_reference', 'material_reference', 'supplier_reference'].includes(field)
}

function catalogOptionsForField(field: string, catalogSummary: CatalogSummary | null) {
  if (!catalogSummary) return []
  if (field === 'organization_reference') return catalogSummary.organizations.map((item) => ({ value: String(item.id), label: `${item.sigla} · ${item.nome}` }))
  if (field === 'service_reference') return catalogSummary.services.map((item) => ({ value: String(item.id), label: item.nome }))
  if (field === 'material_reference') return catalogSummary.materials.map((item) => ({ value: String(item.id), label: `${item.nome} · ${item.categoria}` }))
  if (field === 'supplier_reference') return catalogSummary.fornecedores.map((item) => ({ value: String(item.id), label: `${item.nome} · ${item.servico_associado}` }))
  return []
}

function normalizeCatalogLabel(value: string) {
  return value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toUpperCase().replace(/[^A-Z0-9]+/g, ' ').trim()
}

function candidateValueForEdit(field: string, value: string, catalogSummary: CatalogSummary | null) {
  if (field === 'billing_mode') {
    const normalized = normalizeCatalogLabel(value)
    if (['EXCLUSIVE', 'EXCLUSIVA', 'COBRANCA EXCLUSIVA'].includes(normalized)) return 'exclusive'
    if (['RATEIO', 'RATEADA', 'COBRANCA RATEADA', 'RATEIO ENTRE ORGAOS'].includes(normalized)) return 'rateio'
    return value
  }
  if (isCatalogReferenceField(field)) {
    const wanted = normalizeCatalogLabel(value)
    const option = catalogOptionsForField(field, catalogSummary).find((item) =>
      item.value === value || normalizeCatalogLabel(item.label.split(' · ')[0]) === wanted || normalizeCatalogLabel(item.label) === wanted,
    )
    return option?.value ?? value
  }
  if (field !== 'due_date') return value
  const match = value.match(/^(\d{2})\/(\d{2})\/(\d{4})$/)
  return match ? `${match[3]}-${match[2]}-${match[1]}` : value
}

function reviewFieldBlocksRelease(field: string, checks: InvoiceDocumentCard['release_checks']) {
  const requiredCheckKeys: Record<string, string[]> = {
    reimbursement_term_amount_brl: ['term_total'],
    billing_mode: ['billing_mode'],
    process_number: ['process'],
    due_date: ['due_date'],
    organization_reference: ['organization'],
    supplier_reference: ['catalog_group'],
    material_reference: ['catalog_group'],
  }
  return (requiredCheckKeys[field] ?? []).some((key) => checks.some((check) => check.key === key && !check.complete))
}

function SectionPage({ page }: { page: Page }) {
  const [processes, setProcesses] = useState<ProcessRow[]>([])
  const [alerts, setAlerts] = useState<AlertRow[]>([])
  const [loading, setLoading] = useState(page === 'Processos SEI' || page === 'Alertas')
  const [error, setError] = useState('')

  useEffect(() => {
    if (page !== 'Processos SEI' && page !== 'Alertas') return
    let active = true
    const endpoint = page === 'Processos SEI' ? '/api/v1/processes' : '/api/v1/alerts'
    setLoading(true)
    setError('')
    void fetch(endpoint)
      .then(async (response) => {
        if (!response.ok) throw new Error('Não foi possível consultar os registros persistidos.')
        return await response.json() as { items: ProcessRow[] | AlertRow[] }
      })
      .then((result) => {
        if (!active) return
        if (page === 'Processos SEI') setProcesses(result.items as ProcessRow[])
        else setAlerts(result.items as AlertRow[])
        setError('')
      })
      .catch((loadError) => { if (active) setError(loadError instanceof Error ? loadError.message : 'Falha ao carregar dados da API.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page])

  if (page === 'Processos SEI') return <section className="panel section-card">
    <div className="audit-notice"><ShieldCheck size={19} /><div><strong>Registros locais; consulta ao SEI não configurada</strong><span>O número do processo é armazenado, mas a existência e a situação no SEI não são verificadas.</span></div></div>
    {loading ? <div className="empty-state">Carregando processos registrados…</div> : error ? <div className="empty-state import-error">{error}</div> : processes.length === 0 ? <div className="empty-state">Nenhum processo registrado na base.</div> : <div className="process-grid">{processes.map((process) => <article className="process-card" key={process.id}><div className="process-card-top"><div className="process-file"><FileCheck2 size={18} /></div><span className="process-tag">{process.verification_state === 'verified' ? 'VERIFICADO' : 'NÃO VERIFICADO'}</span></div><strong className="process-number">{process.process_number}</strong><span className="process-subtitle">{process.object_description ?? 'Sem descrição registrada'}</span><div className="process-divider" /><div className="process-meta"><span><FileText size={14} /> Registro local · {new Date(process.created_at).toLocaleDateString('pt-BR')}</span></div></article>)}</div>}
  </section>

  if (page === 'Alertas') return <section className="panel section-card">
    <div className="audit-notice"><AlertTriangle size={19} /><div><strong>Alertas registrados na base</strong><span>A geração automática e o reconhecimento de alertas não estão habilitados.</span></div></div>
    {loading ? <div className="empty-state">Carregando alertas registrados…</div> : error ? <div className="empty-state import-error">{error}</div> : alerts.length === 0 ? <div className="empty-state">Nenhum alerta registrado na base.</div> : <div className="expanded-alert-list">{alerts.map((alert) => <article className="expanded-alert" key={alert.id}><div className="alert-icon"><AlertTriangle size={17} /></div><div className="alert-copy"><strong>{alert.summary}</strong><span>{alert.alert_type} · {alert.status}</span><small>{new Date(alert.created_at).toLocaleString('pt-BR')}</small></div><span className="severity">{alert.severity}</span></article>)}</div>}
  </section>

  if (page === 'Saldos') return <section className="panel section-card balances-placeholder"><div className="placeholder-icon"><Wallet size={23} /></div><h2>Fonte de saldos não configurada</h2><p>Não há planilha oficial vinculada. Nenhum saldo ou disponibilidade financeira é calculado ou exibido até que a fonte, o mapeamento e a permissão de leitura sejam formalmente configurados.</p></section>

  if (page === 'Auditoria') return <section className="panel section-card"><div className="audit-notice"><ShieldCheck size={19} /><div><strong>Consulta da trilha de auditoria indisponível</strong><span>Algumas alterações persistem eventos na base, mas não há tela/API de consulta completa nem identidade autenticada do responsável. Não use isto como trilha oficial de auditoria.</span></div></div></section>

  return <section className="panel section-card"><div className="empty-state">Esta seção não possui uma função operacional configurada.</div></section>
}

export default App
