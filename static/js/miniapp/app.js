// --- Fantasma Pierre: animação de hover ---
document.addEventListener('DOMContentLoaded', () => {
  const ghost = document.getElementById('nav-fantasma');
  if (!ghost) return;
  const nav = document.getElementById('bottomNav');
  // Detecta hover/focus/active no fantasma
  ghost.parentElement.addEventListener('mouseenter', () => ghost.classList.add('lift'));
  ghost.parentElement.addEventListener('mouseleave', () => ghost.classList.remove('lift'));
  ghost.parentElement.addEventListener('touchstart', () => ghost.classList.add('lift'));
  ghost.parentElement.addEventListener('touchend', () => ghost.classList.remove('lift'));
});
// --- Inicialização automática dos dados principais ao carregar o DOM ---
document.addEventListener('DOMContentLoaded', async () => {
  // Tenta autenticar/recuperar sessão e carregar dados essenciais
  try {
    await authTelegram();
  } catch (e) {
    console.warn('Falha ao autenticar automaticamente:', e);
    await tryRecoverSessionFromStorage();
  }
});
lucide.createIcons();

    // Chart.js Global Defaults
    if (window.Chart) {
      // Registrar plugins especiais para Chart.js 4
      try {
        // Registro para Sankey
      const sankeyPlugin = window['chartjs-chart-sankey'] || window.ChartSankey;
      if (sankeyPlugin) {
        // Different builds expose different symbols; try common ones
        const controller = sankeyPlugin.SankeyController || sankeyPlugin.Sankey || sankeyPlugin.Controller;
        const element = sankeyPlugin.SankeyElement || sankeyPlugin.FlowElement || sankeyPlugin.Element;
        if (controller && element) {
          Chart.register(controller, element);
        } else if (sankeyPlugin.SankeyController && sankeyPlugin.FlowElement) {
          Chart.register(sankeyPlugin.SankeyController, sankeyPlugin.FlowElement);
        }
      } else if (typeof SankeyController !== 'undefined' && typeof FlowElement !== 'undefined') {
        Chart.register(SankeyController, FlowElement);
      }

        // Registro para Matrix (Heatmap)
        const matrixPlugin = window['chartjs-chart-matrix'] || window.ChartMatrix;
        if (matrixPlugin) {
            Chart.register(matrixPlugin.MatrixController, matrixPlugin.MatrixElement);
        } else if (typeof MatrixController !== 'undefined') {
            Chart.register(MatrixController, MatrixElement);
        }
      } catch (e) {
        console.warn("Falha ao registrar plugins adicionais do Chart.js:", e);
      }

      Chart.defaults.color = '#64748b';
      Chart.defaults.font.family = "'Schibsted Grotesk', sans-serif";
      Chart.defaults.font.weight = '600';
      
      // Estilo Premium Grená para Tooltips
      Chart.defaults.plugins.tooltip.backgroundColor = '#2d0a10'; // Grená Profundo
      Chart.defaults.plugins.tooltip.titleColor = '#D4AF37';       // Ouro Premium
      Chart.defaults.plugins.tooltip.bodyColor = '#ffffff';        // Texto Branco para leitura
      Chart.defaults.plugins.tooltip.borderColor = 'rgba(212, 175, 55, 0.3)';
      Chart.defaults.plugins.tooltip.borderWidth = 1;
      Chart.defaults.plugins.tooltip.padding = 12;
      Chart.defaults.plugins.tooltip.cornerRadius = 12;
      Chart.defaults.plugins.legend.labels.usePointStyle = true;
      Chart.defaults.plugins.legend.labels.pointStyle = 'circle';
      Chart.defaults.plugins.legend.labels.padding = 20;
    }

  // Mapa global de instâncias de Chart para evitar reuso de canvas sem destruir
  const CHART_INSTANCES = new Map();


    // DOM Elements
    const panels = document.querySelectorAll('.panel');
    const appBody = document.body;
    const htmlRoot = document.documentElement;
    const mainStatus = document.getElementById('mainStatus');
    const homeBalance = document.getElementById('homeBalance');
    const homeBalanceHint = document.getElementById('homeBalanceHint');
    const homeWave = document.getElementById('homeWave');
    const homeLevelCard = document.getElementById('homeLevelCard');
    const homeLevel = document.getElementById('homeLevel');
    const homeXp = document.getElementById('homeXp');
    const homeStreak = document.getElementById('homeStreak');
    const homeProgressLabel = document.getElementById('homeProgressLabel');
    const homeAquariumWater = document.getElementById('homeAquariumWater');
    const homePctReceita = document.getElementById('homePctReceita');
    const homePctDespesa = document.getElementById('homePctDespesa');
    const homeReceita = document.getElementById('homeReceita');
    const homeDespesa = document.getElementById('homeDespesa');
    const homeInsight = document.getElementById('homeInsight');
    const homeRecentList = document.getElementById('homeRecentList');
    const homeRecentRefresh = document.getElementById('homeRecentRefresh');
    const homeChartsPills = document.getElementById('homeChartsPills');
    const homeChartCarousel = document.getElementById('homeChartCarousel');
    const homeChartPills = Array.from(document.querySelectorAll('[data-home-chart-pill]'));
    const homeChartCards = Array.from(document.querySelectorAll('[data-home-chart-card]'));
    const homePatrimonyChartEl = document.getElementById('homePatrimonyChart');
    const homeBudgetGaugesContainer = document.getElementById('homeBudgetGaugesContainer');
    const homeBudgetGaugeTemplate = document.getElementById('homeBudgetGaugeTemplate');
    const homeCashflowChartEl = document.getElementById('homeCashflowChart');
    const homeBudgetChartEl = document.getElementById('homeBudgetChart');
    const homeCategoryChartEl = document.getElementById('homeCategoryChart');
    const homeBadgeContainer = document.getElementById('homeBadgeContainer');
    const homePlanLabel = document.getElementById('homePlanLabel');
    const homeUpgradeBtn = document.getElementById('homeUpgradeBtn');
    const homeProjectionChartEl = document.getElementById('homeProjectionChart');
    const homeVillainsChartEl = document.getElementById('homeVillainsChart');
    const homeSankeyChartEl = document.getElementById('homeSankeyChart');
    const homeHeatmapChartEl = document.getElementById('homeHeatmapChart');
    const homeCategoryValue = document.getElementById('homeCategoryValue');
    const homeCategoryLabel = document.getElementById('homeCategoryLabel');
    const historyList = document.getElementById('historyList');
    const historyStatus = document.getElementById('historyStatus');
    const historyQuery = document.getElementById('historyQuery');
    const historyTipo = document.getElementById('historyTipo');
    const historyOrder = document.getElementById('historyOrder');
    const historyRefresh = document.getElementById('historyRefresh');
    const historyLoadMore = document.getElementById('historyLoadMore');
    const historyDate = document.getElementById('historyDate');
    const historyClearFilters = document.getElementById('historyClearFilters');
    
    const agendamentoList = document.getElementById('agendamentoList');
    const agendamentoStatus = document.getElementById('agendamentoStatus');
    const agendaTabAgendamentos = document.getElementById('agendaTabAgendamentos');
    const agendaTabLembretes = document.getElementById('agendaTabLembretes');
    const agendaTabLimites = document.getElementById('agendaTabLimites');
    const lembreteHistoryWrap = document.getElementById('lembreteHistoryWrap');
    const lembreteHistoryStatus = document.getElementById('lembreteHistoryStatus');
    const lembreteHistoryList = document.getElementById('lembreteHistoryList');
    const orcamentoAgendaWrap = document.getElementById('orcamentoAgendaWrap');
    const orcamentoAgendaStatus = document.getElementById('orcamentoAgendaStatus');
    const agendamentoRefresh = document.getElementById('agendamentoRefresh');
    const agendamentoNew = document.getElementById('agendamentoNew');
    const newAgendamentoModal = document.getElementById('newAgendamentoModal');
    const agendaModalTitle = document.getElementById('agendaModalTitle');
    const agendaValorLabel = document.getElementById('agendaValorLabel');
    const agendaDataLabel = document.getElementById('agendaDataLabel');
    const newAgendDescricao = document.getElementById('newAgendDescricao');
    const newAgendValor = document.getElementById('newAgendValor');
    const newAgendTipo = document.getElementById('newAgendTipo');
    const newAgendFrequencia = document.getElementById('newAgendFrequencia');
    const newAgendData = document.getElementById('newAgendData');
    const newAgendParcelas = document.getElementById('newAgendParcelas');
    const newAgendInfinito = document.getElementById('newAgendInfinito');
    const newAgendSave = document.getElementById('newAgendSave');
    const parcelasGroup = document.getElementById('parcelasGroup');
    
    const metaList = document.getElementById('metaList');
    const metaStatus = document.getElementById('metaStatus');
    const metaRefresh = document.getElementById('metaRefresh');
    const metaNew = document.getElementById('metaNew');
    const metaModal = document.getElementById('metaModal');
    const metaModalTitle = document.getElementById('metaModalTitle');
    const metaDescricao = document.getElementById('metaDescricao');
    const metaValorMeta = document.getElementById('metaValorMeta');
    const metaValorAtual = document.getElementById('metaValorAtual');
    const metaData = document.getElementById('metaData');
    const metaSave = document.getElementById('metaSave');

    const orcamentoList = document.getElementById('orcamentoList');
    const orcamentoNew = document.getElementById('orcamentoNew');
    const orcamentoModal = document.getElementById('orcamentoModal');
    const orcamentoCategoria = document.getElementById('orcamentoCategoria');
    const orcamentoValor = document.getElementById('orcamentoValor');
    const orcamentoSave = document.getElementById('orcamentoSave');

    const editModal = document.getElementById('editModal');
    const editModalBadge = document.getElementById('editModalBadge');
    const editDraftInfo = document.getElementById('editDraftInfo');
    const editDescricao = document.getElementById('editDescricao');
    const editValor = document.getElementById('editValor');
    const editTipo = document.getElementById('editTipo');
    const editData = document.getElementById('editData');
    const editForma = document.getElementById('editForma');
    const editCategoria = document.getElementById('editCategoria');
    const editSubcategoria = document.getElementById('editSubcategoria');
    const editLearnRule = document.getElementById('editLearnRule');
    const editSave = document.getElementById('editSave');
    const editCancel = document.getElementById('editCancel');

    const configRefresh = document.getElementById('configRefresh');
    const perfilInvestidor = document.getElementById('perfilInvestidor');
    const horarioNotificacao = document.getElementById('horarioNotificacao');
    const alertaGastosAtivoToggle = document.getElementById('alertaGastosAtivoToggle');
    const configSave = document.getElementById('configSave');
    const configFinish = document.getElementById('configFinish');

    const gameProfileName = document.getElementById('gameProfileName');
    const gameProfileTitle = document.getElementById('gameProfileTitle');
    const gameProfileBadge = document.getElementById('gameProfileBadge');
    const gameProfileLevelLine = document.getElementById('gameProfileLevelLine');
    const gameProfileXpLine = document.getElementById('gameProfileXpLine');
    const gameProfileProgressBar = document.getElementById('gameProfileProgressBar');
    const gameProfileNextHint = document.getElementById('gameProfileNextHint');
    const gameInteractionsTotal = document.getElementById('gameInteractionsTotal');

    const pierreTotalBalance = document.getElementById('pierreTotalBalance');
    const pierreHealthScore = document.getElementById('pierreHealthScore');
    const pierreHealthLabel = document.getElementById('pierreHealthLabel');
    const pierreInstallmentsList = document.getElementById('pierreInstallmentsList');
    const pierreAccountsList = document.getElementById('pierreAccountsList');
    const pierreCategoriesChartEl = document.getElementById('pierreCategoriesChart');
    const pierreCategoriesEmpty = document.getElementById('pierreCategoriesEmpty');
    let pierreChartInstance = null;
    const gameInteractionsWeek = document.getElementById('gameInteractionsWeek');
    const gameTopFeatures = document.getElementById('gameTopFeatures');
    const gameAlfredoNote = document.getElementById('gameAlfredoNote');
    const gameRankingList = document.getElementById('gameRankingList');
    const gameRankingUpdatedAt = document.getElementById('gameRankingUpdatedAt');
    const gameProfileRefresh = document.getElementById('gameProfileRefresh');
    const gameSeeRanking = document.getElementById('gameSeeRanking');
    const rankingBackBtn = document.getElementById('rankingBackBtn');
    const rankingFullList = document.getElementById('rankingFullList');
   
    const faturaBkBtn = document.getElementById('faturaBkBtn');
    const faturaHeaderInfo = document.getElementById('faturaHeaderInfo');
    const faturaEditList = document.getElementById('faturaEditList');
    const faturaEditorSave = document.getElementById('faturaEditorSave');
    const faturaEditorCancel = document.getElementById('faturaEditorCancel');
    const gameBackHome = document.getElementById('gameBackHome');

  const missoesList = document.getElementById('missoesList');
  const missoesRefresh = document.getElementById('missoesRefresh');
  const missionsCountActive = document.getElementById('missionsCountActive');
  const missionsCountCompleted = document.getElementById('missionsCountCompleted');
  const missionsXpReward = document.getElementById('missionsXpReward');
  const missionFilterBtns = document.querySelectorAll('.mission-filter-btn');

    let sessionId = null;
    let telegramInitData = null;
    let reauthInFlight = null;
    // Flag para evitar concorrência em reload do dashboard
    let isRefreshingHome = false;
    let historyOffset = 0;
    const historyLimit = 20;
    let historyCache = [];
    let metasCache = [];
    let selectedLancamento = null;
    let agendaMode = 'agendamentos';
    let selectedMeta = null;
    let selectedLancamentoIsDraft = false;
    let pendingDraftLaunch = null;
    let homeCharts = {};
    let homeChartsObserver = null;
    let deviceProfile = '';
    let deviceResizeTimer = null;
    let homeRecentCache = [];
    let gameProfileCache = null;
    let gameRankingCache = [];
    let gameRankingRefreshTimer = null;
    const MINIAPP_SESSION_STORAGE_KEY = 'contacomigo-miniapp-session-id';
    const urlParams = new URLSearchParams(window.location.search);
    const initialTabFromUrl = urlParams.get('tab') || '';
    const rawDraftFromUrl = urlParams.get('draft') || '';
    const initialPageFromUrl = urlParams.get('page') || '';
    let currentFaturaToken = urlParams.get('fatura_token') || '';

  let missionsCache = [];
  let missionsCurrentFilter = 'all';
    function detectDeviceProfile() {
      const tgPlatform = String(window.Telegram?.WebApp?.platform || '').toLowerCase();
      const width = window.innerWidth || 0;
      const hasHover = window.matchMedia('(hover: hover)').matches;
      const finePointer = window.matchMedia('(pointer: fine)').matches;
      const touchPoints = navigator.maxTouchPoints || 0;
      const mobileUserAgent = /Android|iPhone|iPad|iPod|Windows Phone|Opera Mini|IEMobile/i.test(navigator.userAgent || '');
      const desktopPlatforms = new Set(['tdesktop', 'macos']);

      if (desktopPlatforms.has(tgPlatform) && !mobileUserAgent) {
        return 'desktop';
      }

      if (tgPlatform === 'ios' || tgPlatform === 'android') {
        return 'mobile';
      }

      if (width >= 860 && (hasHover || finePointer) && !mobileUserAgent && touchPoints <= 2) {
        return 'desktop';
      }
      return 'mobile';
    }
    window.abrirEdicaoOrcamento = function(id_categoria, valor_limite, nome_categoria, periodo) {
      if (id_categoria && id_categoria !== 'undefined' && orcamentoCategoria.querySelector(`option[value="${id_categoria}"]`)) {
          orcamentoCategoria.value = id_categoria;
      } else {
          const options = Array.from(orcamentoCategoria.options);
          const opt = options.find(o => o.text === nome_categoria);
          if (opt) orcamentoCategoria.value = opt.value;
      }
      orcamentoValor.value = String(valor_limite).replace('.', ',');
      
      const orcamentoPeriodo = document.getElementById('orcamentoPeriodo');
      if (orcamentoPeriodo && periodo) {
          orcamentoPeriodo.value = periodo;
      } else if (orcamentoPeriodo) {
          orcamentoPeriodo.value = 'monthly';
      }
      
      openModal('orcamentoModal');
    };

    function applyAdaptiveLayout() {
      const nextProfile = detectDeviceProfile();
      if (nextProfile === deviceProfile) return;

      deviceProfile = nextProfile;
      appBody.classList.remove('device-mobile', 'device-desktop');
      appBody.classList.add(`device-${nextProfile}`);
      htmlRoot.classList.toggle('desktop-layout', nextProfile === 'desktop');

      if (sessionId && Object.keys(homeCharts).length) {
        loadHomeOverview();
      }
    }

    function bindAdaptiveLayoutListeners() {
      applyAdaptiveLayout();
      window.addEventListener('resize', () => {
        clearTimeout(deviceResizeTimer);
        deviceResizeTimer = setTimeout(applyAdaptiveLayout, 120);
      });
      window.addEventListener('orientationchange', () => {
        clearTimeout(deviceResizeTimer);
        deviceResizeTimer = setTimeout(applyAdaptiveLayout, 120);
      });
    }

    // Navigation
    function setActiveNav(tabName) {
      const navButtons = document.querySelectorAll('.nav-btn');
      navButtons.forEach((btn) => {
        const isActive = btn.dataset.tab === tabName;
        btn.classList.toggle('tab-active', isActive);
        btn.classList.toggle('text-brand', isActive);
        btn.classList.toggle('text-telegram-hint', !isActive);
      });
    }

    function openPanel(tabName, keepNav = false) {
      if (!tabName) return;
      if (tabName !== 'perfil-jogo' && gameRankingRefreshTimer) {
        clearInterval(gameRankingRefreshTimer);
        gameRankingRefreshTimer = null;
      }
      panels.forEach(p => p.classList.remove('active'));
      const panel = document.getElementById(tabName);
      if (!panel) return;
      panel.classList.add('active');

      // Garante que ícones do Lucide sejam renderizados se o painel tiver conteúdo estático novo
      if (window.lucide) lucide.createIcons();

      if (!keepNav) {
        setActiveNav(tabName);
      }
      if (tabName === 'missoes' && sessionId) {
        loadMissions();
      }
      if (tabName === 'inicio' && sessionId) {
        loadHomeOverview();
      }
      if (tabName === 'metas' && sessionId) {
        loadMetas();
        loadOrcamentos();
      }
      if (tabName === 'modo-deus' && sessionId) {
        loadModoDeus();
      }
      if (tabName === 'fantasma' && sessionId) {
        loadPierreDashboard();
      }
    }
    const switchTab = (el) => {
      if (!el?.dataset?.tab) return;
      openPanel(el.dataset.tab, false);
    };
    window.switchTab = switchTab;

    const switchTabByName = (tabName) => {
      if (!tabName) return;
      const button = document.querySelector(`.nav-btn[data-tab="${tabName}"]`);
      if (button) {
        switchTab(button);
      } else {
        openPanel(tabName, true);
      }
    };
    window.switchTabByName = switchTabByName;

    // --- SISTEMA DE MODAIS ---
    const modalsOverlay = document.getElementById('modalsOverlay');

    function openModal(modalId) {
      const modal = document.getElementById(modalId);
      if (!modal) return;

      // Mostrar overlay
      if (modalsOverlay) {
        modalsOverlay.classList.remove('hidden');
        modalsOverlay.classList.add('pointer-events-auto');
      }

      // Mostrar modal específico
      modal.classList.remove('hidden');
      // Delay minúsculo para permitir que a transição de opacidade/transform funcione
      setTimeout(() => {
        modal.classList.add('active');
      }, 10);

      document.body.style.overflow = 'hidden';
    }

    function closeModal(modalId) {
      const modal = document.getElementById(modalId);
      if (!modal) return;

      modal.classList.remove('active');
      
      // Aguarda a transição terminar antes de ocultar
      setTimeout(() => {
        modal.classList.add('hidden');
        
        // Verifica se ainda há algum outro modal ativo antes de fechar o overlay
        const activeModals = document.querySelectorAll('.modal-overlay.active');
        if (activeModals.length === 0 && modalsOverlay) {
          modalsOverlay.classList.add('hidden');
          modalsOverlay.classList.remove('pointer-events-auto');
          document.body.style.overflow = 'auto';
        }
      }, 400);
    }

    window.openModal = openModal;
    window.closeModal = closeModal;

    function isEntradaTipo(tipo, value) {
      const tipoNorm = String(tipo || '').toLowerCase();
      if (tipoNorm.includes('entrada') || tipoNorm.includes('receita')) return true;
      if (tipoNorm.includes('saída') || tipoNorm.includes('saida') || tipoNorm.includes('despesa')) return false;
      return Number(value) >= 0;
    }

    function formatMoney(value, tipo) {
      const numeric = Number(value) || 0;
      const abs = Math.abs(numeric)
        .toFixed(2)
        .replace('.', ',')
        .replace(/,0$/, ',0')
        .replace(/,([1-9])0$/, ',$1')
        .replace(/,00$/, '');
      const prefix = isEntradaTipo(tipo, numeric) ? '+' : '-';
      return `${prefix} R$${abs}`;
    }

    function formatCurrency(value) {
      return (Number(value) || 0).toLocaleString('pt-BR', {
        style: 'currency',
        currency: 'BRL',
        minimumFractionDigits: 2,
      });
    }

    function formatDateForInput(value) {
      if (!value) return '';
      if (typeof value === 'string') {
        const br = value.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
        if (br) return `${br[3]}-${br[2]}-${br[1]}`;
      }
      const d = new Date(value);
      if (Number.isNaN(d.getTime())) return '';
      const year = d.getFullYear();
      const month = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    }

    function parseDraftFromUrl(raw) {
      if (!raw) return null;
      try {
        return JSON.parse(decodeURIComponent(raw));
      } catch (error) {
        try {
          return JSON.parse(raw);
        } catch (error2) {
          return null;
        }
      }
    }

    function normalizeDraftLancamento(raw) {
      if (!raw) return null;
      const descricao = raw.descricao || raw.nome_estabelecimento || 'Lançamento';
      const valor = raw.valor ?? raw.valor_total ?? 0;
      const tipo = raw.tipo || raw.tipo_transacao || 'Saída';
      const data = raw.data_transacao || raw.data || '';
      const formaPagamento = raw.forma_pagamento_conta || raw.forma_pagamento || '';
      const contaNome = raw.forma_pagamento_conta || raw.conta_nome || '';
      const categoria = raw.categoria_sugerida || raw.categoria || '';
      const subcategoria = raw.subcategoria_sugerida || raw.subcategoria || '';

      return {
        ...raw,
        id: raw.id || null,
        descricao,
        valor,
        tipo,
        data,
        forma_pagamento: formaPagamento,
        conta_nome: contaNome,
        categoria_sugerida: categoria,
        subcategoria_sugerida: subcategoria,
      };
    }

    function applyDraftDetails(item) {
      if (!item) return;
      const categoria = [item.categoria_sugerida, item.subcategoria_sugerida].filter(Boolean).join(' / ');
      const contaLabel = item.conta_nome || item.forma_pagamento || 'Conta não definida';
      editDraftInfo.innerHTML = `
        <div><b>Pré-preenchido:</b> ${item.descricao || 'Lançamento'}</div>
        <div><b>Conta:</b> ${contaLabel}</div>
        <div><b>Categoria:</b> ${categoria || 'N/A'}</div>
      `;
      editDraftInfo.classList.remove('hidden');
    }

    pendingDraftLaunch = parseDraftFromUrl(rawDraftFromUrl);

    function parseMoneyInput(value) {
      const raw = String(value || '').replace(/\./g, '').replace(',', '.').trim();
      const parsed = parseFloat(raw);
      return Number.isNaN(parsed) ? 0 : parsed;
    }

    function setSelectedLancamento(item) {
      selectedLancamento = item;
      selectedLancamentoIsDraft = Boolean(item && !item.id);
      if (!item) {
        editModalBadge.textContent = 'Nenhum lançamento selecionado';
        editDraftInfo.classList.add('hidden');
        editDraftInfo.innerHTML = '';
        editDescricao.value = '';
        editValor.value = '';
        editTipo.value = 'Saída';
        editData.value = '';
        editForma.value = '';
        editCategoria.value = '';
        editSubcategoria.value = '';
        editLearnRule.checked = false;
        return;
      }
      editModalBadge.textContent = item.id ? `Editando: ${item.descricao || 'Lançamento'}` : `Pré-edição: ${item.descricao || 'Lançamento'}`;
      editDescricao.value = item.descricao || '';
      editValor.value = item.valor != null ? String(item.valor).replace('.', ',') : '';
      editTipo.value = item.tipo || 'Saída';
      editData.value = formatDateForInput(item.data);
      editForma.value = item.forma_pagamento || '';
      editLearnRule.checked = false;

      // Garantir carregamento das categorias no select
      ensureCategoriesLoaded().then(() => {
        if (item.id_categoria) {
          editCategoria.value = item.id_categoria;
          updateSubcategories(item.id_categoria, item.id_subcategoria);
        } else {
          editCategoria.value = '';
          editSubcategoria.innerHTML = '<option value="">Selecione a subcategoria</option>';
        }
      });

      if (item.id) {
        editDraftInfo.classList.add('hidden');
        editDraftInfo.innerHTML = '';
      } else {
        applyDraftDetails(item);
      }
    }

    let categoriesDataCache = null;
    async function ensureCategoriesLoaded() {
      if (categoriesDataCache && editCategoria.options.length > 1) return;
      try {
        const res = await fetchWithSession('/api/miniapp/orcamentos'); // Reaproveita rota que já traz categorias
        const data = await res.json();
        if (data.ok && data.categorias) {
          categoriesDataCache = data.categorias;
          editCategoria.innerHTML = '<option value="">Selecione a categoria</option>' + 
            data.categorias.map(c => `<option value="${c.id}">${c.nome}</option>`).join('');
        }
      } catch (e) { console.error('Erro ao carregar categorias:', e); }
    }

    function updateSubcategories(catId, selectedSubId = null) {
      if (!categoriesDataCache) return;
      const cat = categoriesDataCache.find(c => String(c.id) === String(catId));
      if (cat && cat.subcategorias) {
        editSubcategoria.innerHTML = '<option value="">Selecione a subcategoria</option>' + 
          cat.subcategorias.map(s => `<option value="${s.id}">${s.nome}</option>`).join('');
        if (selectedSubId) editSubcategoria.value = selectedSubId;
      } else {
        editSubcategoria.innerHTML = '<option value="">Selecione a subcategoria</option>';
      }
    }

    editCategoria.addEventListener('change', (e) => updateSubcategories(e.target.value));

    function openEditModal(item) {
      setSelectedLancamento(item);
      openModal('editModal');
    }

    function closeEditModal() {
      closeModal('editModal');
      setSelectedLancamento(null);
    }

    function showToast(message, type = 'success') {
      const toastContainer = document.getElementById('toastContainer');
      const toast = document.createElement('div');
      toast.className = `toast ${type}`;
      const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : '!';
      toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
      toastContainer.appendChild(toast);
      setTimeout(() => toast.remove(), 3000);
    }

    async function reauthenticateSession() {
      if (!telegramInitData) return false;
      if (reauthInFlight) return reauthInFlight;

      reauthInFlight = (async () => {
        try {
          const response = await fetch('/api/telegram/auth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ init_data: telegramInitData }),
          });
          const data = await response.json();
          if (!data.ok || !data.session_id) return false;
          sessionId = data.session_id;
          try { localStorage.setItem(MINIAPP_SESSION_STORAGE_KEY, sessionId); } catch (_) {}
          return true;
        } catch (_) {
          return false;
        } finally {
          reauthInFlight = null;
        }
      })();

      return reauthInFlight;
    }

    function getStoredSessionId() {
      try {
        return localStorage.getItem(MINIAPP_SESSION_STORAGE_KEY) || '';
      } catch (_) {
        return '';
      }
    }

    function storeSessionId(value) {
      if (!value) return;
      try {
        localStorage.setItem(MINIAPP_SESSION_STORAGE_KEY, value);
      } catch (_) {}
    }

    async function tryRecoverSessionFromStorage() {
      // 1) Tenta recuperar do localStorage
      const cached = getStoredSessionId();
      if (cached) {
        try {
          const response = await fetch('/api/miniapp/overview', {
            headers: { 'X-Session-Id': cached },
          });
          if (response.ok) {
            const data = await response.json();
            if (data?.ok) {
              sessionId = cached;
              return true;
            }
          }
        } catch (_) {
          // continue to other fallbacks
        }
      }

      // 2) Fallback: tentar ler `session_id` da query string (ex: ?session_id=...)
      try {
        const urlParam = (new URLSearchParams(window.location.search)).get('session_id');
        if (urlParam) {
          try {
            const resp = await fetch(`/api/miniapp/overview?session_id=${encodeURIComponent(urlParam)}`);
            if (resp.ok) {
              const d = await resp.json();
              if (d?.ok) {
                sessionId = urlParam;
                try { storeSessionId(sessionId); } catch (_) {}
                return true;
              }
            }
          } catch (_) {}
        }
      } catch (_) {}

      return false;
    }

    async function fetchWithSession(url, options = {}, retryOnUnauthorized = true) {
      if (!sessionId) throw new Error('no_session');

      const headers = { ...(options.headers || {}), 'X-Session-Id': sessionId };
      const response = await fetch(url, { ...options, headers });
      if (response.status !== 401 || !retryOnUnauthorized) return response;

      const reauthOk = await reauthenticateSession();
      if (!reauthOk) return response;

      const retryHeaders = { ...(options.headers || {}), 'X-Session-Id': sessionId };
      return fetch(url, { ...options, headers: retryHeaders });
    }

    function formatCurrencyBR(value) {
      return `R$ ${Number(value || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }

    function sourceBadgeConfig(origem) {
      const sourceRaw = String(origem || 'manual').trim();
      const source = sourceRaw.toLowerCase();
      const mapping = {
        manual: ['Manual', 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700'],
        texto: ['Manual', 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700'],
        miniapp: ['Manual', 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700'],
        alfredo: ['Manual', 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700'],
        'por voz': ['Por voz', 'bg-cyan-100 text-cyan-800 border-cyan-200 dark:bg-cyan-900/40 dark:text-cyan-200 dark:border-cyan-800'],
        audio: ['Por voz', 'bg-cyan-100 text-cyan-800 border-cyan-200 dark:bg-cyan-900/40 dark:text-cyan-200 dark:border-cyan-800'],
        voz: ['Por voz', 'bg-cyan-100 text-cyan-800 border-cyan-200 dark:bg-cyan-900/40 dark:text-cyan-200 dark:border-cyan-800'],
        ocr: ['OCR', 'bg-violet-100 text-violet-800 border-violet-200 dark:bg-violet-900/40 dark:text-violet-200 dark:border-violet-800'],
        fatura: ['Fatura', 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/40 dark:text-amber-200 dark:border-amber-800'],
      };
      if (source.startsWith('fatura') || source.startsWith('extrato')) {
        return mapping.fatura;
      }
      return mapping[source] || [sourceRaw || 'Manual', 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700'];
    }

    function getCategoryStyle(descricao, categoria, subcategoria, tipo) {
      const combined = `${descricao || ''} ${categoria || ''} ${subcategoria || ''}`.toLowerCase();
      
      const brands = {
        'uber': 'uber.com',
        ' 99': '99app.com',
        '99app': '99app.com',
        'ifood': 'ifood.com.br',
        'rappi': 'rappi.com',
        'netflix': 'netflix.com',
        'spotify': 'spotify.com',
        'amazon': 'amazon.com',
        'prime': 'amazon.com',
        'mercado livre': 'mercadolivre.com.br',
        'meli': 'mercadolivre.com.br',
        'nubank': 'nubank.com.br',
        'inter': 'bancointer.com.br',
        'itau': 'itau.com.br',
        'bradesco': 'bradesco.com.br',
        'santander': 'santander.com.br',
        'banco do brasil': 'bb.com.br',
        'extra': 'extra.com.br',
        'carrefour': 'carrefour.com.br',
        'pao de acucar': 'paodeacucar.com.br',
        'samsung': 'samsung.com',
        'apple': 'apple.com',
        'claro': 'claro.com.br',
        'vivo': 'vivo.com.br',
        'tim': 'tim.com.br',
        'mcdonald': 'mcdonalds.com.br',
        'burger king': 'burgerking.com.br',
        'bk ': 'burgerking.com.br',
        'starbucks': 'starbucks.com',
        'shell': 'shell.com.br',
        'ipiranga': 'postossipiranga.com.br',
        'petrobras': 'petrobras.com.br',
        'flamengo': 'flamengo.com.br',
        'corinthians': 'corinthians.com.br',
        'palmeiras': 'palmeiras.com.br',
        'sao paulo': 'saopaulofc.net',
        'fluminense': 'fluminense.com.br',
        'vasco': 'vasco.com.br',
        'botafogo': 'botafogo.com.br',
        'gremio': 'gremio.net',
        'internacional': 'internacional.com.br',
        'inter ': 'internacional.com.br',
        'atletico-mg': 'atletico.com.br',
        'atletico mg': 'atletico.com.br',
        'athletico': 'athletico.com.br',
        'cruzeiro': 'cruzeiro.com.br',
        'santos fc': 'santosfc.com.br',
        'bahia': 'esporteclubebahia.com.br',
        'vitoria': 'ecvitoria.com.br',
        'bragantino': 'redbullbragantino.com.br',
        'coritiba': 'coritiba.com.br',
        'chapecoense': 'chapecoense.com',
        'remo': 'clubedoremo.com.br',
        'mirassol': 'mirassolfc.com.br',
        'magalu': 'magazineluiza.com.br',
        'magazine luiza': 'magazineluiza.com.br',
        'americanas': 'americanas.com.br',
        'casas bahia': 'casasbahia.com.br',
        'ponto frio': 'pontofrio.com.br',
        'lojas pacheco': 'drogariaspacheco.com.br',
        'drogasil': 'drogasil.com.br',
        'droga raia': 'drogaraia.com.br',
        'pague menos': 'paguemenos.com.br',
        'renner': 'lojasrenner.com.br',
        'cea': 'cea.com.br',
        'riachuelo': 'riachuelo.com.br',
        'zara': 'zara.com',
        'habibs': 'habibs.com.br',
        'outback': 'outback.com.br',
        'madeiro': 'madeiro.com.br',
        'coco bambu': 'cocobambu.com',
        'boticario': 'boticario.com.br',
        'natura': 'natura.com.br',
        'sephora': 'sephora.com.br',
        'steam': 'steampowered.com',
        'playstation': 'playstation.com',
        'xbox': 'xbox.com',
        'nintendo': 'nintendo.com',
        'google': 'google.com',
        'facebook': 'facebook.com',
        'instagram': 'instagram.com',
        'disney': 'disneyplus.com',
        'hbo': 'max.com',
        'max': 'max.com',
        'gympass': 'gympass.com',
        'wellhub': 'wellhub.com',
        'totalpass': 'totalpass.com.br'
      };

      let logoUrl = null;
      for (const [key, domain] of Object.entries(brands)) {
        if (combined.includes(key)) {
          // Usando o serviço de favicon do Google como primário por ser mais estável contra erros de DNS e redirects
          logoUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=128`;
          break;
        }
      }

      // Category Map for Fallback
      const map = [
        { keys: ['aliment', 'mercado', 'padaria', 'super'], icon: 'shopping-cart', class: 'cat-shopping' },
        { keys: ['restaurante', 'lanche', 'pizza', 'burger'], icon: 'utensils', class: 'cat-food' },
        { keys: ['transporte', 'táxi', 'taxi', 'estacionamento'], icon: 'car', class: 'cat-transport' },
        { keys: ['saúde', 'saude', 'médico', 'medico', 'hospital', 'farmácia'], icon: 'heart-pulse', class: 'cat-health' },
        { keys: ['lazer', 'entretenimento', 'cinema', 'show', 'bar'], icon: 'popcorn', class: 'cat-entertainment' },
        { keys: ['casa', 'aluguel', 'luz', 'água', 'internet'], icon: 'home', class: 'cat-utilities' },
        { keys: ['salário', 'renda', 'recebido', 'pix'], icon: 'coins', class: 'cat-health' },
      ];

      let result = { icon: 'receipt', class: 'cat-shopping', logoUrl: logoUrl };
      for (const item of map) {
        if (item.keys.some(key => combined.includes(key))) {
          result = { icon: item.icon, class: item.class, logoUrl: logoUrl };
          break;
        }
      }

      const isReceita = isEntradaTipo(tipo, 0);
      if (result.icon === 'receipt' && isReceita) {
        result.icon = 'arrow-down-to-line';
        result.class = 'cat-health';
      }
      
      return result;
    }

    function renderHomeRecent(items = []) {
      if (!items.length) {
        homeRecentList.innerHTML = '<div class="rounded-2xl border border-dashed border-telegram-separator bg-telegram-card p-4 text-sm text-telegram-hint font-mono uppercase tracking-widest text-center">Nenhum registro recente</div>';
        return;
      }

      homeRecentList.innerHTML = items.map((item) => {
        const numericValue = Number(item.valor) || 0;
        const isReceita = isEntradaTipo(item.tipo, numericValue);
        const [badgeLabel, badgeClass] = sourceBadgeConfig(item.origem_label || item.origem);
        const style = getCategoryStyle(item.descricao, item.categoria_nome, item.subcategoria_nome, item.tipo);

        // Formatar data: 14 Abr ou Hoje/Ontem
        let dataFormatada = '';
        if (item.data) {
          const d = new Date(item.data);
          const hoje = new Date();
          const ontem = new Date();
          ontem.setDate(hoje.getDate() - 1);

          if (d.toDateString() === hoje.toDateString()) {
            dataFormatada = 'Hoje';
          } else if (d.toDateString() === ontem.toDateString()) {
            dataFormatada = 'Ontem';
          } else {
            dataFormatada = d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' }).replace('.', '');
          }
        }

        const iconHtml = style.logoUrl
          ? `<div class="w-10 h-10 rounded-full overflow-hidden bg-white flex items-center justify-center border border-white/10 shadow-sm">
               <img src="${style.logoUrl}" class="w-full h-full object-contain" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
               <div class="hidden w-full h-full items-center justify-center bg-brand/5 text-brand"><i data-lucide="${style.icon}" class="w-5 h-5"></i></div>
             </div>`
          : `<div class="cat-icon ${style.class} shrink-0 w-10 h-10"><i data-lucide="${style.icon}" class="w-5 h-5"></i></div>`;

        return `
          <button class="recent-item w-full text-left rounded-3xl border border-white/5 bg-telegram-card p-4 hover:bg-brand/5 transition shadow-soft mb-3" data-action="edit" data-id="${item.id}">
            <div class="flex items-center gap-4">
              ${iconHtml}
              <div class="min-w-0 flex-1">
                <div class="flex items-start justify-between gap-2">
                  <div class="min-w-0">
                    <p class="font-bold text-sm text-telegram-text truncate">${item.descricao || 'Lançamento'}</p>
                    <div class="flex items-center gap-2 mt-0.5">
                      <p class="text-[10px] font-bold text-telegram-hint uppercase tracking-wider">${item.categoria_nome || 'Sem categoria'}</p>
                      <span class="text-[10px] text-telegram-hint/50">•</span>
                      <p class="text-[10px] font-bold text-brand-soft uppercase tracking-wider">${dataFormatada}</p>
                    </div>
                  </div>
                  <div class="text-right shrink-0 flex flex-col items-end gap-1">
                    <span class="font-financial text-base font-black ${isReceita ? 'text-emerald-500' : 'text-rose-500'}">${formatMoney(item.valor, item.tipo)}</span>
                    <span class="text-[8px] font-black uppercase tracking-widest rounded-md border border-white/5 px-1.5 py-0.5 bg-black/20 text-telegram-hint">${badgeLabel}</span>
                  </div>
                </div>
              </div>
            </div>
          </button>
        `;
      }).join('');
    }
    function renderHistorySkeleton(count = 5) {
      historyStatus.textContent = '';
      historyList.innerHTML = Array.from({ length: count }).map(() => `
        <div class="flex items-center justify-between gap-3 rounded-2xl border border-telegram-separator bg-telegram-card p-4 shadow-soft animate-pulse">
          <div class="flex items-center gap-3 min-w-0 flex-1">
            <div class="h-10 w-10 rounded-full skeleton-block"></div>
            <div class="min-w-0 flex-1 space-y-2">
              <div class="h-4 w-2/3 skeleton-block"></div>
              <div class="h-3 w-1/2 skeleton-block"></div>
            </div>
          </div>
          <div class="h-8 w-24 rounded-xl skeleton-block"></div>
        </div>
      `).join('');
    }

    function renderMetaSkeleton(count = 3) {
      metaStatus.textContent = '';
      metaList.innerHTML = Array.from({ length: count }).map(() => `
        <div class="rounded-3xl border border-telegram-separator bg-telegram-card p-5 shadow-soft animate-pulse space-y-3">
          <div class="h-4 w-1/3 skeleton-block"></div>
          <div class="h-5 w-2/3 skeleton-block"></div>
          <div class="h-3 w-1/2 skeleton-block"></div>
          <div class="flex gap-2 pt-2">
            <div class="h-8 w-20 rounded-xl skeleton-block"></div>
            <div class="h-8 w-20 rounded-xl skeleton-block"></div>
            <div class="h-8 w-24 rounded-xl skeleton-block"></div>
          </div>
        </div>
      `).join('');
    }

    function renderAgendamentoSkeleton(count = 3) {
      agendamentoStatus.textContent = '';
      agendamentoList.innerHTML = Array.from({ length: count }).map(() => `
        <div class="flex items-center justify-between gap-3 rounded-2xl border border-telegram-separator bg-telegram-card p-4 shadow-soft animate-pulse">
          <div class="space-y-2 flex-1 min-w-0">
            <div class="h-4 w-2/3 skeleton-block"></div>
            <div class="h-3 w-1/2 skeleton-block"></div>
          </div>
          <div class="h-8 w-20 rounded-xl skeleton-block"></div>
        </div>
      `).join('');
      if (lembreteHistoryWrap) lembreteHistoryWrap.classList.add('hidden');
      if (lembreteHistoryList) lembreteHistoryList.innerHTML = '';
      if (lembreteHistoryStatus) lembreteHistoryStatus.textContent = '';
      if (orcamentoAgendaWrap) orcamentoAgendaWrap.classList.add('hidden');
    }

    function refreshAgendaTabs() {
      if (agendaTabAgendamentos) {
        agendaTabAgendamentos.className = agendaMode === 'agendamentos'
          ? 'rounded-xl bg-brand px-4 py-2 text-xs font-semibold text-white shadow-soft transition'
          : 'rounded-xl border border-telegram-separator bg-telegram-card px-4 py-2 text-xs font-semibold text-telegram-text transition';
      }
      if (agendaTabLembretes) {
        agendaTabLembretes.className = agendaMode === 'lembretes'
          ? 'rounded-xl bg-brand px-4 py-2 text-xs font-semibold text-white shadow-soft transition'
          : 'rounded-xl border border-telegram-separator bg-telegram-card px-4 py-2 text-xs font-semibold text-telegram-text transition';
      }
      if (agendaTabLimites) {
        agendaTabLimites.className = agendaMode === 'limites'
          ? 'rounded-xl bg-brand px-4 py-2 text-xs font-semibold text-white shadow-soft transition'
          : 'rounded-xl border border-telegram-separator bg-telegram-card px-4 py-2 text-xs font-semibold text-telegram-text transition';
      }
    }

    function updateAgendaModalLabels() {
      const isReminder = agendaMode === 'lembretes';
      const isLimits = agendaMode === 'limites';
      if (agendaModalTitle) agendaModalTitle.textContent = isReminder ? 'Novo Lembrete' : 'Novo Agendamento';
      if (agendaValorLabel) agendaValorLabel.textContent = isReminder ? 'Valor (opcional)' : 'Valor';
      if (agendaDataLabel) agendaDataLabel.textContent = isReminder ? 'Data do lembrete' : 'Primeira execução';
      if (newAgendSave?.querySelector('.save-text')) {
        newAgendSave.querySelector('.save-text').textContent = isReminder ? 'Criar lembrete' : 'Criar agendamento';
      }
      if (newAgendValor) newAgendValor.required = !isReminder;
      if (lembreteHistoryWrap) lembreteHistoryWrap.classList.toggle('hidden', !isReminder);
      if (orcamentoAgendaWrap) orcamentoAgendaWrap.classList.toggle('hidden', !isLimits);
      if (agendamentoNew) {
        agendamentoNew.title = isLimits ? 'Novo limite' : (isReminder ? 'Novo lembrete' : 'Novo agendamento');
      }
    }

    function setAgendaMode(mode) {
      agendaMode = mode === 'lembretes' ? 'lembretes' : (mode === 'limites' ? 'limites' : 'agendamentos');
      refreshAgendaTabs();
      updateAgendaModalLabels();
      loadAgendamentos();
    }

    function canUseChartMotion() {
      return !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    function canUseUiMotion() {
      return !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    function animateMetaProgressBars() {
      const progressBars = metaList.querySelectorAll('[data-meta-progress]');
      if (!progressBars.length) return;

      if (!canUseUiMotion()) {
        progressBars.forEach((bar) => {
          const target = Number(bar.dataset.metaProgress || 0);
          bar.style.width = `${Math.max(0, Math.min(100, target))}%`;
        });
        return;
      }

      progressBars.forEach((bar) => {
        const target = Number(bar.dataset.metaProgress || 0);
        bar.style.width = '0%';
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            bar.style.width = `${Math.max(0, Math.min(100, target))}%`;
          });
        });
      });
    }

  async function resolveTelegramInitData(maxRetries = 20, intervalMs = 150) {
      for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
        const current = Telegram?.WebApp?.initData;
        if (current) return current;
        if (attempt < maxRetries) {
          await new Promise((resolve) => setTimeout(resolve, intervalMs));
        }
      }
      return '';
    }

    function getChartRuntime() {
      const isMobile = window.matchMedia('(max-width: 768px)').matches;
      return {
        isMobile,
        enableMotion: canUseChartMotion() && !isMobile,
        barThickness: isMobile ? 8 : 12,
        legendFont: isMobile ? 11 : 12,
        maxTicks: isMobile ? 8 : 14,
      };
    }

    function monthLabels(count) {
      const baseDate = new Date();
      const labels = [];
      for (let i = count - 1; i >= 0; i -= 1) {
        const d = new Date(baseDate.getFullYear(), baseDate.getMonth() - i, 1);
        labels.push(d.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', ''));
      }
      return labels;
    }

    function setActiveHomeChartPill(targetId) {
      homeChartPills.forEach((pill) => {
        const isActive = pill.dataset.homeChartPill === targetId;
        pill.classList.toggle('bg-brand/10', isActive);
        pill.classList.toggle('border-brand/25', isActive);
        pill.classList.toggle('text-brand', isActive);
        pill.classList.toggle('font-bold', isActive);
        pill.classList.toggle('bg-telegram-card', !isActive);
        pill.classList.toggle('border-telegram-separator', !isActive);
        pill.classList.toggle('text-telegram-hint', !isActive);
        pill.classList.toggle('font-semibold', !isActive);
      });
    }

    function setupHomeChartsCarousel() {
      if (!homeChartsPills || !homeChartCarousel || !homeChartPills.length || !homeChartCards.length) return;

      homeChartPills.forEach((pill) => {
        pill.addEventListener('click', () => {
          const targetId = pill.dataset.homeChartPill;
          const targetCard = document.getElementById(targetId);
          if (!targetCard) return;
          targetCard.scrollIntoView({ behavior: 'smooth', inline: 'start', block: 'nearest' });
          setActiveHomeChartPill(targetId);
        });
      });

      if (homeChartsObserver) homeChartsObserver.disconnect();
      if ('IntersectionObserver' in window) {
        homeChartsObserver = new IntersectionObserver((entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting && entry.intersectionRatio > 0.58) {
              setActiveHomeChartPill(entry.target.id);
            }
          });
        }, {
          root: homeChartCarousel,
          threshold: [0.58, 0.78],
        });

        homeChartCards.forEach((card) => homeChartsObserver.observe(card));
      }

      setActiveHomeChartPill(homeChartCards[0].id);
    }

        function buildChartDataFromSummary(summary) {
      const now = new Date();
      const startDay = new Date(now.getFullYear(), now.getMonth(), 1).getDay();
      const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
      
      const activity = {};
      (summary?.recent || []).forEach(item => {
        const d = new Date(item.data);
        if (d.getMonth() === now.getMonth()) {
          const day = d.getDate();
          const val = Number(item.valor || 0);
          if (!activity[day]) activity[day] = { incT: 0, expT: 0, incC: 0, expC: 0 };
          if (val > 0) { activity[day].incT += val; activity[day].incC++; }
          else { activity[day].expT += Math.abs(val); activity[day].expC++; }
        }
      });

      const heatmapData = [];
      const daysShort = ['Dom','Seg','Ter','Qua','Qui','Sex','S�b'];
      for (let w = 0; w < 6; w++) {
        daysShort.forEach((d, i) => {
          const dayNum = (w * 7) + i - startDay + 1;
          let type = 'empty'; let label = ""; let stats = { inc: 0, exp: 0 };
          if (dayNum > 0 && dayNum <= daysInMonth) {
            label = dayNum.toString();
            const act = activity[dayNum];
            if (act) {
              stats.inc = act.incC; stats.exp = act.expC;
              type = (act.incT > act.expT) ? 'income_win' : 'expense_win';
            } else { type = 'day'; }
          }
          heatmapData.push({ x: d, y: `Sem ${w+1}`, date: label, type: type, stats: stats });
        });
      }

      const receita = Number(summary?.receita || 0);
      const despesa = Number(summary?.despesa || 0);
      const categories = (Array.isArray(summary?.categories) ? summary.categories : []).slice(0, 6);
      const monthlyCashflow = Array.isArray(summary?.cashflow_monthly) ? summary.cashflow_monthly : [];
      const patrimonySeries = Array.isArray(summary?.patrimony_series) ? summary.patrimony_series : [];
      const budgetItems = Array.isArray(summary?.budget_vs_realizado) ? summary.budget_vs_realizado : [];
      const projectionSeries = Array.isArray(summary?.projection_series) ? summary.projection_series : [];
      const topVillains = Array.isArray(summary?.top_villains) ? summary.top_villains : [];

      const sankeyData = [];
      if (receita > 0) sankeyData.push({ from: 'Receitas', to: 'Caixa', flow: receita });
      if (despesa > 0) {
        sankeyData.push({ from: 'Caixa', to: 'Despesas', flow: despesa });
        categories.forEach(c => { if(c.value > 0) sankeyData.push({ from: 'Despesas', to: c.label, flow: Number(c.value) }); });
      }

      return {
        sixMonths: monthlyCashflow.map(i => i.label || ''),
        patrimonyMonths: patrimonySeries.map(i => i.label || ''),
        patrimonyValues: patrimonySeries.map(i => Number(i.value || 0)),
        fluxoEntradas: monthlyCashflow.map(i => Number(i.entrada || 0)),
        fluxoSaidas: monthlyCashflow.map(i => Number(i.saida || 0)),
        fluxoSaldo: monthlyCashflow.map(i => Number(i.saldo || 0)),
        budgetLabels: budgetItems.map(i => i.label || ''),
        budgetPlanned: budgetItems.map(i => Number(i.orcamento || 0)),
        budgetActual: budgetItems.map(i => Number(i.realizado || 0)),
        categories, distroLabels: categories.map(i => i.label || ''), distroValues: categories.map(i => Number(i.value || 0)),
        projectionLabels: projectionSeries.map(i => i.label || ''),
        projectionHistory: projectionSeries.map(i => i.historico == null ? null : Number(i.historico)),
        projectionFuture: projectionSeries.map(i => i.futuro == null ? null : Number(i.futuro)),
        villains: topVillains.map(i => [i.label, Number(i.value)]),
        sankeyData, heatmapData
      };
    }

    function renderSankeyPremium(container, data) {
      if (!container || !data.length) return;
      const width = 800; const height = 450;
      const vProfundo = '#064E3B'; const gProfundo = '#4a1019';
      const palette = ['#D4AF37', '#818cf8', '#f472b6', '#fbbf24', '#34d399', '#a78bfa'];
      const totalRec = data.filter(d => d.from === 'Receitas').reduce((a, b) => a + b.flow, 0);
      const totalExp = data.filter(d => d.from === 'Caixa' && d.to === 'Despesas').reduce((a, b) => a + b.flow, 0);
      const despesas = data.filter(d => d.from === 'Despesas');
      const maxHeight = 300;
      const scale = maxHeight / Math.max(totalRec, totalExp, 1);
      let svgHtml = `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" style="width:100%; height:auto; overflow:visible;">
        <defs>
          ${despesas.map((c, i) => `<linearGradient id="g-cat-${i}" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="${gProfundo}" stop-opacity="0.4"/><stop offset="100%" stop-color="${palette[i % palette.length]}" stop-opacity="0.5"/></linearGradient>`).join('')}
        </defs>
        <text x="85" y="40" text-anchor="middle" font-size="11" font-weight="900" fill="${vProfundo}">ENTRADA</text>
        <text x="300" y="40" text-anchor="middle" font-size="11" font-weight="900" fill="${gProfundo}">GEST�O</text>
        <text x="610" y="40" text-anchor="middle" font-size="11" font-weight="900" fill="#64748b">SA�DAS</text>
        <rect x="25" y="${70 + (maxHeight - Math.max(40, totalRec * scale))/2}" width="120" height="${Math.max(40, totalRec * scale)}" rx="12" fill="rgba(16, 185, 129, 0.05)" stroke="#10b981" stroke-width="2" />
        <text x="85" y="210" text-anchor="middle" font-size="13" font-weight="900" fill="${vProfundo}">RECEITAS</text>
        <text x="85" y="235" text-anchor="middle" font-size="12" font-weight="bold" fill="${vProfundo}">${formatCurrencyBR(totalRec)}</text>
        <rect x="240" y="${70 + (maxHeight - Math.max(40, totalExp * scale))/2}" width="120" height="${Math.max(40, totalExp * scale)}" rx="12" fill="rgba(123, 30, 45, 0.05)" stroke="#7b1e2d" stroke-width="2" />
        <text x="300" y="210" text-anchor="middle" font-size="13" font-weight="900" fill="${gProfundo}">CAIXA</text>
        ${despesas.slice(0, 5).map((cat, i) => {
          const h = Math.max(45, cat.flow * scale); const y = 70 + (i * 65); const color = palette[i % palette.length];
          return `<path d="M360,210 C460,210 460,${y + h/2} 510,${y + h/2}" stroke="url(#g-cat-${i})" stroke-width="${Math.max(2, cat.flow * scale)}" fill="none" opacity="0.6" /><rect x="510" y="${y}" width="200" height="${h}" rx="12" fill="rgba(255,255,255,0.03)" stroke="${color}" stroke-opacity="0.5" stroke-width="2" /><rect x="510" y="${y}" width="4" height="${h}" rx="2" fill="${color}" /><text x="610" y="${y + h/2 - 5}" text-anchor="middle" font-size="10" font-weight="900" fill="${color}">${cat.to.toUpperCase()}</text><text x="610" y="${y + h/2 + 12}" text-anchor="middle" font-size="11" font-weight="bold" fill="${color}">${formatCurrencyBR(cat.flow)}</text>`;
        }).join('')}
      </svg>`;
      container.innerHTML = svgHtml;
    }

    function destroyHomeCharts() {
      try {
        Object.values(homeCharts).forEach((chart) => { if (chart && typeof chart.destroy === 'function') chart.destroy(); });
      } catch (e) { console.warn('destroyHomeCharts error:', e); }
      homeCharts = {};
    }

    function updateAquariumVisual(receita, despesa) {
      try {
        const svg = document.getElementById('homeAquariumSVG');
        if (!svg) return;
        const vbW = 1200; const vbH = 200;
        const total = Math.max(0.0001, Number(receita || 0) + Number(despesa || 0));
        const ratio = Number(receita || 0) / total;
        const xStart = vbW * 0.08; const xEnd = vbW * 0.92;
        const steps = 10; const points = [];
        for (let i = 0; i <= steps; i += 1) {
          const t = i / steps;
          const y = vbH - t * (vbH * 0.78) - vbH * 0.06;
          const base = xStart * (1 - t) + xEnd * t;
          const globalOffset = (ratio - 0.5) * vbW * 0.42;
          const waviness = Math.sin(t * Math.PI * 3 + (ratio * Math.PI)) * (vbW * 0.04) * (1 - Math.abs(t - 0.5));
          const x = Math.max(0, Math.min(vbW, Math.round(base + globalOffset + waviness)));
          points.push({ x, y: Math.round(y) });
        }
        const last = points.length - 1;
        const forwardPts = points.map(p => `${p.x} ${p.y}`).join(' ');
        const reversePts = points.slice().reverse().map(p => `${p.x} ${p.y}`).join(' ');
        const greenD = `M 0 ${vbH} L 0 0 L ${points[last].x} ${points[last].y} L ${reversePts} Z`;
        const redD = `M ${vbW} ${vbH} L ${vbW} 0 L ${points[last].x} ${points[last].y} L ${forwardPts} Z`;
        const g = svg.querySelector('#aqGreen');
        const r = svg.querySelector('#aqRed');
        if (g) g.setAttribute('d', greenD);
        if (r) r.setAttribute('d', redD);
      } catch (err) { console.warn('updateAquariumVisual error:', err); }
    }

    function renderHomeOverview(summary) {
      const balance = Number(summary?.balance || 0);
      const receita = Number(summary?.receita || 0);
      const despesa = Number(summary?.despesa || 0);
      const progressPct = Math.max(0, Math.min(Number(summary?.progress_pct || 0), 100));
      // Plano do usuário disponível para decisões de UI (evita ReferenceError)
      const userPlan = summary?.plan || 'free';

      const missing = [];
      if (!homeBalance) missing.push('homeBalance');
      if (!homeBalanceHint) missing.push('homeBalanceHint');
      if (!homeLevel) missing.push('homeLevel');
      if (!homeXp) missing.push('homeXp');
      if (!homeStreak) missing.push('homeStreak');
      // Elementos do antigo aquário são agora opcionais e não geram aviso se faltarem
      if (!homeReceita) missing.push('homeReceita');
      if (!homeDespesa) missing.push('homeDespesa');
      if (!homeInsight) missing.push('homeInsight');
      if (!homeBadgeContainer) missing.push('homeBadgeContainer');
      if (!homePlanLabel) {
        // Cria fallback visual para homePlanLabel se não existir
        const fallback = document.createElement('span');
        fallback.id = 'homePlanLabel';
        fallback.style.display = 'none';
        document.body.appendChild(fallback);
        window.homePlanLabel = fallback;
      }
      if (!homeUpgradeBtn) missing.push('homeUpgradeBtn');
      if (!homeRecentList) missing.push('homeRecentList');
      if (missing.length > 5) console.warn('renderHomeOverview: muitos elementos ausentes no DOM:', missing.join(', '));

      if (homeBalance) homeBalance.textContent = formatCurrencyBR(balance);
      if (homeBalanceHint) homeBalanceHint.textContent = balance >= 0 ? 'Você está fechando o mês no azul.' : 'As despesas estão pressionando o mês.';

      if (homeLevel) homeLevel.textContent = String(summary?.level || 1);
      if (homeXp) homeXp.textContent = String(summary?.xp || 0);
      if (homeStreak) homeStreak.textContent = `${summary?.streak || 0} DIAS`;
      
      const totalFluxo = receita + despesa;
      const pctReceita = totalFluxo > 0 ? Math.round((receita / totalFluxo) * 100) : 0;
      const pctDespesa = totalFluxo > 0 ? Math.round((despesa / totalFluxo) * 100) : 0;

      // Novo Efeito Líquido (Aquário Pro)
      const lp = document.getElementById('liquidPath');
      const sp = document.getElementById('shimmerPath');
      const grad = document.getElementById('liquidGrad');

      if (lp && grad) {
        const pct = Math.max(0, Math.min(1, receita / (totalFluxo || 1)));
        const bal = receita - despesa;

        // Wave: pct=1 (só receita) → onda sobe muito
        const waveTopLeft = 420 * (1 - pct * 0.82 - 0.08);
        const waveTopRight = 420 * (1 - pct * 0.92 - 0.04);

        if (bal >= 0) {
          const greenStop = Math.round(pct * 100);
          grad.innerHTML = `
            <stop offset="0%" stop-color="#022c22" stop-opacity="0.9"/>
            <stop offset="${greenStop}%" stop-color="#065f46" stop-opacity="0.8"/>
            <stop offset="100%" stop-color="#134e4a" stop-opacity="0.7"/>
          `;
        } else {
          const rPct = Math.round((1 - pct) * 100);
          grad.innerHTML = `
            <stop offset="0%" stop-color="#7f1d1d" stop-opacity="0.9"/>
            <stop offset="${rPct}%" stop-color="#991b1b" stop-opacity="0.8"/>
            <stop offset="100%" stop-color="#450a0a" stop-opacity="0.85"/>
          `;
        }

        const cy1 = waveTopLeft + (waveTopRight - waveTopLeft) * 0.15;
        const cy2 = waveTopLeft + (waveTopRight - waveTopLeft) * 0.6;
        const wavePath = `M0,${waveTopLeft.toFixed(1)} C90,${cy1.toFixed(1)} 180,${cy2.toFixed(1)} 240,${((waveTopLeft + waveTopRight) / 2).toFixed(1)} C300,${cy2.toFixed(1)} 350,${(waveTopRight + 20).toFixed(1)} 400,${waveTopRight.toFixed(1)} L400,420 L0,420 Z`;
        const shimmer = `M0,${waveTopLeft.toFixed(1)} C90,${cy1.toFixed(1)} 180,${cy2.toFixed(1)} 240,${((waveTopLeft + waveTopRight) / 2).toFixed(1)} C300,${cy2.toFixed(1)} 350,${(waveTopRight + 20).toFixed(1)} 400,${waveTopRight.toFixed(1)}`;

        lp.setAttribute('d', wavePath);
        if (sp) sp.setAttribute('d', shimmer);
      }

      // Lógica do Aquário (Legado): só atualiza se os elementos existirem
      if (homeProgressLabel) {
        homeProgressLabel.textContent = `${100 - progressPct}%`;
      }

      if (homeAquariumWater) {
        try {
          updateAquariumVisual(receita, despesa);
        } catch (e) {
          console.warn('Falha atualizando aquário SVG:', e);
        }
      }
      // Atualiza os badges de porcentagem (Legado)
      if (homePctReceita) homePctReceita.textContent = `REC: ${pctReceita}%`;
      if (homePctDespesa) homePctDespesa.textContent = `DES: ${pctDespesa}%`;

      if (homeReceita) homeReceita.textContent = formatCurrencyBR(receita);
      if (homeDespesa) homeDespesa.textContent = formatCurrencyBR(despesa);
      if (homeInsight) homeInsight.textContent = summary?.insight || 'Carregando insight do Alfredo...';
      // Badge do usuário (nível)
      const badgeSvg = summary?.badge_svg || summary?.level_progress?.badge_svg;
      if (badgeSvg) {
        if (homeBadgeContainer) {
          homeBadgeContainer.innerHTML = `<span class="inline-flex items-center justify-center w-9 h-9 shrink-0">${badgeSvg}</span>`;
          const svgEl = homeBadgeContainer.querySelector('svg');
          if (svgEl) {
            svgEl.setAttribute('width', '36');
            svgEl.setAttribute('height', '36');
            svgEl.style.width = '36px';
            svgEl.style.height = '36px';
            svgEl.style.maxWidth = '36px';
            svgEl.style.maxHeight = '36px';
            svgEl.style.display = 'block';
          }
          // Se o usuário for premium, aumentamos o badge
          if (userPlan === 'premium' || userPlan === 'pro') {
            const span = homeBadgeContainer.querySelector('span');
            if (span) span.classList.add('badge-premium');
          }
        }
      } else if (homeBadgeContainer) {
        homeBadgeContainer.textContent = summary?.badge || '🌱';
      }

      // Plano do usuário (Free/Premium)
      if (homePlanLabel) {
        if (summary?.plan_label) {
          homePlanLabel.textContent = summary.plan_label;
          homePlanLabel.style.display = 'block';
          if (homeUpgradeBtn) {
            homeUpgradeBtn.style.display = (userPlan === 'free' || userPlan === 'trial') ? 'block' : 'none';
          }
        } else {
          homePlanLabel.textContent = '';
          homePlanLabel.style.display = 'none';
          if (homeUpgradeBtn) homeUpgradeBtn.style.display = 'none';
        }
      }

      homeRecentCache = Array.isArray(summary?.recent) ? summary.recent : [];
      const categories = Array.isArray(summary?.categories) ? summary.categories : [];
      const chartRuntime = getChartRuntime();
      const chartData = buildChartDataFromSummary(summary);
      const palette = ['#6366f1', '#f59e0b', '#10b981', '#ef4444', '#00f0ff', '#8b5cf6'];

      destroyHomeCharts();

      const commonAnimation = chartRuntime.enableMotion ? { duration: 520, easing: 'easeOutQuart' } : false;
      const commonLegend = {
        position: 'bottom',
        labels: {
          usePointStyle: true,
          boxWidth: 8,
          boxHeight: 8,
          font: { size: chartRuntime.legendFont },
        },
      };

      const safeChart = (id, config) => {
        const el = typeof id === 'string' ? document.getElementById(id) : id;
        if (!el) return null;
        // chave única por canvas: preferimos id, fallback ao próprio elemento
        const key = el.id || el;

        // Se já existe uma instância, destrua-a antes de criar
        try {
          const existing = CHART_INSTANCES.get(key);
          if (existing && typeof existing.destroy === 'function') {
            try { existing.destroy(); } catch (dErr) { console.warn('Erro ao destruir chart anterior:', dErr); }
            CHART_INSTANCES.delete(key);
          }
        } catch (e) {
          console.warn('safeChart: erro ao checar instância existente:', e);
        }

        // Para Sankey, destrua instância Chart.js global se canvas já estiver em uso
        if (el.id === 'homeSankeyChart' && window.Chart && Chart.getChart) {
          const chart = Chart.getChart(el);
          if (chart) {
            try { chart.destroy(); } catch (err) { console.warn('Erro ao destruir Chart Sankey antigo:', err); }
          }
        }

        // Cria novo gráfico com tratamento de erros robusto
        try {
          const chart = new Chart(el, config);
          try { CHART_INSTANCES.set(key, chart); } catch (mErr) { console.warn('safeChart: falha ao armazenar instância:', mErr); }
          return chart;
        } catch (err) {
          console.warn(`Erro ao criar gráfico ${el.id || el}:`, err);
          return null;
        }
      };

      const chartGaugeCard = document.getElementById('chart-gauge');
      if (homeBudgetGaugesContainer && homeBudgetGaugeTemplate) {
        const budgets = chartData.budgetRaw || [];
        const hasBudgets = budgets.length > 0;
        
        // Controle de visibilidade do card e do pill
        if (chartGaugeCard) chartGaugeCard.classList.toggle('hidden', !hasBudgets);
        const gaugePill = document.querySelector('[data-home-chart-pill="chart-gauge"]');
        if (gaugePill) gaugePill.classList.toggle('hidden', !hasBudgets);

        // Limpa container
        homeBudgetGaugesContainer.innerHTML = '';
        
        if (hasBudgets) {
          // Ajusta grid se houver mais de um
          if (budgets.length > 1) {
            homeBudgetGaugesContainer.classList.remove('grid-cols-1');
            homeBudgetGaugesContainer.classList.add('grid-cols-2');
          } else {
            homeBudgetGaugesContainer.classList.add('grid-cols-1');
            homeBudgetGaugesContainer.classList.remove('grid-cols-2');
          }

          budgets.forEach((b, idx) => {
            const clone = homeBudgetGaugeTemplate.content.cloneNode(true);
            const canvas = clone.querySelector('.budget-canvas');
            const pctEl = clone.querySelector('.budget-percent');
            const nameEl = clone.querySelector('.budget-name');
            const periodEl = clone.querySelector('.budget-period');
            const statusEl = clone.querySelector('.budget-status');

            const percent = b.orcamento > 0 ? Math.min((b.realizado / b.orcamento) * 100, 100) : 0;
            const isOver = b.realizado > b.orcamento;

            pctEl.textContent = `${Math.round((b.realizado / b.orcamento) * 100)}%`;
            if (isOver) pctEl.classList.add('text-rose-500');
            
            nameEl.textContent = b.label || 'Categoria';
            
            const periods = { 'daily': 'Diário', 'weekly': 'Semanal', 'monthly': 'Mensal' };
            periodEl.textContent = periods[b.periodo] || 'Mensal';
            
            if (isOver) statusEl.textContent = 'Estourado';

            homeBudgetGaugesContainer.appendChild(clone);

            // Inicializa o gráfico para este item
            const chartId = `budget_gauge_${idx}`;
            canvas.id = chartId;
            
            homeCharts[chartId] = safeChart(canvas, {
              type: 'doughnut',
              data: {
                datasets: [{
                  data: [Math.min(percent, 100), Math.max(0, 100 - percent)],
                  backgroundColor: [percent > 90 ? '#881337' : '#D4AF37', 'rgba(212, 175, 55, 0.05)'],
                  borderWidth: 0,
                  circumference: 180,
                  rotation: 270,
                  borderRadius: 10
                }]
              },
              options: {
                cutout: '85%',
                aspectRatio: 1.8,
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  tooltip: { enabled: false },
                  legend: { display: false }
                }
              }
            });
          });
        }
      }

      if (homePatrimonyChartEl) {
        homeCharts.patrimony = safeChart(homePatrimonyChartEl, {
          type: 'line',
          data: {
            labels: chartData.patrimonyMonths,
            datasets: [{
              label: 'Patrimônio',
              data: chartData.patrimonyValues,
              fill: true,
              tension: 0.45,
              borderWidth: 3,
              borderColor: '#00f0ff',
              backgroundColor: 'rgba(0, 240, 255, 0.12)',
              pointRadius: 3,
              pointBackgroundColor: '#00f0ff',
              pointHoverRadius: 6,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: commonAnimation,
            plugins: {
              legend: commonLegend,
              tooltip: { callbacks: { label: (ctx) => `Patrimonio: ${formatCurrencyBR(ctx.raw)}` } },
            },
            scales: {
              x: { grid: { display: false }, ticks: { color: '#64748b', maxTicksLimit: chartRuntime.maxTicks } },
              y: { grid: { color: 'rgba(59, 130, 246, 0.12)' }, ticks: { color: '#64748b', callback: (v) => `R$ ${Number(v).toLocaleString('pt-BR')}` } },
            },
          },
        });
      }

      if (homeCashflowChartEl) {
        homeCharts.cashflow = safeChart(homeCashflowChartEl, {
          type: 'bar',
          data: {
            labels: chartData.sixMonths,
            datasets: [
              {
                label: 'Entradas',
                data: chartData.fluxoEntradas,
                borderRadius: 8,
                borderSkipped: false,
                backgroundColor: '#10b981',
                barThickness: chartRuntime.barThickness + 4,
              },
              {
                label: 'Saídas',
                data: chartData.fluxoSaidas,
                borderRadius: 8,
                borderSkipped: false,
                backgroundColor: '#ef4444',
                barThickness: chartRuntime.barThickness + 4,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: commonAnimation,
            interaction: { mode: 'index', intersect: false },
            plugins: {
              legend: commonLegend,
              tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${formatCurrencyBR(ctx.raw)}` } },
            },
            scales: {
              x: { grid: { display: false }, ticks: { color: '#64748b' } },
              y: { grid: { color: 'rgba(123, 30, 45, 0.08)' }, ticks: { color: '#64748b', callback: (v) => `R$ ${Number(v).toLocaleString('pt-BR')}` } },
            },
          },
        });
      }

      const budgetCanvas = document.getElementById('homeBudgetChart');
      if (budgetCanvas) {
        const hasData = chartData.budgetLabels.length > 0;
        if (!hasData) {
          budgetCanvas.parentElement.innerHTML = `
            <div class="empty-state">
              <h3>Sem metas de orçamento</h3>
              <p>Defina limites por categoria para acompanhar.</p>
            </div>
            <canvas id="homeBudgetChart" style="display:none;"></canvas>`;
        } else {
          budgetCanvas.style.display = 'block';
          homeCharts.budget = safeChart(budgetCanvas, {
            type: 'bar',
            data: {
              labels: chartData.budgetLabels,
              datasets: [
                {
                  label: 'Orçamento',
                  data: chartData.budgetCap,
                  borderRadius: 12,
                  borderSkipped: false,
                  backgroundColor: 'rgba(212, 175, 55, 0.1)',
                  barPercentage: 0.8,
                  categoryPercentage: 0.8,
                },
                {
                  label: 'Realizado',
                  data: chartData.budgetRealized,
                  borderRadius: 12,
                  borderSkipped: false,
                  backgroundColor: chartData.budgetRealized.map((value, idx) => value > chartData.budgetCap[idx] ? '#881337' : '#D4AF37'),
                  barPercentage: 0.5,
                  categoryPercentage: 0.6,
                },
              ],
            },
            options: {
              indexAxis: 'y',
              responsive: true,
              maintainAspectRatio: false,
              animation: commonAnimation,
              plugins: {
                legend: { ...commonLegend, position: 'bottom' },
                tooltip: { 
                  backgroundColor: '#0A0A0A',
                  titleColor: '#D4AF37',
                  bodyColor: '#FFFFFF',
                  callbacks: { label: (ctx) => `${ctx.dataset.label}: ${formatCurrencyBR(ctx.raw)}` } 
                },
              },
              scales: {
                x: { grid: { color: 'rgba(212, 175, 55, 0.05)' }, ticks: { color: '#64748b', callback: (v) => `R$ ${Number(v).toLocaleString('pt-BR')}` } },
                y: { grid: { display: false }, ticks: { color: '#D4AF37', font: { weight: 'bold' } } },
              },
            },
          });
        }
      }

      if (homeCategoryChartEl) {
        const hasCategories = categories.length > 0;
        const privatePalette = ["#D4AF37", "#ebe2e2", "#064E3B", "#881337", "#1E3A8A", "#451A03"];
        
        if (!hasCategories) {
          homeCategoryChartEl.parentElement.innerHTML = '<div class="empty-state"><h3>Sem dados de despesas</h3><p>Alfredo está aguardando seus primeiros lançamentos.</p></div>';
        } else {
          homeCharts.category = safeChart(homeCategoryChartEl, {
            type: 'bar',
            data: {
              labels: chartData.distroLabels.slice(0, 6),
              datasets: [{
                label: 'Gastos por Categoria',
                data: chartData.distroValues.slice(0, 6),
                backgroundColor: chartData.distroLabels.slice(0, 6).map((_, idx) => categories[idx]?.color || privatePalette[idx % privatePalette.length]),
                borderRadius: 8,
                barThickness: 20
              }],
            },
            options: {
              indexAxis: 'y',
              responsive: true,
              maintainAspectRatio: false,
              animation: commonAnimation,
              plugins: {
                legend: { display: false },
                tooltip: { 
                  backgroundColor: '#0A0A0A',
                  titleColor: '#D4AF37',
                  callbacks: { label: (ctx) => `${ctx.label}: ${formatCurrencyBR(ctx.raw)}` } 
                },
              },
              scales: {
                x: { display: false },
                y: { grid: { display: false }, ticks: { color: '#D4AF37', font: { weight: 'bold' } } }
              },
              onClick: (_, elements) => {
                if (!elements.length) return;
                const index = elements[0].index;
                homeCategoryValue.textContent = formatCurrencyBR(chartData.distroValues[index] || 0);
                homeCategoryLabel.textContent = chartData.distroLabels[index] || 'Categoria';
              },
            },
          });

          homeCategoryValue.textContent = formatCurrencyBR(chartData.distroValues[0] || 0);
          homeCategoryLabel.textContent = chartData.distroLabels[0] || (hasCategories ? 'Categoria' : 'Sem categoria');
        }
      }

      if (homeProjectionChartEl) {
        homeCharts.projection = safeChart(homeProjectionChartEl, {
          type: 'line',
          data: {
            labels: chartData.projectionLabels,
            datasets: [
              {
                label: 'Histórico',
                data: chartData.projectionHistory,
                tension: 0.4,
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                borderWidth: 3,
                fill: true,
                pointRadius: 0,
              },
              {
                label: 'Futuro estimado',
                data: chartData.projectionFuture,
                tension: 0.4,
                borderColor: '#f59e0b',
                backgroundColor: 'rgba(245, 158, 11, 0.05)',
                borderWidth: 3,
                fill: true,
                pointRadius: 0,
                borderDash: [8, 4],
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: commonAnimation,
            plugins: {
              legend: commonLegend,
              tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${formatCurrencyBR(ctx.raw)}` } },
            },
            scales: {
              x: { grid: { display: false }, ticks: { color: '#64748b' } },
              y: { grid: { color: 'rgba(148, 163, 184, 0.14)' }, ticks: { color: '#64748b', callback: (v) => `R$ ${Number(v).toLocaleString('pt-BR')}` } },
            },
          },
        });
      }

      if (homeVillainsChartEl) {
        homeCharts.villains = safeChart(homeVillainsChartEl, {
          type: 'bar',
          data: {
            labels: chartData.villains.map((item) => item[0]),
            datasets: [{
              label: 'Gasto',
              data: chartData.villains.map((item) => item[1]),
              borderRadius: 8,
              borderSkipped: false,
              backgroundColor: ['#ff0055', '#ef4444', '#f43f5e', '#fb7185', '#fda4af'],
              barThickness: chartRuntime.barThickness + 6,
            }],
          },
          options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            animation: commonAnimation,
            plugins: {
              legend: { display: false },
              tooltip: { callbacks: { label: (ctx) => `Total: ${formatCurrencyBR(ctx.raw)}` } },
            },
            scales: {
              x: { grid: { display: false }, ticks: { color: '#64748b', callback: (v) => `R$ ${Number(v).toLocaleString('pt-BR')}` } },
              y: { grid: { display: false }, ticks: { color: '#475569' } },
            },
          },
        });
      }

            if (homeSankeyChartEl) {
        renderSankeyPremium(homeSankeyChartEl.parentElement, chartData.sankeyData);
        homeSankeyChartEl.style.display = 'none';
      }

      if (homeHeatmapChartEl) {
        homeCharts.heatmap = safeChart(homeHeatmapChartEl, {
          type: 'matrix',
          data: {
            datasets: [{
              data: chartData.heatmapData,
              backgroundColor(ctx) {
                const item = ctx.dataset.data[ctx.dataIndex];
                if (!item || item.type === 'empty') return 'rgba(0,0,0,0)';
                if (item.type === 'income_win') return 'rgba(16, 185, 129, 0.85)';
                if (item.type === 'expense_win') return 'rgba(123, 30, 45, 0.85)';
                return 'rgba(255, 255, 255, 0.05)';
              },
              borderColor: 'rgba(255, 255, 255, 0.1)',
              borderWidth: 1,
              width: ({chart}) => (chart.chartArea || {}).width / 7 - 4,
              height: ({chart}) => (chart.chartArea || {}).height / 6 - 4,
            }]
          },
          options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
              legend: { display: false },
              tooltip: {
                backgroundColor: '#0a0a0a',
                callbacks: {
                  title: (ctx) => `Dia ${ctx[0].raw.date}`,
                  label: (ctx) => [`Receitas: ${ctx.raw.stats.inc}x`, `Despesas: ${ctx.raw.stats.exp}x`]
                }
              }
            },
            scales: {
              x: { type: 'category', labels: ['Dom','Seg','Ter','Qua','Qui','Sex','S�b'], grid: { display: false }, ticks: { color: 'rgba(255,255,255,0.4)', font: { size: 10 } } },
              y: { type: 'category', labels: ['Sem 1','Sem 2','Sem 3','Sem 4','Sem 5','Sem 6'], grid: { display: false }, offset: true, ticks: { display: false } }
            }
          },
          plugins: [{
            id: 'calendarLabels',
            afterDatasetsDraw(chart) {
              const {ctx, data} = chart;
              ctx.save();
              ctx.font = '900 12px monospace';
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              data.datasets[0].data.forEach((item, i) => {
                if (item.date) {
                  const meta = chart.getDatasetMeta(0).data[i];
                  if (meta) {
                    ctx.fillStyle = (item.type === 'income_win' || item.type === 'expense_win') ? '#ffffff' : 'rgba(255,255,255,0.2)';
                    ctx.fillText(item.date, meta.x, meta.y);
                  }
                }
              });
              ctx.restore();
            }
          }]
        });
      }

      renderHomeRecent(summary?.recent || []);
      renderHomeRadar(summary);
      if (window.lucide) lucide.createIcons();
    }