import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Adicionar o diretório raiz ao sys.path para permitir a importação do launcher
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestLauncher(unittest.TestCase):
    def run_main_with_env(self, env_vars):
        """Helper para rodar launcher.main com ambiente controlado."""
        import launcher

        with patch.dict('os.environ', env_vars, clear=True), \
             patch('launcher.load_environment', return_value=True), \
             patch('launcher.apply_migrations'), \
             patch('launcher.signal.signal'):
            launcher.main()

    @patch('launcher.Thread')
    @patch('launcher.start_dashboard')
    @patch('launcher.start_telegram_bot')
    def test_railway_environment_starts_hybrid(self, mock_start_bot, mock_start_dashboard, mock_thread):
        """No Railway atual, modo é híbrido: bot em thread + dashboard principal."""
        env = {
            'RAILWAY_ENVIRONMENT': 'production',
            'PORT': '8080',
            'TELEGRAM_TOKEN': 'fake_token',
            'DATABASE_URL': 'fake_db_url',
        }
        mock_bot_thread = MagicMock()
        mock_thread.return_value = mock_bot_thread

        self.run_main_with_env(env)

        mock_start_bot.assert_not_called()
        mock_thread.assert_called_once_with(
            target=mock_start_bot,
            kwargs={'enable_health_server': False},
            daemon=True,
        )
        mock_bot_thread.start.assert_called_once()
        mock_start_dashboard.assert_called_once()

    @patch('launcher.start_dashboard')
    @patch('launcher.start_telegram_bot')
    def test_render_web_service_starts_dashboard(self, mock_start_bot, mock_start_dashboard):
        """Render Web Service deve iniciar dashboard."""
        env = {
            'RENDER_INSTANCE_ID': 'instance-1',
            'RENDER_SERVICE_TYPE': 'web',
            'TELEGRAM_TOKEN': 'fake_token',
            'DATABASE_URL': 'fake_db_url',
        }

        self.run_main_with_env(env)

        mock_start_bot.assert_not_called()
        mock_start_dashboard.assert_called_once()

    @patch('launcher.start_dashboard')
    @patch('launcher.start_telegram_bot')
    def test_render_worker_starts_bot(self, mock_start_bot, mock_start_dashboard):
        """Render Worker deve iniciar bot."""
        env = {
            'RENDER_INSTANCE_ID': 'instance-1',
            'RENDER_SERVICE_TYPE': 'worker',
            'TELEGRAM_TOKEN': 'fake_token',
            'DATABASE_URL': 'fake_db_url',
        }

        self.run_main_with_env(env)

        mock_start_bot.assert_called_once_with()
        mock_start_dashboard.assert_not_called()

    @patch('launcher.start_dashboard')
    @patch('launcher.start_telegram_bot')
    def test_force_bot_mode(self, mock_start_bot, mock_start_dashboard):
        """Modo forçado 'bot' deve priorizar bot."""
        env = {
            'CONTACOMIGO_MODE': 'bot',
            'PORT': '8080',
            'RAILWAY_ENVIRONMENT': 'production',
            'TELEGRAM_TOKEN': 'fake_token',
            'DATABASE_URL': 'fake_db_url',
        }

        self.run_main_with_env(env)

        mock_start_bot.assert_called_once_with()
        mock_start_dashboard.assert_not_called()

    @patch('launcher.start_dashboard')
    @patch('launcher.start_telegram_bot')
    def test_force_dashboard_mode(self, mock_start_bot, mock_start_dashboard):
        """Modo forçado 'dashboard' deve priorizar dashboard."""
        env = {
            'CONTACOMIGO_MODE': 'dashboard',
            'RAILWAY_ENVIRONMENT': 'production',
            'TELEGRAM_TOKEN': 'fake_token',
            'DATABASE_URL': 'fake_db_url',
        }

        self.run_main_with_env(env)

        mock_start_bot.assert_not_called()
        mock_start_dashboard.assert_called_once_with()

    @patch('launcher.Thread')
    @patch('launcher.start_dashboard')
    @patch('launcher.start_telegram_bot')
    def test_local_mode_starts_both(self, mock_start_bot, mock_start_dashboard, mock_thread):
        """No local, inicia bot em thread e dashboard no processo principal."""
        env = {
            'TELEGRAM_TOKEN': 'fake_token',
            'DATABASE_URL': 'fake_db_url',
        }

        mock_bot_thread = MagicMock()
        mock_thread.return_value = mock_bot_thread

        self.run_main_with_env(env)

        mock_start_bot.assert_not_called()
        mock_thread.assert_called_once_with(
            target=mock_start_bot,
            kwargs={'enable_health_server': False},
            daemon=True,
        )
        mock_bot_thread.start.assert_called_once()
        mock_start_dashboard.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
