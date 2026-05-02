# Guia de Deploy: Alfredo Ops MCP

Siga estes passos exatamente na ordem dentro do terminal do seu servidor Ubuntu (`pvserver@192.168.1.23`).

---

### Passo 1: Criar o Código do Servidor
Copie e cole este bloco inteiro no terminal:

```bash
cat <<'EOF' > ~/alfredo-ops/mcp_server.py
from mcp.server.fastmcp import FastMCP
import subprocess
import os
import uvicorn

# Inicializa o FastMCP
mcp = FastMCP("Alfredo Ops")

def run_command(command):
    """Executa um comando no shell e retorna a saída."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        return f"Erro: {str(e)}"

@mcp.tool()
def health():
    """Verifica se o MCP está online."""
    return "✅ Alfredo Ops MCP is Online and Connected!"

@mcp.tool()
def get_hardware_health():
    """Retorna o status de saúde do hardware (CPU, RAM, Disco)."""
    cpu = run_command("top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4\"%\"}'")
    ram = run_command("free -h | grep Mem | awk '{print $3\"/\"$2}'")
    disk = run_command("df -h / | grep / | awk '{print $3\"/\"$2\" (\"$5\")\"}'")
    return f"🧠 CPU: {cpu} | 📟 RAM: {ram} | 💽 Disco: {disk}"

@mcp.tool()
def systemctl_restart(service_name: str):
    """Reinicia um serviço do sistema (requer sudoers)."""
    return run_command(f"sudo systemctl restart {service_name}")

@mcp.tool()
def get_service_logs(service_name: str, lines: int = 50):
    """Recupera os últimos logs de um serviço específico."""
    return run_command(f"sudo journalctl -u {service_name} -n {lines} --no-pager")

if __name__ == "__main__":
    from starlette.applications import Starlette
    print("🚀 Iniciando Alfredo Ops MCP na porta 10001 via Uvicorn...")
    
    # Busca a aplicação Starlette de forma robusta
    try:
        app = mcp.get_sse_app()
    except:
        try:
            from mcp.server.fastmcp.sse import SSEApp
            app = SSEApp(mcp).starlette_app
        except:
            app = getattr(mcp, "_app", mcp)
    
    uvicorn.run(app, host="0.0.0.0", port=10001)
EOF
```

---

### Passo 2: Configurar o Sudoers (Sem erros de sintaxe)
Copie e cole este bloco:

```bash
sudo bash -c "cat <<'EOF' > /etc/sudoers.d/mcp_nopasswd
# Permissoes Sudoers para o usuario pvserver
pvserver ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart contacomigo
pvserver ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart AdGuardHome
pvserver ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart alfredo-mcp
pvserver ALL=(ALL) NOPASSWD: /usr/bin/journalctl -u *
EOF"
sudo chmod 440 /etc/sudoers.d/mcp_nopasswd
```

---

### Passo 3: Criar o Serviço Systemd
Copie e cole este bloco:

```bash
sudo bash -c "cat <<'EOF' > /etc/systemd/system/alfredo-mcp.service
[Unit]
Description=Alfredo MCP Server - Ops Interface
After=network.target

[Service]
User=pvserver
WorkingDirectory=/home/pvserver/alfredo-ops
ExecStart=/home/pvserver/alfredo-ops/venv/bin/python /home/pvserver/alfredo-ops/mcp_server.py
Restart=always
RestartSec=5
Environment=MCP_AUTH_TOKEN=AlfredoOps_Seguro_2026_!
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF"
```

---

### Passo 4: Instalar Dependências e Iniciar
Execute estes comandos finais:

```bash
# 1. Instalar bibliotecas no venv isolado
~/alfredo-ops/venv/bin/pip install "mcp[sse]" starlette uvicorn

# 2. Recarregar e Iniciar o serviço
sudo systemctl daemon-reload
sudo systemctl restart alfredo-mcp

# 3. VERIFICAR SE A PORTA ABRIU
sudo ss -tulpn | grep 10001
```

---
**Se o último comando mostrar o Python na porta 10001, o deploy foi um sucesso!**



ssh pvserver@192.168.1.23 "
      # Remove caracteres do Windows (\r) de todos os arquivos enviados
      sed -i 's/\r$//' ~/alfredo-ops/mcp_server.py
      sed -i 's/\r$//' ~/alfredo-ops/alfredo-mcp.service
      sed -i 's/\r$//' ~/alfredo-ops/mcp_nopasswd
   
      # Copia para as pastas do sistema com as permissões certas
      sudo cp ~/alfredo-ops/mcp_nopasswd /etc/sudoers.d/
      sudo chmod 440 /etc/sudoers.d/mcp_nopasswd
      sudo cp ~/alfredo-ops/alfredo-mcp.service /etc/systemd/system/
   
      # Recarrega e reinicia
      sudo systemctl daemon-reload
      sudo systemctl restart alfredo-mcp
      
      # Mostra se a porta abriu
      sudo ss -tulpn | grep 10001
    "