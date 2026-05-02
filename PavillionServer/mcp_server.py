from mcp.server.fastmcp import FastMCP
import subprocess
import os
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount

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
    temp = run_command("cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | head -n 1 | awk '{print $1/1000\"°C\"}'") or "N/A"
    return f"🌡️ Temp: {temp} | 🧠 CPU: {cpu} | 📟 RAM: {ram} | 💽 Disco: {disk}"

@mcp.tool()
def systemctl_status(service_name: str):
    """Verifica se um serviço do sistema está ativo."""
    return run_command(f"systemctl is-active {service_name}")

@mcp.tool()
def systemctl_restart(service_name: str):
    """Reinicia um serviço do sistema."""
    return run_command(f"sudo systemctl restart {service_name}")

@mcp.tool()
def get_service_logs(service_name: str, lines: int = 50):
    """Recupera os últimos logs de um serviço específico."""
    return run_command(f"sudo journalctl -u {service_name} -n {lines} --no-pager")

@mcp.tool()
def git_deploy():
    """Realiza git pull e reinicia o bot Alfredo."""
    path = "/home/pvserver/contacomigo"
    pull = run_command(f"cd {path} && git pull")
    restart = run_command("sudo systemctl restart contacomigo")
    return f"Pull: {pull}\nRestart: {restart}"

if __name__ == "__main__":
    print("🚀 Iniciando Alfredo Ops MCP na porta 10001...")
    
    # 1. Obtém a aplicação Starlette interna do FastMCP
    try:
        from mcp.server.fastmcp.sse import SSEApp
        mcp_app = SSEApp(mcp).starlette_app
    except:
        # Fallback para diferentes versões do SDK
        mcp_app = getattr(mcp, "get_sse_app", lambda: getattr(mcp, "_app", mcp))()

    # 2. Cria o roteamento explícito para /sse para bater com o Gemini CLI
    app = Starlette(
        routes=[
            Mount("/sse", app=mcp_app),
            Mount("/", app=mcp_app)
        ]
    )

    uvicorn.run(app, host="0.0.0.0", port=10001)
