CREATE TABLE IF NOT EXISTS lembretes (
    id SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    descricao VARCHAR NOT NULL,
    valor NUMERIC(12, 2),
    tipo VARCHAR,
    data_primeiro_evento DATE NOT NULL,
    frequencia VARCHAR DEFAULT 'unico',
    total_parcelas INTEGER,
    parcela_atual INTEGER DEFAULT 0,
    proxima_data_execucao DATE NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR NOT NULL DEFAULT 'ativo',
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lembretes_usuario ON lembretes(id_usuario);
CREATE INDEX IF NOT EXISTS idx_lembretes_status ON lembretes(status);
CREATE INDEX IF NOT EXISTS idx_lembretes_execucao_ativo ON lembretes(id_usuario, ativo, proxima_data_execucao);
