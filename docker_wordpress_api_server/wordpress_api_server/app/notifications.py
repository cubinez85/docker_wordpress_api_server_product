"""
Модуль уведомлений (Telegram, VK, Email)
Используется как API, так и Worker
"""

import json
import logging
import os
import random
import smtplib
import asyncio
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional
from concurrent.futures import ThreadPoolExecutor

import vk_api
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class Config:
    """Конфигурация из переменных окружения"""
    
    @staticmethod
    def get_telegram_token() -> Optional[str]:
        return os.getenv('TELEGRAM_BOT_TOKEN')

    @staticmethod
    def get_telegram_chat_id() -> Optional[str]:
        return os.getenv('TELEGRAM_CHAT_ID')

    @staticmethod
    def get_vk_token() -> Optional[str]:
        return os.getenv('VK_GROUP_TOKEN')

    @staticmethod
    def get_vk_peer_id() -> Optional[str]:
        return os.getenv('VK_PEER_ID')

    @staticmethod
    def get_vk_api_version() -> str:
        return os.getenv('VK_API_VERSION', '5.199')

    @staticmethod
    def get_smtp_config() -> Dict:
        return {
            'server': os.getenv('SMTP_SERVER', 'localhost'),
            'port': int(os.getenv('SMTP_PORT', '25')),
            'user': os.getenv('SMTP_USER', ''),
            'password': os.getenv('SMTP_PASSWORD', ''),
            'to': os.getenv('EMAIL_TO', '')
        }


class NotificationManager:
    """Управление уведомлениями (Telegram, VK, Email)"""
    
    def __init__(self):
        self.telegram_bot = None
        self.vk = None
        self.vk_peer_id = None
        self.email_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="notify_email")
        self.init_telegram()
        self.init_vk()

    def init_telegram(self):
        token = Config.get_telegram_token()
        chat_id = Config.get_telegram_chat_id()
        proxy_url = os.getenv('TELEGRAM_PROXY_URL', '')
        
        if token and chat_id:
            try:
                from telegram.request import HTTPXRequest
                
                # Если прокси указан в .env, используем его
                if proxy_url:
                    logger.info(f"🔌 Инициализация Telegram через прокси: {proxy_url}")
                    request = HTTPXRequest(proxy_url=proxy_url)
                    self.telegram_bot = Bot(token=token, request=request)
                else:
                    # Иначе пытаемся подключиться напрямую (для локальных тестов)
                    self.telegram_bot = Bot(token=token)
                    
                logger.info("✅ Telegram бот успешно инициализирован")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации Telegram: {e}")
                self.telegram_bot = None
        else:
            logger.info("⚠️ Telegram уведомления отключены (нет токена или chat_id)")

    def init_vk(self):
        token = Config.get_vk_token()
        peer_id = Config.get_vk_peer_id()
        if token and peer_id:
            try:
                vk_session = vk_api.VkApi(token=token, api_version=Config.get_vk_api_version())
                self.vk = vk_session.get_api()
                self.vk_peer_id = int(peer_id)
                logger.info("✅ VK бот инициализирован")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации VK: {e}")
                self.vk = None
        else:
            logger.info("⚠️  VK уведомления отключены")

    def send_telegram(self, submission: Dict):
        if not self.telegram_bot:
            return
        try:
            message = self._format_message(submission, emoji='🎯')
            chat_id = Config.get_telegram_chat_id()
            if not chat_id or not chat_id.isdigit():
                logger.warning("⚠️  Неверный Telegram chat_id")
                return

            async def _send():
                try:
                    await self.telegram_bot.send_message(
                        chat_id=int(chat_id), 
                        text=message, 
                        parse_mode='HTML'
                    )
                    logger.info("✅ Уведомление отправлено в Telegram")
                except TelegramError as e:
                    logger.error(f"❌ Ошибка отправки в Telegram: {e}")
            asyncio.run(_send())
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке Telegram: {e}")

    def send_vk(self, submission: Dict):
        if not self.vk:
            return
        try:
            message = self._format_message(submission, emoji='🎯', html=False)
            self.vk.messages.send(
                peer_id=self.vk_peer_id,
                message=message,
                random_id=random.getrandbits(32)
            )
            logger.info("✅ Уведомление отправлено в VK")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки в VK: {e}")

    def send_email(self, submission: Dict, to_email: Optional[str] = None):
        config = Config.get_smtp_config()
        target_email = to_email or config.get('to')

        if not target_email:
            logger.info("⚠️  Email уведомления отключены")
            return

        future = self.email_executor.submit(self._send_email_sync, submission, target_email, config)

        def log_result(future):
            try:
                result = future.result(timeout=30)
                if result:
                    logger.info(f"✅ Email уведомление отправлено на {target_email}")
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке email: {e}")

        future.add_done_callback(log_result)
        logger.info(f"📧 Запущена отправка email уведомления на {target_email}")

    def _send_email_sync(self, submission: Dict, to_email: str, config: Dict) -> bool:
        try:
            msg = MIMEMultipart()
            msg['From'] = os.getenv('SMTP_FROM', 'noreply@cubinez.ru')
            msg['To'] = to_email
            msg['Subject'] = 'Новая заявка с формы регистрации'

            body = self._format_message(submission, emoji='', html=False)
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            server = smtplib.SMTP(config['server'], config['port'], timeout=10)
            server.ehlo()
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка отправки email: {e}")
            return False

    def _format_message(self, submission: Dict, emoji='🎯', html=True) -> str:
        full_name = submission.get('full_name') or submission.get('ФИО (обязательное поле)', 'Не указано')
        email = submission.get('email') or submission.get('Электронная почта (обязательное поле)', 'Не указано')
        timestamp = submission.get('timestamp') or submission.get('Отметка времени', datetime.now().strftime('%d.%m.%Y %H:%M:%S'))
        
        if html:
            return f"""<b>{emoji} Новая заявка с формы регистрации</b>

<b>📅 Время:</b> {timestamp}
<b>👤 ФИО:</b> {full_name}
<b>📧 Email:</b> {email}
<b>🕐 Обработано:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"""
        else:
            return f"""{emoji} Новая заявка с формы регистрации

📅 Время: {timestamp}
👤 ФИО: {full_name}
📧 Email: {email}
🕐 Обработано: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"""

    def shutdown(self):
        if hasattr(self, 'email_executor'):
            self.email_executor.shutdown(wait=False)
