-- Migration 017: Criar tabela de regras de categorização personalizada
CREATE TABLE IF NOT EXISTS regras_categorizacao (
    id SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    descricao_substring VARCHAR(255) NOT NULL,
    id_categoria INTEGER NOT NULL REFERENCES categorias(id),
    id_subcategoria INTEGER REFERENCES subcategorias(id),
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Garantir que cada usuário tenha apenas uma regra por substring
CREATE UNIQUE INDEX IF NOT EXISTS uq_regra_categorizacao_usuario_desc ON regras_categorizacao (id_usuario, descricao_substring);

-- Índice para busca rápida por usuário
CREATE INDEX IF NOT EXISTS idx_regras_categorizacao_usuario ON regras_categorizacao (id_usuario);
