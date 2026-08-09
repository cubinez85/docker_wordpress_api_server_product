# Полезные команды для управления
docker compose up -d --build # развернуть первый раз на сервере

# Остановить всё
docker compose down

# Запустить снова
docker compose up -d

# Перезапустить только WordPress (например, после изменения кода)
docker compose restart wordpress

# Зайти внутрь контейнера WordPress
docker compose exec wordpress bash

# Зайти в MariaDB
docker compose exec db mariadb -u wp_user -p wordpress

# Обновить образы
docker compose pull
docker compose up -d

# Очистить build cache
docker builder prune -a -f

# Очистить неиспользуемые образы
docker image prune -a -f

# Пересобрать с обновлением базового образа
docker compose build --no-cache --pull api

# Запустить
docker compose up -d

# Логи
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f postgres

# Перезапуск
docker compose restart api worker

# Пересборка
docker compose up -d --build

# Остановка
docker compose down

# Вход в контейнер
docker compose exec api bash
docker compose exec worker bash
docker compose exec postgres psql -U leads_user -d leads_db

Создание админа
docker exec -it leads-worker python3 -c " from passlib.context import CryptContext import psycopg2, os pwd = CryptContext(schemes=['argon2']) conn = psycopg2.connect(host='postgres', database=os.getenv('POSTGRESQL_DB'), user=os.getenv('POSTGRESQL_USER'), password=os.getenv('POSTGRESQL_PASSWORD')) cur = conn.cursor() cur.execute('INSERT INTO users (email, password_hash, is_admin) VALUES (%s, %s, TRUE) ON CONFLICT (email) DO UPDATE SET is_admin=TRUE', ('cubinez85@cubinez.ru', pwd.hash('ВашНадежныйПароль123'))) conn.commit(); print('Admin created/updated') "

создание админа(вариант)
Проверьте, существует ли пользователь: docker exec -it wordpress-postgres psql -U leads_user -d leads_db -c "SELECT id, email, is_admin, is_active FROM users WHERE email = 'cubinez85@cubinez.ru';"

Если пользователь есть, но не админ docker exec -it wordpress-postgres psql -U leads_user -d leads_db -c "UPDATE users SET is_admin = TRUE WHERE email = 'cubinez85@cubinez.ru';"

Проверьте: docker exec -it wordpress-postgres psql -U leads_user -d leads_db -c "SELECT id, email, is_admin FROM users WHERE email = 'cubinez85@cubinez.ru';"

# Резервное копирование (обязательно!)
sudo nano /usr/local/bin/wp-backup.sh

#!/bin/bash
BACKUP_DIR="/home/cubinez85/docker_wordpress_api_server/wordpress-backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

cd /home/cubinez85/docker_wordpress_api_server/wordpress

# Получаем пароль из переменных окружения
MYSQL_PASSWORD=$(docker exec $(docker compose ps -q db) env | grep MYSQL_ROOT_PASSWORD | cut -d= -f2)

# Бэкап базы данных
docker exec $(docker compose ps -q db) mariadb-dump -u root -p"${MYSQL_PASSWORD}" --all-databases | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Бэкап файлов WordPress
docker run --rm -v wordpress_wp_data:/data -v $BACKUP_DIR:/backup alpine \
  tar czf /backup/files_$DATE.tar.gz -C /data .

# Храним бэкапы 30 дней
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $DATE"


sudo chmod +x /usr/local/bin/wp-backup.sh

# cron (запуск каждый день в 3:00):
sudo crontab -e

# для создания папки /home/cubinez85/wordpress-backups запустить cron:
* * * * * /usr/local/bin/wp-backup.sh >> /var/log/wp-backup.log 2>&1
потом:

0 3 * * * /usr/local/bin/wp-backup.sh >> /var/log/wp-backup.log 2>&1

# Установка wordpress через локальный бекап:
cd ~/docker_wordpress_api_server/wordpress

# 1. Проверяем пароль MySQL
docker exec $(docker compose ps -q db) env | grep MYSQL_ROOT_PASSWORD

# 2. Создаем чистую БД
docker exec $(docker compose ps -q db) mariadb -u root -p"*********" -e "DROP DATABASE IF EXISTS wordpress; CREATE DATABASE wordpress;"

# 3. Восстанавливаем БД из нового бэкапа
gunzip -c ~/docker_wordpress_api_server/wordpress-backups/db_20260714_102101.sql.gz | \
docker exec -i $(docker compose ps -q db) mariadb -u root -p"v7aBr7kI-d" wordpress

# 4. Проверяем, что таблицы появились
docker exec $(docker compose ps -q db) mariadb -u root -p"******" -e "SHOW TABLES FROM wordpress;"

# 5. Проверяем количество таблиц
docker exec $(docker compose ps -q db) mariadb -u root -p"*******" -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='wordpress';"

# 1. Восстанавливаем файлы из архива
docker run --rm \
  -v wordpress_wp_data:/data \
  -v ~/docker_wordpress_api_server/wordpress-backups:/backup \
  alpine \
  tar xzf /backup/files_20260714_102101.tar.gz -C /data

# 2. Проверяем, что файлы восстановились
docker run --rm -v wordpress_wp_data:/data alpine ls -la /data

# установить доверенный cert
sudo mkdir /etc/nginx/ssl/

sudo nano /etc/nginx/ssl/openssl.cnf
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = v3_req

[dn]
C = RU
ST = Moscow
L = Moscow
O = Cubinez
OU = IT
CN = wordpress.cubinez.ru

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = wordpress.cubinez.ru
DNS.2 = localhost
IP.1 = 127.0.0.1

Шаг 1: Пересоздайте сертификат с правильным флагом

# Удалите старые сертификаты
sudo rm -f /etc/nginx/ssl/test-register-tilda.*

# Создайте новый сертификат с явным указанием extensions
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/wordpress.key \
  -out /etc/nginx/ssl/wordpress.crt \
  -config /etc/nginx/ssl/openssl.cnf \
  -extensions v3_req

# Установите права
sudo chmod 644 /etc/nginx/ssl/wordpress.crt
sudo chmod 600 /etc/nginx/ssl/wordpress.key

Шаг 2: Проверьте, что SAN теперь есть

openssl x509 -in /etc/nginx/ssl/wordpress.crt -text -noout | grep -A 3 "Alternative"

Должно показать:

            X509v3 Subject Alternative Name: 
                DNS:wordpress.cubinez.ru, DNS:localhost, IP Address:127.0.0.1

Шаг 3: Перезапустите Nginx
sudo nginx -t
sudo systemctl reload nginx

Шаг 4: Скопируйте сертификат в Windows и установите его

# Скопируйте на рабочий стол Windows
cp /etc/nginx/ssl/wordpress.crt /mnt/c/Users/Oleg/OneDrive/Desktop/wordpress.crt

Затем в Windows:
Откройте файл wordpress.crt на рабочем столе
Нажмите "Установить сертификат"
Выберите "Текущий пользователь" → Далее
Выберите "Поместить все сертификаты в следующее хранилище"
Нажмите "Обзор" → выберите "Доверенные корневые центры сертификации"
Далее → Готово
Шаг 5: Полностью закройте браузер и проверьте
Важно: Chrome/Edge нужно закрыть полностью (включая все окна).

# проверка relay

telnet 95.174.94.246 25

EHLO test.cubinez.ru

MAIL FROM:<cubinez85@cubinez.ru>

RCPT TO:<cubinez85@gmail.com>

# wordpress_pages
# wordpress.cubinez.ru
<style>
  .home-reg-container {
    max-width: 600px;
    margin: 50px auto;
    padding: 30px;
    font-family: Arial, sans-serif;
  }
  .home-reg-container h2 {
    text-align: center;
    color: #2c3e50;
    margin-bottom: 10px;
  }
  .home-reg-container .subtitle {
    text-align: center;
    color: #7f8c8d;
    margin-bottom: 30px;
    font-size: 14px;
  }
  .reg-form {
    background: #fff;
    padding: 30px;
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
  }
  .reg-form label {
    display: block;
    margin: 12px 0 4px;
    font-weight: bold;
    color: #333;
  }
  .reg-form input {
    width: 100%;
    padding: 12px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 16px;
    box-sizing: border-box;
  }
  .reg-form input:focus {
    outline: none;
    border-color: #3498db;
  }
  .reg-form button {
    width: 100%;
    padding: 14px;
    background: #27ae60;
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 16px;
    font-weight: bold;
    cursor: pointer;
    margin-top: 20px;
  }
  .reg-form button:hover { background: #229954; }
  .reg-form button:disabled { background: #95a5a6; cursor: not-allowed; }
  .reg-form .message {
    margin-top: 15px;
    padding: 12px;
    border-radius: 4px;
    text-align: center;
  }
  .reg-form .error { background: #ffecec; color: #d32f2f; }
  .reg-form .success { background: #e8f5e9; color: #2e7d32; }
  .reg-form .warning { background: #fff3cd; color: #856404; }
  
  .divider {
    text-align: center;
    margin: 30px 0 20px;
    color: #95a5a6;
    font-size: 14px;
    position: relative;
  }
  .divider::before, .divider::after {
    content: '';
    position: absolute;
    top: 50%;
    width: 40%;
    height: 1px;
    background: #ddd;
  }
  .divider::before { left: 0; }
  .divider::after { right: 0; }
  
  .google-form-link {
    text-align: center;
    padding: 20px;
    background: #f8f9fa;
    border-radius: 8px;
    border: 1px dashed #ddd;
  }
  .google-form-link p {
    margin: 0 0 10px;
    color: #7f8c8d;
    font-size: 14px;
  }
  .google-form-link a {
    display: inline-block;
    padding: 10px 25px;
    background: #4285f4;
    color: white;
    text-decoration: none;
    border-radius: 4px;
    font-weight: bold;
  }
  .google-form-link a:hover { background: #3367d6; }
  
  .login-link {
    text-align: center;
    margin-top: 20px;
    font-size: 14px;
  }
  .login-link a { color: #3498db; text-decoration: none; }
  .login-link a:hover { text-decoration: underline; }
</style>

<div class="home-reg-container">
  <h2>🚀 Регистрация в системе</h2>
  <div class="subtitle">Получите доступ за 10 секунд</div>
  
  <div class="reg-form">
    <label for="regFullName">ФИО *</label>
    <input type="text" id="regFullName" placeholder="Иванов Иван Иванович" required="">
    
    <label for="regEmail">Email *</label>
    <input type="email" id="regEmail" placeholder="example@mail.ru" required="">
    
    <button onclick="handleRegistration()" id="regBtn">Зарегистрироваться</button>
    
    <div id="regMessage"></div>
    
    <div class="login-link">
      Уже зарегистрированы? <a href="/login">Войти в систему</a>
    </div>
  </div>
  
  <div class="divider">или</div>
  
  <div class="google-form-link">
    <p> Предпочитаете Google Form?</p>
    <a href="https://docs.google.com/forms/d/e/1FAIpQLSc-8gkupsL6ExbIoF_3PBKd4-qiBUGJb_Vt6EYFbN-LnXkN0g/viewform?usp=header" target="_blank" rel="noopener">
      Открыть Google Form 
    </a>
  </div>
</div>

<script>
const API_BASE = 'https://wordpress.cubinez.ru/api';

async function handleRegistration() {
    const fullName = document.getElementById('regFullName').value.trim();
    const email = document.getElementById('regEmail').value.trim().toLowerCase();
    const messageDiv = document.getElementById('regMessage');
    const regBtn = document.getElementById('regBtn');
    
    // Валидация
    if (!fullName || !email) {
        messageDiv.innerHTML = '<div class="message error">❌ Заполните все поля</div>';
        return;
    }
    
    if (fullName.length < 2) {
        messageDiv.innerHTML = '<div class="message error">❌ Введите корректное ФИО</div>';
        return;
    }
    
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        messageDiv.innerHTML = '<div class="message error"> Введите корректный email</div>';
        return;
    }
    
    // Блокируем кнопку
    regBtn.disabled = true;
    regBtn.textContent = 'Регистрация...';
    messageDiv.innerHTML = '';
    
    try {
        const response = await fetch(`${API_BASE}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ full_name: fullName, email: email })
        });
        
        let result;
        try {
            result = await response.json();
        } catch (e) {
            throw new Error('Сервер вернул некорректный ответ');
        }
        
        if (response.ok) {
            // Успешная регистрация
            messageDiv.innerHTML = `<div class="message success">
                ✅ ${result.message}<br><br>
                Перенаправление на страницу входа через 3 секунды...
            </div>`;
            setTimeout(() => {
                window.location.href = result.redirect || '/login';
            }, 3000);
        } else if (response.status === 409) {
            // Email уже зарегистрирован
            messageDiv.innerHTML = `<div class="message warning">
                ⚠️ ${result.error}<br><br>
                Перенаправление на страницу входа через 2 секунды...
            </div>`;
            setTimeout(() => {
                window.location.href = result.redirect || '/login';
            }, 2000);
        } else {
            // Другие ошибки
            messageDiv.innerHTML = `<div class="message error">❌ ${result.error || 'Произошла ошибка'}</div>`;
            regBtn.disabled = false;
            regBtn.textContent = 'Зарегистрироваться';
        }
    } catch (error) {
        console.error('Ошибка регистрации:', error);
        messageDiv.innerHTML = `<div class="message error">❌ Ошибка: ${error.message || 'Попробуйте позже'}</div>`;
        regBtn.disabled = false;
        regBtn.textContent = 'Зарегистрироваться';
    }
}

// Enter для отправки
document.getElementById('regEmail').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') handleRegistration();
});
document.getElementById('regFullName').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') handleRegistration();
});
</script>

# /admin
<style>
  .admin-container {
    max-width: 1200px;
    margin: 20px auto;
    padding: 20px;
    font-family: Arial, sans-serif;
    color: #333;
  }
  .admin-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    background: #2c3e50;
    color: white;
    border-radius: 8px;
    margin-bottom: 20px;
  }
  .admin-header h1 { margin: 0; }
  .admin-nav {
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
    flex-wrap: wrap;
  }
  .admin-nav button {
    padding: 10px 20px;
    background: #3498db;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
  }
  .admin-nav button:hover { background: #2980b9; }
  .admin-nav button.active { background: #2c3e50; }
  .admin-nav button.danger { background: #e74c3c; }
  .admin-nav button.danger:hover { background: #c0392b; }
  
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
    margin-bottom: 20px;
  }
  .stat-card {
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    text-align: center;
  }
  .stat-card .value {
    font-size: 32px;
    font-weight: bold;
    color: #2c3e50;
  }
  .stat-card .label {
    color: #7f8c8d;
    font-size: 14px;
    margin-top: 5px;
  }
  
  .data-table {
    width: 100%;
    border-collapse: collapse;
    background: white;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
  }
  .data-table th {
    background: #34495e;
    color: white;
    padding: 12px;
    text-align: left;
    font-weight: normal;
  }
  .data-table td {
    padding: 12px;
    border-bottom: 1px solid #ecf0f1;
  }
  .data-table tr:hover { background: #f8f9fa; }
  
  .badge {
    display: inline-block;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: bold;
  }
  .badge-success { background: #27ae60; color: white; }
  .badge-danger { background: #e74c3c; color: white; }
  .badge-warning { background: #f39c12; color: white; }
  .badge-info { background: #3498db; color: white; }
  
  .action-btn {
    padding: 5px 10px;
    border: none;
    border-radius: 3px;
    cursor: pointer;
    font-size: 12px;
    margin-right: 5px;
  }
  .btn-primary { background: #3498db; color: white; }
  .btn-danger { background: #e74c3c; color: white; }
  .btn-warning { background: #f39c12; color: white; }
  
  .search-box {
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 14px;
    width: 300px;
    margin-bottom: 15px;
  }
  
  .pagination {
    display: flex;
    justify-content: center;
    gap: 5px;
    margin-top: 20px;
  }
  .pagination button {
    padding: 8px 12px;
    border: 1px solid #ddd;
    background: white;
    cursor: pointer;
    border-radius: 4px;
  }
  .pagination button.active {
    background: #3498db;
    color: white;
    border-color: #3498db;
  }
  .pagination button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .loading { text-align: center; padding: 20px; color: #7f8c8d; }
  .error-msg { background: #ffecec; color: #d32f2f; padding: 15px; border-radius: 4px; margin-bottom: 20px; }
  .section { display: none; }
  .section.active { display: block; }
  
  .modal-overlay {
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.5);
    z-index: 1000;
    justify-content: center;
    align-items: center;
  }
  .modal-overlay.active { display: flex; }
  .modal {
    background: white;
    padding: 30px;
    border-radius: 8px;
    max-width: 500px;
    width: 90%;
  }
  .modal h3 { margin-top: 0; }
  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 20px;
  }
</style>

<div class="admin-container">
  <div class="admin-header">
    <h1>🔧 Админ-панель</h1>
    <div>
      <span id="adminEmail" style="margin-right: 15px;"></span>
      <button class="action-btn btn-danger" onclick="handleLogout()">Выйти</button>
    </div>
  </div>

  <div class="admin-nav">
    <button onclick="showSection('dashboard')" class="active" id="nav-dashboard">📊 Дашборд</button>
    <button onclick="showSection('users')" id="nav-users">👥 Пользователи</button>
    <button onclick="showSection('leads')" id="nav-leads">📋 Заявки</button>
    <button onclick="showSection('logs')" id="nav-logs">📝 Логи</button>
  </div>

  <div id="errorContainer"></div>

  <!-- ДАШБОРД -->
  <div id="section-dashboard" class="section active">
    <div class="stats-grid" id="statsGrid">
      <div class="loading">Загрузка статистики...</div>
    </div>
  </div>

  <!-- ПОЛЬЗОВАТЕЛИ -->
  <div id="section-users" class="section">
    <input type="text" class="search-box" id="userSearch" placeholder="🔍 Поиск по email..." oninput="loadUsers(1)">
    <table class="data-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Email</th>
          <th>Роль</th>
          <th>Статус</th>
          <th>Создан</th>
          <th>Действия</th>
        </tr>
      </thead>
      <tbody id="usersTableBody">
        <tr><td colspan="6" class="loading">Загрузка...</td></tr>
      </tbody>
    </table>
    <div class="pagination" id="usersPagination"></div>
  </div>

  <!-- ЗАЯВКИ -->
  <div id="section-leads" class="section">
    <input type="text" class="search-box" id="leadSearch" placeholder="🔍 Поиск по имени или email..." oninput="loadLeads(1)">
    <table class="data-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>ФИО</th>
          <th>Email</th>
          <th>Время формы</th>
          <th>Создана</th>
          <th>Действия</th>
        </tr>
      </thead>
      <tbody id="leadsTableBody">
        <tr><td colspan="6" class="loading">Загрузка...</td></tr>
      </tbody>
    </table>
    <div class="pagination" id="leadsPagination"></div>
  </div>

  <!-- ЛОГИ -->
  <div id="section-logs" class="section">
    <table class="data-table">
      <thead>
        <tr>
          <th>Время</th>
          <th>Админ</th>
          <th>Действие</th>
          <th>Объект</th>
          <th>IP</th>
        </tr>
      </thead>
      <tbody id="logsTableBody">
        <tr><td colspan="5" class="loading">Загрузка...</td></tr>
      </tbody>
    </table>
    <div class="pagination" id="logsPagination"></div>
  </div>
</div>

<!-- Модальное окно подтверждения -->
<div class="modal-overlay" id="confirmModal">
  <div class="modal">
    <h3 id="modalTitle">Подтверждение</h3>
    <p id="modalMessage">Вы уверены?</p>
    <div class="modal-actions">
      <button class="action-btn" onclick="closeModal()">Отмена</button>
      <button class="action-btn btn-danger" id="modalConfirmBtn">Подтвердить</button>
    </div>
  </div>
</div>

<script>
const API_BASE = 'https://wordpress.cubinez.ru/api';
let currentToken = null;
let currentUser = null;
let searchTimeout = null;

// Проверка авторизации
document.addEventListener('DOMContentLoaded', async function() {
    try {
        currentToken = localStorage.getItem('token');
        currentUser = JSON.parse(localStorage.getItem('user') || 'null');
    } catch (e) {
        console.error('Ошибка чтения localStorage:', e);
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/login';
        return;
    }
    
    if (!currentToken || !currentUser) {
        window.location.href = '/login';
        return;
    }
    
    // Проверка, что пользователь - админ
    try {
        const response = await fetch(`${API_BASE}/me`, {
            headers: { 'Authorization': `Bearer ${currentToken}` }
        });
        
        if (!response.ok) {
            throw new Error('Нет доступа');
        }
        
        const data = await response.json();
        
        if (!data.user) {
            throw new Error('Пользователь не найден');
        }
        
        // Обновляем currentUser с актуальными данными
        currentUser = data.user;
        localStorage.setItem('user', JSON.stringify(currentUser));
        
        if (!currentUser.is_admin) {
            showError('У вас нет прав администратора');
            setTimeout(() => window.location.href = '/login', 2000);
            return;
        }
    } catch (error) {
        console.error('Ошибка проверки:', error);
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/login';
        return;
    }
    
    document.getElementById('adminEmail').textContent = currentUser.email;
    loadDashboard();
});

function showError(msg) {
    const container = document.getElementById('errorContainer');
    container.innerHTML = `<div class="error-msg">${msg}</div>`;
    setTimeout(() => container.innerHTML = '', 5000);
}

function showSection(name) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.admin-nav button').forEach(b => b.classList.remove('active'));
    document.getElementById(`section-${name}`).classList.add('active');
    document.getElementById(`nav-${name}`).classList.add('active');
    
    // Показываем индикатор загрузки
    const section = document.getElementById(`section-${name}`);
    const loadingHtml = '<div class="loading">Загрузка...</div>';
    
    if (name === 'dashboard') {
        document.getElementById('statsGrid').innerHTML = loadingHtml;
        loadDashboard();
    } else if (name === 'users') {
        document.getElementById('usersTableBody').innerHTML = `<tr><td colspan="6">${loadingHtml}</td></tr>`;
        loadUsers(1);
    } else if (name === 'leads') {
        document.getElementById('leadsTableBody').innerHTML = `<tr><td colspan="6">${loadingHtml}</td></tr>`;
        loadLeads(1);
    } else if (name === 'logs') {
        document.getElementById('logsTableBody').innerHTML = `<tr><td colspan="5">${loadingHtml}</td></tr>`;
        loadLogs(1);
    }
}

async function apiRequest(url, options = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 секунд таймаут
    
    try {
        const response = await fetch(`${API_BASE}${url}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${currentToken}`,
                ...options.headers
            },
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (response.status === 401) {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            window.location.href = '/login';
            throw new Error('Сессия истекла');
        }
        
        if (response.status === 403) {
            throw new Error('Доступ запрещён');
        }
        
        let data;
        try {
            data = await response.json();
        } catch (e) {
            throw new Error('Сервер вернул некорректный ответ');
        }
        
        if (!response.ok) {
            throw new Error(data.error || 'Ошибка сервера');
        }
        
        return data;
    } catch (error) {
        clearTimeout(timeoutId);
        
        if (error.name === 'AbortError') {
            throw new Error('Превышено время ожидания ответа');
        }
        
        if (error.message === 'Failed to fetch') {
            throw new Error('Нет соединения с сервером');
        }
        
        throw error;
    }
}

// ДАШБОРД
async function loadDashboard() {
    try {
        const data = await apiRequest('/admin/stats');
        
        if (!data.stats) {
            throw new Error('Некорректный формат данных');
        }
        
        const s = data.stats;
        document.getElementById('statsGrid').innerHTML = `
            <div class="stat-card"><div class="value">${s.total_users || 0}</div><div class="label">Всего пользователей</div></div>
            <div class="stat-card"><div class="value">${s.active_users || 0}</div><div class="label">Активных</div></div>
            <div class="stat-card"><div class="value">${s.admin_count || 0}</div><div class="label">Администраторов</div></div>
            <div class="stat-card"><div class="value">${s.total_leads || 0}</div><div class="label">Всего заявок</div></div>
            <div class="stat-card"><div class="value">${s.today_leads || 0}</div><div class="label">Заявок сегодня</div></div>
            <div class="stat-card"><div class="value">${s.recent_leads_7d || 0}</div><div class="label">Заявок за 7 дней</div></div>
        `;
    } catch (error) {
        showError('Ошибка загрузки статистики: ' + error.message);
        document.getElementById('statsGrid').innerHTML = '<div class="error-msg">Не удалось загрузить статистику</div>';
    }
}

// ПОЛЬЗОВАТЕЛИ
async function loadUsers(page = 1) {
    const search = document.getElementById('userSearch').value;
    try {
        const data = await apiRequest(`/admin/users?page=${page}&per_page=20&search=${encodeURIComponent(search)}`);
        const tbody = document.getElementById('usersTableBody');
        
        if (!data.users || data.users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center">Ничего не найдено</td></tr>';
            document.getElementById('usersPagination').innerHTML = '';
        } else {
            tbody.innerHTML = data.users.map(u => `
                <tr>
                    <td>${u.id}</td>
                    <td>${u.email}</td>
                    <td>${u.is_admin ? '<span class="badge badge-warning">Админ</span>' : '<span class="badge badge-info">Пользователь</span>'}</td>
                    <td>${u.is_active ? '<span class="badge badge-success">Активен</span>' : '<span class="badge badge-danger">Заблокирован</span>'}</td>
                    <td>${formatDate(u.created_at)}</td>
                    <td>
                        ${u.id !== currentUser.id ? `
                            <button class="action-btn ${u.is_active ? 'btn-warning' : 'btn-primary'}" 
                                    onclick="toggleUserActive(${u.id}, '${u.email}', ${u.is_active})">
                                ${u.is_active ? 'Блокировать' : 'Разблокировать'}
                            </button>
                            <button class="action-btn btn-warning" 
                                    onclick="toggleUserAdmin(${u.id}, '${u.email}', ${u.is_admin})">
                                ${u.is_admin ? 'Снять админа' : 'Назначить админом'}
                            </button>
                            <button class="action-btn btn-danger" 
                                    onclick="deleteUser(${u.id}, '${u.email}')">
                                Удалить
                            </button>
                        ` : '<span style="color:#7f8c8d;font-size:12px">Это вы</span>'}
                    </td>
                </tr>
            `).join('');
            
            if (data.pagination) {
                renderPagination('usersPagination', data.pagination, 'loadUsers');
            }
        }
    } catch (error) {
        showError('Ошибка загрузки пользователей: ' + error.message);
        document.getElementById('usersTableBody').innerHTML = '<tr><td colspan="6" class="error-msg">Ошибка загрузки</td></tr>';
    }
}

async function toggleUserActive(id, email, currentStatus) {
    const action = currentStatus ? 'заблокировать' : 'разблокировать';
    if (!confirm(`Вы уверены, что хотите ${action} пользователя ${email}?`)) return;
    
    try {
        await apiRequest(`/admin/users/${id}/toggle-active`, { method: 'POST' });
        loadUsers(1);
    } catch (error) {
        showError(error.message);
    }
}

async function toggleUserAdmin(id, email, currentStatus) {
    const action = currentStatus ? 'снять права администратора' : 'назначить администратором';
    if (!confirm(`Вы уверены, что хотите ${action} для ${email}?`)) return;
    
    try {
        await apiRequest(`/admin/users/${id}/toggle-admin`, { method: 'POST' });
        loadUsers(1);
    } catch (error) {
        showError(error.message);
    }
}

async function deleteUser(id, email) {
    if (!confirm(`ВНИМАНИЕ! Вы уверены, что хотите БЕЗВОЗВРАТНО удалить пользователя ${email}?`)) return;
    
    try {
        await apiRequest(`/admin/users/${id}`, { method: 'DELETE' });
        loadUsers(1);
    } catch (error) {
        showError(error.message);
    }
}

// ЗАЯВКИ
async function loadLeads(page = 1) {
    const search = document.getElementById('leadSearch').value;
    try {
        const data = await apiRequest(`/admin/leads?page=${page}&per_page=20&search=${encodeURIComponent(search)}`);
        const tbody = document.getElementById('leadsTableBody');
        
        if (!data.leads || data.leads.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center">Ничего не найдено</td></tr>';
            document.getElementById('leadsPagination').innerHTML = '';
        } else {
            tbody.innerHTML = data.leads.map(l => `
                <tr>
                    <td>${l.id}</td>
                    <td>${l.full_name || '-'}</td>
                    <td>${l.email || '-'}</td>
                    <td>${l.timestamp || '-'}</td>
                    <td>${formatDate(l.created_at)}</td>
                    <td>
                        <button class="action-btn btn-danger" onclick="deleteLead(${l.id})">Удалить</button>
                    </td>
                </tr>
            `).join('');
            
            if (data.pagination) {
                renderPagination('leadsPagination', data.pagination, 'loadLeads');
            }
        }
    } catch (error) {
        showError('Ошибка загрузки заявок: ' + error.message);
        document.getElementById('leadsTableBody').innerHTML = '<tr><td colspan="6" class="error-msg">Ошибка загрузки</td></tr>';
    }
}

async function deleteLead(id) {
    if (!confirm(`Удалить заявку #${id}?`)) return;
    try {
        await apiRequest(`/admin/leads/${id}`, { method: 'DELETE' });
        loadLeads(1);
    } catch (error) {
        showError(error.message);
    }
}

// ЛОГИ
async function loadLogs(page = 1) {
    try {
        const data = await apiRequest(`/admin/logs?page=${page}&per_page=50`);
        const tbody = document.getElementById('logsTableBody');
        
        if (!data.logs || data.logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center">Логов нет</td></tr>';
            document.getElementById('logsPagination').innerHTML = '';
        } else {
            tbody.innerHTML = data.logs.map(l => `
                <tr>
                    <td>${formatDate(l.created_at)}</td>
                    <td>${l.admin_email || 'unknown'}</td>
                    <td><span class="badge badge-info">${l.action || '-'}</span></td>
                    <td>${l.target_type || '-'} #${l.target_id || '-'}</td>
                    <td>${l.ip_address || '-'}</td>
                </tr>
            `).join('');
            
            if (data.pagination) {
                renderPagination('logsPagination', data.pagination, 'loadLogs');
            }
        }
    } catch (error) {
        showError('Ошибка загрузки логов: ' + error.message);
        document.getElementById('logsTableBody').innerHTML = '<tr><td colspan="5" class="error-msg">Ошибка загрузки</td></tr>';
    }
}

function renderPagination(containerId, pagination, functionName) {
    const container = document.getElementById(containerId);
    
    if (!pagination || !pagination.total_pages || pagination.total_pages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    const currentPage = pagination.page || 1;
    const totalPages = pagination.total_pages;
    
    let html = '';
    html += `<button ${currentPage === 1 ? 'disabled' : ''} onclick="${functionName}(${currentPage - 1})">←</button>`;
    
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || Math.abs(i - currentPage) <= 2) {
            html += `<button class="${i === currentPage ? 'active' : ''}" onclick="${functionName}(${i})">${i}</button>`;
        } else if (Math.abs(i - currentPage) === 3) {
            html += `<button disabled>...</button>`;
        }
    }
    
    html += `<button ${currentPage === totalPages ? 'disabled' : ''} onclick="${functionName}(${currentPage + 1})">→</button>`;
    container.innerHTML = html;
}

function formatDate(dateString) {
    if (!dateString) return '-';
    try {
        const date = new Date(dateString);
        return date.toLocaleString('ru-RU', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (e) {
        return dateString;
    }
}

// Debounce для поиска
function handleSearch(inputId, loadFunction) {
    if (searchTimeout) {
        clearTimeout(searchTimeout);
    }
    searchTimeout = setTimeout(() => {
        loadFunction(1);
    }, 500); // 500ms задержка
}

// Модальное окно
function closeModal() {
    document.getElementById('confirmModal').classList.remove('active');
}

function showModal(title, message, onConfirm) {
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalMessage').textContent = message;
    document.getElementById('confirmModal').classList.add('active');
    
    const confirmBtn = document.getElementById('modalConfirmBtn');
    confirmBtn.onclick = function() {
        closeModal();
        onConfirm();
    };
}

async function handleLogout() {
    if (!confirm('Вы уверены, что хотите выйти?')) return;
    
    try {
        // Вызываем API для инвалидации токена
        await apiRequest('/logout', { method: 'POST' });
    } catch (error) {
        console.error('Ошибка при выходе:', error);
    } finally {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/login';
    }
}

// Обработчики поиска с debounce
document.getElementById('userSearch').addEventListener('input', function() {
    handleSearch('userSearch', loadUsers);
});

document.getElementById('leadSearch').addEventListener('input', function() {
    handleSearch('leadSearch', loadLeads);
});
</script>

# change-password-first
<style>
  .force-change-container {
    max-width: 500px;
    margin: 50px auto;
    padding: 30px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    font-family: Arial, sans-serif;
  }
  .force-change-container h2 {
    text-align: center;
    color: #2c3e50;
    margin-bottom: 10px;
  }
  .force-change-container .warning {
    background: #fff3cd;
    border-left: 4px solid #f39c12;
    padding: 15px;
    margin-bottom: 20px;
    border-radius: 4px;
    color: #856404;
  }
  .force-change-container label {
    display: block;
    margin: 12px 0 4px;
    font-weight: bold;
    color: #333;
  }
  .force-change-container input {
    width: 100%;
    padding: 12px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 16px;
    box-sizing: border-box;
  }
  .force-change-container button {
    width: 100%;
    padding: 12px;
    background: #27ae60;
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 16px;
    cursor: pointer;
    margin-top: 20px;
    font-weight: bold;
  }
  .force-change-container button:hover {
    background: #229954;
  }
  .force-change-container button:disabled {
    background: #95a5a6;
    cursor: not-allowed;
  }
  .password-wrapper {
    position: relative;
  }
  .toggle-password {
    position: absolute;
    right: 10px;
    top: 50%;
    transform: translateY(-50%);
    cursor: pointer;
    color: #666;
    user-select: none;
    font-size: 14px;
  }
  .password-requirements {
    background: #f8f9fa;
    padding: 15px;
    border-radius: 4px;
    margin: 15px 0;
    font-size: 14px;
  }
  .password-requirements ul {
    margin: 5px 0;
    padding-left: 20px;
    list-style: none;
  }
  .password-requirements li {
    margin: 3px 0;
  }
  .requirement-met {
    color: #27ae60;
  }
  .requirement-not-met {
    color: #e74c3c;
  }
  .message {
    margin-top: 15px;
    padding: 10px;
    border-radius: 4px;
    text-align: center;
  }
  .error { background: #ffecec; color: #d32f2f; }
  .success { background: #e8f5e9; color: #2e7d32; }
  .loading-overlay {
    text-align: center;
    padding: 30px;
    color: #7f8c8d;
  }
</style>

<div class="force-change-container">
  <div class="loading-overlay" id="loadingBlock">⏳ Проверка доступа...</div>
  
  <div id="formBlock" style="display: none;">
    <h2>🔐 Установите новый пароль</h2>
    
    <div class="warning">
      <strong>⚠️ Важно!</strong><br>
      Для безопасности необходимо установить новый постоянный пароль. 
      Временный пароль из письма больше не будет работать после этой операции.
    </div>

    <label for="newPassword">Новый пароль *</label>
    <div class="password-wrapper">
      <input type="password" id="newPassword" placeholder="Минимум 6 символов" oninput="checkPasswordStrength()">
      <span class="toggle-password" onclick="togglePassword('newPassword', this)">👁️</span>
    </div>
    
    <div class="password-requirements">
      <strong>Требования к паролю:</strong>
      <ul>
        <li id="req-length" class="requirement-not-met">✗ Минимум 6 символов</li>
        <li id="req-letter" class="requirement-not-met">✗ Содержит букву</li>
        <li id="req-digit" class="requirement-not-met">✗ Содержит цифру</li>
      </ul>
    </div>

    <label for="confirmPassword">Подтвердите пароль *</label>
    <div class="password-wrapper">
      <input type="password" id="confirmPassword" placeholder="Повторите пароль" oninput="checkPasswordMatch()">
      <span class="toggle-password" onclick="togglePassword('confirmPassword', this)">👁️</span>
    </div>
    <div id="matchError" style="color: #e74c3c; font-size: 14px; margin-top: 5px;"></div>

    <button onclick="handleForceChange()" id="submitBtn">Установить новый пароль</button>
    
    <div id="message"></div>
  </div>
</div>

<script>
const API_BASE = 'https://wordpress.cubinez.ru/api';

// Показать/скрыть пароль
function togglePassword(inputId, toggleEl) {
    const input = document.getElementById(inputId);
    if (input.type === 'password') {
        input.type = 'text';
        toggleEl.textContent = '🙈';
    } else {
        input.type = 'password';
        toggleEl.textContent = '👁️';
    }
}

// Проверка авторизации и флага must_change_password
document.addEventListener('DOMContentLoaded', async function() {
    const token = localStorage.getItem('token');
    let user = null;
    
    try {
        user = JSON.parse(localStorage.getItem('user') || 'null');
    } catch (e) {
        localStorage.removeItem('user');
    }
    
    // Если нет токена — редирект на login
    if (!token || !user) {
        window.location.href = '/login';
        return;
    }
    
    // Проверяем актуальный статус пользователя через API
    try {
        const response = await fetch(`${API_BASE}/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            throw new Error('Не авторизован');
        }
        
        const data = await response.json();
        
        if (!data.user) {
            throw new Error('Пользователь не найден');
        }
        
        // Обновляем данные пользователя
        localStorage.setItem('user', JSON.stringify(data.user));
        user = data.user;
        
        // Если флаг сброшен — редирект на главную (или /main для обычных пользователей)
        if (user.must_change_password === false) {
            if (user.is_admin === true || user.email === 'cubinez85@cubinez.ru') {
                window.location.href = '/admin';
            } else {
                window.location.href = '/main';
            }
            return;
        }
        
        // Показываем форму
        document.getElementById('loadingBlock').style.display = 'none';
        document.getElementById('formBlock').style.display = 'block';
        
    } catch (error) {
        console.error('Ошибка проверки:', error);
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/login';
    }
});

function checkPasswordStrength() {
    const password = document.getElementById('newPassword').value;
    
    const lengthReq = document.getElementById('req-length');
    const letterReq = document.getElementById('req-letter');
    const digitReq = document.getElementById('req-digit');
    
    if (password.length >= 6) {
        lengthReq.textContent = '✓ Минимум 6 символов';
        lengthReq.className = 'requirement-met';
    } else {
        lengthReq.textContent = '✗ Минимум 6 символов';
        lengthReq.className = 'requirement-not-met';
    }
    
    if (/[a-zA-Zа-яА-ЯёЁ]/.test(password)) {
        letterReq.textContent = '✓ Содержит букву';
        letterReq.className = 'requirement-met';
    } else {
        letterReq.textContent = '✗ Содержит букву';
        letterReq.className = 'requirement-not-met';
    }
    
    if (/\d/.test(password)) {
        digitReq.textContent = '✓ Содержит цифру';
        digitReq.className = 'requirement-met';
    } else {
        digitReq.textContent = '✗ Содержит цифру';
        digitReq.className = 'requirement-not-met';
    }
    
    checkPasswordMatch();
}

function checkPasswordMatch() {
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const matchError = document.getElementById('matchError');
    
    if (confirmPassword && newPassword !== confirmPassword) {
        matchError.textContent = '❌ Пароли не совпадают';
    } else if (confirmPassword && newPassword === confirmPassword) {
        matchError.innerHTML = '<span style="color:#27ae60">✓ Пароли совпадают</span>';
    } else {
        matchError.textContent = '';
    }
}

async function handleForceChange() {
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const messageDiv = document.getElementById('message');
    const submitBtn = document.getElementById('submitBtn');
    const token = localStorage.getItem('token');

    // Валидация
    if (!newPassword || !confirmPassword) {
        messageDiv.innerHTML = '<div class="message error">❌ Заполните все поля</div>';
        return;
    }

    if (newPassword.length < 6) {
        messageDiv.innerHTML = '<div class="message error">❌ Пароль должен быть не менее 6 символов</div>';
        return;
    }

    if (!/[a-zA-Zа-яА-ЯёЁ]/.test(newPassword)) {
        messageDiv.innerHTML = '<div class="message error">❌ Пароль должен содержать хотя бы одну букву</div>';
        return;
    }

    if (!/\d/.test(newPassword)) {
        messageDiv.innerHTML = '<div class="message error">❌ Пароль должен содержать хотя бы одну цифру</div>';
        return;
    }

    if (newPassword !== confirmPassword) {
        messageDiv.innerHTML = '<div class="message error">❌ Пароли не совпадают</div>';
        return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Сохранение...';
    messageDiv.innerHTML = '';

    try {
        const response = await fetch(`${API_BASE}/force-change-password`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                new_password: newPassword,
                confirm_password: confirmPassword
            })
        });

        let result;
        try {
            result = await response.json();
        } catch (e) {
            throw new Error('Сервер вернул некорректный ответ');
        }

        if (response.ok) {
            messageDiv.innerHTML = '<div class="message success">✅ Пароль успешно установлен! Перенаправление на страницу входа...</div>';
            
            // Очищаем токен и редиректим на /login с параметром
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            
            setTimeout(() => {
                window.location.href = '/login?password_changed=1';
            }, 2000);
        } else {
            const errorMsg = result.error || result.message || 'Неизвестная ошибка';
            messageDiv.innerHTML = `<div class="message error">❌ ${errorMsg}</div>`;
            submitBtn.disabled = false;
            submitBtn.textContent = 'Установить новый пароль';
        }
    } catch (error) {
        console.error('Ошибка:', error);
        messageDiv.innerHTML = `<div class="message error">❌ Ошибка: ${error.message || 'Попробуйте ещё раз'}</div>`;
        submitBtn.disabled = false;
        submitBtn.textContent = 'Установить новый пароль';
    }
}
</script>

# forgot-password
<style>
  .wp-reset-form {
    max-width: 500px;
    margin: 50px auto;
    font-family: Arial, sans-serif;
    padding: 30px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    box-sizing: border-box;
  }
  .wp-reset-form h3 {
    text-align: center;
    margin-bottom: 20px;
    color: #333;
  }
  .wp-reset-form .info-block {
    background: #e3f2fd;
    border-left: 4px solid #2196f3;
    padding: 15px;
    margin-bottom: 20px;
    border-radius: 4px;
    color: #1565c0;
    font-size: 14px;
  }
  .wp-reset-form label {
    display: block;
    margin: 12px 0 4px;
    font-weight: bold;
    color: #333;
  }
  .wp-reset-form input {
    width: 100%;
    padding: 12px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 16px;
    box-sizing: border-box;
  }
  .wp-reset-form button {
    background: #007bff;
    color: white;
    border: none;
    padding: 12px 20px;
    font-size: 16px;
    border-radius: 4px;
    cursor: pointer;
    width: 100%;
    margin-top: 20px;
    font-weight: bold;
  }
  .wp-reset-form button:hover {
    background: #0056b3;
  }
  .wp-reset-form button:disabled {
    background: #95a5a6;
    cursor: not-allowed;
  }
  .wp-reset-form .message {
    margin-top: 15px;
    padding: 12px;
    border-radius: 4px;
    text-align: center;
  }
  .wp-reset-form .error {
    background: #ffecec;
    color: #d32f2f;
  }
  .wp-reset-form .success {
    background: #e8f5e9;
    color: #2e7d32;
  }
  .wp-reset-form .success a {
    color: #2e7d32;
    font-weight: bold;
    text-decoration: underline;
  }
  .wp-reset-form .links {
    text-align: center;
    margin-top: 20px;
  }
  .wp-reset-form .links a {
    color: #007bff;
    text-decoration: none;
  }
  .wp-reset-form .links a:hover {
    text-decoration: underline;
  }
</style>

<div class="wp-reset-form">
  <h3>🔑 Восстановление пароля</h3>
  
  <div class="info-block">
    <strong>ℹ️ Как это работает:</strong><br>
    Введите email, указанный при регистрации. Мы отправим ссылку для установки нового пароля. 
    Ссылка действительна в течение 1 часа.
  </div>

  <label for="fpEmail">Электронная почта *</label>
  <input type="email" id="fpEmail" placeholder="example@mail.ru" required="">

  <button type="button" onclick="requestPasswordReset()" id="fpBtn">Отправить ссылку</button>
  <div id="fpMessage"></div>
  
  <div class="links">
    <a href="/login">← Вернуться к входу</a>
  </div>
</div>

<script>
const API_BASE = 'https://wordpress.cubinez.ru/api';

async function requestPasswordReset() {
    const email = document.getElementById('fpEmail').value.trim().toLowerCase();
    const msgDiv = document.getElementById('fpMessage');
    const btn = document.getElementById('fpBtn');

    // Валидация
    if (!email) {
        msgDiv.innerHTML = '<div class="message error">❌ Пожалуйста, введите email</div>';
        return;
    }
    
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        msgDiv.innerHTML = '<div class="message error">❌ Введите корректный email</div>';
        return;
    }

    // Блокируем кнопку
    btn.disabled = true;
    btn.textContent = 'Отправка...';
    msgDiv.innerHTML = '';

    try {
        const response = await fetch(`${API_BASE}/forgot-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });

        let result;
        try {
            result = await response.json();
        } catch (e) {
            throw new Error('Сервер вернул некорректный ответ');
        }

        const isSuccess = response.status === 200;

        if (isSuccess) {
            // ✅ ИСПРАВЛЕНО: правильная ссылка на /login
            msgDiv.innerHTML = `
                <div class="message success">
                    ✅ ${result.message || 'Если email зарегистрирован в системе, ссылка для сброса пароля отправлена.'}<br><br>
                    <a href="/login">← Вернуться к входу</a>
                </div>
            `;
            
            // ✅ ИСПРАВЛЕНО: редирект на /login, а не на главную
            setTimeout(() => {
                window.location.href = '/login';
            }, 5000);
        } else {
            msgDiv.innerHTML = `
                <div class="message error">
                    ❌ ${result.error || 'Произошла ошибка. Попробуйте позже.'}
                </div>
            `;
            btn.disabled = false;
            btn.textContent = 'Отправить ссылку';
        }
    } catch (error) {
        console.error('Ошибка:', error);
        msgDiv.innerHTML = `<div class="message error">❌ Ошибка: ${error.message || 'Не удалось подключиться к серверу'}</div>`;
        btn.disabled = false;
        btn.textContent = 'Отправить ссылку';
    }
}

// Enter для отправки
document.getElementById('fpEmail').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') requestPasswordReset();
});
</script>

# login
<style>
  .auth-container {
    max-width: 500px;
    margin: 50px auto;
    padding: 30px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    font-family: Arial, sans-serif;
  }
  .auth-container h2 {
    text-align: center;
    margin-bottom: 20px;
    color: #333;
  }
  .auth-container input {
    width: 100%;
    padding: 12px;
    margin: 10px 0;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 16px;
    box-sizing: border-box;
  }
  .auth-container button {
    width: 100%;
    padding: 12px;
    background: #007bff;
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 16px;
    cursor: pointer;
    margin-top: 10px;
    font-weight: bold;
  }
  .auth-container button:hover {
    background: #0056b3;
  }
  .auth-container button:disabled {
    background: #95a5a6;
    cursor: not-allowed;
  }
  .auth-container .message {
    margin-top: 15px;
    padding: 10px;
    border-radius: 4px;
    text-align: center;
  }
  .auth-container .error {
    background: #ffecec;
    color: #d32f2f;
  }
  .auth-container .success {
    background: #e8f5e9;
    color: #2e7d32;
  }
  .auth-container .links {
    text-align: center;
    margin-top: 15px;
  }
  .auth-container .links a {
    color: #007bff;
    text-decoration: none;
  }
  .auth-container .links a:hover {
    text-decoration: underline;
  }
</style>

<div class="auth-container">
  <h2>🔐 Вход в систему</h2>
  <input type="email" id="loginEmail" placeholder="Email" required="">
  <input type="password" id="loginPassword" placeholder="Пароль" required="">
  <button onclick="handleLogin()" id="loginBtn">Войти</button>
  <div id="loginMessage"></div>
  <div class="links">
    <a href="/forgot-password">Забыли пароль?</a>
  </div>
</div>

<script>
const API_BASE = 'https://wordpress.cubinez.ru/api';

document.addEventListener('DOMContentLoaded', async function() {
    // ✅ Проверяем, пришёл ли пользователь после смены пароля
    const urlParams = new URLSearchParams(window.location.search);
    const passwordChanged = urlParams.get('password_changed');
    
    if (passwordChanged === '1') {
        const messageDiv = document.getElementById('loginMessage');
        messageDiv.innerHTML = '<div class="message success">✅ Пароль успешно изменён! Войдите с новым паролем.</div>';
        window.history.replaceState({}, document.title, '/login');
        return;
    }
    
    // Обычная проверка токена
    const token = localStorage.getItem('token');
    let user = null;
    
    try {
        user = JSON.parse(localStorage.getItem('user') || 'null');
    } catch (e) {
        localStorage.removeItem('user');
    }
    
    if (!token || !user) return;
    
    try {
        const response = await fetch(`${API_BASE}/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            return;
        }
        
        const data = await response.json();
        if (!data.user) return;
        
        localStorage.setItem('user', JSON.stringify(data.user));
        redirectToUserHome(data.user);
        
    } catch (error) {
        console.error('Ошибка проверки токена:', error);
    }
});

function redirectToUserHome(user) {
    if (user.must_change_password === true) {
        window.location.href = '/change-password-first';
        return;
    }
    
    if (user.is_active === false) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        showMessage('❌ Ваш аккаунт заблокирован. Обратитесь к администратору.', 'error');
        return;
    }
    
    if (user.is_admin === true || user.email === 'cubinez85@cubinez.ru') {
        window.location.href = '/admin';
        return;
    }
    
    window.location.href = '/main';
}

function showMessage(html, type) {
    document.getElementById('loginMessage').innerHTML = `<div class="message ${type}">${html}</div>`;
}

async function handleLogin() {
    const email = document.getElementById('loginEmail').value.trim().toLowerCase();
    const password = document.getElementById('loginPassword').value;
    const loginBtn = document.getElementById('loginBtn');
    const messageDiv = document.getElementById('loginMessage');

    if (!email || !password) {
        showMessage('❌ Заполните все поля', 'error');
        return;
    }
    
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        showMessage('❌ Введите корректный email', 'error');
        return;
    }

    loginBtn.disabled = true;
    loginBtn.textContent = 'Вход...';
    messageDiv.innerHTML = '';

    try {
        const response = await fetch(`${API_BASE}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        let result;
        try {
            result = await response.json();
        } catch (e) {
            throw new Error('Сервер вернул некорректный ответ');
        }

        if (response.ok && result.token && result.user) {
            localStorage.setItem('token', result.token);
            localStorage.setItem('user', JSON.stringify(result.user));
            
            showMessage('✅ Вход выполнен! Перенаправление...', 'success');
            
            setTimeout(() => {
                redirectToUserHome(result.user);
            }, 1000);
        } else {
            const errorMsg = result.error || 'Неверный email или пароль';
            showMessage(`❌ ${errorMsg}`, 'error');
            loginBtn.disabled = false;
            loginBtn.textContent = 'Войти';
        }
    } catch (error) {
        console.error('Ошибка входа:', error);
        showMessage(`❌ Ошибка: ${error.message || 'Попробуйте ещё раз'}`, 'error');
        loginBtn.disabled = false;
        loginBtn.textContent = 'Войти';
    }
}

document.getElementById('loginPassword').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') handleLogin();
});
document.getElementById('loginEmail').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') handleLogin();
});
</script>

# reset-password
<style>
  .wordpress-registration-form {
    max-width: 500px;
    margin: 0 auto;
    font-family: Arial, sans-serif;
    padding: 20px;
    box-sizing: border-box;
  }
  .wordpress-registration-form h3 {
    text-align: center;
    margin-bottom: 20px;
    color: #333;
  }
  .wordpress-registration-form label {
    display: block;
    margin: 12px 0 4px;
    font-weight: bold;
    color: #333;
  }
  .wordpress-registration-form input[type="password"] {
    width: 100%;
    padding: 10px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 16px;
    box-sizing: border-box;
  }
  .wordpress-registration-form button {
    background: #007bff;
    color: white;
    border: none;
    padding: 12px 20px;
    font-size: 16px;
    border-radius: 4px;
    cursor: pointer;
    width: 100%;
    margin-top: 20px;
  }
  .wordpress-registration-form button:hover {
    background: #0056b3;
  }
  .wordpress-registration-form .error {
    color: red;
    font-size: 14px;
    margin-top: 8px;
  }
  .wordpress-registration-form .success {
    color: green;
    font-weight: bold;
    text-align: center;
    margin-top: 15px;
  }
  .wordpress-registration-form .info {
    color: #007bff;
    text-align: center;
    margin-top: 15px;
  }
</style>

<div class="wordpress-registration-form">
  <h3>Сброс пароля</h3>
  <input type="hidden" id="resetToken" value="">

  <label for="newPassword">Новый пароль *</label>
  <input type="password" id="newPassword" minlength="6" required="">

  <label for="confirmPassword">Подтвердите пароль *</label>
  <input type="password" id="confirmPassword" minlength="6" required="">

  <button type="button" onclick="handleResetPassword()">Сохранить новый пароль</button>
  <div id="resetMessage"></div>
</div>

<script>
console.log('[RESET-PASSWORD] Скрипт загружен');

async function handleResetPassword() {
    console.log('[RESET-PASSWORD] Начало обработки');
    
    const messageDiv = document.getElementById('resetMessage');
    const tokenInput = document.getElementById('resetToken');
    const newPasswordInput = document.getElementById('newPassword');
    const confirmPasswordInput = document.getElementById('confirmPassword');

    if (!tokenInput.value) {
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token');
        if (token) {
            tokenInput.value = token;
        } else {
            messageDiv.innerHTML = '<div class="error">Ссылка недействительна</div>';
            return;
        }
    }

    const token = tokenInput.value;
    const newPassword = newPasswordInput.value;
    const confirmPassword = confirmPasswordInput.value;

    console.log('[RESET-PASSWORD] Токен:', token);
    console.log('[RESET-PASSWORD] Пароли совпадают:', newPassword === confirmPassword);

    if (newPassword !== confirmPassword) {
        messageDiv.innerHTML = '<div class="error">Пароли не совпадают</div>';
        return;
    }
    if (newPassword.length < 6) {
        messageDiv.innerHTML = '<div class="error">Пароль должен быть не менее 6 символов</div>';
        return;
    }

    try {
        messageDiv.innerHTML = '<div class="info">Отправка...</div>';
        console.log('[RESET-PASSWORD] Отправка запроса на сервер');
        
        const res = await fetch('https://wordpress.cubinez.ru/api/reset-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                token: token,
                new_password: newPassword,
                confirm_password: confirmPassword
            })
        });

        console.log('[RESET-PASSWORD] Ответ сервера:', res.status);
        const result = await res.json();
        console.log('[RESET-PASSWORD] Данные ответа:', result);

        if (res.ok) {
            console.log('[RESET-PASSWORD] Успех! Подготовка к редиректу...');
            messageDiv.innerHTML = '<div class="success">Пароль успешно изменён! Перенаправление на страницу входа через 2 секунды...</div>';
            
            const targetUrl = 'https://wordpress.cubinez.ru/login';
            console.log('[RESET-PASSWORD] Целевой URL:', targetUrl);
            console.log('[RESET-PASSWORD] Редирект через 2 секунды...');
            
            setTimeout(() => {
                console.log('[RESET-PASSWORD] Выполняю редирект на:', targetUrl);
                window.location.href = targetUrl;
            }, 2000);
        } else {
            console.log('[RESET-PASSWORD] Ошибка сервера:', result);
            messageDiv.innerHTML = `<div class="error">${result.error || 'Неизвестная ошибка'}</div>`;
        }
    } catch (err) {
        console.error('[RESET-PASSWORD] Ошибка сети:', err);
        messageDiv.innerHTML = `<div class="error">Ошибка сети: ${err.message}</div>`;
    }
}

document.addEventListener('DOMContentLoaded', function () {
    console.log('[RESET-PASSWORD] DOM загружен');
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    const tokenInput = document.getElementById('resetToken');
    const messageDiv = document.getElementById('resetMessage');

    console.log('[RESET-PASSWORD] Токен из URL:', token);

    if (!token) {
        messageDiv.innerHTML = '<div class="error">Ссылка недействительна</div>';
    } else {
        tokenInput.value = token;
        console.log('[RESET-PASSWORD] Токен установлен в hidden input');
    }
});
</script>

#Добавьте в конец functions.php:
/**
 * Защита страниц: редирект неавторизованных пользователей на /login
 */
add_action('wp_head', 'custom_auth_redirect_script', 1);
function custom_auth_redirect_script() {
    // Не добавляем скрипт в админку WordPress
    if (is_admin()) {
        return;
    }
    
    ?>
    <script>
    (function() {
        'use strict';
        
        // Страницы, которые НЕ требуют авторизации
        const PUBLIC_PAGES = [
            '/login',
            '/login/',
            '/register',
            '/register/',
            '/forgot-password',
            '/forgot-password/',
            '/reset-password',
            '/reset-password/',
            '/change-password-first',
            '/change-password-first/',
            '/wp-login.php',
            '/wp-admin/',
            '/wp-admin'
        ];
        
        // Получаем текущий путь
        const currentPath = window.location.pathname;
        
        // Проверяем, является ли текущая страница публичной
        const isPublicPage = PUBLIC_PAGES.some(page => currentPath === page || currentPath.startsWith('/wp-'));
        
        // Если это публичная страница — не делаем редирект
        if (isPublicPage) {
            return;
        }
        
        // Проверяем наличие токена в localStorage
        const token = localStorage.getItem('token');
        const userStr = localStorage.getItem('user');
        
        if (!token || !userStr) {
            // Нет токена — редирект на /login
            console.log('[AUTH] Нет токена, редирект на /login');
            window.location.href = '/login/?redirect=' + encodeURIComponent(currentPath);
            return;
        }
        
        // Проверяем валидность токена через API
        fetch('https://wordpress.cubinez.ru/api/me', {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + token,
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (response.status === 401) {
                // Токен невалиден — очищаем и редиректим
                console.log('[AUTH] Токен невалиден, редирект на /login');
                localStorage.removeItem('token');
                localStorage.removeItem('user');
                window.location.href = '/login/?redirect=' + encodeURIComponent(currentPath);
                return null;
            }
            return response.json();
        })
        .then(data => {
            if (!data || !data.user) return;
            
            // Обновляем данные пользователя
            localStorage.setItem('user', JSON.stringify(data.user));
            
            // Если нужно сменить пароль — редирект на change-password-first
            if (data.user.must_change_password === true) {
                if (!currentPath.includes('change-password-first')) {
                    window.location.href = '/change-password-first';
                }
                return;
            }
            
            // Если аккаунт заблокирован — выходим
            if (data.user.is_active === false) {
                localStorage.removeItem('token');
                localStorage.removeItem('user');
                window.location.href = '/login/?error=blocked';
                return;
            }
        })
        .catch(error => {
            console.error('[AUTH] Ошибка проверки токена:', error);
            // При ошибке сети — не редиректим, даём пользователю шанс
        });
    })();
    </script>
    <?php
}
