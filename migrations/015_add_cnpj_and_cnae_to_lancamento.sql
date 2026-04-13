-- Migration: 015_add_cnpj_and_cnae_to_lancamento.sql
-- Adiciona campos para enriquecimento de dados fiscais (CNPJ, Nome Fantasia, CNAE)

ALTER TABLE lancamentos ADD COLUMN IF NOT EXISTS cnpj_contraparte VARCHAR;
ALTER TABLE lancamentos ADD COLUMN IF NOT EXISTS nome_contraparte VARCHAR;
ALTER TABLE lancamentos ADD COLUMN IF NOT EXISTS cnae VARCHAR;

-- Comentário para documentação
COMMENT ON COLUMN lancamentos.cnpj_contraparte IS 'CNPJ ou CPF da contraparte ou estabelecimento da transação';
COMMENT ON COLUMN lancamentos.nome_contraparte IS 'Razão Social ou Nome Fantasia enriquecido via API de CNPJ';
COMMENT ON COLUMN lancamentos.cnae IS 'Código CNAE principal do estabelecimento';
