const playwright = require('@playwright/test');

(async () => {
  const browser = await playwright.chromium.launch({
    executablePath: '/usr/bin/chromium-browser',
    headless: true
  });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true
  });
  const page = await context.newPage();
  
  try {
    console.log('Navegando para a URL...');
    // Aumentar o timeout para o despertar do Render
    await page.goto('https://contacomigo-gt71.onrender.com/webapp', { waitUntil: 'networkidle', timeout: 60000 });
    
    console.log('Aguardando app-content...');
    // Esperar um seletor específico que indique que o app carregou (ex: #homeBalance ou .nav-btn)
    await page.waitForSelector('#app-content', { timeout: 30000 });
    await page.waitForTimeout(5000); // Mais 5s para garantir renderização de JS pesado
    
    console.log('Capturando Home...');
    await page.screenshot({ path: 'screenshot_home.png' });
    
    // Aba Agenda
    console.log('Indo para Agenda...');
    const agendaBtn = page.locator('.nav-btn[data-tab="agendamentos"]');
    await agendaBtn.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'screenshot_agenda.png' });

    // Aba Histórico
    console.log('Indo para Histórico...');
    const historyBtn = page.locator('.nav-btn[data-tab="historico"]');
    await historyBtn.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'screenshot_historico.png' });

    // Aba Modo Deus
    console.log('Indo para Modo Deus...');
    const godBtn = page.locator('.nav-btn[data-tab="modo-deus"]');
    await godBtn.click();
    await page.waitForTimeout(5000); // Dados do Modo Deus demoram mais
    await page.screenshot({ path: 'screenshot_mododeus.png' });

    console.log('Processo concluído.');
  } catch (err) {
    console.error('Erro durante o processo:', err);
  } finally {
    await browser.close();
  }
})();
