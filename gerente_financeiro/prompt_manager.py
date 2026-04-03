import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

@dataclass(frozen=True)
class PromptConfig:
    """Configurações para a construção de um prompt dinâmico."""
    user_name: str
    user_query: str
    financial_context: Dict[str, Any]
    conversation_history: str = ""
    perfil_ia: Optional[str] = None
    behavioral_analysis_json: Optional[Dict[str, Any]] = None # Adicionado para PROMPT_CONTEXTO_CONVERSA
    # Adicionamos uma "intenção" pré-processada (ex: "function_call", "general_analysis", "insight", "conversation", "monthly_report")
    intent: str = "general_analysis" 
    # Lista de skills relevantes para a intenção "general_analysis"
    relevant_skills: Optional[List[str]] = None
    # Parâmetros específicos para relatórios mensais
    mes_nome: Optional[str] = None
    ano: Optional[int] = None
    receita_total: Optional[float] = None
    despesa_total: Optional[float] = None
    saldo_mes: Optional[float] = None
    taxa_poupanca: Optional[float] = None
    gastos_agrupados: Optional[str] = None


class PromptManager:
    """
    Gerencia e constrói prompts dinamicamente a partir de templates modulares.
    """
    def __init__(self, template_dir: Path):
        if not template_dir.is_dir():
            raise FileNotFoundError(f"O diretório de templates não existe: {template_dir}")
        
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def _load_template_content(self, template_path_str: str, **kwargs) -> str:
        """Carrega e renderiza o conteúdo de um template específico."""
        try:
            template = self.env.get_template(template_path_str)
            return template.render(**kwargs)
        except TemplateNotFound:
            raise ValueError(f"Template não encontrado: {template_path_str}. Verifique o caminho e o nome do arquivo.")
        except Exception as e:
            raise RuntimeError(f"Erro ao renderizar template {template_path_str}: {e}")

    def build_prompt(self, config: PromptConfig) -> str:
        """
        Constrói o prompt final com base na configuração e intenção.
        """
        # Lógica de Roteamento baseada na Intenção
        if config.intent == "function_call":
            persona = self._load_template_content("system/persona_gerente_vdm.md", user_name=config.user_name, pergunta_usuario=config.user_query, perfil_ia=config.perfil_ia)
            function_rules = self._load_template_content("rules/function_calling.md")
            
            return self._load_template_content(
                "skills/function_call_query.j2",
                persona=persona,
                function_rules=function_rules,
                user_name=config.user_name,
                user_query=config.user_query
            )
        
        elif config.intent == "insight":
            # Para PROMPT_INSIGHT_FINAL
            return self._load_template_content(
                "templates/insight_final.j2",
                user_name=config.user_name,
                user_query=config.user_query
            )

        elif config.intent == "conversation":
            # Para PROMPT_CONTEXTO_CONVERSA
            # Garante que financial_context seja um JSON válido, mesmo que vazio
            financial_context_str = json.dumps(config.financial_context, indent=2) if config.financial_context else "{}"
            behavioral_analysis_str = json.dumps(config.behavioral_analysis_json, indent=2) if config.behavioral_analysis_json else "{}"

            return self._load_template_content(
                "templates/conversation_context.j2",
                user_name=config.user_name,
                conversation_history=config.conversation_history,
                user_query=config.user_query,
                financial_context=config.financial_context, # Passa o dict para o Jinja
                behavioral_analysis_json=config.behavioral_analysis_json # Passa o dict para o Jinja
            )
        
        elif config.intent == "monthly_report":
            # Para PROMPT_ANALISE_RELATORIO_MENSAL
            # Verifica se todos os dados necessários estão presentes
            required_fields = ["mes_nome", "ano", "receita_total", "despesa_total", "saldo_mes", "taxa_poupanca", "gastos_agrupados"]
            for field in required_fields:
                if getattr(config, field) is None:
                    raise ValueError(f"Campo '{field}' é obrigatório para a intenção 'monthly_report'.")

            return self._load_template_content(
                "templates/monthly_report_analysis.j2",
                user_name=config.user_name,
                mes_nome=config.mes_nome,
                ano=config.ano,
                receita_total=config.receita_total,
                despesa_total=config.despesa_total,
                saldo_mes=config.saldo_mes,
                taxa_poupanca=config.taxa_poupanca,
                gastos_agrupados=config.gastos_agrupados
            )

        elif config.intent == "general_analysis":
            # Para análises gerais, montamos um prompt mais completo
            persona = self._load_template_content("system/persona_gerente_vdm.md", user_name=config.user_name, pergunta_usuario=config.user_query, perfil_ia=config.perfil_ia)
            formatting_rules = self._load_template_content("rules/formatting_html.md")

            skills_content = ""
            if config.relevant_skills:
                for skill_name in config.relevant_skills:
                    skills_content += self._load_template_content(f"skills/{skill_name}.md") + '''\n\n'''
            
            # Remove o último \n\n se houver skills
            if skills_content:
                skills_content = skills_content.strip()

            return self._load_template_content(
                "main_analysis.j2",
                persona=persona,
                formatting_rules=formatting_rules,
                skills=skills_content,
                user_name=config.user_name,
                user_query=config.user_query,
                financial_context=config.financial_context,
                conversation_history=config.conversation_history
            )
        else:
            raise ValueError(f"Intenção '{config.intent}' não reconhecida pelo PromptManager.")

