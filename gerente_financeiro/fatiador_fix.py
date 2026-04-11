async def _enviar_mensagem_fatiada(message, texto: str, is_html: bool = True, **kwargs):
    """Divide a mensagem em pedaços menores de 4000 caracteres, garantindo HTML válido se necessário."""
    limite = 4000
    pedaços = []
    tags_abertas = []
    temp_texto = texto
    
    while temp_texto:
        if len(temp_texto) <= limite:
            fatia = temp_texto
            temp_texto = ""
        else:
            quebra = temp_texto.rfind('\n', 0, limite)
            if quebra == -1:
                quebra = limite
            fatia = temp_texto[:quebra]
            temp_texto = temp_texto[quebra:].lstrip()
            
        if is_html:
            # Reabre as tags que ficaram abertas da fatia anterior
            prefixo = "".join([f"<{t}>" for t in tags_abertas])
            fatia_atual = prefixo + fatia
            
            # Analisa tags nesta fatia para atualizar a lista de abertas para a próxima
            tags_re = re.compile(r'<(b|i|code|a)(?:\s+[^>]*?)?>|</(b|i|code|a)>', re.IGNORECASE)
            for match in tags_re.finditer(fatia):
                tag_name = match.group(1)
                if tag_name: # Abertura
                    tags_abertas.append(tag_name.lower())
                else: # Fechamento
                    tag_fechou = match.group().lower()[2:-1]
                    if tags_abertas and tags_abertas[-1] == tag_fechou:
                        tags_abertas.pop()
            
            # Fecha as tags abertas no final desta fatia para garantir HTML válido na mensagem
            sufixo = "".join([f"</{t}>" for t in reversed(tags_abertas)])
            fatia_atual += sufixo
            pedaços.append(fatia_atual)
        else:
            pedaços.append(fatia)
    
    for p in pedaços:
        if not p.strip(): continue
        try:
            if is_html:
                # IMPORTANTE: Usar reply_html direto aqui para evitar recursão infinita
                await message.reply_html(p, **kwargs)
            else:
                await message.reply_text(p, **kwargs)
        except Exception as e:
            logger.error("Erro ao enviar fatia: %s", e)
            if is_html:
                # Fallback para texto plano se falhar o HTML da fatia
                p_plano = re.sub(r"<[^>]+>", "", p)
                try:
                    await message.reply_text(p_plano, **kwargs)
                except Exception:
                    pass
