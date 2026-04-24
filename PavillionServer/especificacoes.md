::Especificações Técnicas.

- Marca: HP
- Modelo: 11-N226BR
- Linha: Pavilion X360
- Cor: Vermelho
- Sistema Operacional: Ubuntu(se outro sistema gratuito for melhor pode ser trocado)

Processador
- Modelo: Intel® Celeron® N2830 Dual Core.

Tela
- Tipo de monitor: Touch, iluminação auxiliar por WLED.
- Polegadas: 11,6"   
- Resolução: 1.366 x 768

Memória
- Capacidade: 4 GB   
- Barramento da memória: SDRAM DDR3L

Armazenamento
- Capacidade do SSD: 120GB   
- desempenho de Leitura (até 450 MB/s) e Gravação (até 400 MB/s)

Placa de vídeo
- Tipo: integrada   
- Modelo: Intel® HD Graphics com até 1.792 MB de memória gráfica total.

- Som: Dois alto-falantes DTS Studio Sound.
- Placa de rede: LAN Ethernet 10/100BASE-T (conector RJ-45).
- Placa wireless: WLAN 1x1 802.11b/g/n.
- Webcam HD HP TrueVision voltada para a frente com conjunto de dois microfones digitais integrados + sensor de luz ambiente.
- Bluetooth: sim
- Leitor de cartões: Digital Media Card Reader de vários formatos para cartões Secure Digital.

- Conexões:
1 USB 3.0 SuperSpeed
2 Universal Serial Bus (USB) 2.0
1 HDMI
1 RJ-45 (LAN)
1 Conector conjunto para saída de fone de ouvido/entrada de microfone


alfredo-server with id 970ddca7-a0a3-4708-a15c-b56f07e792c4



tunnel: alfredo-server
    credentials-file: /etc/cloudflared/970ddca7-a0a3-4708-a15c-b56f07e792c4.json
   
    ingress:
      - hostname: alfredo.seudominio.com
        service: http://localhost:5000
      - service: http_status:404



    [Unit]
        Description=ContaComigo Server - Alfredo
        After=network.target
   
        [Service]
        User=pvserver
        WorkingDirectory=/home/pvserver/contacomigo
        ExecStart=/home/pvserver/contacomigo/venv/bin/python launcher.py
        Restart=always
        RestartSec=10
        Environment=PYTHONUNBUFFERED=1
   
        [Install]
        WantedBy=multi-user.target