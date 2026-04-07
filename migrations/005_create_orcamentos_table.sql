CREATE TABLE IF NOT EXISTS orcamentos_categoria (
    id SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    id_categoria INTEGER NOT NULL REFERENCES categorias(id) ON DELETE CASCADE,
    valor_limite NUMERIC(12, 2) NOT NULL,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(id_usuario, id_categoria)
);