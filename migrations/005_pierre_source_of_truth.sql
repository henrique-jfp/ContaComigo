-- migrations/005_pierre_source_of_truth.sql

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS pierre_initial_sync_done BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS last_pierre_sync_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE lancamentos ADD COLUMN IF NOT EXISTS id_conta INTEGER REFERENCES contas(id);

CREATE TABLE IF NOT EXISTS saldos_conta (
    id SERIAL PRIMARY KEY,
    id_conta INTEGER NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    saldo NUMERIC(15, 2) NOT NULL,
    saldo_disponivel NUMERIC(15, 2),
    capturado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_saldo_conta_dia ON saldos_conta (id_conta, (capturado_em::date));

CREATE TABLE IF NOT EXISTS faturas_cartao (
    id SERIAL PRIMARY KEY,
    id_conta INTEGER NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    external_id VARCHAR UNIQUE,
    valor_total NUMERIC(12, 2) NOT NULL,
    data_vencimento DATE,
    data_fechamento DATE,
    status VARCHAR NOT NULL DEFAULT 'fechada',
    mes_referencia DATE,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parcelamentos (
    id SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    id_conta INTEGER REFERENCES contas(id) ON DELETE CASCADE,
    external_id VARCHAR UNIQUE,
    descricao VARCHAR NOT NULL,
    valor_total NUMERIC(12, 2) NOT NULL,
    valor_parcela NUMERIC(12, 2) NOT NULL,
    parcela_atual INTEGER NOT NULL,
    total_parcelas INTEGER NOT NULL,
    data_compra DATE,
    data_proxima_parcela DATE,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
