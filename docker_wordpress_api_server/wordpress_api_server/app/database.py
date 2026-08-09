"""
Модуль для работы с базой данных PostgreSQL
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from config import POSTGRESQL_CONFIG
import logging

logger = logging.getLogger(__name__)


def get_connection():
    """Получить подключение к БД"""
    return psycopg2.connect(**POSTGRESQL_CONFIG)


def get_cursor(conn):
    """Получить курсор с RealDictCursor"""
    return conn.cursor(cursor_factory=RealDictCursor)


def get_db_connection():
    """
    Получить подключение к БД (алиас для совместимости).
    Используется в auth.py и других модулях.
    """
    return get_connection()


def execute_query(conn, query, params=None, fetch='all'):
    """
    Универсальная функция для выполнения запросов.
    
    Args:
        conn: подключение к БД
        query: SQL запрос
        params: параметры запроса (tuple/list)
        fetch: тип выборки ('all', 'one', 'none')
    
    Returns:
        Результат запроса или None
    """
    try:
        cursor = get_cursor(conn)
        cursor.execute(query, params)
        
        if fetch == 'all':
            result = cursor.fetchall()
        elif fetch == 'one':
            result = cursor.fetchone()
        else:
            conn.commit()
            result = None
        
        cursor.close()
        return result
    except Exception as e:
        logger.error(f"❌ Ошибка выполнения запроса: {e}")
        raise


def execute_insert(conn, query, params):
    """
    Выполнить INSERT и вернуть ID созданной записи.
    
    Args:
        conn: подключение к БД
        query: SQL запрос (должен содержать RETURNING id)
        params: параметры запроса
    
    Returns:
        ID созданной записи или None
    """
    try:
        cursor = get_cursor(conn)
        cursor.execute(query, params)
        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        
        if result:
            return result.get('id') if isinstance(result, dict) else result[0]
        return None
    except Exception as e:
        logger.error(f"❌ Ошибка INSERT: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise


def check_email_exists(conn, email):
    """
    Проверить, существует ли email в таблице users.
    
    Args:
        conn: подключение к БД
        email: email для проверки
    
    Returns:
        dict с данными пользователя или None
    """
    try:
        cursor = get_cursor(conn)
        cursor.execute("SELECT id, email, is_admin, is_active FROM users WHERE email = %s", (email,))
        result = cursor.fetchone()
        cursor.close()
        return result
    except Exception as e:
        logger.error(f"❌ Ошибка проверки email: {e}")
        return None


class DatabaseManager:
    """
    Менеджер базы данных с автоматическим управлением подключением.
    Используется в Worker и других модулях.
    """
    
    def __init__(self):
        self.connection = None
        self.connect()
    
    def connect(self):
        """Подключиться к БД"""
        try:
            self.connection = get_connection()
            self.connection.autocommit = False
            logger.info("✅ Подключение к PostgreSQL установлено")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к PostgreSQL: {e}")
            self.connection = None
    
    def get_cursor(self):
        """Получить курсор"""
        if not self.connection:
            raise Exception("Нет подключения к БД")
        return get_cursor(self.connection)
    
    def commit(self):
        """Зафиксировать транзакцию"""
        if self.connection:
            self.connection.commit()
    
    def rollback(self):
        """Откатить транзакцию"""
        if self.connection:
            try:
                self.connection.rollback()
            except Exception as e:
                logger.error(f"❌ Ошибка rollback: {e}")
    
    def close(self):
        """Закрыть подключение"""
        if self.connection:
            try:
                self.connection.close()
                logger.info("✅ Подключение к PostgreSQL закрыто")
            except Exception as e:
                logger.error(f"❌ Ошибка закрытия подключения: {e}")
            finally:
                self.connection = None
    
    def __enter__(self):
        """Поддержка context manager"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Автоматическое закрытие при выходе из context manager"""
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()
