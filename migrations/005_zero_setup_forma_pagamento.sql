-- Zero Setup migration: remove account linkage from transactions and normalize payment method.

-- 1) Normalize existing payment data before setting NOT NULL.
UPDATE lancamentos
SET forma_pagamento = 'Nao_informado'
WHERE forma_pagamento IS NULL OR btrim(forma_pagamento) = '';

-- Normalize legacy variants before enforcing strict CHECK.
UPDATE lancamentos
SET forma_pagamento = CASE
	WHEN lower(btrim(forma_pagamento)) IN ('pix') THEN 'Pix'
	WHEN lower(btrim(forma_pagamento)) IN ('credito', 'crédito') THEN 'Crédito'
	WHEN lower(btrim(forma_pagamento)) IN ('debito', 'débito') THEN 'Débito'
	WHEN lower(btrim(forma_pagamento)) IN ('boleto') THEN 'Boleto'
	WHEN lower(btrim(forma_pagamento)) IN ('dinheiro') THEN 'Dinheiro'
	WHEN lower(btrim(forma_pagamento)) IN ('nao_informado', 'não_informado', 'nao informado', 'não informado', 'n/a') THEN 'Nao_informado'
	ELSE 'Nao_informado'
END;

-- 2) Remove account linkage from transactions.
ALTER TABLE lancamentos
DROP COLUMN IF EXISTS id_conta;

-- 3) Enforce default + not null for payment method.
ALTER TABLE lancamentos
ALTER COLUMN forma_pagamento SET DEFAULT 'Nao_informado';

ALTER TABLE lancamentos
ALTER COLUMN forma_pagamento SET NOT NULL;

-- 4) Replace old constraint if exists and enforce allowed values.
ALTER TABLE lancamentos
DROP CONSTRAINT IF EXISTS ck_lancamentos_forma_pagamento;

ALTER TABLE lancamentos
ADD CONSTRAINT ck_lancamentos_forma_pagamento
CHECK (forma_pagamento IN ('Pix', 'Crédito', 'Débito', 'Boleto', 'Dinheiro', 'Nao_informado'));
