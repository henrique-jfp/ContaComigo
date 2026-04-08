from googleapiclient.discovery import build
from google.oauth2 import service_account
from datetime import datetime, timedelta

# Caminho para credencial do Google Service Account
SERVICE_ACCOUNT_FILE = 'credenciais/service-account-key.json'
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Função para criar evento no Google Calendar

def criar_evento_google_calendar(titulo, descricao, data_inicio, data_fim, email_usuario):
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    evento = {
        'summary': titulo,
        'description': descricao,
        'start': {'dateTime': data_inicio.isoformat(), 'timeZone': 'America/Sao_Paulo'},
        'end': {'dateTime': data_fim.isoformat(), 'timeZone': 'America/Sao_Paulo'},
        'attendees': [{'email': email_usuario}],
    }
    try:
        evento_criado = service.events().insert(calendarId='primary', body=evento).execute()
        return evento_criado.get('htmlLink')
    except Exception as e:
        print(f'Erro ao criar evento no Google Calendar: {e}')
        return None
