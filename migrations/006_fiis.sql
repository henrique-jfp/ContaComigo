-- Migração para suporte a FIIs (Fundos de Investimento Imobiliário)
-- Data: 2026-04-10

CREATE TABLE IF NOT EXISTS carteira_fiis (
    id SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    quantidade_cotas NUMERIC(10, 2) NOT NULL,
    preco_medio NUMERIC(10, 2) NOT NULL,
    data_entrada DATE,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_carteira_fii_usuario_ticker UNIQUE (id_usuario, ticker)
);

CREATE INDEX IF NOT EXISTS idx_carteira_fiis_usuario ON carteira_fiis(id_usuario);

CREATE TABLE IF NOT EXISTS historico_alertas_fii (
    id SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    tipo_alerta VARCHAR(50) NOT NULL,
    valor_referencia NUMERIC(10, 4),
    enviado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_historico_alertas_fii_usuario ON historico_alertas_fii(id_usuario);
