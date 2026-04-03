# Deploy com WeasyPrint (HTML → PDF) — Guia rápido

Este documento descreve como preparar e deployar o ContaComigo em um container Docker com suporte a WeasyPrint, permitindo conversão fiel do HTML (`relatorio_inspiracao.html`) em PDF.

Requisitos
- Docker (build local ou via plataforma: Railway, Render, etc.)
- `requirements.txt` já inclui `weasyprint`.

Passos (local / CI)

1. Build da imagem localmente:

```bash
docker build -t contacomigo:weasy .
```

2. Rodar localmente (mapeando porta):

```bash
docker run --rm -p 8000:8000 contacomigo:weasy
```

3. Rodar o endpoint e testar `/relatorio` no bot (ou acesso web) — o processo estará escutando em `0.0.0.0:8000`.

Deploy no Railway

1. No Railway, crie um novo serviço e escolha "Deploy from Dockerfile" (ou conecte o repositório e defina para usar Dockerfile). O Railway irá construir a imagem automaticamente.
2. Defina variáveis de ambiente necessárias (ex.: tokens do Telegram, DATABASE_URL, etc.).
3. Após o deploy, reinicie o serviço para garantir que o novo container seja usado.

Notas importantes
- O Dockerfile já instala as bibliotecas de sistema necessárias (cairo, pango, libgdk-pixbuf, shared-mime-info). Se sua plataforma fornecer uma imagem base diferente, ajuste o Dockerfile conforme necessário.
- Tamanho da imagem: incluir libs nativas aumenta o tamanho; é recomendado usar cache de builds e multi-stage se quiser otimizar.
- Verificação: após o deploy, gere um `/relatorio` e verifique o PDF. O `pdf_generator.py` tentará usar WeasyPrint quando disponível; os logs indicarão se WeasyPrint foi utilizado.

Dicas de troubleshooting
- Se WeasyPrint lançar erro relacionado a fontes ou Pango, verifique logs e, localmente, execute `docker run -it contacomigo:weasy /bin/bash` e tente importar `weasyprint` no Python para reproducibilidade.
- Se o PDF estiver faltando fontes web (google fonts), prefira embutir as fontes no repositório em `static/fonts` e utilizar as fontes locais no CSS do template.
