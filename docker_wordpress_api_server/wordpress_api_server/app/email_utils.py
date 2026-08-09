"""
Утилиты для отправки email
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://wordpress.cubinez.ru')


def send_welcome_email(email: str, temp_password: str) -> bool:
    """Отправить приветственное письмо с временным паролем"""
    import os
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        msg = MIMEMultipart()
        msg['From'] = os.getenv('SMTP_FROM', 'cubinez85@cubinez.ru')
        msg['To'] = email
        msg['Subject'] = 'Добро пожаловать! Ваши данные для входа'

        login_url = f"https://wordpress.cubinez.ru/login"
        reset_url = f"https://wordpress.cubinez.ru/forgot-password"

        body = f"""Здравствуйте!

Вы успешно зарегистрированы в нашей системе.

Ваши данные для входа:
📧 Email: {email}
🔑 Временный пароль: {temp_password}

⚠️  Важно: Рекомендуется изменить пароль при первом входе!

🔗 Страница входа: {login_url}
🔗 Забыли пароль: {reset_url}

Если вы не регистрировались в нашей системе, просто проигнорируйте это письмо.

С уважением,
Команда поддержки
"""
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # Подключение к SMTP серверу (Postfix на localhost)
        smtp_server = os.getenv('SMTP_SERVER', 'localhost')
        smtp_port = int(os.getenv('SMTP_PORT', '25'))
        
        # Подключаемся БЕЗ аутентификации (Postfix на localhost не требует)
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        server.ehlo()
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Email отправлен на {email}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка отправки email: {e}")
        import traceback
        traceback.print_exc()
        return False
