import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, timedelta
import re

# --- КОНСТАНТЫ ---
STATUS_LIST = ["В работе", "Ожидает оплаты", "Выполнен", "Оплачен"]

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def format_phone(phone_str):
    """Форматирование телефона в +7 000 000-00-00"""
    if not phone_str or pd.isna(phone_str):
        return ""
    # Убираем все кроме цифр
    digits = ''.join(filter(str.isdigit, str(phone_str)))
    # Если начинается с 8, заменяем на 7
    if digits.startswith('8') and len(digits) == 11:
        digits = '7' + digits[1:]
    # Если без кода страны
    if len(digits) == 10:
        digits = '7' + digits
    # Форматируем
    if len(digits) >= 11:
        return f"+{digits[0]} {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return phone_str

def format_vk(vk_str):
    """Форматирование VK ID"""
    if not vk_str or pd.isna(vk_str):
        return ""
    vk = str(vk_str).strip()
    # Убираем лишнее
    vk = vk.replace("https://", "").replace("http://", "")
    if vk.startswith("vk.com/"):
        return vk
    if vk.startswith("id") and vk[2:].isdigit():
        return f"vk.com/{vk}"
    if vk.isdigit():
        return f"vk.com/id{vk}"
    # Если это username
    return f"vk.com/{vk}"

def format_telegram(tg_str):
    """Форматирование Telegram"""
    if not tg_str or pd.isna(tg_str):
        return ""
    tg = str(tg_str).strip()
    tg = tg.replace("https://", "").replace("http://", "").replace("@", "")
    if tg.startswith("t.me/"):
        return tg
    return f"t.me/{tg}"

def format_date_display(date_str):
    """Форматирование даты в dd.mm.yyyy"""
    if pd.isna(date_str) or date_str is None or date_str == '':
        return ""
    try:
        if isinstance(date_str, str):
            if '.' in date_str:
                return date_str
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            date_obj = pd.to_datetime(date_str)
        return date_obj.strftime("%d.%m.%Y")
    except:
        return str(date_str)

def parse_date_to_db(date_str):
    """Преобразует строку даты в формат БД"""
    if pd.isna(date_str) or not date_str or date_str == '':
        return None
    try:
        if isinstance(date_str, date):
            return date_str.strftime("%Y-%m-%d")
        if isinstance(date_str, str):
            if '.' in date_str:
                return datetime.strptime(date_str, "%d.%m.%Y").strftime("%Y-%m-%d")
            return date_str
        return pd.to_datetime(date_str).strftime("%Y-%m-%d")
    except:
        return None

def format_currency(amount):
    """Форматирование валюты"""
    if pd.isna(amount) or amount is None:
        return "0"
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)

def parse_currency(amount_str):
    """Преобразует строку в число"""
    if not amount_str or pd.isna(amount_str):
        return 0.0
    try:
        clean = str(amount_str).replace(" ", "").replace(",", "").replace("₽", "").strip()
        return float(clean) if clean else 0.0
    except:
        return 0.0

def make_clickable_phone(phone):
    """Создаёт кликабельную ссылку для телефона"""
    if not phone or pd.isna(phone):
        return ""
    digits = ''.join(filter(str.isdigit, str(phone)))
    return f'<a href="tel:+{digits}">{phone}</a>'

def make_clickable_vk(vk):
    """Создаёт кликабельную ссылку для VK"""
    if not vk or pd.isna(vk):
        return ""
    url = vk if vk.startswith("http") else f"https://{vk}"
    return f'<a href="{url}" target="_blank">{vk}</a>'

def make_clickable_tg(tg):
    """Создаёт кликабельную ссылку для Telegram"""
    if not tg or pd.isna(tg):
        return ""
    url = tg if tg.startswith("http") else f"https://{tg}"
    return f'<a href="{url}" target="_blank">{tg}</a>'

def update_client_first_order_date(client_id):
    """Обновляет дату первого заказа клиента по первой оплате"""
    result = run_query('''
        SELECT MIN(oi.payment_date) as first_payment
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE o.client_id = ? AND oi.payment_date IS NOT NULL
    ''', (client_id,), fetch=True)
    
    if not result.empty and result['first_payment'].iloc[0]:
        run_query(
            "UPDATE clients SET first_order_date = ? WHERE id = ?",
            (result['first_payment'].iloc[0], client_id)
        )

def init_db():
    conn = sqlite3.connect('studio.db')
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON;")
    
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    sex TEXT,
                    phone TEXT,
                    vk_id TEXT,
                    tg_id TEXT,
                    group_id INTEGER,
                    first_order_date DATE,
                    FOREIGN KEY (group_id) REFERENCES groups(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS services_catalog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    min_price REAL,
                    description TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER,
                    execution_date DATE,
                    status TEXT,
                    total_amount REAL DEFAULT 0,
                    FOREIGN KEY (client_id) REFERENCES clients(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER,
                    service_name TEXT,
                    payment_date DATE,
                    amount REAL,
                    hours REAL,
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
            cols = [description[0] for description in c.description]
            conn.close()
            return pd.DataFrame(data, columns=cols)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        st.error(f"Ошибка БД: {e}")
        return pd.DataFrame() if fetch else False

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Studio Admin", layout="wide")
init_db()

st.title("🎛️ CRM Студии Звукозаписи")

menu = ["Клиенты и Группы", "Прайс-лист Услуг", "Заказы", "Детализация Заказа", "ОТЧЁТЫ"]
choice = st.sidebar.selectbox("Навигация", menu)

# --- 1. КЛИЕНТЫ И ГРУППЫ ---
if choice == "Клиенты и Группы":
    st.subheader("Клиенты")
    
    # Получаем группы
    groups_df = run_query("SELECT id, name FROM groups", fetch=True)
    groups_list = groups_df['name'].tolist() if not groups_df.empty else []
    group_map = dict(zip(groups_df['name'], groups_df['id'])) if not groups_df.empty else {}
    
    # Форма добавления клиента
    with st.expander("➕ Добавить нового клиента"):
        with st.form("add_client"):
            c_name = st.text_input("Имя *", placeholder="Иван Иванов")
            c_sex = st.selectbox("Пол", ["М", "Ж"])
            
            # Телефон
            c_phone_raw = st.text_input(
                "Телефон", 
                placeholder="+7 999 123-45-67",
                help="Введите номер в любом формате, он будет автоматически отформатирован"
            )
            
            # VK ID
            c_vk_raw = st.text_input(
                "VK ID", 
                placeholder="id123456789 или username",
                help="Введите ID или username, ссылка сформируется автоматически"
            )
            
            # Telegram
            c_tg_raw = st.text_input(
                "Telegram", 
                placeholder="username (без @)",
                help="Введите username без @, ссылка сформируется автоматически"
            )
            
            # Группа
            if groups_list:
                c_group = st.selectbox("Группа", options=["Без группы"] + groups_list)
            else:
                c_group = "Без группы"
                st.info("Группы еще не созданы")
            
            if st.form_submit_button("Сохранить клиента"):
                if c_name:
                    # Форматируем поля
                    phone = format_phone(c_phone_raw) if c_phone_raw else ""
                    vk = format_vk(c_vk_raw) if c_vk_raw else ""
                    tg = format_telegram(c_tg_raw) if c_tg_raw else ""
                    g_id = group_map.get(c_group) if c_group != "Без группы" else None
                    
                    run_query('''INSERT INTO clients 
                        (name, sex, phone, vk_id, tg_id, group_id) 
                        VALUES (?,?,?,?,?,?)''', 
                        (c_name, c_sex, phone, vk, tg, g_id))
                    st.success("✅ Клиент добавлен!")
                    st.rerun()
                else:
                    st.error("Введите имя клиента")

    # Управление группами
    with st.expander("⚙️ Группы клиентов", expanded=False):
        col1, col2 = st.columns([2, 1])
        with col1:
            with st.form("add_group"):
                new_group = st.text_input("Название группы")
                if st.form_submit_button("Добавить группу"):
                    if new_group:
                        run_query("INSERT INTO groups (name) VALUES (?)", (new_group,))
                        st.success("Группа добавлена")
                        st.rerun()
        with col2:
            st.write("Список групп:")
            if not groups_df.empty:
                for idx, row in groups_df.iterrows():
                    col_a, col_b, col_c = st.columns([3, 1, 1])
                    with col_a:
                        new_name = st.text_input(
                            "Название", 
                            value=row['name'], 
                            key=f"group_name_{row['id']}",
                            label_visibility="collapsed"
                        )
                    with col_b:
                        if st.button("💾", key=f"update_{row['id']}", help="Сохранить"):
                            if new_name and new_name != row['name']:
                                run_query("UPDATE groups SET name=? WHERE id=?", (new_name, row['id']))
                                st.success("Группа обновлена")
                                st.rerun()
                    with col_c:
                        if st.button("🗑️", key=f"delete_{row['id']}", help="Удалить"):
                            clients_check = run_query(
                                "SELECT COUNT(*) as count FROM clients WHERE group_id=?", 
                                (row['id'],), 
                                fetch=True
                            )
                            if not clients_check.empty and clients_check['count'].iloc[0] > 0:
                                st.warning("Нельзя удалить группу с клиентами!")
                            else:
                                run_query("DELETE FROM groups WHERE id=?", (row['id'],))
                                st.success("Группа удалена")
                                st.rerun()
            else:
                st.info("Групп пока нет")

    # Поиск и фильтрация
    st.markdown("### 🔍 Поиск и фильтрация")
    search_col1, search_col2 = st.columns([2, 1])
    with search_col1:
        search_query = st.text_input("Поиск по имени, телефону, VK или Telegram", placeholder="Введите текст...")
    with search_col2:
        filter_group = st.selectbox("Фильтр по группе", ["Все"] + groups_list)

    # Запрос клиентов
    clients_query = '''
    SELECT 
        c.id, 
        c.name, 
        c.sex, 
        c.phone, 
        c.vk_id, 
        c.tg_id, 
        COALESCE(g.name, 'Без группы') as group_name,
        c.first_order_date
    FROM clients c 
    LEFT JOIN groups g ON c.group_id = g.id
    WHERE 1=1
    '''
    
    params = []
    
    if search_query:
        clients_query += ''' AND (LOWER(c.name) LIKE LOWER(?) OR 
                                  c.phone LIKE ? OR 
                                  LOWER(c.vk_id) LIKE LOWER(?) OR 
                                  LOWER(c.tg_id) LIKE LOWER(?))'''
        search_pattern = f'%{search_query}%'
        params.extend([search_pattern] * 4)
    
    if filter_group != "Все":
        clients_query += ' AND g.name = ?'
        params.append(filter_group)
    
    clients_query += ' ORDER BY c.id DESC'
    clients_df_data = run_query(clients_query, tuple(params), fetch=True)
    
    if not clients_df_data.empty:
        st.info(f"Найдено клиентов: {len(clients_df_data)}")
        
        # Создаём копию для отображения с кликабельными ссылками
        display_df = clients_df_data.copy()
        display_df['first_order_date'] = display_df['first_order_date'].apply(format_date_display)
        display_df['phone'] = display_df['phone'].apply(format_phone)
        display_df['vk_id'] = display_df['vk_id'].apply(format_vk)
        display_df['tg_id'] = display_df['tg_id'].apply(format_telegram)
        
        # Создаём HTML таблицу с кликабельными ссылками
        html_df = display_df.copy()
        html_df['phone'] = html_df['phone'].apply(make_clickable_phone)
        html_df['vk_id'] = html_df['vk_id'].apply(make_clickable_vk)
        html_df['tg_id'] = html_df['tg_id'].apply(make_clickable_tg)
        
        # Переименовываем колонки
        html_df.columns = ['ID', 'Имя', 'Пол', 'Телефон', 'VK', 'Telegram', 'Группа', 'Первая оплата']
        
        # Отображаем HTML таблицу
        st.markdown(
            html_df.to_html(escape=False, index=False),
            unsafe_allow_html=True
        )
        
        st.markdown("---")
        
        # Редактирование клиента
        st.markdown("### ✏️ Редактирование клиента")
        edit_id = st.selectbox(
            "Выберите клиента для редактирования",
            options=clients_df_data['id'].tolist(),
            format_func=lambda x: f"#{x} - {clients_df_data[clients_df_data['id']==x]['name'].iloc[0]}"
        )
        
        if edit_id:
            client_row = clients_df_data[clients_df_data['id'] == edit_id].iloc[0]
            
            with st.form("edit_client_form"):
                col1, col2 = st.columns(2)
                with col1:
                    edit_name = st.text_input("Имя", value=client_row['name'])
                    edit_sex = st.selectbox("Пол", ["М", "Ж"], index=0 if client_row['sex'] == "М" else 1)
                    edit_phone = st.text_input("Телефон", value=client_row['phone'] or "")
                with col2:
                    edit_vk = st.text_input("VK ID", value=client_row['vk_id'] or "")
                    edit_tg = st.text_input("Telegram", value=client_row['tg_id'] or "")
                    edit_group = st.selectbox(
                        "Группа", 
                        ["Без группы"] + groups_list,
                        index=(groups_list.index(client_row['group_name']) + 1) if client_row['group_name'] in groups_list else 0
                    )
                
                if st.form_submit_button("💾 Сохранить изменения"):
                    phone = format_phone(edit_phone) if edit_phone else ""
                    vk = format_vk(edit_vk) if edit_vk else ""
                    tg = format_telegram(edit_tg) if edit_tg else ""
                    g_id = group_map.get(edit_group) if edit_group != "Без группы" else None
                    
                    run_query('''
                        UPDATE clients 
                        SET name=?, sex=?, phone=?, vk_id=?, tg_id=?, group_id=?
                        WHERE id=?
                    ''', (edit_name, edit_sex, phone, vk, tg, g_id, edit_id))
                    st.success("✅ Клиент обновлён!")
                    st.rerun()
    else:
        st.info("Клиенты не найдены")

# --- 2. ПРАЙС-ЛИСТ ---
elif choice == "Прайс-лист Услуг":
    st.subheader("Справочник Услуг")
    
    with st.expander("➕ Добавить новую услугу"):
        with st.form("add_service"):
            s_name = st.text_input("Наименование услуги")
            s_price_str = st.text_input("Мин. прайс ₽", placeholder="10 000")
            s_desc = st.text_area("Описание")
            
            if st.form_submit_button("Добавить услугу"):
                if s_name:
                    s_price = parse_currency(s_price_str)
                    run_query("INSERT INTO services_catalog (name, min_price, description) VALUES (?,?,?)", 
                              (s_name, s_price, s_desc))
                    st.success("Услуга добавлена")
                    st.rerun()
    
    services_df = run_query("SELECT * FROM services_catalog", fetch=True)
    
    if not services_df.empty:
        # Форматируем цену для отображения
        display_services = services_df.copy()
        display_services['min_price'] = display_services['min_price'].apply(lambda x: f"{format_currency(x)} ₽")
        
        # Переименовываем колонки
        display_services.columns = ['ID', 'Услуга', 'Мин. прайс', 'Описание']
        
        st.dataframe(display_services, use_container_width=True, hide_index=True)
        
        # Редактирование услуги
        st.markdown("### ✏️ Редактирование услуги")
        edit_service_id = st.selectbox(
            "Выберите услугу",
            options=services_df['id'].tolist(),
            format_func=lambda x: f"#{x} - {services_df[services_df['id']==x]['name'].iloc[0]}"
        )
        
        if edit_service_id:
            service_row = services_df[services_df['id'] == edit_service_id].iloc[0]
            
            with st.form("edit_service_form"):
                edit_s_name = st.text_input("Наименование", value=service_row['name'])
                edit_s_price = st.text_input(
                    "Мин. прайс ₽", 
                    value=format_currency(service_row['min_price'])
                )
                edit_s_desc = st.text_area("Описание", value=service_row['description'] or "")
                
                if st.form_submit_button("💾 Сохранить"):
                    run_query('''
                        UPDATE services_catalog 
                        SET name=?, min_price=?, description=?
                        WHERE id=?
                    ''', (edit_s_name, parse_currency(edit_s_price), edit_s_desc, edit_service_id))
                    st.success("✅ Услуга обновлена!")
                    st.rerun()
    else:
        st.info("Услуги еще не добавлены")

# --- 3. ЗАКАЗЫ ---
elif choice == "Заказы":
    st.subheader("Управление Заказами")
    
    clients_df = run_query("SELECT id, name FROM clients", fetch=True)
    client_names = clients_df['name'].tolist() if not clients_df.empty else []
    client_map = dict(zip(clients_df['name'], clients_df['id'])) if not clients_df.empty else {}
    client_map_reverse = dict(zip(clients_df['id'], clients_df['name'])) if not clients_df.empty else {}

    with st.expander("➕ Создать новый заказ"):
        with st.form("new_order"):
            if client_names:
                o_client = st.selectbox("Клиент", client_names)
                o_date = st.date_input("Дата исполнения", value=date.today())
                o_status = st.selectbox("Статус", STATUS_LIST)
                
                if st.form_submit_button("Создать заказ"):
                    c_id = client_map.get(o_client)
                    run_query("INSERT INTO orders (client_id, execution_date, status) VALUES (?,?,?)", 
                              (c_id, o_date.strftime("%Y-%m-%d"), o_status))
                    st.success("✅ Заказ создан!")
                    st.rerun()
            else:
                st.warning("Сначала добавьте клиентов")

    # Фильтры
    st.markdown("### 🔍 Фильтры")
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        order_search = st.text_input("Поиск по клиенту", placeholder="Имя клиента...")
    with filter_col2:
        status_filter = st.selectbox("Статус", ["Все"] + STATUS_LIST)
    with filter_col3:
        date_filter = st.selectbox("Период", ["Все время", "Текущий месяц", "Последние 7 дней"])

    # Запрос заказов
    orders_query = '''
    SELECT 
        o.id, 
        o.client_id,
        o.execution_date,
        o.status,
        o.total_amount
    FROM orders o 
    JOIN clients c ON o.client_id = c.id
    WHERE 1=1
    '''
    params = []

    if order_search:
        orders_query += " AND LOWER(c.name) LIKE LOWER(?)"
        params.append(f"%{order_search}%")
    
    if status_filter != "Все":
        orders_query += " AND o.status = ?"
        params.append(status_filter)
    
    if date_filter == "Текущий месяц":
        current_month = date.today().replace(day=1).strftime("%Y-%m-%d")
        orders_query += " AND o.execution_date >= ?"
        params.append(current_month)
    elif date_filter == "Последние 7 дней":
        last_week = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
        orders_query += " AND o.execution_date >= ?"
        params.append(last_week)

    orders_query += " ORDER BY o.id DESC"
    orders_df = run_query(orders_query, tuple(params), fetch=True)
    
    if not orders_df.empty:
        orders_df['client_name'] = orders_df['client_id'].map(client_map_reverse)
        
        # Статистика за текущий месяц (по дате оплаты!)
        current_month_start = date.today().replace(day=1).strftime("%Y-%m-%d")
        stats_df = run_query('''
            SELECT oi.amount, o.status 
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            WHERE oi.payment_date >= ?
        ''', (current_month_start,), fetch=True)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Оплат (месяц)", len(stats_df) if not stats_df.empty else 0)
        with col2:
            total_sum = stats_df['amount'].sum() if not stats_df.empty else 0
            st.metric("Сумма оплат", f"{format_currency(total_sum)} ₽")
        with col3:
            avg_check = stats_df['amount'].mean() if not stats_df.empty and len(stats_df) > 0 else 0
            avg_text = f"{format_currency(avg_check)} ₽" if avg_check > 0 else "—"
            st.metric("Средняя оплата", avg_text)
        with col4:
            in_work = len(orders_df[orders_df['status'] == 'В работе'])
            st.metric("В работе", in_work)

        # Таблица заказов
        display_orders = orders_df[['id', 'client_name', 'execution_date', 'status', 'total_amount']].copy()
        display_orders['execution_date'] = display_orders['execution_date'].apply(format_date_display)
        display_orders['total_amount'] = display_orders['total_amount'].apply(lambda x: f"{format_currency(x)} ₽")
        display_orders.columns = ['ID', 'Клиент', 'Дата исполнения', 'Статус', 'Сумма']
        
        st.dataframe(display_orders, use_container_width=True, hide_index=True)
        
        # Редактирование заказа
        st.markdown("### ✏️ Редактирование заказа")
        edit_order_id = st.selectbox(
            "Выберите заказ",
            options=orders_df['id'].tolist(),
            format_func=lambda x: f"#{x} - {orders_df[orders_df['id']==x]['client_name'].iloc[0]}"
        )
        
        if edit_order_id:
            order_row = orders_df[orders_df['id'] == edit_order_id].iloc[0]
            
            with st.form("edit_order_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    edit_client = st.selectbox(
                        "Клиент", 
                        client_names,
                        index=client_names.index(order_row['client_name']) if order_row['client_name'] in client_names else 0
                    )
                with col2:
                    edit_date = st.date_input(
                        "Дата исполнения", 
                        value=datetime.strptime(order_row['execution_date'], "%Y-%m-%d").date()
                    )
                with col3:
                    edit_status = st.selectbox(
                        "Статус", 
                        STATUS_LIST,
                        index=STATUS_LIST.index(order_row['status']) if order_row['status'] in STATUS_LIST else 0
                    )
                
                if st.form_submit_button("💾 Сохранить"):
                    client_id = client_map.get(edit_client)
                    run_query('''
                        UPDATE orders 
                        SET client_id=?, execution_date=?, status=?
                        WHERE id=?
                    ''', (client_id, edit_date.strftime("%Y-%m-%d"), edit_status, edit_order_id))
                    st.success("✅ Заказ обновлён!")
                    st.rerun()
    else:
        st.info("Заказы не найдены")

# --- 4. ДЕТАЛИЗАЦИЯ ЗАКАЗА ---
elif choice == "Детализация Заказа":
    st.subheader("Внутренние услуги заказа")
    
    orders_df = run_query(
        "SELECT o.id, c.name, o.execution_date FROM orders o JOIN clients c ON o.client_id = c.id ORDER BY o.id DESC", 
        fetch=True
    )
    
    if not orders_df.empty:
        orders_df['label'] = orders_df.apply(
            lambda x: f"Заказ #{x['id']} - {x['name']} ({format_date_display(x['execution_date'])})", 
            axis=1
        )
        order_selection = st.selectbox("Выберите заказ", orders_df['label'])
        order_id = int(orders_df[orders_df['label'] == order_selection]['id'].iloc[0])
        
        # Получаем client_id для обновления first_order_date
        client_id_result = run_query("SELECT client_id FROM orders WHERE id=?", (order_id,), fetch=True)
        current_client_id = client_id_result['client_id'].iloc[0] if not client_id_result.empty else None

        # Услуги из каталога
        services_cat = run_query("SELECT name FROM services_catalog", fetch=True)
        srv_list = services_cat['name'].tolist() if not services_cat.empty else []
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### ➕ Добавить услугу")
            with st.form("add_item_form"):
                service_choice = st.selectbox("Услуга", srv_list if srv_list else ["Нет услуг в каталоге"])
                i_date = st.date_input("Дата оплаты", value=date.today())
                
                # Поле суммы с форматированием
                amount_str = st.text_input("Сумма ₽", value="0", placeholder="10 000")
                i_amount = parse_currency(amount_str)
                
                i_hours = st.text_input("Кол-во часов", value="0", placeholder="1.5")
                try:
                    i_hours_val = float(i_hours.replace(",", ".")) if i_hours else 0.0
                except:
                    i_hours_val = 0.0
                
                if st.form_submit_button("Добавить услугу"):
                    if service_choice and i_amount > 0:
                        run_query(
                            '''INSERT INTO order_items 
                            (order_id, service_name, payment_date, amount, hours)
                            VALUES (?,?,?,?,?)''',
                            (order_id, service_choice, i_date.strftime("%Y-%m-%d"), i_amount, i_hours_val)
                        )
                        # Обновляем сумму заказа
                        total_res = run_query(
                            "SELECT SUM(amount) as total FROM order_items WHERE order_id=?",
                            (order_id,),
                            fetch=True
                        )
                        total = total_res['total'].iloc[0] if not total_res.empty and total_res['total'].iloc[0] else 0.0
                        run_query("UPDATE orders SET total_amount=? WHERE id=?", (total, order_id))
                        
                        # Обновляем first_order_date клиента
                        if current_client_id:
                            update_client_first_order_date(current_client_id)
                        
                        st.success("✅ Услуга добавлена!")
                        st.rerun()
                    else:
                        st.error("Заполните все поля корректно")

        with col2:
            st.markdown(f"#### 📋 Состав заказа #{order_id}")
            
            items_df = run_query(
                '''SELECT id, service_name, payment_date, amount, hours 
                   FROM order_items WHERE order_id=?''',
                (order_id,),
                fetch=True
            )
            
            if not items_df.empty:
                display_items = items_df.copy()
                display_items['payment_date'] = display_items['payment_date'].apply(format_date_display)
                display_items['amount'] = display_items['amount'].apply(lambda x: f"{format_currency(x)} ₽")
                display_items['hours'] = display_items['hours'].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "0.0")
                display_items.columns = ['ID', 'Услуга', 'Дата оплаты', 'Сумма', 'Часы']
                
                st.dataframe(display_items, use_container_width=True, hide_index=True)

                # Итого
                total_amount = items_df['amount'].sum()
                st.success(f"💰 **Итого:** {format_currency(total_amount)} ₽")
                
                # Редактирование услуги
                st.markdown("---")
                st.markdown("#### ✏️ Редактировать / Удалить услугу")
                
                edit_item_id = st.selectbox(
                    "Выберите услугу",
                    options=items_df['id'].tolist(),
                    format_func=lambda x: f"#{x} - {items_df[items_df['id']==x]['service_name'].iloc[0]}"
                )
                
                if edit_item_id:
                    item_row = items_df[items_df['id'] == edit_item_id].iloc[0]
                    
                    with st.form("edit_item_form"):
                        col_a, col_b = st.columns(2)
                        with col_a:
                            edit_service = st.selectbox(
                                "Услуга",
                                srv_list,
                                index=srv_list.index(item_row['service_name']) if item_row['service_name'] in srv_list else 0
                            )
                            edit_item_date = st.date_input(
                                "Дата оплаты",
                                value=datetime.strptime(item_row['payment_date'], "%Y-%m-%d").date() if item_row['payment_date'] else date.today()
                            )
                        with col_b:
                            edit_amount = st.text_input("Сумма ₽", value=format_currency(item_row['amount']))
                            edit_hours = st.text_input("Часы", value=f"{float(item_row['hours']):.1f}" if pd.notna(item_row['hours']) else "0.0")
                        
                        col_save, col_delete = st.columns(2)
                        with col_save:
                            if st.form_submit_button("💾 Сохранить"):
                                run_query('''
                                    UPDATE order_items 
                                    SET service_name=?, payment_date=?, amount=?, hours=?
                                    WHERE id=?
                                ''', (
                                    edit_service,
                                    edit_item_date.strftime("%Y-%m-%d"),
                                    parse_currency(edit_amount),
                                    float(edit_hours.replace(",", ".")) if edit_hours else 0.0,
                                    edit_item_id
                                ))
                                
                                # Обновляем сумму заказа
                                total_res = run_query(
                                    "SELECT SUM(amount) as total FROM order_items WHERE order_id=?",
                                    (order_id,),
                                    fetch=True
                                )
                                total = total_res['total'].iloc[0] if not total_res.empty and total_res['total'].iloc[0] else 0.0
                                run_query("UPDATE orders SET total_amount=? WHERE id=?", (total, order_id))
                                
                                # Обновляем first_order_date клиента
                                if current_client_id:
                                    update_client_first_order_date(current_client_id)
                                
                                st.success("✅ Услуга обновлена!")
                                st.rerun()
                    
                    # Кнопка удаления вне формы
                    if st.button("🗑️ Удалить эту услугу", type="secondary"):
                        run_query("DELETE FROM order_items WHERE id=?", (edit_item_id,))
                        total_res = run_query(
                            "SELECT SUM(amount) as total FROM order_items WHERE order_id=?",
                            (order_id,),
                            fetch=True
                        )
                        total = total_res['total'].iloc[0] if not total_res.empty and total_res['total'].iloc[0] else 0.0
                        run_query("UPDATE orders SET total_amount=? WHERE id=?", (total, order_id))
                        
                        # Обновляем first_order_date клиента
                        if current_client_id:
                            update_client_first_order_date(current_client_id)
                        
                        st.success("🗑️ Услуга удалена!")
                        st.rerun()
            else:
                st.info("В этом заказе пока нет услуг")
    else:
        st.info("Сначала создайте заказ")

# --- 5. ОТЧЁТЫ ---
elif choice == "ОТЧЁТЫ":
    st.header("📊 Аналитические Отчёты")
    
    # Основной запрос — по дате оплаты!
    main_query = '''
    SELECT 
        oi.id as item_id,
        oi.payment_date,
        oi.amount,
        oi.hours,
        oi.service_name,
        o.id as order_id,
        o.status,
        o.execution_date,
        c.id as client_id,
        c.name as client_name,
        c.first_order_date,
        g.name as group_name
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.id
    JOIN clients c ON o.client_id = c.id
    LEFT JOIN groups g ON c.group_id = g.id
    WHERE oi.payment_date IS NOT NULL
    '''
    df = run_query(main_query, fetch=True)
    
    if not df.empty:
        df['payment_date'] = pd.to_datetime(df['payment_date'])
        df['year'] = df['payment_date'].dt.year
        df['month'] = df['payment_date'].dt.month
        df['month_name'] = df['payment_date'].dt.strftime('%B')

        years = sorted(df['year'].unique())
        
        # Отчет 1: Оплаты за год по группам
        st.subheader("1. Оплаты за год по группам")
        sel_year_1 = st.selectbox("Выберите год", years, index=len(years)-1, key='y1')
        
        df_1 = df[df['year'] == sel_year_1].groupby('group_name').agg(
            Количество_оплат=('item_id', 'count'),
            Сумма=('amount', 'sum'),
            Средняя_оплата=('amount', 'mean')
        ).reset_index()
        df_1['Сумма'] = df_1['Сумма'].apply(lambda x: f"{format_currency(x)} ₽")
        df_1['Средняя_оплата'] = df_1['Средняя_оплата'].apply(lambda x: f"{format_currency(x)} ₽")
        df_1.columns = ['Группа', 'Кол-во оплат', 'Сумма', 'Средняя оплата']
        st.dataframe(df_1, use_container_width=True, hide_index=True)

        # Отчет 2: Оплаты за год по клиентам
        st.subheader("2. Оплаты за год по клиентам")
        sel_year_2 = st.selectbox("Выберите год", years, index=len(years)-1, key='y2')
        
        df_2 = df[df['year'] == sel_year_2].groupby('client_name').agg(
            Количество_оплат=('item_id', 'count'),
            Сумма=('amount', 'sum')
        ).reset_index().sort_values(by='Сумма', ascending=False)
        df_2['Сумма'] = df_2['Сумма'].apply(lambda x: f"{format_currency(x)} ₽")
        df_2.columns = ['Клиент', 'Кол-во оплат', 'Сумма']
        st.dataframe(df_2, use_container_width=True, hide_index=True)

        # Отчет 3: Новые клиенты за год (по первой оплате)
        st.subheader("3. Новые клиенты за год")
        sel_year_3 = st.selectbox("Выберите год", years, index=len(years)-1, key='y3')
        
        df_new_clients = run_query('''
            SELECT 
                c.name, 
                c.first_order_date,
                COUNT(oi.id) as payments_count, 
                SUM(oi.amount) as total_sum
            FROM clients c 
            JOIN orders o ON c.id = o.client_id
            JOIN order_items oi ON o.id = oi.order_id
            WHERE strftime('%Y', c.first_order_date) = ?
            GROUP BY c.id
            ORDER BY total_sum DESC
        ''', (str(sel_year_3),), fetch=True)
        
        if not df_new_clients.empty:
            df_new_clients['first_order_date'] = df_new_clients['first_order_date'].apply(format_date_display)
            df_new_clients['total_sum'] = df_new_clients['total_sum'].apply(lambda x: f"{format_currency(x)} ₽")
            df_new_clients.columns = ['Клиент', 'Первая оплата', 'Кол-во оплат', 'Сумма']
            st.dataframe(df_new_clients, use_container_width=True, hide_index=True)
        else:
            st.info("Нет новых клиентов за этот год")

        # Отчет 4: Сводка по годам
        st.subheader("4. Сводка по годам")
        df_4 = df.groupby('year').agg(
            Количество_оплат=('item_id', 'count'),
            Макс_оплата=('amount', 'max'),
            Мин_оплата=('amount', 'min'),
            Средняя_оплата=('amount', 'mean'),
            Сумма_год=('amount', 'sum')
        ).reset_index()
        df_4['Средний_месячный'] = df_4['Сумма_год'] / 12
        
        # Копия для графика
        df_4_chart = df_4[['year', 'Сумма_год']].copy()
        
        df_4['Макс_оплата'] = df_4['Макс_оплата'].apply(lambda x: f"{format_currency(x)} ₽")
        df_4['Мин_оплата'] = df_4['Мин_оплата'].apply(lambda x: f"{format_currency(x)} ₽")
        df_4['Средняя_оплата'] = df_4['Средняя_оплата'].apply(lambda x: f"{format_currency(x)} ₽")
        df_4['Сумма_год'] = df_4['Сумма_год'].apply(lambda x: f"{format_currency(x)} ₽")
        df_4['Средний_месячный'] = df_4['Средний_месячный'].apply(lambda x: f"{format_currency(x)} ₽")
        df_4.columns = ['Год', 'Кол-во оплат', 'Макс', 'Мин', 'Средняя', 'Сумма за год', 'Средний мес.']
        st.dataframe(df_4, use_container_width=True, hide_index=True)
        
        st.bar_chart(df_4_chart.set_index('year'))

        # Отчет 5: Оплаты за месяц
        st.subheader("5. Оплаты за месяц (детализация)")
        c1, c2 = st.columns(2)
        with c1: 
            sel_year_5 = st.selectbox("Год", years, index=len(years)-1, key='y5')
        with c2: 
            sel_month_5 = st.selectbox("Месяц", range(1,13), index=date.today().month-1, key='m5')
        
        df_5 = df[(df['year'] == sel_year_5) & (df['month'] == sel_month_5)]
        df_5_res = df_5.groupby('client_name').agg(
            Количество_оплат=('item_id', 'count'),
            Сумма=('amount', 'sum')
        ).reset_index().sort_values(by='Сумма', ascending=False)
        df_5_res['Сумма'] = df_5_res['Сумма'].apply(lambda x: f"{format_currency(x)} ₽")
        df_5_res.columns = ['Клиент', 'Кол-во оплат', 'Сумма']
        st.dataframe(df_5_res, use_container_width=True, hide_index=True)

        # Отчет 6: Динамика по месяцам
        st.subheader("6. Динамика по месяцам")
        sel_year_6 = st.selectbox("Выберите год", years, index=len(years)-1, key='y6')
        df_6 = df[df['year'] == sel_year_6].groupby('month').agg(
            Количество_оплат=('item_id', 'count'),
            Средняя_оплата=('amount', 'mean'),
            Сумма=('amount', 'sum')
        ).reset_index()
        
        df_6_chart = df_6[['month', 'Сумма']].copy()
        
        df_6['Средняя_оплата'] = df_6['Средняя_оплата'].apply(lambda x: f"{format_currency(x)} ₽")
        df_6['Сумма'] = df_6['Сумма'].apply(lambda x: f"{format_currency(x)} ₽")
        df_6.columns = ['Месяц', 'Кол-во оплат', 'Средняя оплата', 'Сумма']
        st.dataframe(df_6, use_container_width=True, hide_index=True)
        
        st.line_chart(df_6_chart.set_index('month'))

        # Отчет 7: Оплаты за последнюю неделю
        st.subheader("7. Оплаты за последнюю неделю")
        df_7 = run_query('''
            SELECT c.name, oi.payment_date, SUM(oi.amount) as total_amount
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN clients c ON o.client_id = c.id
            WHERE oi.payment_date >= date('now','-7 days')
            GROUP BY c.name, oi.payment_date
            ORDER BY oi.payment_date DESC
        ''', fetch=True)
        
        if not df_7.empty:
            df_7['payment_date'] = df_7['payment_date'].apply(format_date_display)
            df_7['total_amount'] = df_7['total_amount'].apply(lambda x: f"{format_currency(x)} ₽")
            df_7.columns = ['Клиент', 'Дата оплаты', 'Сумма']
            st.dataframe(df_7, use_container_width=True, hide_index=True)
        else:
            st.info("Нет оплат за последнюю неделю")
    else:
        st.warning("В базе данных пока нет оплат для формирования отчётов.")