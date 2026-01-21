import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import re

st.set_page_config(page_title="Studio Admin", layout="wide")

# --- CSS ---
st.markdown("""
<style>
input[type="number"]::-webkit-inner-spin-button { display: none; }
a { color: #0066ff; }
</style>
""", unsafe_allow_html=True)

# --- ФУНКЦИИ ---

def format_phone(phone: str) -> str:
    """Автоматическое форматирование телефона"""
    digits = re.sub(r'\D', '', phone)
    if len(digits) >= 11 and digits.startswith('7'):
        digits = digits[1:]
    elif len(digits) == 11 and digits.startswith('8'):
        digits = digits[1:]
    
    if len(digits) >= 10:
        return f"+7 {digits[:3]} {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"
    elif len(digits) >= 7:
        return f"+7 {digits[:3]} {digits[3:6]}-{digits[6:]}"
    elif len(digits) >= 4:
        return f"+7 {digits[:3]} {digits[3:]}"
    return f"+7 {digits}"

def parse_phone(phone: str) -> str:
    """Очищает телефон для хранения"""
    return re.sub(r'\D', '', phone)[-10:]  # оставляем 10 цифр

def format_currency(x):
    return f"{int(float(x)):,.0f}".replace(",", " ") if pd.notna(x) else "0"

def format_date(d):
    return pd.to_datetime(d).strftime("%d.%m.%Y") if pd.notna(d) else ""

# --- БД ---
def init_db():
    conn = sqlite3.connect('studio.db')
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON;")
    
    c.execute('''CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT, sex TEXT, phone TEXT, vk_id TEXT, tg_id TEXT,
                    group_id INTEGER, first_order_date DATE,
                    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS services_catalog (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, min_price REAL, description TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, execution_date DATE, status TEXT, total_amount REAL DEFAULT 0,
                    FOREIGN KEY (client_id) REFERENCES clients(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER, service_name TEXT, payment_date DATE, amount REAL, hours REAL,
                    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE)''')
    conn.commit()
    conn.close()

def run_query(query, params=(), fetch=False):
    conn = sqlite3.connect('studio.db')
    c = conn.cursor()
    try:
        c.execute(query, params)
        if fetch:
            data = c.fetchall()
            cols = [d[0] for d in c.description]
            return pd.DataFrame(data, columns=cols)
        conn.commit()
        return True
    except Exception as e:
        st.error(f"БД: {e}")
        return None if fetch else False
    finally:
        conn.close()

init_db()

st.title("🎛️ CRM Студии Звукозаписи")
menu = ["Клиенты и Группы", "Прайс-лист Услуг", "Заказы", "Детализация Заказа", "ОТЧЁТЫ"]
choice = st.sidebar.selectbox("Навигация", menu)

# ====================== КЛИЕНТЫ ======================
if choice == "Клиенты и Группы":
    st.subheader("Клиенты")

    # --- Автоматическая маска телефона ---
    if 'phone_input' not in st.session_state:
        st.session_state.phone_input = ""

    def on_phone_change():
        st.session_state.phone_input = format_phone(st.session_state.phone_raw)

    with st.expander("➕ Добавить нового клиента"):
        with st.form("add_client"):
            c_name = st.text_input("Имя *")
            c_sex = st.selectbox("Пол", ["М", "Ж"])
            
            st.text_input("Телефон", key="phone_raw", on_change=on_phone_change,
                          placeholder="+7 999 123-45-67")
            phone_display = st.session_state.phone_input
            
            c_vk = st.text_input("VK ID (только цифры)", placeholder="123456789")
            c_tg = st.text_input("Telegram username", placeholder="username")
            
            groups = run_query("SELECT name FROM groups", fetch=True)
            group_list = groups['name'].tolist() if not groups.empty else []
            c_group = st.selectbox("Группа", [""] + group_list)

            if st.form_submit_button("Сохранить"):
                if c_name:
                    phone_clean = parse_phone(phone_display)
                    g_id = run_query("SELECT id FROM groups WHERE name=?", (c_group,), fetch=True)['id'].iloc[0] if c_group else None
                    
                    run_query('''INSERT INTO clients (name, sex, phone, vk_id, tg_id, group_id)
                                 VALUES (?,?,?,?,?,?)''', (c_name, c_sex, phone_clean, c_vk, c_tg, g_id))
                    st.success("Клиент добавлен")
                    st.rerun()
                else:
                    st.error("Введите имя")

    # --- Таблица клиентов ---
    search = st.text_input("Поиск")
    clients = run_query('''
        SELECT c.id, c.name, c.sex, c.phone, c.vk_id, c.tg_id, g.name as group_name, c.first_order_date
        FROM clients c LEFT JOIN groups g ON c.group_id = g.id
        WHERE ? = '' OR LOWER(c.name) LIKE LOWER(?) OR c.phone LIKE ?
    ''', ('', f'%{search}%', f'%{search}%'), fetch=True)

    if not clients.empty:
        clients['phone'] = clients['phone'].apply(lambda x: f'<a href="tel:+7{x}">{format_phone(x)}</a>' if x else "")
        clients['vk_id'] = clients['vk_id'].apply(lambda x: f'<a href="https://vk.com/id{x}" target="_blank">vk.com/id{x}</a>' if x else "")
        clients['tg_id'] = clients['tg_id'].apply(lambda x: f'<a href="https://t.me/{x}" target="_blank">@{x}</a>' if x else "")
        clients['first_order_date'] = clients['first_order_date'].apply(format_date)

        st.markdown(clients.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("Клиенты не найдены")

# ====================== ПРАЙС ======================
elif choice == "Прайс-лист Услуг":
    st.subheader("Прайс-лист")
    with st.expander("➕ Добавить услугу"):
        with st.form("add_service"):
            name = st.text_input("Название")
            price = st.number_input("Цена", min_value=0)
            desc = st.text_area("Описание")
            if st.form_submit_button("Добавить"):
                run_query("INSERT INTO services_catalog (name, min_price, description) VALUES (?,?,?)", (name, price, desc))
                st.success("Добавлено")
                st.rerun()

    services = run_query("SELECT * FROM services_catalog", fetch=True)
    if not services.empty:
        services['min_price'] = services['min_price'].apply(lambda x: f"{format_currency(x)} ₽")
        st.dataframe(services, use_container_width=True)

# ====================== ЗАКАЗЫ ======================
elif choice == "Заказы":
    # ... (оставил как в предыдущей версии, но с новым списком статусов)
    statuses = ["В работе", "Выполнен", "Оплачено", "Ожидает оплаты"]
    # ... (код из предыдущего сообщения, только status_filter использует этот список)

# ====================== ОТЧЁТЫ ======================
elif choice == "ОТЧЁТЫ":
    st.header("Отчёты (по первой оплате)")

    # Основной запрос — по order_items
    df = run_query('''
        SELECT oi.payment_date, oi.amount, o.id as order_id, c.name as client_name, g.name as group_name
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN clients c ON o.client_id = c.id
        LEFT JOIN groups g ON c.group_id = g.id
    ''', fetch=True)

    if not df.empty:
        df['payment_date'] = pd.to_datetime(df['payment_date'])
        df['year'] = df['payment_date'].dt.year
        years = sorted(df['year'].unique())

        # --- Отчёт 3: Новые клиенты по первой оплате ---
        st.subheader("3. Новые клиенты (по первой оплате)")
        sel_year = st.selectbox("Год", years, key='new_clients_year')

        new_clients = run_query('''
            SELECT 
                c.name,
                MIN(oi.payment_date) as first_payment_date,
                COUNT(DISTINCT o.id) as orders_count,
                SUM(oi.amount) as total_paid
            FROM clients c
            JOIN orders o ON c.id = o.client_id
            JOIN order_items oi ON o.id = oi.order_id
            WHERE strftime('%Y', oi.payment_date) = ?
            GROUP BY c.id
            HAVING MIN(oi.payment_date) = (
                SELECT MIN(oi2.payment_date) FROM order_items oi2 
                JOIN orders o2 ON oi2.order_id = o2.id 
                WHERE o2.client_id = c.id
            )
        ''', (str(sel_year),), fetch=True)

        if not new_clients.empty:
            new_clients['first_payment_date'] = new_clients['first_payment_date'].apply(format_date)
            new_clients['total_paid'] = new_clients['total_paid'].apply(lambda x: f"{format_currency(x)} ₽")
            st.dataframe(new_clients, use_container_width=True)
        else:
            st.info("Нет клиентов с первой оплатой в этом году")

        # Остальные отчёты (1,4,5,6,7) — оставил как раньше, но на основе payment_date

    else:
        st.warning("Нет оплат в базе")