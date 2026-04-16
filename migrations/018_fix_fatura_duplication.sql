-- Correção de Duplicidade de Fatura (Retroativa)
-- Transforma pagamentos de fatura em 'Transferência' em vez de 'Despesa'/'Receita'
-- Apenas para usuários que possuem cartões sincronizados (onde as despesas individuais já existem)

UPDATE lancamentos
SET tipo = 'Transferência'
WHERE id IN (
    SELECT l.id
    FROM lancamentos l
    WHERE (
        (LOWER(l.descricao) LIKE '%pagamento%fatura%') OR 
        (LOWER(l.descricao) LIKE '%pagamento recebido%') OR 
        (LOWER(l.descricao) LIKE '%pagamento efetuado - cartoe%') OR
        (LOWER(l.descricao) LIKE '%pagamento efetuado - cartõe%')
    )
    AND l.tipo IN ('Despesa', 'Saída', 'Receita', 'Entrada')
    AND EXISTS (
        SELECT 1 FROM contas c2 
        WHERE c2.id_usuario = l.id_usuario 
        AND c2.tipo = 'Cartão de Crédito' 
        AND c2.external_id IS NOT NULL
    )
);
