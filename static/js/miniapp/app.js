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
    const lembreteHistoryWrap = document.getElementById('lembreteHistoryWrap');
    const lembreteHistoryStatus = document.getElementById('lembreteHistoryStatus');
    const lembreteHistoryList = document.getElementById('lembreteHistoryList');
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
    }

    function updateAgendaModalLabels() {
      const isReminder = agendaMode === 'lembretes';
      if (agendaModalTitle) agendaModalTitle.textContent = isReminder ? 'Novo Lembrete' : 'Novo Agendamento';
      if (agendaValorLabel) agendaValorLabel.textContent = isReminder ? 'Valor (opcional)' : 'Valor';
      if (agendaDataLabel) agendaDataLabel.textContent = isReminder ? 'Data do lembrete' : 'Primeira execução';
      if (newAgendSave?.querySelector('.save-text')) {
        newAgendSave.querySelector('.save-text').textContent = isReminder ? 'Criar lembrete' : 'Criar agendamento';
      }
      if (newAgendValor) newAgendValor.required = !isReminder;
      if (lembreteHistoryWrap) lembreteHistoryWrap.classList.toggle('hidden', !isReminder);
    }

    function setAgendaMode(mode) {
      agendaMode = mode === 'lembretes' ? 'lembretes' : 'agendamentos';
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
      const receita = Number(summary?.receita || 0);
      const despesa = Number(summary?.despesa || 0);
      const categories = (Array.isArray(summary?.categories) ? summary.categories : []).slice(0, 5);
      const monthlyCashflow = Array.isArray(summary?.cashflow_monthly) ? summary.cashflow_monthly : [];
      const patrimonySeries = Array.isArray(summary?.patrimony_series) ? summary.patrimony_series : [];
      const budgetItems = Array.isArray(summary?.budget_vs_realizado) ? summary.budget_vs_realizado : [];
      const projectionSeries = Array.isArray(summary?.projection_series) ? summary.projection_series : [];
      const topVillains = Array.isArray(summary?.top_villains) ? summary.top_villains : [];

      const sixMonths = monthlyCashflow.length ? monthlyCashflow.map((item) => item.label || '') : [];
      const fluxoEntradas = monthlyCashflow.map((item) => Number(item.entrada || 0));
      const fluxoSaidas = monthlyCashflow.map((item) => Number(item.saida || 0));

      const patrimonyMonths = patrimonySeries.map((item) => item.label || '');
      const patrimonyValues = patrimonySeries.map((item) => Number(item.value || 0));

      const budgetLabels = budgetItems.map((item) => item.label || 'Categoria');
      const budgetCap = budgetItems.map((item) => Number(item.orcamento || 0));
      const budgetRealized = budgetItems.map((item) => Number(item.realizado || 0));

      const distroLabels = categories.map((item) => item.label || 'Categoria');
      const distroValues = categories.map((item) => Math.max(0, Number(item.value || 0)));

      const projectionLabels = projectionSeries.map((item) => item.label || '');
      const projectionHistory = projectionSeries.map((item) => item.historico == null ? null : Number(item.historico || 0));
      const projectionFuture = projectionSeries.map((item) => item.futuro == null ? null : Number(item.futuro || 0));

      const villains = topVillains.map((item) => [item.label || 'Sem nome', Number(item.value || 0)]);

      // Sankey Data (Flow) - Estrutura robusta
      const sankeyData = [];
      if (receita > 0 || despesa > 0) {
        if (receita > 0) {
          sankeyData.push({ from: 'Receitas', to: 'Caixa', flow: receita });
        }
        if (despesa > 0) {
          sankeyData.push({ from: 'Caixa', to: 'Despesas', flow: despesa });
          // Link despesas para categorias (top 5)
          categories.forEach(cat => {
            if (cat.value > 0) {
              sankeyData.push({ from: 'Despesas', to: cat.label, flow: Number(cat.value) });
            }
          });
        }
        const saldoLivre = receita - despesa;
        if (saldoLivre > 0) {
          sankeyData.push({ from: 'Caixa', to: 'Saldo Livre', flow: saldoLivre });
        }
      }

      // Heatmap Data (Real Calendar Mapping)
      const heatmapData = [];
      const daysShort = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
      
      const now = new Date();
      const refDate = new Date(now.getFullYear(), now.getMonth(), 1);
      const startDayOfWeek = refDate.getDay(); 
      const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
      
      const activityMap = {}; 
      const recent = summary?.recent || [];
      recent.forEach(item => {
        if (!item.data) return;
        const d = new Date(item.data);
        if (isNaN(d.getTime())) return;
        if (d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear()) {
          const date = d.getDate();
          activityMap[date] = (activityMap[date] || 0) + 1;
        }
      });

      for (let wIdx = 0; wIdx < 6; wIdx++) {
        daysShort.forEach((d, dIdx) => {
          const dayOfMonth = (wIdx * 7) + dIdx - startDayOfWeek + 1;
          let value = 0;
          let dateLabel = "";
          
          if (dayOfMonth > 0 && dayOfMonth <= daysInMonth) {
            value = activityMap[dayOfMonth] || 0;
            dateLabel = dayOfMonth.toString();
          }

          heatmapData.push({
            x: d,
            y: `Sem ${wIdx + 1}`,
            v: value,
            date: dateLabel 
          });
        });
      }

      return {
        sixMonths,
        patrimonyMonths,
        patrimonyValues,
        fluxoEntradas,
        fluxoSaidas,
        fluxoSaldo,
        budgetLabels,
        budgetPlanned,
        budgetActual,
        categories,
        projectionLabels,
        projectionValues,
        villains,
        sankeyData,
        heatmapData
      };
    }

    // Função para renderizar o Sankey Premium via SVG (Substituindo o feio do Chart.js)
    function renderSankeyPremium(container, data) {
      if (!container || !data.length) return;
      
      const width = 700;
      const height = 400;
      
      // Agrupar dados
      const receitaTotal = data.filter(d => d.from === 'Receitas').reduce((a, b) => a + b.flow, 0);
      const despesasNodes = data.filter(d => d.from === 'Despesas');
      const despesaTotal = data.filter(d => d.from === 'Caixa' && d.to === 'Despesas').reduce((a, b) => a + b.flow, 0);

      // Cores Premium
      const grena = "#7b1e2d";
      const ouro = "#D4AF37";
      const verde = "#10b981";

      let svgHtml = `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" style="width:100%; height:100%; overflow:visible;">
        <defs>
          <linearGradient id="flow-receita" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="${verde}" stop-opacity="0.2"/>
            <stop offset="100%" stop-color="${grena}" stop-opacity="0.4"/>
          </linearGradient>
          <linearGradient id="flow-categoria" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="${grena}" stop-opacity="0.3"/>
            <stop offset="100%" stop-color="${ouro}" stop-opacity="0.5"/>
          </linearGradient>
        </defs>

        <text x="75" y="25" text-anchor="middle" font-size="10" font-weight="bold" fill="rgba(255,255,255,0.4)" style="text-transform:uppercase; letter-spacing:1px">Entrada</text>
        <text x="350" y="25" text-anchor="middle" font-size="10" font-weight="bold" fill="rgba(255,255,255,0.4)" style="text-transform:uppercase; letter-spacing:1px">Distribuição</text>
        <text x="610" y="25" text-anchor="middle" font-size="10" font-weight="bold" fill="rgba(255,255,255,0.4)" style="text-transform:uppercase; letter-spacing:1px">Saídas</text>

        <!-- Fluxo Principal -->
        <path d="M140,60 C240,60 240,60 290,60 L290,360 C240,360 240,360 140,360 Z" fill="url(#flow-receita)" opacity="0.15" />
        
        <!-- Nó Receitas -->
        <rect x="20" y="60" width="120" height="300" rx="12" fill="${verde}" fill-opacity="0.05" stroke="${verde}" stroke-opacity="0.3" />
        <rect x="20" y="60" width="4" height="300" rx="2" fill="${verde}" />
        <text x="80" y="200" text-anchor="middle" font-size="13" font-weight="bold" fill="#fff">Receitas</text>
        <text x="80" y="218" text-anchor="middle" font-size="10" fill="rgba(255,255,255,0.5)">${formatCurrencyBR(receitaTotal)}</text>

        <!-- Nó Caixa -->
        <rect x="290" y="60" width="120" height="300" rx="12" fill="${grena}" fill-opacity="0.05" stroke="${grena}" stroke-opacity="0.3" />
        <rect x="290" y="60" width="4" height="300" rx="2" fill="${grena}" />
        <text x="350" y="200" text-anchor="middle" font-size="13" font-weight="bold" fill="#fff">Caixa</text>
        <text x="350" y="218" text-anchor="middle" font-size="10" fill="rgba(255,255,255,0.5)">Gestão</text>

        <!-- Categorias Dinâmicas -->
        ${despesasNodes.slice(0, 5).map((cat, i) => {
          const yPos = 65 + (i * 65);
          const h = 55;
          return `
            <path d="M410,${yPos} C480,${yPos} 480,${yPos} 540,${yPos} L540,${yPos + h} C480,${yPos + h} 480,${yPos + h} 410,${yPos + h} Z" fill="url(#flow-categoria)" opacity="0.6" />
            <rect x="540" y="${yPos}" width="150" height="${h}" rx="10" fill="${ouro}" fill-opacity="0.05" stroke="${ouro}" stroke-opacity="0.2" />
            <rect x="540" y="${yPos}" width="3" height="${h}" rx="1.5" fill="${ouro}" />
            <text x="615" y="${yPos + 22}" text-anchor="middle" font-size="10" font-weight="bold" fill="#fff">${cat.to}</text>
            <text x="615" y="${yPos + 40}" text-anchor="middle" font-size="9" fill="${ouro}" font-family="monospace">${formatCurrencyBR(cat.flow)}</text>
          `;
        }).join('')}
      </svg>`;

      container.innerHTML = svgHtml;
    }
        fluxoSaidas,
        budgetLabels,
        budgetCap,
        budgetRealized,
        budgetRaw: budgetItems,
        distroLabels,
        distroValues,
        projectionLabels,
        projectionHistory,
        projectionFuture,
        villains,
        sankeyData,
        heatmapData,
      };
    }

    function destroyHomeCharts() {
      // Destrói todas as instâncias registradas no mapa e no objeto homeCharts
      try {
        Object.values(homeCharts).forEach((chart) => {
          if (chart && typeof chart.destroy === 'function') chart.destroy();
        });
      } catch (e) { console.warn('destroyHomeCharts: erro destruindo homeCharts:', e); }
      // Também destrói qualquer instância remanescente no mapa global
      try {
        for (const [key, chart] of CHART_INSTANCES.entries()) {
          try { if (chart && typeof chart.destroy === 'function') chart.destroy(); } catch (dErr) { /* ignore */ }
        }
        CHART_INSTANCES.clear();
      } catch (e) { console.warn('destroyHomeCharts: erro destruindo CHART_INSTANCES:', e); }
      homeCharts = {};
    }

    // Atualiza a forma orgânica do aquário (SVG) baseada em receitas vs despesas
    function updateAquariumVisual(receita, despesa) {
      try {
        const svg = document.getElementById('homeAquariumSVG');
        if (!svg) return;
        const vbW = 1200;
        const vbH = 200;
        const total = Math.max(0.0001, Number(receita || 0) + Number(despesa || 0));
        const ratio = Number(receita || 0) / total;

        const xStart = vbW * 0.08;
        const xEnd = vbW * 0.92;
        const steps = 10;
        const points = [];
        for (let i = 0; i <= steps; i += 1) {
          const t = i / steps;
          const y = vbH - t * (vbH * 0.78) - vbH * 0.06; // leave top/bottom margin
          const base = xStart * (1 - t) + xEnd * t;
          const globalOffset = (ratio - 0.5) * vbW * 0.42; // shift curve horizontally by ratio
          const waviness = Math.sin(t * Math.PI * 3 + (ratio * Math.PI)) * (vbW * 0.04) * (1 - Math.abs(t - 0.5));
          const x = Math.max(0, Math.min(vbW, Math.round(base + globalOffset + waviness)));
          points.push({ x, y: Math.round(y) });
        }

        // Construir path simples conectando os pontos (a blur filter suaviza a borda)
        const last = points.length - 1;
        const forwardPts = points.map(p => `${p.x} ${p.y}`).join(' ');
        const reversePts = points.slice().reverse().map(p => `${p.x} ${p.y}`).join(' ');

        const greenD = `M 0 ${vbH} L 0 0 L ${points[last].x} ${points[last].y} L ${reversePts} Z`;
        const redD = `M ${vbW} ${vbH} L ${vbW} 0 L ${points[last].x} ${points[last].y} L ${forwardPts} Z`;

        const g = svg.querySelector('#aqGreen');
        const r = svg.querySelector('#aqRed');
        const b = svg.querySelector('#aqBlend');
        if (g) g.setAttribute('d', greenD);
        if (r) r.setAttribute('d', redD);
        if (b) b.setAttribute('d', redD);
      } catch (err) {
        console.warn('updateAquariumVisual erro:', err);
      }
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
        // O Sankey agora é renderizado via SVG customizado (Premium)
        renderSankeyPremium(homeSankeyChartEl.parentElement, chartData.sankeyData);
        homeSankeyChartEl.style.display = 'none'; // Esconde o canvas original
      }

      if (homeHeatmapChartEl) {
        homeCharts.heatmap = safeChart(homeHeatmapChartEl, {
          type: 'matrix',
          data: {
            datasets: [{
              label: 'Frequência de Lançamentos',
              data: chartData.heatmapData,
              backgroundColor(ctx) {
                if (!ctx.dataset || !ctx.dataset.data[ctx.dataIndex]) return 'rgba(0,0,0,0)';
                const value = ctx.dataset.data[ctx.dataIndex].v;
                if (value === 0) return 'rgba(255, 255, 255, 0.03)';
                const alpha = Math.min(0.9, 0.2 + (value * 0.25));
                return `rgba(212, 175, 55, ${alpha})`; // Ouro para atividade
              },
              borderColor: 'rgba(212, 175, 55, 0.1)',
              borderWidth: 1,
              width: ({chart}) => (chart.chartArea || {}).width / 7 - 4,
              height: ({chart}) => (chart.chartArea || {}).height / 6 - 4,
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: commonAnimation,
            plugins: {
              legend: { display: false },
              tooltip: {
                backgroundColor: '#2d0a10',
                titleColor: '#D4AF37',
                callbacks: {
                  title: (ctx) => `Dia ${ctx[0].raw.date || ctx[0].raw.x}`,
                  label: (ctx) => `${ctx.raw.v} lançamento(s)`
                }
              }
            },
            scales: {
              x: { type: 'category', labels: ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'], grid: { display: false }, ticks: { color: 'rgba(255,255,255,0.4)', font: { size: 10 } } },
              y: { type: 'category', labels: ['Sem 1', 'Sem 2', 'Sem 3', 'Sem 4', 'Sem 5', 'Sem 6'], grid: { display: false }, offset: true, ticks: { display: false } }
            }
          }
        });
      }

      renderHomeRecent(summary?.recent || []);
      renderHomeRadar(summary);
      lucide.createIcons();
    }

    function renderHomeRadar(summary) {
      const homeRadarSection = document.getElementById('homeRadarSection');
      const homeCardsGrid = document.getElementById('homeCardsGrid');
      const homeInstallmentsBlock = document.getElementById('homeInstallmentsBlock');
      const homeInstallmentsList = document.getElementById('homeInstallmentsList');
      const homeInstallmentsCount = document.getElementById('homeInstallmentsCount');

      if (!homeRadarSection) return;

      const cards = summary?.cards || [];
      const installments = summary?.installments || [];

      if (cards.length === 0 && installments.length === 0) {
        homeRadarSection.classList.add('hidden');
        return;
      }

      homeRadarSection.classList.remove('hidden');

      // 1. Renderizar Cartões
      if (homeCardsGrid) {
        homeCardsGrid.innerHTML = '';
        if (cards.length > 0) {
          cards.forEach(card => {
            const fatura = card.fatura || 0;
            const limite = card.limite || 0;
            const pct = limite > 0 ? Math.min(100, Math.round((fatura / limite) * 100)) : null;
            
            // Lógica de Vencimento
            const hoje = new Date();
            hoje.setHours(0,0,0,0);
            const dataVenc = card.vence ? new Date(card.vence) : null;
            if (dataVenc) dataVenc.setHours(12,0,0,0); // Ajuste de timezone
            const isVencido = dataVenc && dataVenc < hoje;
            const venceStr = dataVenc ? dataVenc.toLocaleDateString('pt-BR', {day:'2-digit', month:'2-digit'}) : 'S/D';
            
            let statusColor = 'text-emerald-500';
            let bgAccent = 'bg-emerald-500/10';
            let iconColor = 'text-emerald-500';
            let badge = '';

            if (isVencido) {
              statusColor = 'text-red-500';
              bgAccent = 'bg-red-500/10';
              iconColor = 'text-red-500';
              badge = '<span class="text-[7px] font-black uppercase bg-red-500 text-white px-1 rounded ml-auto">VENCIDO</span>';
            } else if (pct !== null) {
              if (pct > 85) { statusColor = 'text-red-500'; iconColor = 'text-red-500'; }
              else if (pct > 50) { statusColor = 'text-yellow-500'; iconColor = 'text-yellow-500'; }
            }
            
            homeCardsGrid.innerHTML += `
              <div class="min-w-[170px] glass-card rounded-2xl p-3 border border-white/5 shrink-0 snap-center shadow-lg">
                <div class="flex items-center gap-2 mb-3">
                  <div class="w-7 h-7 rounded-full ${bgAccent} flex items-center justify-center">
                    <i data-lucide="credit-card" class="w-3.5 h-3.5 ${iconColor}"></i>
                  </div>
                  <span class="text-[10px] font-bold text-telegram-text truncate">${card.nome}</span>
                  ${badge}
                </div>
                <div class="space-y-0.5">
                  <p class="text-[9px] font-bold uppercase tracking-tight text-telegram-hint">Fatura Atual</p>
                  <p class="text-base font-black text-telegram-text">${formatCurrencyBR(fatura)}</p>
                  <div class="flex items-end justify-between mt-3">
                    <div class="flex flex-col">
                      <span class="text-[8px] font-bold text-telegram-hint uppercase">Vence</span>
                      <span class="text-[10px] font-extrabold text-telegram-text">${venceStr}</span>
                    </div>
                    <div class="text-right">
                      ${pct !== null ? `
                        <span class="text-[9px] font-black ${statusColor}">${pct}%</span>
                        <div class="w-12 h-1 bg-white/5 rounded-full mt-0.5 overflow-hidden">
                          <div class="h-full ${statusColor.replace('text', 'bg')}" style="width: ${pct}%"></div>
                        </div>
                      ` : `
                        <span class="text-[8px] font-bold text-telegram-hint italic">S/ Limite</span>
                      `}
                    </div>
                  </div>
                </div>
              </div>
            `;
          });
          if (window.lucide) lucide.createIcons();
        }
      }

      // 2. Renderizar Parcelas
      if (homeInstallmentsBlock && homeInstallmentsList) {
        if (installments.length > 0) {
          homeInstallmentsBlock.classList.remove('hidden');
          homeInstallmentsCount.textContent = installments.length;
          homeInstallmentsList.innerHTML = installments.map(p => {
            const vence = p.vence ? new Date(p.vence).toLocaleDateString('pt-BR', {day:'2-digit', month:'2-digit'}) : '--/--';
            return `
              <div class="flex items-center justify-between gap-3">
                <div class="flex items-center gap-2 min-w-0">
                  <div class="w-1.5 h-1.5 rounded-full bg-brand/40"></div>
                  <div class="truncate">
                    <p class="text-[11px] font-bold text-telegram-text truncate">${p.desc}</p>
                    <p class="text-[9px] font-semibold text-telegram-hint">Parcela ${p.parcela}</p>
                  </div>
                </div>
                <div class="text-right shrink-0">
                  <p class="text-[11px] font-extrabold text-telegram-text">${formatCurrencyBR(p.valor)}</p>
                  <p class="text-[9px] font-bold text-brand-soft">${vence}</p>
                </div>
              </div>
            `;
          }).join('');
        } else {
          homeInstallmentsBlock.classList.add('hidden');
        }
      }
    }

    async function loadHomeOverview() {
      if (isRefreshingHome) {
        console.log('loadHomeOverview: atualização já em andamento, ignorando nova chamada.');
        return;
      }
      isRefreshingHome = true;
      try {
        if (!sessionId) {
        console.warn('loadHomeOverview: sem sessionId. Tentando recuperar...');
        await tryRecoverSessionFromStorage();
        if (!sessionId) {
          console.warn('loadHomeOverview: recovery falhou, tentando autenticar...');
          try { await authTelegram(); } catch (e) { console.warn('authTelegram falhou:', e); }
        }
      }
        console.log('loadHomeOverview: sessionId=', sessionId);
        try {
          console.log("🚀 Carregando visão geral...");
          const response = await fetchWithSession('/api/miniapp/overview');
          console.log('loadHomeOverview: response status', response.status);
          const data = await response.json();
          if (!data.ok) {
            console.error("❌ Erro na API de visão geral:", data.error);
            throw new Error(data.error || 'overview_error');
          }
          // Backend pode retornar { summary: {...} } ou { data: {...} }
          const summary = data.summary || data.data || data;
          console.log("✅ Dados recebidos (overview):", summary);
          renderHomeOverview(summary || {});
        } catch (error) {
          console.error("🔥 Falha crítica ao carregar home:", error);
          if (homeBalance) homeBalance.textContent = 'R$ 0,00';
          if (homeBalanceHint) homeBalanceHint.textContent = 'Não foi possível carregar o resumo agora.';
          if (homeInsight) homeInsight.textContent = 'O Alfredo não conseguiu montar o resumo agora. Tente atualizar em instantes.';
          if (homeRecentList) homeRecentList.innerHTML = '<div class="rounded-2xl border border-dashed border-telegram-separator bg-telegram-card p-4 text-sm text-telegram-hint">Resumo indisponível no momento.</div>';
        }
      } finally {
        isRefreshingHome = false;
      }
    }

    function renderGameTopFeatures(features = []) {
      if (!features.length) {
        gameTopFeatures.innerHTML = '<div class="rounded-2xl border border-dashed border-telegram-separator bg-telegram-card p-3 text-xs text-telegram-hint">Ainda sem interações suficientes para ranking de features.</div>';
        return;
      }

      gameTopFeatures.innerHTML = features.map((item, idx) => {
        const total = Number(item.interactions || 0);
        const bar = Math.max(12, Math.min(100, 100 - idx * 14));
        return `
          <div class="rounded-2xl border border-telegram-separator bg-telegram-card p-3">
            <div class="flex items-center justify-between gap-2">
              <span class="text-xs font-bold text-telegram-text truncate">${item.feature}</span>
              <span class="text-xs font-semibold text-brand">${total}x</span>
            </div>
            <div class="mt-2 h-1.5 w-full rounded-full bg-slate-200/70 overflow-hidden">
              <div class="h-full rounded-full" style="width:${bar}%; background: linear-gradient(90deg, #7b1e2d, #b85d6e);"></div>
            </div>
          </div>
        `;
      }).join('');
    }

    function renderGameRanking(items = []) {
      if (!items.length) {
        gameRankingList.innerHTML = '<div class="rounded-2xl border border-dashed border-telegram-separator bg-telegram-card p-3 text-xs text-telegram-hint">Sem dados no ranking deste mês ainda.</div>';
        return;
      }

      gameRankingList.innerHTML = items.slice(0, 20).map((item) => {
        const isMe = Boolean(item.is_current_user);
        const medal = item.position === 1 ? '🥇' : item.position === 2 ? '🥈' : item.position === 3 ? '🥉' : '•';
        return `
          <div class="rounded-2xl border p-3 ${isMe ? 'border-brand/40 bg-brand/5' : 'border-telegram-separator bg-telegram-card'}">
            <div class="flex items-center justify-between gap-3">
              <div class="min-w-0">
                <p class="text-xs font-bold ${isMe ? 'text-brand' : 'text-telegram-text'}">${medal} #${item.position} ${item.name}</p>
                <p class="text-[11px] text-telegram-hint">Nível ${item.level} • ${item.interactions} interações</p>
              </div>
              <span class="text-sm font-extrabold ${isMe ? 'text-brand' : 'text-telegram-text'}">${item.monthly_xp} XP</span>
            </div>
          </div>
        `;
      }).join('');
    }

    function renderGameProfile(profile) {
      if (!profile) return;
      const xp = profile.xp || {};
      const progress = Math.max(0, Math.min(100, Number(xp.progress_pct || 0)));

      gameProfileName.textContent = profile.name || 'Jogador';
      gameProfileTitle.textContent = profile.title || 'Iniciante';
      if (profile.badge_svg) {
        gameProfileBadge.innerHTML = `<span class="w-[50px] h-[50px] inline-flex items-center justify-center shrink-0">${profile.badge_svg}</span><span>${profile.title || 'Em evolução'}</span>`;
        const svgEl = gameProfileBadge.querySelector('svg');
        if (svgEl) {
          svgEl.setAttribute('width', '50');
          svgEl.setAttribute('height', '50');
          svgEl.style.width = '50px';
          svgEl.style.height = '50px';
          svgEl.style.maxWidth = '50px';
          svgEl.style.maxHeight = '50px';
          svgEl.style.display = 'block';
        }
      } else {
        gameProfileBadge.textContent = profile.badge || '🌱 Em evolução';
      }
      gameProfileLevelLine.textContent = `Nível ${profile.level || 1}`;
      gameProfileXpLine.textContent = `${xp.xp_in_level || 0} / ${xp.xp_needed || 1} XP`;
      gameProfileProgressBar.style.width = `${progress}%`;
      gameProfileNextHint.textContent = `Faltam ${xp.xp_to_next || 0} XP para o nível ${xp.next_level || ((profile.level || 1) + 1)}`;
      if (gameInteractionsTotal) gameInteractionsTotal.textContent = String(profile.interactions_total || 0);
      if (gameInteractionsWeek) gameInteractionsWeek.textContent = String(profile.interactions_week || 0);
      if (gameAlfredoNote) gameAlfredoNote.textContent = profile.alfredo_note || 'Mantenha consistência para subir no ranking.';
      renderGameTopFeatures(Array.isArray(profile.top_features) ? profile.top_features : []);
    }

    async function loadGameProfile() {
      if (!sessionId) return;
      try {
        const response = await fetchWithSession('/api/miniapp/game-profile');
        const data = await response.json();
        if (!data.ok) throw new Error(data.error || 'profile_error');
        gameProfileCache = data.profile || null;
        renderGameProfile(gameProfileCache);
      } catch (_) {
        gameAlfredoNote.textContent = 'Nao foi possivel carregar o perfil gamer agora.';
      }
    }

    async function loadMonthlyRanking() {
      if (!sessionId) return;
      try {
        const response = await fetchWithSession('/api/miniapp/ranking-monthly');
        const data = await response.json();
        if (!data.ok) throw new Error(data.error || 'ranking_error');
        gameRankingCache = Array.isArray(data.ranking) ? data.ranking : [];
        renderGameRanking(gameRankingCache);

        const updatedAt = new Date(data.updated_at || Date.now());
        gameRankingUpdatedAt.textContent = `Atualizado ${updatedAt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
      } catch (_) {
        gameRankingUpdatedAt.textContent = 'Falha ao atualizar';
      }
    }

    async function loadPierreParcelamentos() {
      if (!sessionId) return;
      showToast('Buscando parcelamentos...', 'warning');
      try {
        const response = await fetchWithSession('/api/miniapp/pierre/parcelamentos');
        const data = await response.json();
        if (data.ok) {
          // O backend já envia o texto formatado em data.data
          window.Telegram.WebApp.showPopup({
            title: 'Radar de Parcelamentos',
            message: data.data,
            buttons: [{type: 'close'}]
          });
        } else {
          showToast('Falha ao buscar dados do Pierre', 'error');
        }
      } catch(e) {
        showToast('Erro de conexão', 'error');
      }
    }

    async function downloadPierreLivroCaixa() {
      if (!sessionId) return;
      showToast('Gerando livro caixa analítico...', 'warning');
      try {
        const response = await fetchWithSession('/api/miniapp/pierre/livro-caixa');
        const data = await response.json();
        if (data.ok) {
          window.Telegram.WebApp.showPopup({
            title: 'Livro Caixa Analítico',
            message: 'Dados processados com sucesso. O Alfredo enviará o PDF detalhado no seu chat em instantes.',
            buttons: [{type: 'close'}]
          });
        } else {
          showToast('Falha ao gerar livro caixa', 'error');
        }
      } catch(e) {
        showToast('Erro ao processar', 'error');
      }
    }

    async function loadPierreDashboard() {
      if (!sessionId) return;
      try {
        const response = await fetchWithSession('/api/miniapp/pierre/dashboard');
        const data = await response.json();
        if (data.ok) {
          renderPierreDashboard(data.data);
        } else {
          showToast('Pierre temporariamente fora do ar', 'error');
        }
      } catch(e) {
        showToast('Erro ao conectar com Pierre', 'error');
      }
    }

    function renderPierreDashboard(data) {
      // 1. Patrimônio e Saúde (Utiliza valor exato do backend ou parsing robusto)
      const balanceValue = typeof data.balance === 'number' ? data.balance : Number(data.balance || 0);
      pierreTotalBalance.textContent = formatCurrencyBR(isNaN(balanceValue) ? 0 : balanceValue);
      
      const health = data.health || { score: '--', label: '---' };
      pierreHealthScore.textContent = health.score;
      pierreHealthLabel.textContent = health.label;
      
      // Cores dinâmicas para o score
      if (health.score >= 80) pierreHealthLabel.className = 'text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-500/10 text-green-400';
      else if (health.score >= 60) pierreHealthLabel.className = 'text-[10px] font-bold px-2 py-0.5 rounded-full bg-yellow-500/10 text-yellow-400';
      else pierreHealthLabel.className = 'text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-500/10 text-red-400';

      // 2. Lista de Contas
      renderPierreAccounts(data.accounts);

      // 3. Gráfico de Categorias (Vilões)
      renderPierreCategories(data.categories);

      // 4. Radar de Parcelas
      renderPierreInstallments(data.installments);
    }

    function renderPierreAccounts(accounts) {
      if (!pierreAccountsList) return;
      
      let items = accounts;
      if (typeof accounts === 'string') {
        try { items = JSON.parse(accounts); } catch(e) { items = []; }
      }
      if (items?.data && Array.isArray(items.data)) items = items.data;

      if (!Array.isArray(items) || !items.length) {
        pierreAccountsList.innerHTML = '<p class="text-xs text-telegram-hint text-center py-2">Nenhuma conta mapeada.</p>';
        return;
      }

      pierreAccountsList.innerHTML = items.map(acc => {
        const type = acc.type === 'CREDIT' ? 'Cartão' : 'Conta';
        // Priorizar display_info enviado pelo backend (com limite disponível)
        const displayBalance = acc.display_info || formatCurrencyBR(Number(acc.balance || acc.amount || 0));
        
        return `
          <div class="flex items-center justify-between p-3 rounded-2xl bg-white/5 border border-white/5">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-full bg-purple-500/10 flex items-center justify-center text-purple-400">
                <i data-lucide="${acc.type === 'CREDIT' ? 'credit-card' : 'landmark'}" class="w-5 h-5"></i>
              </div>
              <div class="min-w-0">
                <p class="text-xs font-bold text-telegram-text truncate">${acc.name || 'Banco'}</p>
                <p class="text-[10px] text-telegram-hint">${type}</p>
              </div>
            </div>
            <div class="text-right">
              <p class="text-xs font-black text-telegram-text">${displayBalance}</p>
            </div>
          </div>
        `;
      }).join('');
      
      if (window.lucide) lucide.createIcons();
    }

    async function forcePierreSync() {
      const btn = document.getElementById('pierreSyncBtn');
      if (!btn || btn.disabled) return;
      
      const originalHtml = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<i class="w-3 h-3 animate-spin" data-lucide="refresh-cw"></i> Sincronizando...';
      if (window.lucide) lucide.createIcons();

      try {
        const response = await fetchWithSession('/api/miniapp/pierre/sync', { method: 'POST' });
        const data = await response.json();
        if (data.ok) {
          showToast('Bancos sincronizados!', 'success');
          await loadPierreDashboard();
        } else {
          showToast('Falha na sincronia', 'error');
        }
      } catch(e) {
        showToast('Erro de conexão', 'error');
      } finally {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
        if (window.lucide) lucide.createIcons();
      }
    }

    window.forcePierreSync = forcePierreSync;

    function renderPierreCategories(categoriesData) {
      if (pierreChartInstance) pierreChartInstance.destroy();
      if (!pierreCategoriesChartEl) return;

      const labels = [];
      const values = [];
      
      let rawData = categoriesData;
      if (typeof categoriesData === 'string') {
        try { rawData = JSON.parse(categoriesData); } catch(e) {}
      }
      if (rawData?.data) rawData = rawData.data;

      if (rawData && typeof rawData === 'object' && !Array.isArray(rawData)) {
        const entries = Object.entries(rawData)
          .sort((a, b) => Number(b[1]) - Number(a[1]))
          .slice(0, 5);
        
        entries.forEach(([label, value]) => {
          labels.push(label);
          values.push(Number(value));
        });
      }

      if (labels.length === 0) {
        pierreCategoriesEmpty?.classList.remove('hidden');
        return;
      } else {
        pierreCategoriesEmpty?.classList.add('hidden');
      }

      pierreChartInstance = new Chart(pierreCategoriesChartEl, {
        type: 'doughnut',
        data: {
          labels: labels,
          datasets: [{
            data: values,
            backgroundColor: ['#a855f7', '#d946ef', '#ec4899', '#f43f5e', '#f97316'],
            borderWidth: 0,
            hoverOffset: 10
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'right',
              labels: {
                color: '#94a3b8',
                font: { size: 10, weight: 'bold' },
                padding: 15,
                usePointStyle: true
              }
            }
          },
          cutout: '70%'
        }
      });
    }

    function renderPierreInstallments(data) {
      if (!pierreInstallmentsList) return;
      
      let rawData = data;
      if (typeof data === 'string') {
        try { rawData = JSON.parse(data); } catch(e) {}
      }
      if (rawData?.data) rawData = rawData.data;

      const purchases = rawData?.purchases || rawData?.installments || (Array.isArray(rawData) ? rawData : []);
      
      if (!Array.isArray(purchases) || !purchases.length) {
        pierreInstallmentsList.innerHTML = '<div class="text-center py-4 text-xs text-telegram-hint">Nenhum compromisso futuro mapeado no Pierre.</div>';
        return;
      }

      const now = new Date();
      const sorted = [...purchases]
        .filter(p => p && (p.description || p.name || p.merchant))
        .sort((a, b) => {
          const dA = new Date(a.dueDate || a.date || a.vencimento || 8640000000000000);
          const dB = new Date(b.dueDate || b.date || b.vencimento || 8640000000000000);
          return dA - dB;
        })
        .slice(0, 8);

      pierreInstallmentsList.innerHTML = sorted.map(p => {
        // Busca agressiva por campos
        const dateRaw = p.dueDate || p.date || p.vencimento || p.data;
        const amountRaw = p.amount || p.value || p.valor || p.totalAmount || 0;
        const instNum = p.installmentNumber || p.currentInstallment || p.parcela || '?';
        const instTot = p.totalInstallments || p.totalParcelas || '?';

        const dueDate = dateRaw ? new Date(dateRaw) : null;
        const isValidDate = dueDate && !isNaN(dueDate.getTime());
        const isPast = isValidDate && dueDate < now && dueDate.toDateString() !== now.toDateString();
        const diffDays = isValidDate ? Math.ceil((dueDate - now) / (1000 * 60 * 60 * 24)) : 999;
        
        let badgeClass = 'bg-blue-500/10 text-blue-400';
        let badgeText = 'Próxima';
        
        if (isPast) {
          badgeClass = 'bg-red-500/10 text-red-400';
          badgeText = 'Vencida';
        } else if (diffDays <= 2) {
          badgeClass = 'bg-orange-500/10 text-orange-400';
          badgeText = 'Urgente';
        }

        return `
          <div class="flex items-center justify-between p-3 rounded-2xl bg-white/5 border border-white/5 transition active:scale-95">
            <div class="min-w-0 flex-1">
              <p class="text-xs font-bold text-telegram-text truncate">${p.description || p.name || p.merchant || 'Parcela'}</p>
              <p class="text-[10px] text-telegram-hint">${instNum}/${instTot} • ${isValidDate ? dueDate.toLocaleDateString('pt-BR') : 'Sem data'}</p>
            </div>
            <div class="text-right ml-3">
              <p class="text-xs font-black text-telegram-text">${formatCurrencyBR(Number(amountRaw))}</p>
              <span class="text-[8px] font-bold uppercase px-1.5 py-0.5 rounded-md ${badgeClass}">${badgeText}</span>
            </div>
          </div>
        `;
      }).join('');
    }

    function renderGameRankingFull(items = []) {
      if (!items.length) {
        rankingFullList.innerHTML = '<div class="rounded-2xl border border-dashed border-telegram-separator bg-telegram-card p-4 text-center text-xs text-telegram-hint mt-8">Sem dados no ranking deste mês ainda. Comece a usar o app!</div>';
        return;
      }

      rankingFullList.innerHTML = items.map((item, idx) => {
        const isMe = Boolean(item.is_current_user);
        const medal = item.position === 1 ? '🥇' : item.position === 2 ? '🥈' : item.position === 3 ? '🥉' : '•';
        return `
          <div class="rounded-2xl border p-4 ${isMe ? 'border-brand/40 bg-brand/8 shadow-lg' : 'border-telegram-separator bg-telegram-card'} transition">
            <div class="flex items-center justify-between gap-3">
              <div class="flex items-center gap-3 flex-1 min-w-0">
                <div class="text-2xl font-bold">${medal}</div>
                <div class="min-w-0">
                  <p class="text-sm font-bold truncate ${isMe ? 'text-brand' : 'text-telegram-text'}">#${item.position} ${item.name}</p>
                  <p class="text-xs text-telegram-hint">Nível ${item.level} • ${item.interactions} interações • ${item.monthly_xp} XP</p>
                </div>
              </div>
              <div class="text-right flex-shrink-0">
                <p class="text-lg font-extrabold ${isMe ? 'text-brand' : 'text-telegram-text'}">${item.monthly_xp}</p>
                <p class="text-[10px] text-telegram-hint">XP</p>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    async function loadMonthlyRankingFull() {
      if (!sessionId) return;
      try {
        rankingFullList.innerHTML = '<div class="text-center text-xs text-telegram-hint mt-4"><div class="spinner mx-auto"></div> Carregando ranking...</div>';
        const response = await fetchWithSession('/api/miniapp/ranking-monthly');
        const data = await response.json();
        if (!data.ok) throw new Error(data.error || 'ranking_error');
        gameRankingCache = Array.isArray(data.ranking) ? data.ranking : [];
        renderGameRankingFull(gameRankingCache);
      } catch (_) {
        rankingFullList.innerHTML = '<div class="rounded-2xl border border-dashed border-telegram-separator bg-telegram-card p-4 text-center text-xs text-telegram-hint">Falha ao carregar ranking. Tente novamente.</div>';
      }
    }

    async function loadFaturaEditor() {
      if (!sessionId) return;
      if (!currentFaturaToken) {
        faturaHeaderInfo.innerHTML = '<p class="text-red-500 text-xs">Token da fatura não encontrado. Reabra pelo botão Editar da fatura.</p>';
        faturaEditList.innerHTML = '';
        return;
      }
      try {
        faturaHeaderInfo.innerHTML = '<div class="text-xs text-telegram-hint"><div class="spinner inline mr-2"></div> Carregando lançamentos...</div>';
        const response = await fetchWithSession(`/api/miniapp/fatura-editor?token=${encodeURIComponent(currentFaturaToken)}`);
        const data = await response.json();
        if (!data.ok) throw new Error(data.error || 'fatura_error');
        
        const transacoes = Array.isArray(data.transacoes) ? data.transacoes : [];
        const conta = data.conta || 'Cartão de Crédito';
        const total = transacoes.length;
        const totalDebito = transacoes.reduce((sum, t) => sum + (t.valor < 0 ? Math.abs(t.valor) : 0), 0);
        
        faturaHeaderInfo.innerHTML = `<p class="font-semibold">📌 ${conta}</p><p class="text-[11px]">${total} lançamentos • Débito: R$ ${totalDebito.toFixed(2)}</p>`;
        renderFaturaEditor(transacoes);
      } catch (err) {
        faturaHeaderInfo.innerHTML = '<p class="text-red-500 text-xs">Falha ao carregar. Tente novamente.</p>';
        faturaEditList.innerHTML = '';
      }
    }

    async function tryOpenPendingFaturaEditor() {
      if (!sessionId || currentFaturaToken) return;
      try {
        const response = await fetchWithSession('/api/miniapp/fatura-editor-pending');
        const data = await response.json();
        if (!data.ok || !data.has_pending || !data.token) return;

        currentFaturaToken = data.token;
        openPanel('fatura-editor-panel', true);
        await loadFaturaEditor();
      } catch (_) {
        // Silencioso: abertura pendente é opcional.
      }
    }

    function renderFaturaEditor(transacoes = []) {
      if (!transacoes.length) {
        faturaEditList.innerHTML = '<div class="rounded-2xl border border-dashed border-telegram-separator bg-telegram-card p-4 text-center text-xs text-telegram-hint">Nenhum lançamento para editar.</div>';
        return;
      }

      faturaEditList.innerHTML = transacoes.map((t, idx) => {
        const data = new Date(t.data_transacao).toLocaleDateString('pt-BR');
        return `
          <div class="rounded-2xl border border-telegram-separator bg-telegram-card p-3" data-fatura-id="${idx}">
            <div class="flex flex-col gap-2">
              <input type="text" class="fatura-desc floating-input text-sm" value="${(t.descricao || '').replace(/"/g, '&quot;')}" placeholder="Descrição">
              <div class="grid grid-cols-2 gap-2">
                <input type="number" class="fatura-valor floating-input text-sm" value="${t.valor}" step="0.01" placeholder="Valor">
                <input type="date" class="fatura-data floating-input text-sm" value="${new Date(t.data_transacao).toISOString().split('T')[0]}">
              </div>
              <button class="fatura-delete text-xs font-semibold text-red-500 hover:text-red-600 transition flex items-center justify-end w-full gap-1 mt-1" onclick="this.closest('[data-fatura-id]').remove()">
                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i> Excluir
              </button>
            </div>
          </div>
        `;
      }).join('');
      
      lucide.createIcons();
    }

    async function saveFaturaEdits() {
      if (!sessionId) return;
      
      const items = Array.from(document.querySelectorAll('[data-fatura-id]')).map((el, idx) => ({
        index: idx,
        descricao: el.querySelector('.fatura-desc').value || '',
        valor: parseFloat(el.querySelector('.fatura-valor').value) || 0,
        data_transacao: el.querySelector('.fatura-data').value,
      }));
      try {
        faturaEditorSave.disabled = true;
        faturaEditorSave.textContent = '⏳ Salvando...';

        const response = await fetchWithSession('/api/miniapp/fatura-editor-save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: currentFaturaToken, transacoes: items }),
        });

        const data = await response.json();
        if (!data.ok) throw new Error(data.error || 'save_error');

        showToast('✅ Lançamentos salvos com sucesso!', 'success');
        setTimeout(() => switchTabByName('inicio'), 1500);
      } catch (err) {
        showToast('❌ Erro ao salvar: ' + (err.message || 'Tente novamente'), 'error');
      } finally {
        faturaEditorSave.disabled = false;
        faturaEditorSave.textContent = '💾 Confirmar';
      }
    }

    function cancelFaturaEditor() {
      if (confirm('⚠️ Descartar todas as edições?')) {
        switchTabByName('inicio');
      }
    }

    function getMissionTypeIcon(type) {
      const icons = { daily: '📅', weekly: '📆', special: '⭐' };
      return icons[type] || '🎯';
    }

    function getMissionTypeLabel(type) {
      const labels = { daily: 'Diária', weekly: 'Semanal', special: 'Especial' };
      return labels[type] || 'Missão';
    }

    function renderMissions(missions = []) {
      if (!missions || missions.length === 0) {
        missoesList.innerHTML = `
          <div class="rounded-2xl border border-dashed border-telegram-separator bg-telegram-card p-6 text-center">
            <p class="text-2xl mb-2">🎯</p>
            <p class="text-sm font-semibold text-telegram-text">Nenhuma missão encontrada</p>
            <p class="text-xs text-telegram-hint mt-1">Explore novas funcionalidades para destravar missões</p>
          </div>
        `;
        missionsCountActive.textContent = '0';
        missionsCountCompleted.textContent = '0';
        missionsXpReward.textContent = '0';
        return;
      }

      const filtered = missionsCurrentFilter === 'all' ? missions : missions.filter((m) => m.type === missionsCurrentFilter);

      if (filtered.length === 0) {
        missoesList.innerHTML = `
          <div class="rounded-2xl border border-dashed border-telegram-separator bg-telegram-card p-6 text-center">
            <p class="text-sm font-semibold text-telegram-text">Nenhuma missão ${getMissionTypeLabel(missionsCurrentFilter).toLowerCase()}</p>
            <p class="text-xs text-telegram-hint mt-1">Tente outro filtro</p>
          </div>
        `;
        return;
      }

      missoesList.innerHTML = filtered.map((mission) => {
        const progress = Math.max(0, Math.min(100, Number(mission.progress || 0)));
        const isCompleted = mission.status === 'completed' || mission.status === 'claimed';
        const isClaimed = mission.status === 'claimed';

        return `
          <div class="glass-card rounded-2xl p-4 border ${isCompleted ? 'border-green-500/30 bg-green-500/5' : 'border-telegram-separator'} transition">
            <div class="flex items-start justify-between gap-3 mb-3">
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-lg">${getMissionTypeIcon(mission.type)}</span>
                  <span class="text-xs font-semibold uppercase tracking-[0.1em] text-telegram-hint">${getMissionTypeLabel(mission.type)}</span>
                  ${isCompleted ? '<span class="ml-auto text-xs font-bold text-green-500">✓ Concluída</span>' : ''}
                </div>
                <h3 class="text-sm font-bold text-telegram-text">${mission.name}</h3>
                <p class="text-xs text-telegram-hint mt-1">${mission.description}</p>
              </div>
              <div class="text-right">
                <div class="text-lg font-extrabold text-brand">${mission.xp_reward}</div>
                <div class="text-[10px] text-telegram-hint font-semibold">XP</div>
              </div>
            </div>

            <div class="space-y-2">
              <div class="flex items-center justify-between text-xs">
                <span class="text-telegram-hint font-semibold">Progresso</span>
                <span class="font-bold text-telegram-text">${mission.current_value || 0} / ${mission.target_value || 1}</span>
              </div>
              <div class="h-2 w-full rounded-full bg-telegram-separator overflow-hidden">
                <div class="h-full rounded-full transition-all duration-500 ease-out" style="width: ${progress}%; background: linear-gradient(90deg, #7b1e2d, #b85d6e);"></div>
              </div>
            </div>

            ${isCompleted ? `
              <button class="mt-3 w-full py-2 text-xs font-semibold rounded-lg transition ${isClaimed ? 'bg-gray-300 text-gray-600 cursor-not-allowed' : 'bg-green-500 text-white hover:bg-green-600 active:scale-95'}" ${isClaimed ? 'disabled' : 'onclick="claimMissionReward(' + mission.id + ')"'}>
                ${isClaimed ? '✓ Já resgatado' : '🎁 Resgatar ' + mission.xp_reward + ' XP'}
              </button>
            ` : ''}
          </div>
        `;
      }).join('');

      const active = missions.filter((m) => m.status === 'active').length;
      const completed = missions.filter((m) => m.status === 'completed' || m.status === 'claimed').length;
      const totalXp = missions.filter((m) => m.status === 'claimed' || m.status === 'completed').reduce((sum, m) => sum + (m.xp_reward || 0), 0);

      missionsCountActive.textContent = String(active);
      missionsCountCompleted.textContent = String(completed);
      missionsXpReward.textContent = String(totalXp);

      const gameMissionsCount = document.getElementById('gameMissionsCount');
      if (gameMissionsCount) {
        gameMissionsCount.textContent = String(active);
      }
    }

    async function loadMissions() {
      if (!sessionId) return;
      try {
        const response = await fetchWithSession('/api/miniapp/missions');
        const data = await response.json();
        if (!data.ok) throw new Error(data.error || 'missions_error');

        missionsCache = Array.isArray(data.missions) ? data.missions : [];
        renderMissions(missionsCache);
      } catch (error) {
        missoesList.innerHTML = `
          <div class="rounded-2xl border border-dashed border-telegram-separator bg-telegram-card p-6 text-center">
            <p class="text-sm font-semibold text-red-500">Erro ao carregar missões</p>
            <p class="text-xs text-telegram-hint mt-1">${error.message || 'Tente novamente'}</p>
          </div>
        `;
      }
    }

    async function claimMissionReward(missionId) {
      if (!sessionId) return;
      try {
        const response = await fetchWithSession('/api/miniapp/mission-claim', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mission_id: missionId }),
        });

        const data = await response.json();
        if (!data.ok) throw new Error(data.error || 'claim_error');

        showToast('🎉 Recompensa resgatada com sucesso!', 'success');
        loadMissions();
        loadGameProfile();
      } catch (error) {
        showToast('❌ Erro ao resgatar: ' + (error.message || 'Tente novamente'), 'error');
      }
    }

    missoesRefresh.addEventListener('click', loadMissions);

    missionFilterBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const filter = btn.dataset.missionFilter;
        missionsCurrentFilter = filter;
        
        missionFilterBtns.forEach(b => {
          b.classList.remove('tab-active', 'border-brand/25', 'bg-brand/10', 'text-brand');
          b.classList.add('border-telegram-separator', 'bg-telegram-card', 'text-telegram-text');
        });
        
        btn.classList.add('tab-active', 'border-brand/25', 'bg-brand/10', 'text-brand');
        btn.classList.remove('border-telegram-separator', 'bg-telegram-card', 'text-telegram-text');
        
        renderMissions(missionsCache);
      });
    });

    function openGameProfilePanel() {
      openPanel('perfil-jogo', true);
      loadGameProfile();
      loadMonthlyRanking();

      if (gameRankingRefreshTimer) {
        clearInterval(gameRankingRefreshTimer);
      }
      gameRankingRefreshTimer = setInterval(() => {
        if (document.hidden || !sessionId || !document.getElementById('perfil-jogo')?.classList.contains('active')) return;
        loadMonthlyRanking();
      }, 15000);
    }

    function openNewAgendamentoModal() {
      newAgendDescricao.value = '';
      newAgendValor.value = '';
      newAgendTipo.value = 'Saída';
      newAgendFrequencia.value = 'mensal';
      newAgendParcelas.value = '12';
      newAgendInfinito.checked = false;
      const hoje = new Date().toISOString().split('T')[0];
      newAgendData.value = hoje;
      updateParcelasVisibility();
      openModal('newAgendamentoModal');
    }

    function closeNewAgendamentoModal() {
      closeModal('newAgendamentoModal');
    }

    function updateParcelasVisibility() {
      const unico = newAgendFrequencia.value === 'unico';
      if (unico) {
        newAgendInfinito.checked = false;
      }
      newAgendInfinito.disabled = unico;
      parcelasGroup.classList.toggle('hidden', unico || newAgendInfinito.checked);
    }

    async function createAgendamento() {
      if (!sessionId) return;
      
      const descricao = newAgendDescricao.value.trim();
      const valor = parseMoneyInput(newAgendValor.value);
      const tipo = newAgendTipo.value;
      const frequencia = newAgendFrequencia.value;
      const data = newAgendData.value;
      const recorrenciaInfinita = frequencia !== 'unico' && newAgendInfinito.checked;
      const parcelas = frequencia === 'unico' ? 1 : (recorrenciaInfinita ? null : (parseInt(newAgendParcelas.value, 10) || 1));

      if (!descricao || !valor || !data) {
        showToast('Preencha todos os campos obrigatórios', 'error');
        return;
      }

      const saveBtn = newAgendSave;
      const originalText = saveBtn.querySelector('.save-text').textContent;
      saveBtn.disabled = true;
      saveBtn.querySelector('.save-text').textContent = '';
      const spinner = document.createElement('div');
      spinner.className = 'spinner';
      saveBtn.appendChild(spinner);

      try {
        const response = await fetch('/api/miniapp/agendamentos', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Session-Id': sessionId },
          body: JSON.stringify({
            descricao,
            valor,
            tipo,
            frequencia,
            data_primeiro_evento: data,
            total_parcelas: parcelas,
            parcela_atual: 0
          }),
        });
        const data_resp = await response.json();
        if (data_resp.ok) {
          showToast(`✓ ${descricao} agendado com sucesso!`, 'success');
          await loadAgendamentos();
          closeNewAgendamentoModal();
        } else {
          showToast(`Erro: ${data_resp.message || 'Tente novamente'}`, 'error');
        }
      } catch (e) {
        showToast('Erro de conexão ao criar agendamento', 'error');
      } finally {
        spinner.remove();
        saveBtn.querySelector('.save-text').textContent = originalText;
        saveBtn.disabled = false;
      }
    }

    async function loadConfiguracoes() {
      if (!sessionId) return;
      try {
        const response = await fetchWithSession('/api/miniapp/configuracoes');
        const data = await response.json();
        if (!data.ok) return;
        if (perfilInvestidor) perfilInvestidor.value = data.usuario?.perfil_investidor || '';
        if (horarioNotificacao) horarioNotificacao.value = data.usuario?.horario_notificacao || '09:00';
        if (alertaGastosAtivoToggle) alertaGastosAtivoToggle.checked = Boolean(data.usuario?.alerta_gastos_ativo);
        
        // Notificações do Alfredo
        const tgLembretes = document.getElementById('toggle_notif_lembretes');
        if (tgLembretes) tgLembretes.checked = Boolean(data.usuario?.notif_lembretes ?? true);
        
        const tgRisco = document.getElementById('toggle_notif_alertas_risco');
        if (tgRisco) tgRisco.checked = Boolean(data.usuario?.notif_alertas_risco ?? true);
        
        const tgInsights = document.getElementById('toggle_notif_insights');
        if (tgInsights) tgInsights.checked = Boolean(data.usuario?.notif_insights ?? true);
        
        const tgGamificacao = document.getElementById('toggle_notif_gamificacao');
        if (tgGamificacao) tgGamificacao.checked = Boolean(data.usuario?.notif_gamificacao ?? true);

      } catch (e) {}
    }

    // Expor funções para abrir/fechar modal de notificações
    window.openNotificacoesModal = function() {
      const modalsOverlay = document.getElementById('modalsOverlay');
      const notificacoesModal = document.getElementById('notificacoesModal');
      if (modalsOverlay) {
        modalsOverlay.classList.remove('hidden');
        modalsOverlay.classList.add('pointer-events-auto');
      }
      if (notificacoesModal) {
        notificacoesModal.classList.remove('hidden');
        notificacoesModal.classList.add('active');
      }
      document.body.style.overflow = 'hidden';
    };

    window.closeNotificacoesModal = function() {
      const modalsOverlay = document.getElementById('modalsOverlay');
      const notificacoesModal = document.getElementById('notificacoesModal');
      if (notificacoesModal) {
        notificacoesModal.classList.remove('active');
        setTimeout(() => {
            notificacoesModal.classList.add('hidden');
            // Verificação extra para limpar o overlay global
            const activeModals = document.querySelectorAll('.modal-overlay.active, #notificacoesModal.active');
            if (activeModals.length === 0 && modalsOverlay) {
                modalsOverlay.classList.add('hidden');
                modalsOverlay.classList.remove('pointer-events-auto');
                document.body.style.overflow = '';
            }
        }, 300);
      }
    };
    // Expor função para salvar configurações de notificação ao trocar o toggle
    window.saveNotificationPreferences = async function() {
      const sId = localStorage.getItem(MINIAPP_SESSION_STORAGE_KEY) || telegramInitData;
      if (!sId) return;
      const payload = {
        notif_lembretes: document.getElementById('toggle_notif_lembretes')?.checked ?? true,
        notif_alertas_risco: document.getElementById('toggle_notif_alertas_risco')?.checked ?? true,
        notif_insights: document.getElementById('toggle_notif_insights')?.checked ?? true,
        notif_gamificacao: document.getElementById('toggle_notif_gamificacao')?.checked ?? true,
      };

      try {
        const response = await fetch('/api/miniapp/configuracoes', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'X-Session-Id': sId },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (data.ok) {
          showToast('Preferências salvas!', 'success');
        } else {
          showToast('Erro ao salvar preferências.', 'error');
        }
      } catch (e) {
        showToast('Erro de conexão.', 'error');
      }
    };

    async function saveConfiguracoes() {
      if (!sessionId || !perfilInvestidor || !horarioNotificacao) return;
      try {
        const response = await fetch('/api/miniapp/configuracoes', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'X-Session-Id': sessionId },
          body: JSON.stringify({
            perfil_investidor: perfilInvestidor.value,
            horario_notificacao: horarioNotificacao.value,
          }),
        });
        const data = await response.json();
        if (data.ok) {
          mainStatus.textContent = 'Configurações salvas';
          mainStatus.className = 'font-bold text-transparent bg-clip-text bg-gradient-to-r from-brand to-brand-soft';
          await loadConfiguracoes();
        }
      } catch (e) {}
    }

    async function saveLancamentoEdit() {
      if (!sessionId || !selectedLancamento) return;
      
      const saveBtn = editSave;
      const originalText = saveBtn.querySelector('.save-text').textContent;
      saveBtn.disabled = true;
      saveBtn.querySelector('.save-text').textContent = '';
      const spinner = document.createElement('div');
      spinner.className = 'spinner';
      saveBtn.appendChild(spinner);
      
      const payload = {
        descricao: editDescricao.value.trim(),
        valor: parseMoneyInput(editValor.value),
        tipo: editTipo.value,
        data_transacao: editData.value,
        forma_pagamento: editForma.value.trim(),
        id_categoria: editCategoria.value || null,
        id_subcategoria: editSubcategoria.value || null,
        learn_rule: editLearnRule.checked,
      };
      try {
        const isDraft = !selectedLancamento.id;
        const requestPayload = isDraft
          ? {
              ...payload,
              categoria_sugerida: selectedLancamento.categoria_sugerida || null,
              subcategoria_sugerida: selectedLancamento.subcategoria_sugerida || null,
            }
          : payload;
        const response = await fetch(
          isDraft ? '/api/miniapp/lancamentos' : `/api/miniapp/lancamentos/${selectedLancamento.id}`,
          {
            method: isDraft ? 'POST' : 'PATCH',
            headers: { 'Content-Type': 'application/json', 'X-Session-Id': sessionId },
            body: JSON.stringify(requestPayload),
          }
        );
        const data = await response.json();
        if (data.ok) {
          showToast(
            isDraft ? `✓ ${selectedLancamento.descricao} salvo com sucesso!` : `✓ ${selectedLancamento.descricao} atualizado com sucesso!`,
            'success'
          );
          await loadHomeOverview();
          await loadHistory(true);
          closeEditModal();
        } else {
          showToast(`Erro ao ${isDraft ? 'salvar' : 'atualizar'}: ${data.message || data.error || 'Tente novamente'}`, 'error');
        }
      } catch (e) {
        showToast('Erro de conexão ao salvar', 'error');
      } finally {
        spinner.remove();
        saveBtn.querySelector('.save-text').textContent = originalText;
        saveBtn.disabled = false;
      }
    }

    async function deleteLancamentoById(id) {
      if (!sessionId) return;
      if (!confirm('Tem certeza que deseja excluir este lançamento?')) return;
      try {
        const response = await fetch(`/api/miniapp/lancamentos/${id}`, {
          method: 'DELETE',
          headers: { 'X-Session-Id': sessionId },
        });
        const data = await response.json();
        if (data.ok) {
          showToast('✓ Lançamento excluído com sucesso!', 'success');
          await loadHomeOverview();
          await loadHistory(true);
          if (selectedLancamento && selectedLancamento.id === id) {
            closeEditModal();
          }
        } else {
          showToast('Erro ao excluir lançamento', 'error');
        }
      } catch (e) {
        showToast('Erro de conexão ao excluir', 'error');
      }
    }

    async function deleteAgendamentoById(id) {
      if (!sessionId) return;
      if (!confirm('Tem certeza que deseja excluir este agendamento?')) return;
      try {
        const response = await fetch(`/api/miniapp/agendamentos/${id}`, {
          method: 'DELETE',
          headers: { 'X-Session-Id': sessionId },
        });
        const data = await response.json();
        if (data.ok) {
          showToast('✓ Agendamento excluido com sucesso!', 'success');
          await loadAgendamentos();
        } else {
          showToast('Erro ao excluir agendamento', 'error');
        }
      } catch (e) {
        showToast('Erro de conexao ao excluir agendamento', 'error');
      }
    }

    // Logic
    async function authTelegram() {
      if (!window.Telegram || !Telegram.WebApp) {
        mainStatus.textContent = 'Erro TG';
        mainStatus.className = "text-carmine font-bold";
        return;
      }
      Telegram.WebApp.ready();
      Telegram.WebApp.expand();
      if (Telegram.WebApp.requestFullscreen) {
        try { Telegram.WebApp.requestFullscreen(); } catch (e) {}
      }

      const initData = await resolveTelegramInitData();
      if (!initData) {
        const recovered = await tryRecoverSessionFromStorage();
        if (!recovered) {
          mainStatus.textContent = 'Erro de Sessão';
          mainStatus.className = 'text-amber-500 font-bold';
          homeBalanceHint.textContent = 'A sessão do seu teclado expirou ou está desatualizada.';
          homeInsight.textContent = '⚠️ Para corrigir isso permanentemente: feche o MiniApp, digite /start no chat do bot para atualizar seus atalhos e clique no botão "🚀 Abrir o App" novamente.';
          switchTabByName('inicio');
          return;
        }

        mainStatus.textContent = 'Sincronizado';
        switchTabByName(pendingDraftLaunch ? 'inicio' : (initialTabFromUrl || 'inicio'));
        loadHomeOverview();
        loadHistory(true);
        loadConfiguracoes();
        setTimeout(() => {
          loadAgendamentos();
          loadMetas();
          loadOrcamentos();
          loadMissions();
          loadGameProfile();
          loadMonthlyRanking();
          tryOpenPendingFaturaEditor();
        }, 80);
        return;
      }

      telegramInitData = initData;

      try {
        const response = await fetch('/api/telegram/auth', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ init_data: initData })
        });
        const data = await response.json();
        if (!data.ok) {
          mainStatus.textContent = 'Falha de sessao';
          mainStatus.className = "text-carmine font-bold";
          homeBalanceHint.textContent = 'Sua sessao do Telegram expirou.';
          homeInsight.textContent = 'Feche este MiniApp e abra novamente pelo bot para sincronizar os dados.';
          switchTabByName('inicio');
          return;
        }
        sessionId = data.session_id;
        storeSessionId(sessionId);

        // Check if the user has Open Finance integration active (Modo Deus)
        if (data.user && data.user.has_pierre_access) {
            const ghostTab = document.getElementById('nav-fantasma');
            if (ghostTab) ghostTab.classList.remove('hidden');
        }
        mainStatus.textContent = 'Sincronizado';

        // Abre a interface imediatamente e carrega dados em segundo plano.
        switchTabByName(pendingDraftLaunch ? 'inicio' : (initialTabFromUrl || 'inicio'));
        if (pendingDraftLaunch) {
          const draft = normalizeDraftLancamento(pendingDraftLaunch);
          if (draft) {
            setSelectedLancamento(draft);
            editModal.classList.add('active');
            document.body.style.overflow = 'hidden';
          }
        }

        // Carrega o essencial em paralelo sem bloquear a abertura do miniapp.
        loadHomeOverview();
        loadHistory(true);
        loadConfiguracoes();

        // Carregamentos não críticos ficam assíncronos após a primeira pintura.
        setTimeout(() => {
          loadAgendamentos();
          loadMetas();
          loadOrcamentos();
          loadMissions();
          loadGameProfile();
          loadMonthlyRanking();
          tryOpenPendingFaturaEditor();
          
          // Verifica se há fatura pendente de edição
          if (initialPageFromUrl === 'fatura_editor') {
            openPanel('fatura-editor-panel', true);
            loadFaturaEditor();
          }
        }, 80);

        setInterval(() => {
          if (document.hidden || !sessionId) return;
          // Evita iniciar nova carga se a anterior ainda estiver em andamento
          if (isRefreshingHome) {
            // ainda carregando, pula este ciclo
            return;
          }
          loadHistory(true);
          loadHomeOverview();
          if (document.getElementById('metas')?.classList.contains('active')) {
              loadMetas();
              loadOrcamentos();
          }
        }, 20000);
      } catch(e) {
        mainStatus.textContent = 'Erro Conexão';
        mainStatus.className = 'text-carmine font-bold';
        homeBalanceHint.textContent = 'Nao foi possivel autenticar o MiniApp agora.';
        homeInsight.textContent = 'Verifique a conexao e tente abrir novamente pelo bot.';
      }
    }

    async function loadHistory(reset = false) {
      if (!sessionId) return;
      if (reset) { historyOffset = 0; renderHistorySkeleton(6); }
      const params = new URLSearchParams({
        limit: historyLimit,
        offset: historyOffset,
        query: historyQuery.value || '',
        tipo: historyTipo.value || '',
        order: historyOrder.value || 'date_desc'
      });
      if (historyDate?.value) {
        params.set('start_date', historyDate.value);
        params.set('end_date', historyDate.value);
      }
      try {
        const response = await fetchWithSession(`/api/miniapp/history?${params.toString()}`);
        const data = await response.json();
        if (!data.ok) return;
        historyStatus.textContent = '';
        if (reset) historyCache = [];
        if (reset) historyList.innerHTML = '';
        data.items.forEach(item => {
          historyCache.push(item);
          const numericValue = Number(item.valor) || 0;
          const isReceita = isEntradaTipo(item.tipo, numericValue);
          const valueText = formatMoney(item.valor, item.tipo);
          const style = getCategoryStyle(item.descricao, item.categoria_nome, item.subcategoria_nome, item.tipo);

          const iconHtml = style.logoUrl 
            ? `<div class="w-10 h-10 rounded-full overflow-hidden bg-white flex items-center justify-center border border-white/10 shadow-sm shrink-0">
                 <img src="${style.logoUrl}" class="w-full h-full object-contain" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                 <div class="hidden w-full h-full items-center justify-center bg-brand/5 text-brand"><i data-lucide="${style.icon}" class="w-5 h-5"></i></div>
               </div>`
            : `<div class="cat-icon ${style.class} shrink-0 w-10 h-10"><i data-lucide="${style.icon}" class="w-5 h-5"></i></div>`;

          const div = document.createElement('div');
          div.className = 'flex items-center justify-between gap-3 p-3 sm:p-4 rounded-3xl hover:bg-brand/5 transition border border-white/5 bg-telegram-card shadow-sm mb-3';
          div.innerHTML = `
            <div class="flex items-center gap-3 min-w-0 flex-1">
              ${iconHtml}
              <div class="min-w-0 flex-1">
                <p class="font-bold text-sm truncate text-telegram-text">${item.descricao || 'Lançamento'}</p>
                <p class="text-[10px] font-bold text-telegram-hint uppercase tracking-wider mt-0.5">${item.categoria_nome || 'Uncategorized'} • ${new Date(item.data).toLocaleDateString('pt-BR')}</p>
              </div>
            </div>
            <div class="flex flex-col items-end gap-1.5 shrink-0 ml-2">
              <span class="font-financial text-base font-black ${isReceita ? 'text-emerald-500' : 'text-rose-500'} whitespace-nowrap">${valueText}</span>
              <div class="flex items-center gap-1.5">
                <button class="history-edit-btn rounded-lg border border-white/5 bg-black/20 p-1.5 text-telegram-hint hover:text-brand transition" data-action="edit" data-id="${item.id}"><i data-lucide="pencil" class="w-3.5 h-3.5"></i></button>
                <button class="history-delete-btn rounded-lg border border-white/5 bg-black/20 p-1.5 text-telegram-hint hover:text-red-500 transition" data-action="delete" data-id="${item.id}"><i data-lucide="trash-2" class="w-3.5 h-3.5"></i></button>
              </div>
            </div>
          `;
          historyList.appendChild(div);
        });

        historyOffset = reset ? data.items.length : historyOffset + data.items.length;
        lucide.createIcons();
      } catch(e){}
    }

    function openMetaModal(meta = null) {
      selectedMeta = meta;
      metaModalTitle.textContent = meta ? 'Editar Meta' : 'Nova Meta';
      metaDescricao.value = meta?.descricao || '';
      metaValorMeta.value = meta?.valor_meta != null ? String(meta.valor_meta).replace('.', ',') : '';
      metaValorAtual.value = meta?.valor_atual != null ? String(meta.valor_atual).replace('.', ',') : '';
      metaData.value = formatDateForInput(meta?.data_meta || '');
      openModal('metaModal');
    }

    function closeMetaModal() {
      closeModal('metaModal');
      selectedMeta = null;
      metaDescricao.value = '';
      metaValorMeta.value = '';
      metaValorAtual.value = '';
      metaData.value = '';
    }

    async function saveMeta() {
      if (!sessionId) return;
      const descricao = metaDescricao.value.trim();
      const valor_meta = parseMoneyInput(metaValorMeta.value);
      const valor_atual = parseMoneyInput(metaValorAtual.value);
      const data_meta = metaData.value;

      if (!descricao || !valor_meta || !data_meta) {
        showToast('Preencha descrição, valor da meta e data alvo', 'error');
        return;
      }

      const saveBtn = metaSave;
      const saveText = saveBtn.querySelector('.save-text');
      const originalText = saveText.textContent;
      saveBtn.disabled = true;
      saveText.textContent = '';
      const spinner = document.createElement('div');
      spinner.className = 'spinner';
      saveBtn.appendChild(spinner);

      try {
        const payload = { descricao, valor_meta, valor_atual, data_meta };
        const response = await fetch(
          selectedMeta ? `/api/miniapp/metas/${selectedMeta.id}` : '/api/miniapp/metas',
          {
            method: selectedMeta ? 'PATCH' : 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Session-Id': sessionId },
            body: JSON.stringify(payload),
          }
        );
        const data = await response.json();
        if (data.ok) {
          showToast(selectedMeta ? '✓ Meta atualizada com sucesso!' : '✓ Meta criada com sucesso!', 'success');
          await loadMetas();
          closeMetaModal();
        } else {
          showToast(`Erro ao salvar meta: ${data.message || data.error || 'Tente novamente'}`, 'error');
        }
      } catch (e) {
        showToast('Erro de conexão ao salvar meta', 'error');
      } finally {
        spinner.remove();
        saveText.textContent = originalText;
        saveBtn.disabled = false;
      }
    }

    async function deleteMetaById(id) {
      if (!sessionId) return;
      if (!confirm('Tem certeza que deseja excluir esta meta?')) return;
      try {
        const response = await fetch(`/api/miniapp/metas/${id}`, {
          method: 'DELETE',
          headers: { 'X-Session-Id': sessionId },
        });
        const data = await response.json();
        if (data.ok) {
          showToast('✓ Meta excluída com sucesso!', 'success');
          await loadMetas();
        } else {
          showToast('Erro ao excluir meta', 'error');
        }
      } catch (e) {
        showToast('Erro de conexão ao excluir meta', 'error');
      }
    }

    async function confirmMetaMesById(id) {
      if (!sessionId) return;
      const valorInformado = prompt('Valor que você confirmou para este mês (deixe vazio para usar o valor da meta):', '');
      if (valorInformado === null) return;
      const valorConfirmado = valorInformado.trim() ? parseMoneyInput(valorInformado) : null;

      try {
        const response = await fetch(`/api/miniapp/metas/${id}/confirmar`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Session-Id': sessionId },
          body: JSON.stringify(valorConfirmado != null ? { valor_confirmado: valorConfirmado } : {}),
        });
        const data = await response.json();
        if (data.ok) {
          showToast('✓ Mês confirmado para essa meta!', 'success');
          await loadMetas();
        } else {
          showToast('Erro ao confirmar mês da meta', 'error');
        }
      } catch (e) {
        showToast('Erro de conexão ao confirmar meta', 'error');
      }
    }

    // --- Lógica de Orçamentos ---
    const tabToggleMetas = document.getElementById('tabToggleMetas');
    const tabToggleOrcamentos = document.getElementById('tabToggleOrcamentos');
    const viewMetas = document.getElementById('viewMetas');
    const viewOrcamentos = document.getElementById('viewOrcamentos');

    if (tabToggleMetas && tabToggleOrcamentos) {
      tabToggleMetas.addEventListener('click', () => {
        tabToggleMetas.classList.add('bg-brand', 'text-white', 'shadow-sm');
        tabToggleMetas.classList.remove('text-telegram-hint', 'hover:text-telegram-text');
        tabToggleOrcamentos.classList.remove('bg-brand', 'text-white', 'shadow-sm');
        tabToggleOrcamentos.classList.add('text-telegram-hint', 'hover:text-telegram-text');
        viewMetas.classList.remove('hidden');
        viewOrcamentos.classList.add('hidden');
        loadMetas();
      });

      tabToggleOrcamentos.addEventListener('click', () => {
        tabToggleOrcamentos.classList.add('bg-brand', 'text-white', 'shadow-sm');
        tabToggleOrcamentos.classList.remove('text-telegram-hint', 'hover:text-telegram-text');
        tabToggleMetas.classList.remove('bg-brand', 'text-white', 'shadow-sm');
        tabToggleMetas.classList.add('text-telegram-hint', 'hover:text-telegram-text');
        viewOrcamentos.classList.remove('hidden');
        viewMetas.classList.add('hidden');
        loadOrcamentos();
      });
    }

    function openOrcamentoModal() {
      orcamentoValor.value = '';
      openModal('orcamentoModal');
    }
    function closeOrcamentoModal() {
      closeModal('orcamentoModal');
    }

    async function loadOrcamentos() {
      if (!sessionId) return;
      try {
        const res = await fetchWithSession('/api/miniapp/orcamentos');
        const data = await res.json();
        if (!data.ok) return;

        if (orcamentoCategoria.options.length === 0) {
            orcamentoCategoria.innerHTML = data.categorias.map(c => `<option value="${c.id}">${c.nome}</option>`).join('');
        }
        if (data.items.length === 0) {
            orcamentoList.innerHTML = '<div class="text-xs text-telegram-hint text-center p-4 border border-dashed rounded-xl border-telegram-separator bg-telegram-card">Nenhum limite definido.</div>';
            return;
        }

        orcamentoList.innerHTML = data.items.map(o => {
            const pct = Math.min(100, Math.max(0, (o.valor_gasto / o.valor_limite) * 100));
            const color = pct >= 100 ? 'linear-gradient(90deg, #ef4444, #b91c1c)' : (pct >= 80 ? 'linear-gradient(90deg, #f59e0b, #d97706)' : 'linear-gradient(90deg, #10b981, #059669)');
            const periodoLabel = o.periodo === 'daily' ? 'diário' : (o.periodo === 'weekly' ? 'semanal' : 'mensal');
            return `
            <div class="mb-3 group cursor-pointer" onclick="abrirEdicaoOrcamento('${o.id_categoria}', ${o.valor_limite}, '${o.categoria_nome}', '${o.periodo}')">
                <div class="flex justify-between text-[10px] font-bold uppercase tracking-wider mb-1 text-telegram-hint group-hover:text-brand transition">
                    <span class="flex items-center gap-1">${o.categoria_nome} <span class="opacity-60">• ${periodoLabel}</span> <i data-lucide="pencil" class="w-2.5 h-2.5 opacity-40"></i></span>
                    <span class="text-telegram-text">R$ ${o.valor_gasto.toFixed(2).replace('.', ',')} / R$ ${o.valor_limite.toFixed(2).replace('.', ',')}</span>
                </div>
                <div class="h-2 w-full rounded-full bg-telegram-separator overflow-hidden shadow-inner">
                    <div class="h-full rounded-full transition-all duration-700" style="width: ${pct}%; background: ${color};"></div>
                </div>
            </div>`;
        }).join('');
        lucide.createIcons();
      } catch(e) {}
    }

    if (orcamentoNew) orcamentoNew.addEventListener('click', openOrcamentoModal);
    if (orcamentoSave) orcamentoSave.addEventListener('click', async () => {
      const id_categoria = orcamentoCategoria.value;
      const valor = parseMoneyInput(orcamentoValor.value);
      const periodo = document.getElementById('orcamentoPeriodo')?.value || 'monthly';
      try {
          const res = await fetchWithSession('/api/miniapp/orcamentos', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify({id_categoria, valor_limite: valor, periodo: periodo}) 
          });
          if ((await res.json()).ok) {
              showToast('✅ Limite salvo com sucesso!', 'success');
              closeOrcamentoModal();
              loadOrcamentos();
              loadHomeOverview();
          }
      } catch(e) { showToast('Erro ao salvar', 'error'); }
    });

    async function loadMetas() {
      if (!sessionId) return;
      renderMetaSkeleton(3);
      try {
        const response = await fetchWithSession('/api/miniapp/metas');
        const data = await response.json();
        if (!data.ok || !data.items.length) { metasCache = []; metaStatus.textContent = 'Nenhuma meta.'; metaList.innerHTML = '<div class="rounded-2xl border border-dashed border-telegram-separator bg-telegram-card p-4 text-sm text-telegram-hint">Nenhuma meta em andamento.</div>'; return; }
        metaStatus.textContent = '';
        metasCache = data.items || [];
        metaList.innerHTML = '';
        metasCache.forEach(item => {
          const valorMeta = Number(item.valor_meta) || 0;
          const valorAtual = Number(item.valor_atual) || 0;
          const faltante = Math.max(0, valorMeta - valorAtual);
          const progress = valorMeta > 0 ? Math.round((valorAtual / valorMeta) * 100) : 0;
          const progNorm = Math.min(progress, 100);
          const confirmado = Boolean(item.confirmado_mes_atual);
          const prazo = item.data_meta ? new Date(item.data_meta) : null;
          const prazoValido = prazo && !Number.isNaN(prazo.getTime());
          const hoje = new Date();
          const diffMs = prazoValido ? (prazo.getTime() - hoje.getTime()) : 0;
          const diasRestantes = prazoValido ? Math.max(0, Math.ceil(diffMs / (1000 * 60 * 60 * 24))) : 0;
          const mesesRestantes = prazoValido ? Math.max(1, Math.ceil(diasRestantes / 30)) : 1;
          const aporteMensal = faltante > 0 ? (faltante / mesesRestantes) : 0;
          const statusPrazo = !prazoValido
            ? 'Sem data alvo'
            : diasRestantes === 0
              ? 'Prazo final chegou'
              : `${diasRestantes} dias restantes`;

          const div = document.createElement('div');
          div.className = 'flex-1 bg-telegram-card rounded-3xl p-5 border border-telegram-separator relative overflow-hidden group mb-2 shadow-soft';
          div.innerHTML = `
            <div class="relative z-10 flex justify-between items-start gap-3">
              <div class="min-w-0 flex-1 pr-2">
                <p class="text-sm font-semibold text-telegram-text truncate">${item.descricao}</p>
                <p class="text-lg font-bold mt-1 text-telegram-text">${progNorm}% <span class="text-xs text-telegram-hint font-normal ml-1">de ${formatCurrency(valorMeta)}</span></p>
                <div class="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200/80">
                  <div
                    class="h-full rounded-full transition-[width] duration-700 ease-out"
                    data-meta-progress="${progNorm}"
                    style="width: 0%; background: linear-gradient(90deg, #7b1e2d 0%, #b85d6e 100%);"
                  ></div>
                </div>
                <p class="text-xs mt-1 text-telegram-hint">Faltam <b>${formatCurrency(faltante)}</b> para concluir</p>
                <p class="text-xs mt-1 text-brand">Aporte mensal sugerido: <b>${formatCurrency(aporteMensal)}</b></p>
                <p class="text-xs mt-1 text-telegram-hint">Prazo: ${prazoValido ? prazo.toLocaleDateString('pt-BR') : '-'} • ${statusPrazo}</p>
                <p class="text-xs mt-1 ${confirmado ? 'text-emerald-600' : 'text-telegram-hint'}">${confirmado ? '✓ Mês confirmado' : 'Mês ainda não confirmado'}</p>
              </div>
              <span class="text-sm font-semibold text-brand shrink-0 whitespace-nowrap">${formatCurrency(valorAtual)}</span>
            </div>
            <div class="relative z-10 mt-4 flex flex-wrap gap-2">
              <button class="rounded-lg border border-telegram-separator px-3 py-1.5 text-xs font-semibold text-telegram-text bg-telegram-card hover:bg-brand/5 transition flex items-center" data-meta-action="edit" data-id="${item.id}"><i data-lucide="pencil" class="w-3 h-3 mr-1"></i> Editar</button>
              <button class="rounded-lg border border-telegram-separator px-3 py-1.5 text-xs font-semibold text-red-500 bg-telegram-card hover:bg-red-50 transition flex items-center" data-meta-action="delete" data-id="${item.id}"><i data-lucide="trash-2" class="w-3 h-3 mr-1"></i> Excluir</button>
              <button class="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 hover:bg-emerald-100 transition flex items-center" data-meta-action="confirm" data-id="${item.id}"><i data-lucide="check-circle" class="w-3 h-3 mr-1"></i> ${confirmado ? 'Atualizar' : 'Confirmar mês'}</button>
            </div>
          `;
          metaList.appendChild(div);
        });
        animateMetaProgressBars();
        lucide.createIcons();
      } catch(e){}
    }

    async function loadAgendamentos() {
      if (!sessionId) return;
      renderAgendamentoSkeleton(3);
      try {
        const response = await fetchWithSession('/api/miniapp/agendamentos');
        const data = await response.json();
        if (!data.ok || !data.items.length) { agendamentoStatus.textContent = 'Nenhum agendamento.'; agendamentoList.innerHTML = '<div class="rounded-2xl border border-dashed border-telegram-separator bg-telegram-card p-4 text-sm text-telegram-hint">Nenhum agendamento futuro.</div>'; return; }
        agendamentoStatus.textContent = '';
        agendamentoList.innerHTML = '';
        data.items.forEach(item => {
          const isReceita = formatMoney(item.valor, item.tipo).startsWith('+');
          const valueText = formatMoney(item.valor, item.tipo);
          const div = document.createElement('div');
          div.className = 'flex items-center justify-between p-4 rounded-2xl bg-telegram-card border border-telegram-separator mb-2 shadow-soft';
          div.innerHTML = `
            <div class="min-w-0 flex-1 pr-2">
              <p class="font-semibold text-sm text-telegram-text truncate">${item.descricao}</p>
              <p class="text-[11px] sm:text-xs text-telegram-hint mt-0.5 truncate"><i data-lucide="clock" class="inline w-3 h-3 mr-1"></i>${item.frequencia} • ${new Date(item.proxima_data_execucao).toLocaleDateString('pt-BR')}</p>
            </div>
            <div class="flex flex-col items-end gap-1.5 shrink-0">
              <span class="font-bold text-brand text-sm whitespace-nowrap">${valueText}</span>
              <button class="agendamento-delete-btn rounded-md border border-telegram-separator bg-telegram-card p-1.5 text-telegram-hint hover:text-red-500 transition" data-action="delete" data-id="${item.id}"><i data-lucide="trash-2" class="w-3.5 h-3.5"></i></button>
            </div>
          `;
          agendamentoList.appendChild(div);
        });
        lucide.createIcons();
      } catch(e){}
    }

    // Refresh and Modal binds
    historyRefresh.addEventListener('click', () => loadHistory(true));
    historyLoadMore.addEventListener('click', () => loadHistory(false));
    
    // Novo Modal de Filtros
    const historyOpenFilters = document.getElementById('historyOpenFilters');
    const historyFilterModal = document.getElementById('historyFilterModal');
    const historyApplyFilters = document.getElementById('historyApplyFilters');
    const historySearchInput = document.getElementById('historySearchInput');

    if (historyOpenFilters) {
      historyOpenFilters.addEventListener('click', () => {
        openModal('historyFilterModal');
      });
    }

    window.closeHistoryFilterModal = () => {
      closeModal('historyFilterModal');
    };

    if (historyApplyFilters) {
      historyApplyFilters.addEventListener('click', () => {
        loadHistory(true);
        closeHistoryFilterModal();
      });
    }

    if (historySearchInput) {
      let searchTimer;
      historySearchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
          historyQuery.value = e.target.value;
          loadHistory(true);
        }, 400);
      });
    }

    historyClearFilters.addEventListener('click', () => {
      historyTipo.value = '';
      historyOrder.value = 'date_desc';
      historyDate.value = '';
      if(historySearchInput) historySearchInput.value = '';
      historyQuery.value = '';
      loadHistory(true);
      closeHistoryFilterModal();
    });
    agendamentoRefresh.addEventListener('click', loadAgendamentos);
    agendamentoNew.addEventListener('click', openNewAgendamentoModal);
    metaRefresh.addEventListener('click', loadMetas);
    metaNew.addEventListener('click', () => openMetaModal(null));
    metaSave.addEventListener('click', saveMeta);
    if (configRefresh) configRefresh.addEventListener('click', loadConfiguracoes);
    editSave.addEventListener('click', saveLancamentoEdit);
    newAgendSave.addEventListener('click', createAgendamento);
    newAgendFrequencia.addEventListener('change', updateParcelasVisibility);
    newAgendInfinito.addEventListener('change', updateParcelasVisibility);
    
    // Novo evento de salvar o toggle de notificações em tempo real
    if (alertaGastosAtivoToggle) {
      alertaGastosAtivoToggle.addEventListener('change', async (e) => {
        if (!sessionId) return;
        const ativo = e.target.checked;
        try {
          const response = await fetch('/api/miniapp/toggle-notificacoes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Session-Id': sessionId },
            body: JSON.stringify({
              telegram_id: window.Telegram?.WebApp?.initDataUnsafe?.user?.id || 0,
              ativo: ativo
            }),
          });
          const data = await response.json();
          if (data.sucesso) {
            showToast('✓ ' + data.mensagem, 'success');
            if (window.Telegram?.WebApp?.HapticFeedback) {
              window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
            }
          } else {
            showToast('Erro ao atualizar lembretes', 'error');
            e.target.checked = !ativo;
          }
        } catch (error) {
          showToast('Erro de conexão ao atualizar lembretes', 'error');
          e.target.checked = !ativo;
        }
      });
    }

    if (configSave) configSave.addEventListener('click', saveConfiguracoes);
    if (configFinish) configFinish.addEventListener('click', saveConfiguracoes);
    editModal.addEventListener('click', (e) => {
      if (e.target === editModal) closeEditModal();
    });
    newAgendamentoModal.addEventListener('click', (e) => {
      if (e.target === newAgendamentoModal) closeNewAgendamentoModal();
    });
    metaModal.addEventListener('click', (e) => {
      if (e.target === metaModal) closeMetaModal();
    });
    orcamentoModal.addEventListener('click', (e) => {
      if (e.target === orcamentoModal) closeOrcamentoModal();
    });

    // Boot
    historyList.addEventListener('click', (event) => {
      const target = event.target;
      const id = target?.dataset?.id;
      if (!id || !target.dataset.action) return;
      const item = historyCache.find((lanc) => String(lanc.id) === String(id));
      if (target.dataset.action === 'edit' && item) {
        openEditModal(item);
      }
      if (target.dataset.action === 'delete') {
        deleteLancamentoById(Number(id));
      }
    });

    homeRecentList.addEventListener('click', (event) => {
      const target = event.target.closest('[data-action="edit"]');
      if (!target?.dataset?.id) return;
      const item = homeRecentCache.find((lanc) => String(lanc.id) === String(target.dataset.id)) || historyCache.find((lanc) => String(lanc.id) === String(target.dataset.id));
      if (item) {
        openEditModal(item);
      }
    });

    homeRecentRefresh.addEventListener('click', loadHomeOverview);
    
    if (homeUpgradeBtn) {
      homeUpgradeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (window.Telegram?.WebApp) {
          const botUsername = window.botUsername || 'ContaComigoBot';
          window.Telegram.WebApp.openTelegramLink(`https://t.me/${botUsername}?start=premium`);
          setTimeout(() => window.Telegram.WebApp.close(), 100);
        }
      });
    }

    // Ghost (Pierre) interactions: reveal on hover / touch and ensure accessible click
    const ghostBtn = document.getElementById('nav-fantasma');
    if (ghostBtn) {
      ghostBtn.addEventListener('pointerenter', () => {
        ghostBtn.dataset.visible = 'true';
      });
      ghostBtn.addEventListener('pointerleave', () => {
        ghostBtn.dataset.visible = 'false';
      });
      ghostBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        // open modo-deus panel
        switchTabByName('modo-deus');
      });
    }

    homeLevelCard.addEventListener('click', openGameProfilePanel);
    gameProfileRefresh.addEventListener('click', async () => {
      await loadGameProfile();
      await loadMonthlyRanking();
    });
    gameSeeRanking.addEventListener('click', () => {
      openPanel('ranking-panel', true);
      loadMonthlyRankingFull();
      if (gameRankingRefreshTimer) clearInterval(gameRankingRefreshTimer);
      gameRankingRefreshTimer = setInterval(() => {
        if (document.hidden || !sessionId || !document.getElementById('ranking-panel')?.classList.contains('active')) return;
        loadMonthlyRankingFull();
      }, 15000);
    });
    rankingBackBtn.addEventListener('click', () => switchTabByName('inicio'));
    gameBackHome.addEventListener('click', () => switchTabByName('inicio'));

    faturaBkBtn.addEventListener('click', () => switchTabByName('inicio'));
    faturaEditorSave.addEventListener('click', saveFaturaEdits);
    faturaEditorCancel.addEventListener('click', cancelFaturaEditor);

    metaList.addEventListener('click', (event) => {
      const target = event.target.closest('[data-meta-action]');
      if (!target?.dataset?.id) return;
      const action = target.dataset.metaAction;
      const item = metasCache.find((meta) => String(meta.id) === String(target.dataset.id));

      if (action === 'edit' && item) {
        openMetaModal(item);
        return;
      }
      if (action === 'delete') {
        deleteMetaById(Number(target.dataset.id));
        return;
      }
      if (action === 'confirm') {
        confirmMetaMesById(Number(target.dataset.id));
      }
    });

    agendamentoList.addEventListener('click', (event) => {
      const target = event.target;
      const id = target?.dataset?.id;
      if (!id || target.dataset.action !== 'delete') return;
      deleteAgendamentoById(Number(id));
    });

    bindAdaptiveLayoutListeners();
    setupHomeChartsCarousel();
    authTelegram();

    // --- MODO DEUS ---
    async function loadModoDeus(force = false) {
      const skeleton = document.getElementById('modoDeusSkeleton');
      const content = document.getElementById('modoDeusContent');

      // Se não for forçado e já estiver visível, não recarrega (opcional)
      if (!force && content && !content.classList.contains('hidden')) return;

      if (skeleton) skeleton.classList.remove('hidden');
      if (content) content.classList.add('hidden');

      try {
        const response = await fetchWithSession('/api/miniapp/modo_deus');
        const data = await response.json();

        if (data.ok === false) {
          showToast('Erro ao carregar Modo Deus', 'error');
          return;
        }

        renderModoDeus(data);

        if (skeleton) skeleton.classList.add('hidden');
        if (content) content.classList.remove('hidden');
        if (window.lucide) lucide.createIcons();
      } catch (err) {
        console.error('Erro Modo Deus:', err);
        showToast('Falha na conexão do Modo Deus', 'error');
      }
    }

    window.loadModoDeus = loadModoDeus;

    function getBrandLogoHtml(name) {
      const normalized = String(name).toLowerCase();
      const brands = {
        'netflix': 'netflix.com',
        'spotify': 'spotify.com',
        'amazon': 'amazon.com',
        'prime': 'amazon.com',
        'apple': 'apple.com',
        'google': 'google.com',
        'youtube': 'youtube.com',
        'gympass': 'gympass.com',
        'wellhub': 'wellhub.com',
        'openai': 'openai.com',
        'chatgpt': 'openai.com',
        'disney': 'disneyplus.com',
        'hbo': 'max.com',
        'max': 'max.com',
        'claro': 'claro.com.br',
        'vivo': 'vivo.com.br',
        'tim': 'tim.com.br',
        'ifood': 'ifood.com.br',
        'uber': 'uber.com',
        ' 99': '99app.com',
        '99app': '99app.com',
        'nubank': 'nubank.com.br',
        'inter': 'bancointer.com.br',
        'itau': 'itau.com.br',
        'bradesco': 'bradesco.com.br',
        'santander': 'santander.com.br',
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
        'extra': 'extra.com.br',
        'carrefour': 'carrefour.com.br',
        'pao de acucar': 'paodeacucar.com.br',
        'magalu': 'magazineluiza.com.br',
        'americanas': 'americanas.com.br',
        'drogasil': 'drogasil.com.br',
        'renner': 'lojasrenner.com.br',
        'outback': 'outback.com.br',
        'mcdonald': 'mcdonalds.com.br',
        'burger king': 'burgerking.com.br',
        'shell': 'shell.com.br',
        'ipiranga': 'postossipiranga.com.br'
      };

      for (const [key, domain] of Object.entries(brands)) {
        if (normalized.includes(key)) {
          return `<div class="w-6 h-6 shrink-0 rounded-full overflow-hidden bg-white flex items-center justify-center shadow-sm border border-telegram-separator"><img src="https://www.google.com/s2/favicons?domain=${domain}&sz=64" class="w-full h-full object-contain" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';"><i data-lucide="tag" class="w-3 h-3 text-telegram-hint hidden"></i></div>`;
        }
      }
      return `<div class="w-6 h-6 shrink-0 rounded-full overflow-hidden bg-brand/10 flex items-center justify-center shadow-sm border border-brand/20"><i data-lucide="tag" class="w-3 h-3 text-brand"></i></div>`;
    }

    function renderModoDeus(data) {
      const fmt = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
      const dtFmt = (d) => d ? new Date(d).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' }) : '--';
      const vg = data.visao_geral || {};

      const mdMonthYear = document.getElementById('modoDeusMonthYear');
      if (mdMonthYear) {
        mdMonthYear.textContent = new Date().toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' }).toUpperCase();
      }

      // Saúde Financeira (Score e Label vindos do Backend)
      const health = data.health || { score: 0, label: 'Erro' };
      const score = health.score;
      const label = health.label;

      const sEl = document.getElementById('modoDeusScore');
      if (sEl) {
        sEl.textContent = score;
        sEl.style.color = score >= 80 ? '#3B6D11' : (score >= 60 ? '#854F0B' : '#A32D2D');
      }

      const lEl = document.getElementById('modoDeusScoreLabel');
      if (lEl) {
        lEl.textContent = label;
        lEl.className = `text-[10px] font-bold px-2 py-0.5 rounded-full ${score >= 80 ? 'bg-green-100 text-green-700' : (score >= 60 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700')}`;
      }

      const mdPatrimonio = document.getElementById('mdPatrimonio');
      if (mdPatrimonio) mdPatrimonio.textContent = fmt.format(vg.patrimonio_liquido || 0);

      const vpcEl = document.getElementById('mdPatrimonioVar');
      if (vpcEl) {
        vpcEl.textContent = 'LUCRO/PREJUÍZO ACUMULADO';
        vpcEl.className = 'text-[10px] mt-1 font-semibold text-brand/70';
      }

      const mdDisponivel = document.getElementById('mdDisponivel');
      const mdLimiteDiario = document.getElementById('mdLimiteDiario');
      if (mdDisponivel && mdLimiteDiario) {
        if (vg.resultado_mes <= 0) {
          // Se estiver negativo ou zero, o foco é o bloqueio total
          mdDisponivel.textContent = "🛑 BLOQUEIO";
          mdDisponivel.className = 'text-xl font-black text-red-500 truncate font-financial animate-pulse';

          mdLimiteDiario.textContent = 'GASTOS CONGELADOS';
          mdLimiteDiario.className = 'text-[9px] mt-1 text-red-500/80 font-black font-mono';
        } else {
          // Se estiver positivo, o valor principal é quanto ele pode gastar por dia
          mdDisponivel.textContent = fmt.format(vg.limite_diario_seguro || 0);
          mdDisponivel.className = 'text-xl font-black text-telegram-text truncate font-financial';

          mdLimiteDiario.textContent = 'LIMITE DIÁRIO SEGURO';
          mdLimiteDiario.className = 'text-[9px] mt-1 text-emerald-500 font-black font-mono';
        }
      }
      const rMes = vg.resultado_mes || 0;
      const rEl = document.getElementById('mdResultado');
      if (rEl) {
        rEl.textContent = fmt.format(rMes);
        rEl.className = `text-lg font-bold truncate ${rMes >= 0 ? 'text-green-600' : 'text-red-600'}`;
      }

      const mdEntradas = document.getElementById('mdEntradas');
      if (mdEntradas) mdEntradas.textContent = `Entradas ${fmt.format(vg.entradas_mes || 0)}`;

      const mdSaidas = document.getElementById('mdSaidas');
      if (mdSaidas) mdSaidas.textContent = `Saídas ${fmt.format(vg.saidas_mes || 0)}`;

      const tFlow = (vg.entradas_mes || 0) + (vg.saidas_mes || 0);
      const pEnt = tFlow > 0 ? ((vg.entradas_mes || 0) / tFlow * 100) : 50;
      const mdBarEntrada = document.getElementById('mdBarEntrada');
      const mdBarSaida = document.getElementById('mdBarSaida');
      if (mdBarEntrada) mdBarEntrada.style.width = `${pEnt}%`;
      if (mdBarSaida) mdBarSaida.style.width = `${100 - pEnt}%`;

      const mdNetResult = document.getElementById('mdNetResult');
      if (mdNetResult) mdNetResult.textContent = rMes >= 0 ? `Sobra de ${fmt.format(rMes)}` : `Déficit de ${fmt.format(Math.abs(rMes))}`;

      const mdDiasRestantes = document.getElementById('mdDiasRestantes');
      if (mdDiasRestantes) mdDiasRestantes.textContent = `${vg.dias_restantes_mes || 0} dias restantes`;

      const catsL = document.getElementById('mdTopCategories');
      const catsBlock = catsL?.closest('.glass-card');
      if (catsL) {
        const topCats = data.top_categorias || [];
        if (topCats.length > 0) {
          if (catsBlock) catsBlock.classList.remove('hidden');
          catsL.innerHTML = '';
          const maxT = topCats[0].total;
          
          topCats.forEach((c, idx) => {
            const hasSub = c.subcategorias && c.subcategorias.length > 0;
            const catId = `md-cat-${idx}`;
            
            let subsHtml = '';
            if (hasSub) {
              subsHtml = `<div id="${catId}-subs" class="hidden mt-3 pl-4 border-l-2 border-slate-200 dark:border-slate-700 space-y-2">`;
              c.subcategorias.forEach(s => {
                const subPerc = (s.total / c.total * 100).toFixed(0);
                subsHtml += `
                  <div class="flex justify-between items-center text-[10px]">
                    <span class="text-telegram-hint font-medium">${s.nome}</span>
                    <div class="flex items-center gap-2">
                      <span class="text-telegram-hint font-bold">${fmt.format(s.total)}</span>
                      <span class="text-[8px] px-1 rounded bg-slate-100 dark:bg-slate-800 text-telegram-hint">${subPerc}%</span>
                    </div>
                  </div>
                `;
              });
              subsHtml += `</div>`;
            }

            const itemHtml = `
              <div class="category-item">
                <button onclick="toggleCategorySubs('${catId}')" class="w-full text-left focus:outline-none active:opacity-70 transition-opacity">
                  <div class="flex justify-between text-[11px] mb-1.5">
                    <div class="flex items-center gap-1.5">
                      <span class="text-telegram-text font-bold">${c.nome}</span>
                      ${hasSub ? `<i data-lucide="chevron-down" id="${catId}-icon" class="w-3 h-3 text-telegram-hint transition-transform duration-300"></i>` : ''}
                    </div>
                    <span class="text-telegram-text font-black">${fmt.format(c.total)}</span>
                  </div>
                  <div class="h-2 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div class="h-full rounded-full transition-all duration-1000" style="width: ${(c.total / maxT * 100)}%; background-color: ${c.cor_hex}"></div>
                  </div>
                </button>
                ${subsHtml}
              </div>
            `;
            catsL.innerHTML += itemHtml;
          });
        } else if (catsBlock) {
          catsBlock.classList.add('hidden');
        }
      }

      // Função global para o toggle
      window.toggleCategorySubs = function(id) {
        const subs = document.getElementById(`${id}-subs`);
        const icon = document.getElementById(`${id}-icon`);
        if (subs) {
          const isHidden = subs.classList.contains('hidden');
          // Fecha outros? (opcional, vamos deixar abrir múltiplos por enquanto)
          subs.classList.toggle('hidden');
          if (icon) {
            icon.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
          }
        }
      };

      const mdTotalAssinaturas = document.getElementById('mdTotalAssinaturas');
      const assL = document.getElementById('mdAssinaturasList');
      const assBlock = assL?.closest('.glass-card');
      if (assL) {
        const assObj = data.assinaturas || { lista: [], total_mensal: 0 };
        if (assObj.lista.length > 0) {
          if (assBlock) assBlock.classList.remove('hidden');
          assL.innerHTML = '';
          if (mdTotalAssinaturas) mdTotalAssinaturas.textContent = fmt.format(assObj.total_mensal);
          assObj.lista.slice(0, 10).forEach(a => {
            const logo = getBrandLogoHtml(a.descricao);
            assL.innerHTML += `<div class="flex items-center justify-between gap-3"><div class="flex items-center gap-3 min-w-0">${logo}<span class="text-[12px] font-bold text-telegram-text truncate">${a.descricao}</span></div><span class="text-[12px] text-telegram-text font-black whitespace-nowrap">${fmt.format(a.valor)}</span></div>`;
          });
        } else if (assBlock) {
          assBlock.classList.add('hidden');
        }
      }

      const mdTotalParcelas = document.getElementById('mdTotalParcelas');
      const parcL = document.getElementById('mdParcelasList');
      const parcBlock = parcL?.closest('.glass-card');
      if (parcL) {
        const parcObj = data.parcelamentos || { lista: [], total_mensal_parcelas: 0 };
        if (parcObj.lista.length > 0) {
          if (parcBlock) parcBlock.classList.remove('hidden');
          parcL.innerHTML = '';
          if (mdTotalParcelas) mdTotalParcelas.textContent = fmt.format(parcObj.total_mensal_parcelas);
          parcObj.lista.slice(0, 10).forEach(p => {
            parcL.innerHTML += `<div><div class="flex justify-between text-[11px] mb-1"><span class="text-telegram-text truncate mr-2">${p.descricao}</span><span class="text-telegram-hint">${p.parcela_atual}/${p.total_parcelas}</span></div><div class="h-1 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden"><div class="h-full bg-amber-500" style="width: ${p.percentual_concluido}%"></div></div></div>`;
          });
        } else if (parcBlock) {
          parcBlock.classList.add('hidden');
        }
      }

      const cartL = document.getElementById('mdCartoesList');
      const cartBlock = cartL?.closest('.glass-card');
       if (cartL) {
        const cards = data.cartoes || [];
        const pastBills = data.faturas_historico || [];
        
        if (cards.length > 0 || pastBills.length > 0) {
          if (cartBlock) cartBlock.classList.remove('hidden');
          cartL.innerHTML = '';
          
          // 1. Faturas em Aberto
          if (cards.length > 0) {
            cards.forEach(c => {
              const v = c.dias_para_vencer;
              const b = v !== null && v <= 7 ? `<span class="px-1.5 py-0.5 rounded bg-red-100 text-red-700 text-[8px] font-bold">VENCE EM ${v}D</span>` : (v !== null && v <= 14 ? `<span class="px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 text-[8px] font-bold">VENCE EM ${v}D</span>` : '');
              cartL.innerHTML += `
                <div class="flex items-center gap-3">
                  <div class="w-2 h-2 rounded-full" style="background-color: ${c.cor_hex}"></div>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="text-[11px] font-bold text-telegram-text truncate">${c.nome_conta}</span>${b}
                    </div>
                    <p class="text-[9px] text-telegram-hint">Vence ${dtFmt(c.data_vencimento)}</p>
                  </div>
                  <div class="text-right">
                    <div class="text-[11px] font-bold text-telegram-text">${fmt.format(c.valor_total)}</div>
                    <p class="text-[9px] text-telegram-hint">de ${fmt.format(c.limite_cartao)}</p>
                  </div>
                </div>`;
            });
          }

          // 2. Histórico de Faturas (Pagas)
          if (pastBills.length > 0) {
            cartL.innerHTML += `
              <div class="mt-4 pt-3 border-t border-telegram-separator">
                <h4 class="text-[9px] font-bold text-telegram-hint uppercase tracking-wider mb-3">Faturas Pagas Recentemente</h4>
                <div class="space-y-3">
                  ${pastBills.map(f => `
                    <div class="flex items-center justify-between opacity-70">
                      <div class="min-w-0">
                        <p class="text-[10px] font-bold text-telegram-text truncate">${f.nome_conta}</p>
                        <p class="text-[8px] text-telegram-hint">Paga em ${dtFmt(f.data_vencimento)}</p>
                      </div>
                      <div class="text-right">
                        <p class="text-[10px] font-black text-emerald-600">${fmt.format(f.valor_total)}</p>
                        <span class="text-[7px] font-bold px-1 rounded bg-emerald-100 text-emerald-700">PAGA</span>
                      </div>
                    </div>
                  `).join('')}
                </div>
              </div>`;
          }
        } else if (cartBlock) {
          cartBlock.classList.add('hidden');
        }
      }

      const mL = document.getElementById('mdMetasList');
      const mBlock = mL?.closest('.glass-card');
      if (mL) {
        const metas = data.metas || [];
        if (metas.length > 0) {
          if (mBlock) mBlock.classList.remove('hidden');
          mL.innerHTML = '';
          metas.forEach(m => {
            mL.innerHTML += `<div><div class="flex justify-between text-[11px] mb-1"><span class="text-telegram-text truncate mr-2">${m.descricao}</span><span class="text-telegram-text font-bold">${m.percentual.toFixed(0)}%</span></div><div class="h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden"><div class="h-full bg-green-500" style="width: ${m.percentual}%"></div></div></div>`;
          });
        } else if (mBlock) {
          mBlock.classList.add('hidden');
        }
      }

      const oL = document.getElementById('mdOrcamentosList');
      const oBlock = oL?.closest('.glass-card');
      if (oL) {
        const orcs = data.orcamentos || [];
        if (orcs.length > 0) {
          if (oBlock) oBlock.classList.remove('hidden');
          oL.innerHTML = '';
          orcs.forEach(o => {
            const cC = o.status === 'estourado' ? 'bg-red-100 text-red-700' : (o.status === 'atencao' ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700');
            oL.innerHTML += `<div class="flex items-center justify-between"><span class="text-[11px] text-telegram-text font-medium">${o.categoria}</span><span class="px-2 py-0.5 rounded-full ${cC} text-[9px] font-bold">${o.percentual_usado.toFixed(0)}% usado</span></div>`;
          });
        } else if (oBlock) {
          oBlock.classList.add('hidden');
        }
      }
      const fBlock = document.getElementById('mdFiisBlock');
      if (data.fiis && data.fiis.lista && data.fiis.lista.length > 0) {
        if (fBlock) fBlock.classList.remove('hidden');
        const mdRendaFII = document.getElementById('mdRendaFII');
        if (mdRendaFII) mdRendaFII.textContent = data.fiis.renda_mensal_estimada ? fmt.format(data.fiis.renda_mensal_estimada) + '/mês' : '—';
        const fL = document.getElementById('mdFiisList');
        if (fL) {
          fL.innerHTML = '';
          data.fiis.lista.forEach(f => {
            fL.innerHTML += `<div class="flex justify-between items-center text-[11px]"><div><span class="font-bold text-telegram-text">${f.ticker}</span><p class="text-[9px] text-telegram-hint">${f.quantidade_cotas} cotas</p></div><div class="text-right"><span class="text-telegram-text font-bold">${fmt.format(f.valor_posicao)}</span><p class="text-[9px] text-telegram-hint">PM: ${fmt.format(f.preco_medio)}</p></div></div>`;
          });
        }
      } else if (fBlock) {
        fBlock.classList.add('hidden');
      }

      const aBlock = document.getElementById('mdAlertasBlock');
      if (data.alertas && data.alertas.length > 0) {
        if (aBlock) aBlock.classList.remove('hidden');
        const aI = document.getElementById('mdAlertasList');
        if (aI) {
          aI.innerHTML = '';
          data.alertas.forEach(a => {
            const dC = a.tipo === 'critico' ? 'bg-red-500' : (a.tipo === 'aviso' ? 'bg-amber-500' : 'bg-blue-500');
            aI.innerHTML += `<div class="flex items-start gap-3"><div class="w-2 h-2 rounded-full mt-1.5 ${dC}"></div><div><p class="text-[11px] font-bold text-telegram-text">${a.titulo}</p><p class="text-[10px] text-telegram-hint">${a.detalhe}</p></div></div>`;
          });
        }
      } else if (aBlock) {
        aBlock.classList.add('hidden');
      }

      const vL = document.getElementById('mdVencimentosList');
      if (vL) {
        vL.innerHTML = '';
        (data.proximos_vencimentos || []).forEach(v => {
          vL.innerHTML += `<div class="flex items-center justify-between text-[11px]"><div class="flex items-center gap-2"><div class="w-1.5 h-1.5 rounded-full" style="background-color: ${v.cor_hex}"></div><span class="text-telegram-text truncate max-w-[120px]">${v.descricao}</span><span class="text-[9px] text-telegram-hint">${dtFmt(v.data)}</span></div><span class="font-bold text-telegram-text">${fmt.format(v.valor)}</span></div>`;
        });
      }

      const iL = document.getElementById('mdInsightsList');
      if (iL) {
        iL.innerHTML = '';
        (data.insights_rapidos || []).forEach(i => {
          iL.innerHTML += `<p>— ${i}</p>`;
        });
      }
    }

    // --- SISTEMA DE AJUDA DOS GRÁFICOS ---
    window.showChartHelp = function(chartId) {
      const helpData = {
        'gauge': {
          title: 'Saúde do Orçamento',
          msg: 'Mede o quanto você já gastou em relação aos limites (teto) definidos por categoria. Se estiver abaixo de 100%, você está cumprindo seu planejamento.'
        },
        'patrimonio': {
          title: 'Evolução Patrimonial',
          msg: 'Mostra o acúmulo total do seu dinheiro (contas + investimentos) ao longo do tempo. Serve para ver se sua riqueza líquida está crescendo.'
        },
        'fluxo': {
          title: 'Fluxo de Caixa',
          msg: 'Comparativo direto entre o que entrou (verde) e o que saiu (vermelho) mês a mês. O ideal é a barra verde ser sempre maior.'
        },
        'distribuicao': {
          title: 'Distribuição de Despesas',
          msg: 'Quais categorias estão "roubando" mais o seu dinheiro. Útil para identificar para onde seu dinheiro está indo realmente.'
        },
        'projecao': {
          title: 'Projeção de Saldo',
          msg: 'Uma estimativa baseada no seu comportamento atual de como seu dinheiro estará nos próximos meses se você mantiver o ritmo.'
        },
        'viloes': {
          title: 'Top 5 Vilões',
          msg: 'Identifica os 5 estabelecimentos ou descrições específicas onde você mais gastou nos últimos 90 dias.'
        },
        'sankey': {
          title: 'Caminho do Dinheiro',
          msg: 'Visualiza o fluxo completo: desde a sua Renda, passando pelas contas, até o destino final em cada categoria de gasto.'
        },
        'heatmap': {
          title: 'Mapa de Calor',
          msg: 'Mostra sua rotina de lançamentos por dia da semana. Ajuda a entender em quais dias você é mais ativo financeiramente.'
        }
      };

      const info = helpData[chartId];
      if (info && window.Telegram?.WebApp) {
        // Vibração tátil suave para indicar interação
        if (window.Telegram.WebApp.HapticFeedback) {
          window.Telegram.WebApp.HapticFeedback.impactOccurred('medium');
        }
        window.Telegram.WebApp.showAlert(`${info.title}\n\n${info.msg}`);
      }
    };
