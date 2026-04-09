import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuração básica (ajuste para seu provedor)
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USER = 'SEU_EMAIL@gmail.com'
SMTP_PASS = 'SUA_SENHA_OU_APP_PASSWORD'

# Função para enviar email simples

def enviar_email(destinatario, assunto, corpo):
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = destinatario
    msg['Subject'] = assunto
    msg.attach(MIMEText(corpo, 'plain'))
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f'Erro ao enviar email: {e}')
        return False
