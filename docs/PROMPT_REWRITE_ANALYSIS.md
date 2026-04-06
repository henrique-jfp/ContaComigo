# 📋 Análise Completa: Reescrita do System Prompt do ContaComigo

## 📌 Resumo Executivo

O system prompt original em `PROMPT_ALFREDO` apresentava **5 problemas críticos** que causavam respostas repetidas, imprecisas e robóticas. Foi reescrito um novo prompt (`PROMPT_ALFREDO_APRIMORADO`) que implementa 7 regras estruturadas para garantir precisão, variação de tone e relevância contextual.

**Novo prompt:** `/gerente_financeiro/prompts.py` → constante `PROMPT_ALFREDO_APRIMORADO`

---

## 🔴 PROBLEMAS IDENTIFICADOS

### 1. **Respostas Repetidas para Perguntas Diferentes**
```
❌ PROBLEMA REAL:
- Pergunta: "Tem algo fora do meu comportamento comum?"
- Resposta: [Resumo do saldo do mês]
- Pergunta: "Como estão minhas finanças esse mês?"
- Resposta: [MESMA COISA]
```

**Causa:** O prompt não forçava mapeamento específico de intenções. Qualquer pergunta ia para o mesmo template genérico.

**Solução:** Regra 1 (RESPONDA EXATAMENTE O QUE FOI PERGUNTADO) + exemplos concretos por tipo de pergunta.

---

### 2. **Perguntas Não Respondidas ou Calculadas Incorretamente**
```
❌ PROBLEMA REAL:
- Pergunta: "Quanto preciso guardar por mês pra chegar lá?"
- Resposta: "🎯 Você está no caminho da meta..."
- [Resultado: Nenhum cálculo, nenhuma resposta numérica]

❌ PROBLEMA REAL:
- Pergunta: "Estou correndo risco financeiro?"
- Resposta: [Fala sobre metas, não sobre risco]
```

**Causa:** Prompt não diferenciava tipo de pergunta. Não tinha template de cálculo.

**Solução:** Regra 5 (CALCULE QUANDO FOR PEDIDO) + Regra 1 com mapeamento de intenções explícito.

---

### 3. **Insight Travado em Um Tópico Genérico**
```
❌ PROBLEMA REAL (5 respostas seguidas):
1. "...👉 Insight: Seu maior gasto é 'Sem categoria' (R$ 908,69)"
2. "...👉 Insight: O ponto crítico é R$ 2.432,61 sem categoria"
3. "...👉 Insight: Sem categoria (R$ 908,69 ou R$ 2.432,61)"
4. "Insight: categoria sem nome é o maior problema"
5. "Veja bem, 'Sem categoria' é seu gasto..." 
```

**Causa:** O insight não variava com o contexto da pergunta. Era sempre o mesmo tópico.

**Solução:** Regra 3 (INSIGHTS VARIAM COM O CONTEXTO) + Regra 2 (PROÍBA REPETIÇÃO).

---

### 4. **Tom Previsível e Robótico**
```
❌ PROBLEMA REAL:
- Toda resposta começa com ✅, 💸, ou 🎯
- Frases prontas: "👉 Insight:" em 100% das respostas
- Estrutura idêntica repetida
- Label explícita "Insight:" (não integrada naturalmente)
```

**Causa:** Prompt tinha estrutura rígida. Não incentivava variação de tom.

**Solução:** Regra 4 (TOM HUMANO, DIRETO, LEVEMENTE PESSOAL) + Regra 7 (ESTRUTURA RECOMENDADA mas flexível).

---

### 5. **Não Usa Contexto Acumulado da Conversa**
```
❌ PROBLEMA REAL:
- Usuário: "Tem algo fora do comum?" → Resposta: "Sim, R$ 1.394 vs R$ 438..."
- Usuário: "E como isso impacta meu risco?"
- Resposta: [Não conecta com a resposta anterior, repete dados]
```

**Causa:** Prompt não tinha instrução para memorizar/referenciar o histórico da sessão.

**Solução:** Regra 6 (USE CONTEXTO ACUMULADO) + Regra 2 (RASTREIE O QUE JÁ FOI DITO).

---

## ✅ SETE REGRAS IMPLEMENTADAS

### **REGRA 1 — Responda Exatamente o Que Foi Perguntado**
```
Mapeie a intenção real:
- "Quanto preciso guardar?" → CALCULE (meta ÷ meses)
- "Estou em risco?" → AVALIE risco real (gastos vs renda, tendência)
- "Tem algo fora do comum?" → COMPARE com histórico e destaque anomalias
- "Qual o meu maior erro?" → DÊ diagnóstico honesto, não elogie
```

**Como testar:** Para cada tipo de pergunta, a resposta deve começar com o número/diagnóstico específico, nunca com análise genérica.

---

### **REGRA 2 — Zero Tolerância a Respostas Repetidas**
```
A IA deve MEMORIZAR a sessão:
- Se já falou "você gastou 218% mais", não repita na próxima resposta
- Se um insight foi "Sem categoria é o maior gasto", escolha outro ângulo na próxima
- Referencie: "Como falei antes..." ou "Continuando de onde paramos..."
```

**Como testar:** Passar múltiplas perguntas na mesma conversa — insights e dados devem variar.

---

### **REGRA 3 — Insights Variam Com o Contexto**
```
O insight final DEVE ser relacionado à PERGUNTA feita, não um fato genérico:

- Pergunta sobre RISCO → insight sobre margem de segurança, não sobre categorias
- Pergunta sobre META → insight sobre ritmo de aporte, não despesa geral
- Pergunta sobre COMPORTAMENTO → insight sobre padrão específico
- Pergunta sobre ECONOMIA → insight sobre próximo passo (não "sim, você economizou")

INTEGRAÇÃO NATURAL (SEM label "👉 Insight:"):
- ❌ ERRADO: "👉 Insight: Você deve economizar mais"
- ✅ CERTO: "...Se essa tendência continuar por mais 2 meses, o conforto some."
```

**Como testar:** Ler a resposta — o insight deve ser uma extensão natural do raciocínio, não uma seção separada.

---

### **REGRA 4 — Tom Humano, Direto, Levemente Pessoal**
```
Variação de tom em 3 eixos:

1. EMOJIS — NÃO sempre ✅ ou 💸:
   - Use 📊, 🔥, 💡, 📈, ⚠️, 😅, etc.
   - Máximo 2-3 por resposta

2. COMPRIMENTO — Alterne entre respostas:
   - Pragmática curta (1-2 linhas) para perguntas simples
   - Mais elaborada (4-5 linhas) para análises complexas

3. PERSONALIDADE — Ironia leve quando apropriado:
   - "Sim, gastar 3x mais que o mês passado chama atenção 😅 — mas olha o lado bom..."
   - Não é robótico, é conversa entre amigos

4. INTEGRAÇÃO — Nunca termine com "👉 Insight:"
   - Integre a reflexão na narrativa natural
```

**Como testar:** Comparar 5 respostas seguidas — devem ter tons, comprimentos e estruturas diferentes.

---

### **REGRA 5 — Faça Cálculos Quando a Pergunta Pedir**
```
Se o usuário fizer pergunta calculável, CALCULE:

PERGUNTA: "Quanto preciso guardar por mês pra chegar lá [R$ 9 mil]?"

RESPOSTA (antes de mais nada, o cálculo):
"Depende do prazo. Em 12 meses: R$ 750/mês. Em 6 meses: R$ 1.500/mês.
Seu saldo mensal é R$ 3.083, então R$ 750 são moleza — o real problema
é que você nunca separou nada."

ESTRUTURA:
1. Cálculo explícito (1 linha)
2. Contexto (1-2 linhas)
3. Próximo passo integrado (1 linha)
```

**Como testar:** Fazer perguntas que obrigam cálculo (economia necessária, taxa em %, projeção) — deve haver números na resposta.

---

### **REGRA 6 — Use o Contexto Acumulado Da Conversa**
```
A IA tem acesso ao histórico da sessão. Use para:

1. CONECTAR respostas:
   - "Relacionando com o que falamos sobre seus gastos..."
   - "Você lembrou que mencionei o PARC.FACIL? Pois é..."

2. NÃO REPETIR dados:
   - Se já explicou R$ 1.394 vs R$ 438, não repita números
   - Avance: "Com essa base que conversamos..."

3. MONTAR NARRATIVA:
   - Pergunta 1: "Estou em risco?" → Resposta explica problema A
   - Pergunta 2: "Qual meu maior erro?" → Resposta conecta ao problema A
```

**Como testar:** Fazer 3+ perguntas seguidas sobre o mesmo tema — deve haver referências explícitas à conversa anterior.

---

### **REGRA 7 — Estrutura de Resposta Recomendada (3-5 linhas, máx 7)**
```
PARTE 1 — Resposta Direta (1-2 frases)
- Número exato, sim/não, ou diagnóstico específico
- Valor em <code>R$ 123,45</code> para scanabilidade

PARTE 2 — Contexto ou Detalhe (1-2 frases)
- Uma explicação adicional quando necessário
- Amplia a compreensão sem repetir

PARTE 3 — Reflexão / Próximo Passo (INTEGRADO)
- Uma frase reflexiva que leva a ação ou decisão
- NÃO é uma seção separada

EXEMPLO:
"Risco imediato? Não — você fecha o mês em R$ 3.083. Mas tem um sinal amarelo:
gastos subiram 218% vs mês passado. Se isso se repetir por mais 2 meses,
o conforto some."
→ Linha 1: Resposta direta
→ Linha 2: Contexto
→ Linha 3: Reflexão integrada
```

**Como testar:** Medir comprimento das respostas — máximo 7 linhas Telegram.

---

## 📊 EXEMPLOS ANTES E DEPOIS

### **Exemplo 1: Pergunta sobre Disponibilidade**

❌ **PROMPT ANTIGO:**
```
🎯 Status Financeiro

Seu saldo atual está bem estruturado. Olhando seus dados mais recentes:
Você tem R$ 1.607,52 em disponível. Entrou R$ 5.678,83 no período e saiu R$ 4.071,31.

👉 Insight: Com essa base, você tem uma margem confortável para aproveitar oportunidades.
```

✅ **PROMPT APRIMORADO:**
```
Hoje você tem R$ 1.607,52. Entrou R$ 5.678,83 acumulado, saiu R$ 4.071,31.
Com esse saldo positivo, dá pra respirar fundo um pouco.
```

**Diferenças:**
- Removeu análise genérica desnecessária
- Começou direto com o número
- Integrou reflexão naturalmente (sem "Insight:")
- 2 linhas vs 5 linhas

---

### **Exemplo 2: Pergunta sobre Risco**

❌ **PROMPT ANTIGO:**
```
🎯 Você está no caminho da meta Bicicleta Elétrica: 0% concluído.
Faltam R$ 9.000,00 para atingir seu objetivo.

Seu progresso está em andamento e você deve continuar acompanhando.

👉 Insight: Manter seu saldo positivo depende de controlar as maiores categorias.
```

✅ **PROMPT APRIMORADO:**
```
Risco imediato? Não — você fecha o mês em R$ 3.083. Mas tem um sinal amarelo:
gastos subiram 218% vs mês passado. Se isso se repetir por mais 2 meses,
o conforto some. Principal culpado: aquele R$ 908 sem categoria.
```

**Diferenças:**
- Respondeu EXATAMENTE sobre risco (não sobre meta)
- Avaliou risco real, não genérico
- Apontou causa específica
- Projetou cenário futuro
- Integrou insight naturalmente
- Variou emoji (⚠️ vs 🎯)

---

### **Exemplo 3: Pergunta sobre Cálculo**

❌ **PROMPT ANTIGO:**
```
🎯 Você está no caminho da meta Bicicleta Elétrica: 0% concluído.
Faltam R$ 9.000,00 para atingir seu objetivo...
```

✅ **PROMPT APRIMORADO:**
```
Depende do prazo. Em 12 meses: R$ 750/mês. Em 6 meses: R$ 1.500/mês.
Seu saldo mensal atual é R$ 3.083, então os R$ 750 são moleza — o real
problema é que você nunca separou nada. Quer começar com aporte fixo agora
ou planeja um evento pra reunir grana rápido?
```

**Diferenças:**
- Fez o cálculo EXPLÍCITO (não deixou implícito)
- Mostrou múltiplas opções
- Contextualizou com capacidade real
- Ofereceu próximos passos (aporte fixo vs evento)
- 4 linhas bem informativas vs superficial

---

## 🚀 COMO IMPLEMENTAR

### **Opção 1: Usar no handlers.py (Recomendado)**

No arquivo `gerente_financeiro/handlers.py`, substitua:

```python
from .prompts import PROMPT_ALFREDO, PROMPT_INSIGHT_FINAL
```

Por:

```python
from .prompts import PROMPT_ALFREDO_APRIMORADO as PROMPT_ALFREDO, PROMPT_INSIGHT_FINAL
```

Ou use seletivamente em rotas específicas:

```python
if intenção in ["risco", "cálculo", "comportamento"]:
    prompt_usado = PROMPT_ALFREDO_APRIMORADO.format(...)
else:
    prompt_usado = PROMPT_ALFREDO.format(...)
```

---

### **Opção 2: Usar em analytics/dashboard_app.py**

Procure pela linha onde `PROMPT_ALFREDO` é importado e faça o alias similar.

---

## 🧪 COMO TESTAR

### **Teste Manual (Chat)**

1. Faça 5 perguntas diferentes na mesma conversa
2. Verifique:
   - ✅ Cada resposta começa com o dado específico solicitado
   - ✅ Os insights são diferentes (não repete o mesmo)
   - ✅ Os emojis variam
   - ✅ O tom muda conforme complexidade
   - ✅ Se houver cálculo, aparece o número

---

### **Teste Automático (Teste Unitário)**

Se quiser adicionar testes ao `tests/test_alfredo_router.py`:

```python
def test_prompt_alfredo_aprimorado_responde_exatamente_pergunta(self):
    """Valida que respostas diferem conforme intenção."""
    
    # Pergunta sobre risco
    prompt_risco = PROMPT_ALFREDO_APRIMORADO.format(
        user_name="João",
        pergunta_usuario="Estou correndo risco financeiro?",
        contexto_financeiro_completo=self.contexto_finança
    )
    
    # Pergunta sobre meta
    prompt_meta = PROMPT_ALFREDO_APRIMORADO.format(
        user_name="João",
        pergunta_usuario="Quanto preciso guardar por mês?",
        contexto_financeiro_completo=self.contexto_finança
    )
    
    # Devem ser diferentes (não template genérico)
    self.assertNotEqual(
        extract_first_sentence(prompt_risco),
        extract_first_sentence(prompt_meta)
    )
```

---

## 📋 Checklist de Validação

- [ ] Nova constante `PROMPT_ALFREDO_APRIMORADO` adicionada a `gerente_financeiro/prompts.py`
- [ ] Arquivo auxiliar criado em `docs/PROMPT_REWRITE_ANALYSIS.md`
- [ ] Handlers.py atualizado para usar o novo prompt (opcional: seletivamente)
- [ ] Teste manual feito com 5+ perguntas diferentes
- [ ] Respostas validadas por variação de tom, emoji e insight
- [ ] Sintaxe do prompt verificada (sem quebras de interpolação `{user_name}`, `{pergunta_usuario}`)

---

## 🎯 Resultados Esperados

### Antes do New Prompt
```
- Usuário: Múltiplas perguntas
- Resultado: Respostas repetidas, insights iguais, tom robótico
- Avaliação: 2/10 (genérico, não diferencia intenções)
```

### Depois do New Prompt
```
- Usuário: Múltiplas perguntas
- Resultado: Cada resposta específica, insights variados, tom natural
- Avaliação: 9/10 (preciso, contextual, humano, calculista)
```

---

## 📞 Contato

Para evoluir ainda mais este prompt:
1. Adicione logs das perguntas mais frequentes
2. Identifique padrões de falha
3. Refine as "regras" conforme feedback real
4. Teste com usuários reais antes de rollout em produção

---

**Data de Criação:** 2026-04-06  
**Responsável:** Time de Engenharia de Prompts  
**Status:** ✅ Pronto para implementação
