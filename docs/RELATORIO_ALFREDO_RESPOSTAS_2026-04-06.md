# Relatorio Alfredo - Respostas Obtidas

Data: 2026-04-06
Escopo: roteamento local/deterministico do Alfredo (fallback local)
Fonte: execucoes de teste e simulacao controlada em ambiente local

## Resumo Executivo

- Cobertura no stress test de 110 perguntas: 110/110 (100%).
- Perguntas sem intencao detectada: 0.
- Teste automatizado do roteador: `10 passed`.

## Distribuicao de Intencoes (stress test)

- alerta: 23
- analise: 18
- consultoria: 16
- contas: 14
- metas: 13
- previsao: 12
- saldo: 6
- comparacao: 5
- resumo_mes: 2
- resumo_semana: 1

## Respostas Obtidas (amostras reais)

Cenario da simulacao: entradas de R$ 5.000,00, saidas de R$ 2.001,40 e saldo de R$ 2.998,60.

### Caso 1
Pergunta: Quanto eu tenho hoje disponivel?

Resposta:
```text
💰 <b>Seu saldo atual</b>
━━━━━━━━━━━━━━━━━━

<b>Saldo:</b> <code>R$ 2.998,60</code>
<b>Entradas acumuladas:</b> <code>R$ 5.000,00</code>
<b>Saídas acumuladas:</b> <code>R$ 2.001,40</code>
```

### Caso 2
Pergunta: Tem alguma conta vencendo hoje?

Resposta:
```text
🧾 <b>Contas e compromissos</b>

<b>Vencem hoje:</b> nada encontrado no banco.

<b>Até o fim da semana:</b>
• Internet (R$ 120,00) em 08/04/2026
• Energia (R$ 210,00) em 11/04/2026
```

### Caso 3
Pergunta: Como esse mes se compara com o anterior?

Resposta:
```text
📊 <b>Comparação com o mês anterior</b>

• <b>Mês atual:</b> R$ 2.001,40
• <b>Mês anterior:</b> R$ 2.001,40
• <b>Variação:</b> ficou igual R$ 0,00 (+0.0%)
```

### Caso 4
Pergunta: Estou correndo risco financeiro?

Resposta:
```text
🚨 <b>Diagnóstico de risco</b>

• <b>Risco atual:</b> baixo
• <b>Saldo do mês:</b> R$ 2.998,60
• <b>Gastos do mês:</b> R$ 2.001,40
• <b>Entradas do mês:</b> R$ 5.000,00

<b>Principais fontes de gasto:</b>
• Moradia: R$ 1.800,00
• Alimentação: R$ 85,90
• Saúde: R$ 73,20
```

### Caso 5
Pergunta: Se eu continuar assim, como termino o mes?

Resposta:
```text
🔮 <b>Previsão do mês</b>

• <b>Saída média diária:</b> R$ 333,57
• <b>Saída projetada no mês:</b> R$ 10.007,00
• <b>Saldo projetado:</b> R$ -5.007,00
• <b>Limite diário seguro:</b> R$ 124,94

<b>Leitura rápida:</b> seguindo esse ritmo, o mês tende a fechar no vermelho.
```

### Caso 6
Pergunta: Onde eu mais estou gastando dinheiro?

Resposta:
```text
💸 <b>Análise de gastos</b>

<b>Onde você mais gasta:</b>
• Moradia: R$ 1.800,00
• Alimentação: R$ 85,90
• Saúde: R$ 73,20
• Transporte: R$ 42,30

<b>Maior gasto recente:</b> Aluguel — R$ 1.800,00
```

### Caso 7
Pergunta: Se voce fosse meu gerente, o que eu deveria fazer agora?

Resposta:
```text
🧭 <b>Consulta do Alfredo</b>

• <b>Status geral:</b> positivo
• <b>Risco:</b> baixo
• Seu próximo passo é manter consistência e guardar uma parte do excedente.
• Se quiser evoluir, transforme o saldo positivo em meta.

<b>Maiores categorias hoje:</b>
• Moradia: R$ 1.800,00
• Alimentação: R$ 85,90
• Saúde: R$ 73,20
```

### Caso 8
Pergunta: Estou conseguindo guardar dinheiro?

Resposta:
```text
🎯 <b>Metas ativas</b>
━━━━━━━━━━━━━━━━━━

• <b>Reserva de emergencia</b>
  R$ 3.500,00 de R$ 10.000,00 (35%) | prazo: 03/10/2026
```

### Caso 9
Pergunta: Quanto gastei essa semana?

Resposta:
```text
📅 <b>Resumo da semana</b>

• <b>Entradas:</b> R$ 5.000,00
• <b>Saídas:</b> R$ 2.001,40
• <b>Saldo:</b> R$ 2.998,60

<b>Principais gastos da semana:</b>
• Moradia: R$ 1.800,00
• Alimentação: R$ 85,90
• Saúde: R$ 73,20
```

### Caso 10
Pergunta: Me da um resumo geral de tudo

Resposta:
```text
📅 <b>Resumo do mês</b>

• <b>Entradas:</b> R$ 5.000,00
• <b>Saídas:</b> R$ 2.001,40
• <b>Saldo do mês:</b> R$ 2.998,60

<b>Top categorias de gasto:</b>
• Moradia: R$ 1.800,00
• Alimentação: R$ 85,90
• Saúde: R$ 73,20

<b>Últimos lançamentos:</b>
• Salario: +R$ 5.000,00
• Aluguel: -R$ 1.800,00
• iFood: -R$ 85,90
```

### Caso 11
Pergunta: Esse gasto foi fora do padrao?

Resposta:
```text
🚨 <b>Diagnóstico de risco</b>

• <b>Risco atual:</b> baixo
• <b>Saldo do mês:</b> R$ 2.998,60
• <b>Gastos do mês:</b> R$ 2.001,40
• <b>Entradas do mês:</b> R$ 5.000,00

<b>Principais fontes de gasto:</b>
• Moradia: R$ 1.800,00
• Alimentação: R$ 85,90
• Saúde: R$ 73,20
```

### Caso 12
Pergunta: Posso continuar gastando hoje?

Resposta:
```text
🔮 <b>Previsão do mês</b>

• <b>Saída média diária:</b> R$ 333,57
• <b>Saída projetada no mês:</b> R$ 10.007,00
• <b>Saldo projetado:</b> R$ -5.007,00
• <b>Limite diário seguro:</b> R$ 124,94

<b>Leitura rápida:</b> seguindo esse ritmo, o mês tende a fechar no vermelho.
```

## Observacoes

- As respostas acima sao exatamente do fallback local, sem depender da resposta textual do modelo externo.
- Em producao, com dados reais do usuario, os valores e rankings mudam dinamicamente.
- O objetivo deste relatorio e comprovar qualidade de roteamento + formato de resposta em cada categoria critica.
