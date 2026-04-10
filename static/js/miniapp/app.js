lucide.createIcons();

    // Chart.js Global Defaults
    if (window.Chart) {
      // Registrar plugins especiais para Chart.js 4
      try {
        // Registro para Sankey
        const sankeyPlugin = window['chartjs-chart-sankey'] || window.ChartSankey;
        if (sankeyPlugin) {
            Chart.register(sankeyPlugin.SankeyController, sankeyPlugin.FlowElement);
        } else if (typeof SankeyController !== 'undefined') {
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
      Chart.defaults.font.family = "'Outfit', sans-serif";
      Chart.defaults.font.weight = '600';
      
      // Cores dos Tooltips explicitamente contrastadas
      const isDarkMode = window.Telegram?.WebApp?.colorScheme === 'dark';
      Chart.defaults.plugins.tooltip.backgroundColor = isDarkMode ? '#1e293b' : '#ffffff';
      Chart.defaults.plugins.tooltip.titleColor = isDarkMode ? '#f8fafc' : '#0f172a';
      Chart.defaults.plugins.tooltip.bodyColor = isDarkMode ? '#f8fafc' : '#0f172a';
      Chart.defaults.plugins.tooltip.borderColor = 'rgba(123, 30, 45, 0.1)';
      Chart.defaults.plugins.tooltip.borderWidth = 1;
      Chart.defaults.plugins.tooltip.padding = 12;
      Chart.defaults.plugins.tooltip.cornerRadius = 12;
      Chart.defaults.plugins.legend.labels.usePointStyle = true;
      Chart.defaults.plugins.legend.labels.pointStyle = 'circle';
      Chart.defaults.plugins.legend.labels.padding = 20;
    }

    // DOM Elements
    const panels = document.querySelectorAll('.panel');
    const appBody = document.body;
    const htmlRoot = document.documentElement;
    const mainStatus = document.getElementById('mainStatus');
    const homeBalance = document.getElementById('homeBalance');
    const homeBalanceHint = document.getElementById('homeBalanceHint');
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
    const agendamentoRefresh = document.getElementById('agendamentoRefresh');
    const agendamentoNew = document.getElementById('agendamentoNew');
    const newAgendamentoModal = document.getElementById('newAgendamentoModal');
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
    let historyOffset = 0;
    const historyLimit = 20;
    let historyCache = [];
    let metasCache = [];
    let selectedLancamento = null;
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
    window.abrirEdicaoOrcamento = function(id_categoria, valor_limite, nome_categoria) {
      if (id_categoria && id_categoria !== 'undefined' && orcamentoCategoria.querySelector(`option[value="${id_categoria}"]`)) {
          orcamentoCategoria.value = id_categoria;
      } else {
          const options = Array.from(orcamentoCategoria.options);
          const opt = options.find(o => o.text === nome_categoria);
          if (opt) orcamentoCategoria.value = opt.value;
      }
      orcamentoValor.value = String(valor_limite).replace('.', ',');
      orcamentoModal.classList.add('active');
      document.body.style.overflow = 'hidden';
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
        return;
      }
      editModalBadge.textContent = item.id ? `Editando: ${item.descricao || 'Lançamento'}` : `Pré-edição: ${item.descricao || 'Lançamento'}`;
      editDescricao.value = item.descricao || '';
      editValor.value = item.valor != null ? String(item.valor).replace('.', ',') : '';
      editTipo.value = item.tipo || 'Saída';
      editData.value = formatDateForInput(item.data);
      editForma.value = item.forma_pagamento || '';
      if (item.id) {
        editDraftInfo.classList.add('hidden');
        editDraftInfo.innerHTML = '';
      } else {
        applyDraftDetails(item);
      }
    }

    function openEditModal(item) {
      setSelectedLancamento(item);
      editModal.classList.add('active');
      document.body.style.overflow = 'hidden';
    }

    function closeEditModal() {
      editModal.classList.remove('active');
      document.body.style.overflow = 'auto';
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
      const cached = getStoredSessionId();
      if (!cached) return false;
      try {
        const response = await fetch('/api/miniapp/overview', {
          headers: { 'X-Session-Id': cached },
        });
        if (!response.ok) return false;
        const data = await response.json();
        if (!data?.ok) return false;
        sessionId = cached;
        return true;
      } catch (_) {
        return false;
      }
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

    function getCategoryIcon(categoria, subcategoria, tipo) {
      const combined = `${categoria || ''} ${subcategoria || ''}`.toLowerCase();
      
      const map = [
        { keys: ['aliment', 'mercado', 'padaria', 'supermercado', 'açougue', 'feira'], icon: 'shopping-cart' },
        { keys: ['restaurante', 'ifood', 'delivery', 'lanche', 'pizza', 'hamburguer'], icon: 'utensils' },
        { keys: ['café', 'coffee', 'confeitaria'], icon: 'coffee' },
        { keys: ['transporte', 'uber', '99', 'táxi', 'taxi', 'estacionamento', 'pedágio'], icon: 'car' },
        { keys: ['combustível', 'gasolina', 'posto', 'etanol', 'diesel'], icon: 'fuel' },
        { keys: ['passagem', 'ônibus', 'onibus', 'metro', 'metrô', 'trem'], icon: 'bus' },
        { keys: ['moradia', 'aluguel', 'casa', 'condomínio', 'condominio'], icon: 'home' },
        { keys: ['energia', 'luz', 'eletricidade'], icon: 'zap' },
        { keys: ['água', 'agua', 'saneamento'], icon: 'droplets' },
        { keys: ['internet', 'telefone', 'celular', 'claro', 'vivo', 'tim'], icon: 'wifi' },
        { keys: ['saúde', 'saude', 'médico', 'medico', 'hospital', 'dentista', 'convênio', 'unimed', 'terapia'], icon: 'heart-pulse' },
        { keys: ['farmácia', 'farmacia', 'remédio', 'medicamento'], icon: 'pill' },
        { keys: ['lazer', 'entretenimento', 'cinema', 'show', 'ingresso', 'festa', 'bar'], icon: 'popcorn' },
        { keys: ['assinatura', 'streaming', 'netflix', 'spotify', 'amazon', 'prime'], icon: 'play-square' },
        { keys: ['educação', 'educacao', 'escola', 'faculdade', 'curso', 'livro'], icon: 'graduation-cap' },
        { keys: ['vestuário', 'vestuario', 'roupa', 'calçado', 'loja', 'shopping'], icon: 'shirt' },
        { keys: ['eletrônico', 'eletronico', 'computador', 'tecnologia', 'software', 'hardware'], icon: 'laptop' },
        { keys: ['pet', 'cachorro', 'gato', 'veterinário', 'ração', 'animal'], icon: 'dog' },
        { keys: ['viagem', 'voo', 'hotel', 'hospedagem', 'airbnb', 'turismo'], icon: 'plane' },
        { keys: ['beleza', 'cabelo', 'salão', 'barbearia', 'cosmético', 'estética'], icon: 'scissors' },
        { keys: ['esporte', 'academia', 'gympass', 'smartfit', 'futebol', 'crossfit'], icon: 'dumbbell' },
        { keys: ['imposto', 'taxa', 'ipva', 'iptu', 'darf', 'multa'], icon: 'landmark' },
        { keys: ['salário', 'salario', 'renda', 'pagamento', 'prolabore', 'adiantamento'], icon: 'coins' },
        { keys: ['investimento', 'rendimento', 'dividendos', 'cdb', 'selic', 'bolsa', 'poupança'], icon: 'trending-up' },
        { keys: ['transferência', 'transferencia', 'pix', 'ted', 'doc'], icon: 'arrow-right-left' },
      ];
      for (const item of map) { if (item.keys.some(key => combined.includes(key))) return item.icon; }
      const tipoNorm = String(tipo || '').toLowerCase();
      if (tipoNorm.includes('entrada') || tipoNorm.includes('receita')) return 'arrow-down-to-line';
      return 'receipt';
    }

    function renderHomeRecent(items = []) {
      if (!items.length) {
        homeRecentList.innerHTML = '<div class="rounded-2xl border border-dashed border-telegram-separator bg-telegram-card p-4 text-sm text-telegram-hint">Sem movimentações recentes por enquanto.</div>';
        return;
      }

      homeRecentList.innerHTML = items.map((item) => {
        const numericValue = Number(item.valor) || 0;
        const isReceita = isEntradaTipo(item.tipo, numericValue);
        const [badgeLabel, badgeClass] = sourceBadgeConfig(item.origem_label || item.origem);
        const iconName = getCategoryIcon(item.categoria_nome, item.subcategoria_nome, item.tipo);
        return `
          <button class="recent-item w-full text-left rounded-2xl border border-telegram-separator bg-telegram-card p-4 hover:bg-brand/5 transition shadow-soft" data-action="edit" data-id="${item.id}">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-full ${isReceita ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-300' : 'bg-rose-100 text-rose-600 dark:bg-rose-900/40 dark:text-rose-300'} flex items-center justify-center shrink-0">
                <i data-lucide="${iconName}" class="w-5 h-5"></i>
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-start justify-between gap-2">
                  <div class="min-w-0">
                    <p class="font-semibold text-sm text-telegram-text truncate">${item.descricao || 'Lançamento'}</p>
                    <p class="text-xs text-telegram-hint mt-0.5 truncate">${item.categoria_nome ? `${item.categoria_nome}${item.subcategoria_nome ? ` / ${item.subcategoria_nome}` : ''}` : 'Sem categoria'} • ${new Date(item.data).toLocaleDateString('pt-BR')}</p>
                  </div>
                  <div class="text-right shrink-0 flex flex-col items-end gap-1.5">
                    <span class="font-extrabold ${isReceita ? 'text-emerald-600' : 'text-rose-600'}">${formatMoney(item.valor, item.tipo)}</span>
                    <span class="text-[9px] font-bold uppercase tracking-[0.16em] rounded-full border px-1.5 py-0.5 ${badgeClass}">${badgeLabel}</span>
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

      // Heatmap Data (Activity by Day of Week vs Week of Month)
      const heatmapData = [];
      const days = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
      const weeks = ['Sem 1', 'Sem 2', 'Sem 3', 'Sem 4', 'Sem 5'];
      
      const activityMap = {}; 
      const recent = summary?.recent || [];
      recent.forEach(item => {
        if (!item.data) return;
        const d = new Date(item.data);
        if (isNaN(d.getTime())) return;
        const dayIdx = d.getDay();
        const weekIdx = Math.floor((d.getDate() - 1) / 7);
        const key = `${dayIdx}-${weekIdx}`;
        activityMap[key] = (activityMap[key] || 0) + 1;
      });

      weeks.forEach((w, wIdx) => {
        days.forEach((d, dIdx) => {
          heatmapData.push({
            x: d,
            y: w,
            v: activityMap[`${dIdx}-${wIdx}`] || 0
          });
        });
      });

      return {
        sixMonths,
        patrimonyMonths,
        patrimonyValues,
        fluxoEntradas,
        fluxoSaidas,
        budgetLabels,
        budgetCap,
        budgetRealized,
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
      Object.values(homeCharts).forEach((chart) => {
        if (chart && typeof chart.destroy === 'function') chart.destroy();
      });
      homeCharts = {};
    }

    function renderHomeOverview(summary) {
      const balance = Number(summary?.balance || 0);
      const receita = Number(summary?.receita || 0);
      const despesa = Number(summary?.despesa || 0);
      const progressPct = Math.max(0, Math.min(Number(summary?.progress_pct || 0), 100));

      homeBalance.textContent = formatCurrencyBR(balance);
      homeBalanceHint.textContent = balance >= 0 ? 'Você está fechando o mês no azul.' : 'As despesas estão pressionando o mês.';

      homeLevel.textContent = String(summary?.level || 1);
      homeXp.textContent = String(summary?.xp || 0);
      homeStreak.textContent = String(summary?.streak || 0);
      
      const totalFluxo = receita + despesa;
      const pctReceita = totalFluxo > 0 ? Math.round((receita / totalFluxo) * 100) : 0;
      const pctDespesa = totalFluxo > 0 ? Math.round((despesa / totalFluxo) * 100) : 0;
      
      // Lógica do Aquário: Nível é o saldo restante (proporcional ao verde)
      const waterLevel = Math.max(15, 100 - progressPct); // Garante visibilidade mínima
      homeProgressLabel.textContent = `${100 - progressPct}%`;

      // Animação de enchimento: efeito de "briga" entre cores
      if (homeAquariumWater) {
        // 1. Reset
        homeAquariumWater.style.height = '0%';
        homeAquariumWater.style.background = '#ef4444'; 

        setTimeout(() => {
          // 2. Primeiro sobe a despesa (vermelho) de forma agressiva
          homeAquariumWater.style.height = '100%'; 
          
          setTimeout(() => {
            // 3. Aplica o gradiente dividido (Hard Stop)
            // A parte de baixo (0% a progressPct%) fica vermelha
            // A parte de cima (progressPct% a 100%) fica verde
            const despesaPos = Math.max(5, progressPct); // Garante um pouco de vermelho se houver gasto
            homeAquariumWater.style.background = `linear-gradient(to top, #ef4444 0%, #ef4444 ${despesaPos}%, #10b981 ${despesaPos}%, #059669 100%)`;
            
            // Mantemos a altura em 100% para o tanque parecer "cheio" de decisões financeiras
            // ou ajustamos para waterLevel se quiser que o volume total represente a saúde
            homeAquariumWater.style.height = '100%'; 
          }, 1200);
        }, 300);
      }

      if (homePctReceita) homePctReceita.textContent = `REC: ${pctReceita}%`;
      if (homePctDespesa) homePctDespesa.textContent = `DES: ${pctDespesa}%`;

      homeReceita.textContent = `Receitas: ${formatCurrencyBR(receita)}`;
      homeDespesa.textContent = `Despesas: ${formatCurrencyBR(despesa)}`;
      homeInsight.textContent = summary?.insight || 'Carregando insight do Alfredo...';

      // Badge do usuário (nível)
      const badgeSvg = summary?.badge_svg || summary?.level_progress?.badge_svg;
      if (badgeSvg) {
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
      } else {
        homeBadgeContainer.textContent = summary?.badge || '🌱';
      }

      // Plano do usuário (Free/Premium)
      if (summary?.plan_label) {
        homePlanLabel.textContent = summary.plan_label;
        homePlanLabel.style.display = 'block';
        
        // Mostrar botão de upgrade se for free ou trial
        const userPlan = summary.plan || 'free';
        if (userPlan === 'free' || userPlan === 'trial') {
          homeUpgradeBtn.style.display = 'block';
        } else {
          homeUpgradeBtn.style.display = 'none';
        }
      } else {
        homePlanLabel.textContent = '';
        homePlanLabel.style.display = 'none';
        homeUpgradeBtn.style.display = 'none';
      }

      homeRecentCache = Array.isArray(summary?.recent) ? summary.recent : [];
      const categories = Array.isArray(summary?.categories) ? summary.categories : [];
      const chartRuntime = getChartRuntime();
      const chartData = buildChartDataFromSummary(summary);

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

      // Helper para criar gráficos com segurança
      const safeChart = (id, config) => {
        try {
          const el = typeof id === 'string' ? document.getElementById(id) : id;
          if (!el) return null;
          return new Chart(el, config);
        } catch (err) {
          console.warn(`Erro ao criar gráfico ${id}:`, err);
          return null;
        }
      };

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

      if (homeBudgetChartEl) {
        homeCharts.budget = safeChart(homeBudgetChartEl, {
          type: 'bar',
          data: {
            labels: chartData.budgetLabels,
            datasets: [
              {
                label: 'Orçamento',
                data: chartData.budgetCap,
                borderRadius: 12,
                borderSkipped: false,
                backgroundColor: 'rgba(148, 163, 184, 0.25)',
                barPercentage: 0.8,
                categoryPercentage: 0.8,
              },
              {
                label: 'Realizado',
                data: chartData.budgetRealized,
                borderRadius: 12,
                borderSkipped: false,
                backgroundColor: chartData.budgetRealized.map((value, idx) => value > chartData.budgetCap[idx] ? '#ef4444' : '#f59e0b'),
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
              legend: commonLegend,
              tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${formatCurrencyBR(ctx.raw)}` } },
            },
            scales: {
              x: { grid: { color: 'rgba(148, 163, 184, 0.14)' }, ticks: { color: '#64748b', callback: (v) => `R$ ${Number(v).toLocaleString('pt-BR')}` } },
              y: { grid: { display: false }, ticks: { color: '#475569' } },
            },
          },
        });
      }

      if (homeCategoryChartEl) {
        const hasCategories = categories.length > 0;
        const palette = ['#6366f1', '#f59e0b', '#10b981', '#ef4444', '#00f0ff', '#8b5cf6'];
        homeCharts.category = safeChart(homeCategoryChartEl, {
          type: 'doughnut',
          data: {
            labels: chartData.distroLabels.slice(0, 6),
            datasets: [{
              data: chartData.distroValues.slice(0, 6),
              backgroundColor: chartData.distroLabels.slice(0, 6).map((_, idx) => categories[idx]?.color || palette[idx % palette.length]),
              borderWidth: 0,
              hoverOffset: 8,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: commonAnimation,
            cutout: '70%',
            plugins: {
              legend: commonLegend,
              tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${formatCurrencyBR(ctx.raw)}` } },
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

      if (homeSankeyChartEl && chartData.sankeyData.length) {
        homeCharts.sankey = safeChart(homeSankeyChartEl, {
          type: 'sankey',
          data: {
            datasets: [{
              label: 'Fluxo Financeiro',
              data: chartData.sankeyData,
              colorFrom: (c) => palette[c.index % palette.length],
              colorTo: (c) => palette[(c.index + 1) % palette.length],
              colorMode: 'gradient',
              alpha: 0.45,
              fontFamily: "'Outfit', sans-serif",
              fontWeight: 'bold',
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: commonAnimation,
            plugins: {
              legend: { display: false },
              tooltip: { callbacks: { label: (ctx) => `Fluxo: ${formatCurrencyBR(ctx.raw.flow)}` } }
            }
          }
        });
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
                const alpha = Math.min(0.9, 0.1 + (value * 0.25));
                return `rgba(251, 113, 133, ${alpha})`;
              },
              borderColor: 'rgba(251, 113, 133, 0.15)',
              borderWidth: 1,
              width: ({chart}) => (chart.chartArea || {}).width / 7 - 4,
              height: ({chart}) => (chart.chartArea || {}).height / 5 - 4,
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: commonAnimation,
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  title: () => 'Densidade de Gastos',
                  label: (ctx) => `${ctx.raw.v} lançamento(s) na ${ctx.raw.y} (${ctx.raw.x})`
                }
              }
            },
            scales: {
              x: { type: 'category', labels: ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'], grid: { display: false } },
              y: { type: 'category', labels: ['Sem 1', 'Sem 2', 'Sem 3', 'Sem 4', 'Sem 5'], grid: { display: false }, offset: true }
            }
          }
        });
      }

      renderHomeRecent(summary?.recent || []);
      lucide.createIcons();
    }

    async function loadHomeOverview() {
      if (!sessionId) return;
      try {
        console.log("🚀 Carregando visão geral...");
        const response = await fetchWithSession('/api/miniapp/overview');
        const data = await response.json();
        if (!data.ok) {
          console.error("❌ Erro na API de visão geral:", data.error);
          throw new Error(data.error || 'overview_error');
        }
        console.log("✅ Dados recebidos:", data.summary);
        renderHomeOverview(data.summary || {});
      } catch (error) {
        console.error("🔥 Falha crítica ao carregar home:", error);
        homeBalance.textContent = 'R$ 0,00';
        homeBalanceHint.textContent = 'Não foi possível carregar o resumo agora.';
        homeInsight.textContent = 'O Alfredo não conseguiu montar o resumo agora. Tente atualizar em instantes.';
        homeRecentList.innerHTML = '<div class="rounded-2xl border border-dashed border-telegram-separator bg-telegram-card p-4 text-sm text-telegram-hint">Resumo indisponível no momento.</div>';
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
      gameInteractionsTotal.textContent = String(profile.interactions_total || 0);
      gameInteractionsWeek.textContent = String(profile.interactions_week || 0);
      gameAlfredoNote.textContent = profile.alfredo_note || 'Mantenha consistência para subir no ranking.';
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
      // 1. Patrimônio e Saúde (Parsing robusto)
      let balance = 0;
      if (typeof data.balance === 'number') balance = data.balance;
      else if (data.balance?.totalBalance) balance = Number(data.balance.totalBalance);
      else if (typeof data.balance === 'string') balance = Number(data.balance);
      
      pierreTotalBalance.textContent = formatCurrencyBR(isNaN(balance) ? 0 : balance);
      
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
        const balance = Number(acc.balance || 0);
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
              <p class="text-xs font-black text-telegram-text">${formatCurrencyBR(isNaN(balance) ? 0 : balance)}</p>
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

      const purchases = rawData?.purchases || rawData || [];
      if (!Array.isArray(purchases) || !purchases.length) {
        pierreInstallmentsList.innerHTML = '<div class="text-center py-4 text-xs text-telegram-hint">Nenhum compromisso futuro mapeado no Pierre.</div>';
        return;
      }

      const now = new Date();
      // Ordenar: Primeiro as vencidas, depois as mais próximas
      const sorted = [...purchases]
        .filter(p => p && (p.description || p.name))
        .sort((a, b) => {
          const dA = a.dueDate ? new Date(a.dueDate) : new Date(8640000000000000);
          const dB = b.dueDate ? new Date(b.dueDate) : new Date(8640000000000000);
          return dA - dB;
        })
        .slice(0, 6);

      pierreInstallmentsList.innerHTML = sorted.map(p => {
        const dueDate = p.dueDate ? new Date(p.dueDate) : null;
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

        const instNum = p.installmentNumber || '?';
        const instTot = p.totalInstallments || '?';
        const amount = Number(p.amount || 0);

        return `
          <div class="flex items-center justify-between p-3 rounded-2xl bg-white/5 border border-white/5 transition active:scale-95">
            <div class="min-w-0 flex-1">
              <p class="text-xs font-bold text-telegram-text truncate">${p.description || p.name || 'Parcela'}</p>
              <p class="text-[10px] text-telegram-hint">${instNum}/${instTot} • ${isValidDate ? dueDate.toLocaleDateString('pt-BR') : 'Sem data'}</p>
            </div>
            <div class="text-right ml-3">
              <p class="text-xs font-black text-telegram-text">${formatCurrencyBR(isNaN(amount) ? 0 : amount)}</p>
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
      newAgendamentoModal.classList.add('active');
      document.body.style.overflow = 'hidden';
    }

    function closeNewAgendamentoModal() {
      newAgendamentoModal.classList.remove('active');
      document.body.style.overflow = 'auto';
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
      } catch (e) {}
    }

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
        order: historyOrder.value || 'added_desc'
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
          const iconName = getCategoryIcon(item.categoria_nome, item.subcategoria_nome, item.tipo);
          
          const div = document.createElement('div');
          div.className = 'flex items-center justify-between gap-3 p-3 sm:p-4 rounded-2xl hover:bg-brand/5 transition border border-telegram-separator/40 bg-telegram-card/40 shadow-sm mb-2';
          div.innerHTML = `
            <div class="flex items-center gap-3 min-w-0 flex-1">
              <div class="w-10 h-10 rounded-full ${isReceita ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-300' : 'bg-rose-100 text-rose-600 dark:bg-rose-900/40 dark:text-rose-300'} flex items-center justify-center shrink-0">
                <i data-lucide="${iconName}" class="w-5 h-5"></i>
              </div>
              <div class="min-w-0 flex-1">
                <p class="font-semibold text-sm truncate text-telegram-text">${item.descricao || 'Lançamento'}</p>
                <p class="text-[11px] sm:text-xs text-telegram-hint truncate mt-0.5">${item.categoria_nome ? item.categoria_nome : 'Sem categoria'} • ${new Date(item.data).toLocaleDateString('pt-BR')}</p>
              </div>
            </div>
            <div class="flex flex-col items-end gap-1.5 shrink-0 ml-2">
              <span class="font-bold ${isReceita ? 'text-emerald-600' : 'text-rose-600'} text-sm whitespace-nowrap">${valueText}</span>
              <div class="flex items-center gap-1.5">
                <button class="history-edit-btn rounded-md border border-telegram-separator bg-telegram-card p-1.5 text-telegram-hint hover:text-brand transition" data-action="edit" data-id="${item.id}"><i data-lucide="pencil" class="w-3.5 h-3.5"></i></button>
                <button class="history-delete-btn rounded-md border border-telegram-separator bg-telegram-card p-1.5 text-telegram-hint hover:text-red-500 transition" data-action="delete" data-id="${item.id}"><i data-lucide="trash-2" class="w-3.5 h-3.5"></i></button>
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
      metaModal.classList.add('active');
      document.body.style.overflow = 'hidden';
    }

    function closeMetaModal() {
      metaModal.classList.remove('active');
      document.body.style.overflow = 'auto';
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
    function openOrcamentoModal() {
      orcamentoValor.value = '';
      orcamentoModal.classList.add('active');
      document.body.style.overflow = 'hidden';
    }
    function closeOrcamentoModal() {
      orcamentoModal.classList.remove('active');
      document.body.style.overflow = 'auto';
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
            orcamentoList.innerHTML = '<div class="text-xs text-telegram-hint text-center p-4 border border-dashed rounded-xl border-telegram-separator bg-telegram-card">Nenhum orçamento definido.</div>';
            return;
        }

        orcamentoList.innerHTML = data.items.map(o => {
            const pct = Math.min(100, Math.max(0, (o.valor_gasto / o.valor_limite) * 100));
            const color = pct >= 100 ? 'linear-gradient(90deg, #ef4444, #b91c1c)' : (pct >= 80 ? 'linear-gradient(90deg, #f59e0b, #d97706)' : 'linear-gradient(90deg, #10b981, #059669)');
            return `
            <div class="mb-3 group cursor-pointer" onclick="abrirEdicaoOrcamento('${o.id_categoria}', ${o.valor_limite}, '${o.categoria_nome}')">
                <div class="flex justify-between text-xs font-semibold mb-1 text-telegram-text hover:text-brand transition">
                    <span class="flex items-center gap-1">${o.categoria_nome} <i data-lucide="pencil" class="w-3 h-3 opacity-50"></i></span>
                    <span>R$ ${o.valor_gasto.toFixed(2).replace('.', ',')} / R$ ${o.valor_limite.toFixed(2).replace('.', ',')}</span>
                </div>
                <div class="h-2 w-full rounded-full bg-telegram-separator overflow-hidden">
                    <div class="h-full rounded-full transition-all" style="width: ${pct}%; background: ${color};"></div>
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
      try {
          const res = await fetchWithSession('/api/miniapp/orcamentos', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id_categoria, valor_limite: valor}) });
          if ((await res.json()).ok) {
              showToast('✅ Limite de orçamento salvo!', 'success');
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
    historyTipo.addEventListener('change', () => loadHistory(true));
    historyOrder.addEventListener('change', () => loadHistory(true));
    historyDate.addEventListener('change', () => loadHistory(true));
    historyClearFilters.addEventListener('click', () => {
      historyTipo.value = '';
      historyOrder.value = 'added_desc';
      historyDate.value = '';
      loadHistory(true);
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