    // Função para renderizar o Sankey Premium via SVG (DESIGN FIEL À IMAGEM)
    function renderSankeyPremium(container, data) {
      if (!container || !data.length) return;
      const width = 800; const height = 450;
      const grena = "#7b1e2d"; const verde = "#10b981"; const ouro = "#D4AF37";
      const palette = ["#fbbf24", "#818cf8", "#f472b6", "#34d399", "#a78bfa"];

      const receitaTotal = data.filter(d => d.from === 'Receitas').reduce((a, b) => a + b.flow, 0);
      const despesasNodes = data.filter(d => d.from === 'Despesas');

      let svgHtml = `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" style="width:100%; height:auto; overflow:visible;">
        <defs>
          <linearGradient id="grad-main" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="${verde}" stop-opacity="0.2"/>
            <stop offset="100%" stop-color="${grena}" stop-opacity="0.2"/>
          </linearGradient>
        </defs>

        <!-- Column Labels (Legíveis em Grená) -->
        <text x="80" y="45" text-anchor="middle" font-size="12" font-weight="900" fill="${grena}" style="text-transform:uppercase; letter-spacing:1px">Entrada</text>
        <text x="300" y="45" text-anchor="middle" font-size="12" font-weight="900" fill="${grena}" style="text-transform:uppercase; letter-spacing:1px">Gestão</text>
        <text x="610" y="45" text-anchor="middle" font-size="12" font-weight="900" fill="${grena}" style="text-transform:uppercase; letter-spacing:1px">Saídas</text>

        <!-- Main Flow -->
        <path d="M145,70 C220,70 220,70 240,70 L240,370 C220,370 220,370 145,370 Z" fill="url(#grad-main)" />
        
        <!-- Nodes -->
        <rect x="25" y="70" width="120" height="300" rx="12" fill="rgba(16, 185, 129, 0.05)" stroke="${verde}" stroke-width="2" />
        <text x="85" y="210" text-anchor="middle" font-size="13" font-weight="900" fill="${grena}">RECEITAS</text>
        <text x="85" y="235" text-anchor="middle" font-size="12" font-weight="bold" fill="${verde}">${formatCurrencyBR(receitaTotal)}</text>

        <rect x="240" y="70" width="120" height="300" rx="12" fill="rgba(123, 30, 45, 0.05)" stroke="${grena}" stroke-width="2" />
        <text x="300" y="210" text-anchor="middle" font-size="13" font-weight="900" fill="${grena}">CAIXA</text>
        <text x="300" y="235" text-anchor="middle" font-size="10" font-weight="bold" fill="${grena}">GESTÃO</text>

        ${despesasNodes.slice(0, 5).map((cat, i) => {
          const y = 70 + (i * 64); const h = 58; const color = palette[i % palette.length];
          return `
            <path d="M360,${y + 15} C460,${y + 15} 460,${y + 15} 510,${y + 15} L510,${y + h - 15} C460,${y + h - 15} 460,${y + h - 15} 360,${y + h - 15} Z" fill="${color}" fill-opacity="0.2" />
            <rect x="510" y="${y}" width="200" height="${h}" rx="12" fill="rgba(255,255,255,0.03)" stroke="${color}" stroke-opacity="0.4" stroke-width="2" />
            <rect x="510" y="${y}" width="4" height="${h}" rx="2" fill="${color}" />
            <text x="610" y="${y + 24}" text-anchor="middle" font-size="10" font-weight="900" fill="${grena}">${cat.to.toUpperCase()}</text>
            <text x="610" y="${y + 44}" text-anchor="middle" font-size="12" font-weight="bold" fill="${grena}">${formatCurrencyBR(cat.flow)}</text>
          `;
        }).join('')}
      </svg>`;
      container.innerHTML = svgHtml;
    }

    function buildChartDataFromSummary(summary) {
      const now = new Date();
      const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
      const startDay = firstDay.getDay();
      const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
      
      const activity = {};
      (summary?.recent || []).forEach(item => {
        const d = new Date(item.data);
        if (d.getMonth() === now.getMonth()) {
          const day = d.getDate();
          const val = Number(item.valor || 0);
          if (!activity[day]) activity[day] = { count: 0, hasIncome: false };
          activity[day].count++;
          if (val > 0) activity[day].hasIncome = true;
        }
      });

      const heatmapData = [];
      const daysShort = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];
      for (let w = 0; w < 6; w++) {
        daysShort.forEach((d, i) => {
          const dayNum = (w * 7) + i - startDay + 1;
          let val = 0; let label = ""; let type = 'empty';
          if (dayNum > 0 && dayNum <= daysInMonth) {
            label = dayNum.toString();
            const act = activity[dayNum];
            if (act) {
              val = act.count;
              type = act.hasIncome ? 'income' : 'expense';
            } else { type = 'day'; }
          }
          heatmapData.push({ x: d, y: `Sem ${w+1}`, v: val, date: label, type: type });
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

      const sixMonths = monthlyCashflow.map(i => i.label || '');
      const fluxoEntradas = monthlyCashflow.map(i => Number(i.entrada || 0));
      const fluxoSaidas = monthlyCashflow.map(i => Number(i.saida || 0));
      const fluxoSaldo = monthlyCashflow.map(i => Number(i.saldo || 0));
      const patrimonyMonths = patrimonySeries.map(i => i.label || '');
      const patrimonyValues = patrimonySeries.map(i => Number(i.value || 0));
      const budgetLabels = budgetItems.map(i => i.label || '');
      const budgetPlanned = budgetItems.map(i => Number(i.orcamento || 0));
      const budgetActual = budgetItems.map(i => Number(i.realizado || 0));
      const distroLabels = categories.map(i => i.label || '');
      const distroValues = categories.map(i => Number(i.value || 0));
      const projectionLabels = projectionSeries.map(i => i.label || '');
      const projectionHistory = projectionSeries.map(i => i.historico == null ? null : Number(i.historico));
      const projectionFuture = projectionSeries.map(i => i.futuro == null ? null : Number(i.futuro));
      const villains = topVillains.map(i => [i.label, Number(i.value)]);

      const sankeyData = [];
      if (receita > 0) sankeyData.push({ from: 'Receitas', to: 'Caixa', flow: receita });
      if (despesa > 0) {
        sankeyData.push({ from: 'Caixa', to: 'Despesas', flow: despesa });
        categories.forEach(c => { if(c.value > 0) sankeyData.push({ from: 'Despesas', to: c.label, flow: Number(c.value) }); });
      }

      return {
        sixMonths, patrimonyMonths, patrimonyValues, fluxoEntradas, fluxoSaidas, fluxoSaldo,
        budgetLabels, budgetPlanned, budgetActual, categories, distroLabels, distroValues,
        projectionLabels, projectionHistory, projectionFuture, villains, sankeyData, heatmapData
      };
    }

    function renderHomeOverview(summary) {
      if (!summary) return;
      destroyHomeCharts();
      const chartData = buildChartDataFromSummary(summary);

      const homeSankeyChartEl = document.getElementById('homeSankeyChart');
      if (homeSankeyChartEl) {
        renderSankeyPremium(homeSankeyChartEl.parentElement, chartData.sankeyData);
        homeSankeyChartEl.style.display = 'none';
      }

      const homeHeatmapChartEl = document.getElementById('homeHeatmapChart');
      if (homeHeatmapChartEl) {
        homeCharts.heatmap = safeChart(homeHeatmapChartEl, {
          type: 'matrix',
          data: {
            datasets: [{
              data: chartData.heatmapData,
              backgroundColor(ctx) {
                const item = ctx.dataset.data[ctx.dataIndex];
                if (!item || item.type === 'empty') return 'rgba(0,0,0,0)';
                if (item.type === 'income') return 'rgba(16, 185, 129, 0.7)';
                if (item.type === 'expense') return 'rgba(123, 30, 45, 0.7)';
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
                backgroundColor: '#2d0a10',
                callbacks: {
                  title: (ctx) => `Dia ${ctx[0].raw.date}`,
                  label: (ctx) => `${ctx.raw.v} lançamento(s)`
                }
              }
            },
            scales: {
              x: { type: 'category', labels: ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'], grid: { display: false } },
              y: { type: 'category', labels: ['Sem 1','Sem 2','Sem 3','Sem 4','Sem 5','Sem 6'], grid: { display: false }, offset: true, ticks: { display: false } }
            }
          },
          plugins: [{
            id: 'calendarLabels',
            afterDatasetsDraw(chart) {
              const {ctx, data} = chart;
              ctx.save();
              ctx.font = 'bold 10px monospace';
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = 'rgba(255,255,255,0.4)';
              data.datasets[0].data.forEach((item, i) => {
                if (item.date) {
                  const meta = chart.getDatasetMeta(0).data[i];
                  ctx.fillText(item.date, meta.x, meta.y);
                }
              });
              ctx.restore();
            }
          }]
        });
      }
    }
