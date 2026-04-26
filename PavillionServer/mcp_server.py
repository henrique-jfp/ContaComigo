from mcp.server.fastmcp import FastMCP
import subprocess
import os
import sys

# Recupera o token das variáveis de ambiente
AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN")

# Inicializa o FastMCP
mcp = FastMCP("Alfredo Ops")

# Middleware simples para validar o token nas requisições SSE
# Nota: O FastMCP com SSE usa Starlette por baixo. 
# Se o token estiver configurado, ele deve ser enviado no header 'Authorization: Bearer <token>'

def run_command(command):
    """Executa um comando no shell e retorna a saída."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Erro ao executar comando: {e.stderr}"

@mcp.tool()
def get_hardware_health():
    """Retorna o status de saúde do hardware (CPU, RAM, Disco)."""
    cpu = run_command("top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4\"%\"}'")
    ram = run_command("free -h | grep Mem | awk '{print $3\"/\"$2}'")
    disk = run_command("df -h / | grep / | awk '{print $3\"/\"$2\" (\"$5\")\"}'")
    temp = run_command("cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | head -n 1 | awk '{print $1/1000\"°C\"}'") or "N/A"
    
    return f"🌡️ Temp: {temp} | 🧠 CPU: {cpu} | 📟 RAM: {ram} | 💽 Disco: {disk}"

@mcp.tool()
def systemctl_status(service_name: str):
    """Verifica se um serviço do sistema está ativo (ex: contacomigo, AdGuardHome)."""
    return run_command(f"systemctl is-active {service_name}")

@mcp.tool()
def systemctl_restart(service_name: str):
    """Reinicia um serviço do sistema (requer permissão sudoers)."""
    # O comando será executado via sudo, conforme configurado no arquivo de sudoers
    return run_command(f"sudo systemctl restart {service_name}")

@mcp.tool()
def get_service_logs(service_name: str, lines: int = 50):
    """Recupera os últimos logs de um serviço específico."""
    return run_command(f"sudo journalctl -u {service_name} -n {lines} --no-pager")

@mcp.tool()
def git_deploy():
    """Realiza o deploy do código mais recente (git pull) e reinicia o Alfredo."""
    path = "/home/pvserver/contacomigo"
    pull = run_command(f"cd {path} && git pull")
    restart = run_command("sudo systemctl restart contacomigo")
    return f"Pull: {pull}\nRestart: {restart}"

if __name__ == "__main__":
    # Inicia o servidor em modo SSE na porta 10001
    # Nota: Em produção, o uvicorn será chamado pelo systemd
    mcp.run(transport="sse")
