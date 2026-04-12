#!/usr/bin/env zsh
set -euo pipefail

# Script conveniente para adicionar/commitar/push das alterações relacionadas ao relatório
# Uso:
#   ./scripts/git_commit_and_push_relatorio_fix.sh ["mensagem de commit"]
# Se nenhuma mensagem for passada, será usada uma padrão.

# Caminho relativo ao repositório (executa a partir da raiz do projeto)
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "Status atual do git (resumido):"
git status --porcelain
echo

COMMIT_MSG="${1:-chore(relatorio): melhorias no gerador PDF, template de inspiração e dependências}"

echo "Commit message: $COMMIT_MSG"

echo "Staging de arquivos modificados..."

# Lista explícita de arquivos que alteramos neste fluxo
files=(
  "templates/relatorio_inspiracao.html"
  "templates/relatorio_clean.html"
  "gerente_financeiro/relatorio_handler.py"
  "gerente_financeiro/pdf_generator.py"
  "gerente_financeiro/services.py"
  "scripts/generate_preview_pdf.py"
  "requirements.txt"
  "Dockerfile"
  "docs/WEASYPRINT_DEPLOY.md"
)

for f in "${files[@]}"; do
  if [ -e "$f" ]; then
    git add "$f"
    echo "  -> staged: $f"
  else
    echo "  -> not found (skipping): $f"
  fi
done

if git diff --staged --quiet; then
  echo "Nenhuma alteração staged. Nada para commitar. Saindo."
  exit 0
fi

git commit -m "$COMMIT_MSG"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Fazendo push para origin/$CURRENT_BRANCH..."
git push origin "$CURRENT_BRANCH"

echo "Push concluído com sucesso."
git --no-pager log -n 3 --oneline --decorate

echo "Pronto — por favor, reinicie/redeploy o serviço no Railway para aplicar as mudanças." 
