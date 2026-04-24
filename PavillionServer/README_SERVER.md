# 🧠 Servidor ContaComigo (Alfredo) - HP Pavilion X360

Este documento descreve a configuração, operação e manutenção do servidor local que hospeda o ecossistema ContaComigo.

## 🚀 Hardware "pvserver
*   **Modelo:** HP Pavilion X360 11-N226BR
*   **CPU:** Intel Celeron N2830 (Dual Core)
*   **RAM:** 4GB DDR3L (Otimizada com 4GB Swap + ZRAM)
*   **Armazenamento:** SSD 120GB
*   **SO:** Ubuntu Server 24.04 LTS (Headless/Minimized)

## 🏗️ Arquitetura de Deploy
O sistema roda de forma híbrida para máxima performance no hardware limitado:
1.  **Core:** Python 3.12+ em Ambiente Virtual (`venv`).
2.  **Bibliotecas Pesadas:** Instaladas via `apt` no sistema (Pandas, Numpy, OpenCV, Psycopg2) e compartilhadas com o venv via `--system-site-packages`.
3.  **Persistência:** O sistema é gerenciado pelo `systemd`, garantindo auto-restart.
4.  **Acesso Externo:** Cloudflare Tunnel expondo a porta `10000` para o domínio `alfredo.henriquedejesus.dev`.

---

## 🛠️ Comandos de Gestão (O Painel de Controle)

### 1. Monitorar o Alfredo (Logs em tempo real)
Use este comando para ver o que o bot está processando (mensagens, OCR, erros):
```bash
sudo journalctl -u contacomigo -f
```

### 2. Status dos Serviços
Verifique se o sistema e o túnel de internet estão vivos:
```bash
sudo systemctl status contacomigo   # O Cérebro (Python/Flask)
sudo systemctl status cloudflared  # O Túnel (Internet/HTTPS)
```

### 3. Reiniciar o Sistema
Se você alterou o código ou o arquivo `.env`:
```bash
sudo systemctl restart contacomigo
```

### 4. Ver Saúde do Hardware
Para monitorar temperatura e uso de memória:
```bash
btop
```

---

## 🌐 Configuração de Rede & Portas
*   **Porta Local:** `10000` (Padrão herdado do Render).
*   **Túnel Cloudflare:** Encaminha tráfego de `https://alfredo.henriquedejesus.dev` -> `http://localhost:10000`.
*   **Configuração do Túnel:** Localizada em `/etc/cloudflared/config.yml`.

---

## ⚠️ Manutenção e Cuidados 24h

1.  **Tampa do Notebook:** O servidor está configurado para **NÃO DORMIR** ao fechar a tampa. Pode deixá-lo fechado no canto para economizar espaço.
2.  **Energia:** O notebook deve ficar permanentemente na tomada. Em caso de queda de luz, a bateria interna segura o sistema por algumas horas (Nobreak natural).
3.  **Atualização de Código:**
    ```bash
    cd ~/contacomigo
    git pull
    sudo systemctl restart contacomigo
    ```
4.  **Limpeza de Logs:** O Ubuntu gerencia isso sozinho, mas se o SSD encher, use `sudo journalctl --vacuum-time=7d`.

---

## 📁 Estrutura de Pastas Críticas
*   `~/contacomigo`: Pasta raiz do projeto.
*   `~/contacomigo/venv`: Ambiente virtual Python.
*   `/etc/systemd/system/contacomigo.service`: Script de inicialização automática.
*   `/etc/cloudflared/`: Credenciais e configuração do túnel HTTPS.

---
**Status do Servidor:** 🟢 Operacional
**Mantenedor:** pvserver
**Última Atualização:** Abril/2026
