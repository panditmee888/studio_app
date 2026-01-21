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
    digits = ''.join(filter(str.isdigit, str(phone_str)))
    if digits.startswith('8') and len(digits) == 11:
        digits = '7' + digits[1:]
    if len(digits) == 10:
        digits = '7' + digits
    if len(digits) >= 11:
        return f"+{digits[0]} {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return phone_str

def format_vk(vk_str):
    """Форматирование VK ID для отображения"""
    if not vk_str or pd.isna(vk_str):
        return ""
    vk = str(vk_str).strip()
    vk = vk.replace("https://", "").replace("http://", "")
    if vk.startswith("vk.com/id"):
        return vk
    if vk.startswith("id") and vk[2:].isdigit():
        return f"vk.com/id{vk}"
    if vk.isdigit():
        return f"vk.com/id{vk}"
    return f"vk.com/{vk}"

def format_telegram(tg_str):
    """Форматирование Telegram для отображения"""
    if not tg_str or pd.isna(tg_str):
        return ""
    tg = str(tg_str).strip()
    tg = tg.replace("https://", "").replace("http://", "").replace("@", "")
    if tg.startswith("t.me/"):
        return tg
    return f"t.me/{tg}"

def get_phone_link(phone_str):
    """Генерация ссылки tel:"""
    if not phone_str: return ""
    digits = ''.join(filter(str.isdigit, str(phone_str)))
    if len(digits) == 11:
        return f"tel:{digits}"
    if len(digits) == 10:
        return f"tel:7{digits}"
    return ""

def get_vk_link(vk_str):
    """Генерация полной ссылки VK"""
    if not vk_str: return ""
    vk = str(vk_str).strip()
    vk = vk.replace("https://", "").replace("http://", "").replace("vk.com/id", "")
    return f"https://vk.com/id{vk}"

def get_telegram_link(tg_str):
    """Генерация полной ссылки Telegram"""
    if not tg_str: return ""
    tg = str(tg_str).strip()
    tg = tg.replace("https://", "").replace("http://", "").replace("@", "").replace("t.me/", "")
    return f"https://t.me/{tg}"

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
    with st.expander("➕ Добавить нового клиента", expanded=False):
        with st.form("add_client"):
            c_name = st.text_input("Имя *", placeholder="Иван Иванов")
            c_sex = st.selectbox("Пол", ["М", "Ж"])
            c_phone_raw = st.text_input("Телефон", placeholder="Введите номер телефона")
            c_vk_raw = st.text_input("VK ID", placeholder="id123456789 или username")
            c_tg_raw = st.text_input("Telegram", placeholder="username (без @)")
            
            if groups_list:
                c_group = st.selectbox("Группа", options=["Без группы"] + groups_list)
            else:
                c_group = "Без группы"
                st.info("Группы еще не созданы")
            
            if st.form_submit_button("Сохранить клиента"):
                if c_name:
                    phone = c_phone_raw if c_phone_raw else ""
                    vk = c_vk_raw if c_vk_raw else ""
                    tg = c_tg_raw if c_tg_raw else ""
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
                        new_name = st.text_input("Название", value=row['name'], key=f"group_name_{row['id']}", label_visibility="collapsed")
                    with col_b:
                        if st.button("💾", key=f"update_{row['id']}", help="Сохранить"):
                            if new_name and new_name != row['name']:
                                run_query("UPDATE groups SET name=? WHERE id=?", (new_name, row['id']))
                                st.success("Группа обновлена")
                                st.rerun()
                    with col_c:
                        if st.button("🗑️", key=f"delete_{row['id']}", help="Удалить"):
                            clients_check = run_query("SELECT COUNT(*) as count FROM clients WHERE group_id=?", (row['id'],), fetch=True)
                            if not clients_check.empty and clients_check['count'].iloc[0] > 0:
                                st.warning("Нельзя удалить группу с клиентами!")
                            else:
                                run_query("DELETE FROM groups WHERE id=?", (row['id'],))
                                st.success("Группа удалена")
                                st.rerun()
            else:
                st.info("Групп пока нет")
    
    # Поиск и фильтрация
    search_col1, search_col2 = st.columns([2, 1])
    with search_col1:
        search_query = st.text_input("🔍 Поиск клиента", placeholder="Имя, телефон, VK, TG...")
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
    
            # Создаём копию для отображения с форматированием
            display_df = clients_df_data.copy()
    
            # Форматируем все поля
            display_df['first_order_date'] = display_df['first_order_date'].apply(format_date_display)
    
            # Форматируем контакты для отображения и готовим ссылки
            display_df['phone_display'] = display_df['phone'].apply(format_phone)
            display_df['phone_url'] = display_df['phone'].apply(get_phone_url)
    
            display_df['vk_display'] = display_df['vk_id'].apply(format_vk)
            display_df['vk_url'] = display_df['vk_id'].apply(lambda x: f"https://{format_vk(x)}" if format_vk(x) else "")
    
            display_df['tg_display'] = display_df['tg_id'].apply(format_telegram)
            display_df['tg_url'] = display_df['tg_id'].apply(lambda x: f"https://{format_telegram(x)}" if format_telegram(x) else "")
    
            # Переименовываем колонки для отображения
            display_df.columns = ['ID', 'Имя', 'Пол', 'Телефон', 'VK', 'Telegram', 'Группа', 'Первая оплата', 
                         'phone_display', 'phone_url', 'vk_display', 'vk_url', 'tg_display', 'tg_url']
    
            # Отображаем форматированную таблицу с кликабельными ссылками
            st.dataframe(
                display_df[['ID', 'Имя', 'Пол', 'phone_display', 'phone_url', 'vk_display', 'vk_url', 'tg_display', 'tg_url', 'Группа', 'Первая оплата']],
                column_config={
                    "ID": st.column_config.NumberColumn("ID", disabled=True),
                    "Имя": st.column_config.TextColumn("Имя"),
                    "Пол": st.column_config.TextColumn("Пол"),
            
                    # 📞 Телефон: кликабельная ссылка для звонка, отображается в формате +7 XXX XXX-XX-XX
                    "phone_display": st.column_config.LinkColumn(
                        "Телефон",
                        display_text=":parent",
                        url="phone_url"
                    ),
                    "phone_url": None,  # Скрываем техническую колонку с ссылкой
            
                    # 📘 VK: кликабельная ссылка, отображается как vk.com/idXXXX или vk.com/username
                    "vk_display": st.column_config.LinkColumn(
                        "VK",
                        display_text=":parent",
                        url="vk_url"
                    ),
                    "vk_url": None,  # Скрываем техническую колонку с ссылкой
            
                    # 💬 Telegram: кликабельная ссылка, отображается как t.me/username
                    "tg_display": st.column_config.LinkColumn(
                        "Telegram",
                        display_text=":parent",
                        url="tg_url"
                    ),
                    "tg_url": None,  # Скрываем техническую колонку с ссылкой
            
                    "Группа": st.column_config.TextColumn("Группа"),
                    "Первая оплата": st.column_config.TextColumn("Первая оплата")
                },
                use_container_width=True,
                hide_index=True
    )

        # --- ВЫБОР КЛИЕНТА ДЛЯ РЕДАКТИРОВАНИЯ ---
        # Формируем список для выбора
        clients_options = ["-- Выберите клиента для редактирования --"] + \
                          [f"#{row['id']} {row['name']}" for _, row in clients_df_data.iterrows()]
        
        selected_client_opt = st.selectbox("Редактирование клиента", clients_options)
        
        if selected_client_opt != "-- Выберите клиента для редактирования --":
            # Получаем ID из строки выбора
            client_id = int(selected_client_opt.split()[0][1:])
            client_row = clients_df_data[clients_df_data['id'] == client_id].iloc[0].to_frame().T
            
            st.markdown(f"#### ✏️ Редактирование клиента: {client_row['name'].iloc[0]}")
            
            # Подготовка данных для редактора (одна строка)
            edit_df = client_row.copy()
            edit_df['first_order_date'] = edit_df['first_order_date'].apply(format_date_display)
            
            edited_client = st.data_editor(
                edit_df[['id', 'name', 'sex', 'phone', 'vk_id', 'tg_id', 'group_name', 'first_order_date']],
                column_config={
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "name": st.column_config.TextColumn("Имя"),
                    "sex": st.column_config.SelectboxColumn("Пол", options=["М", "Ж"]),
                    "phone": st.column_config.TextColumn("Телефон"),
                    "vk_id": st.column_config.TextColumn("VK ID"),
                    "tg_id": st.column_config.TextColumn("Telegram"),
                    "group_name": st.column_config.SelectboxColumn("Группа", options=["Без группы"] + groups_list),
                    "first_order_date": st.column_config.TextColumn("Первая оплата"),
                },
                hide_index=True,
                use_container_width=True,
                key="edit_client_row",
                num_rows="fixed"
            )
            
            col_save, col_del = st.columns(2)
            with col_del:
                if st.button("🗑️ Удалить клиента", type="secondary"):
                    # Проверка на заказы
                    orders_check = run_query("SELECT COUNT(*) as count FROM orders WHERE client_id=?", (client_id,), fetch=True)
                    if not orders_check.empty and orders_check['count'].iloc[0] > 0:
                        st.error("❌ Нельзя удалить клиента, у которого есть заказы! Сначала удалите заказы.")
                    else:
                        run_query("DELETE FROM clients WHERE id=?", (client_id,))
                        st.success("Клиент удален")
                        st.rerun()
            
            # Сохранение изменений
            if not edited_client.equals(edit_df):
                new_row = edited_client.iloc[0]
                group_name = new_row['group_name']
                g_id = group_map.get(group_name) if group_name != "Без группы" else None
                first_order = parse_date_to_db(new_row['first_order_date'])
                
                run_query('''
                    UPDATE clients 
                    SET name=?, sex=?, phone=?, vk_id=?, tg_id=?, group_id=?, first_order_date=?
                    WHERE id=?
                ''', (
                    new_row['name'],
                    new_row['sex'],
                    new_row['phone'],
                    new_row['vk_id'],
                    new_row['tg_id'],
                    g_id,
                    first_order,
                    client_id
                ))
                st.success("✅ Изменения сохранены!")
                st.rerun()
    else:
        st.info("Клиенты не найдены")

# --- 2. ПРАЙС-ЛИСТ ---
elif choice == "Прайс-лист Услуг":
    st.subheader("Справочник Услуг")
    
    with st.expander("➕ Добавить новую услугу", expanded=False):
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
        # Просмотр
        display_services = services_df.copy()
        display_services['min_price'] = display_services['min_price'].apply(lambda x: f"{format_currency(x)} ₽")
        display_services.columns = ['ID', 'Услуга', 'Мин. прайс', 'Описание']
        st.dataframe(display_services, use_container_width=True, hide_index=True)

        # --- ВЫБОР УСЛУГИ ---
        services_options = ["-- Выберите услугу для редактирования --"] + \
                           [f"#{row['id']} {row['name']}" for _, row in services_df.iterrows()]
        
        selected_service_opt = st.selectbox("Редактирование услуги", services_options)
        
        if selected_service_opt != "-- Выберите услугу для редактирования --":
            service_id = int(selected_service_opt.split()[0][1:])
            service_row = services_df[services_df['id'] == service_id].iloc[0].to_frame().T
            
            edited_service = st.data_editor(
                service_row,
                column_config={
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "name": st.column_config.TextColumn("Услуга"),
                    "min_price": st.column_config.NumberColumn("Мин. прайс ₽", format="%.0f"),
                    "description": st.column_config.TextColumn("Описание")
                },
                hide_index=True,
                use_container_width=True,
                key="edit_service_row",
                num_rows="fixed"
            )
            
            if st.button("🗑️ Удалить услугу", type="secondary"):
                run_query("DELETE FROM services_catalog WHERE id=?", (service_id,))
                st.success("Услуга удалена")
                st.rerun()
            
            if not edited_service.equals(service_row):
                new_row = edited_service.iloc[0]
                run_query('''
                    UPDATE services_catalog 
                    SET name=?, min_price=?, description=?
                    WHERE id=?
                ''', (
                    new_row['name'],
                    new_row['min_price'],
                    new_row['description'],
                    service_id
                ))
                st.success("✅ Изменения сохранены!")
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

    with st.expander("➕ Создать новый заказ", expanded=True):
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
        
        # --- ВЫБОР ЗАКАЗА ---
        orders_options = ["-- Выберите заказ для редактирования --"] + \
                         [f"#{row['id']} {row['client_name']} ({row['status']})" for _, row in orders_df.iterrows()]
        
        selected_order_opt = st.selectbox("Редактирование заказа", orders_options)
        
        if selected_order_opt != "-- Выберите заказ для редактирования --":
            order_id = int(selected_order_opt.split()[0][1:])
            order_row = orders_df[orders_df['id'] == order_id].iloc[0].to_frame().T
            
            st.markdown(f"#### ✏️ Редактирование заказа #{order_id}")
            
            # Подготовка даты
            edit_df = order_row[['id', 'client_id', 'client_name', 'execution_date', 'status', 'total_amount']].copy()
            edit_df['execution_date'] = edit_df['execution_date'].apply(format_date_display)
            
            edited_order = st.data_editor(
                edit_df,
                column_config={
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "client_name": st.column_config.SelectboxColumn("Клиент", options=client_names, required=True),
                    "execution_date": st.column_config.TextColumn("Дата исполнения"),
                    "status": st.column_config.SelectboxColumn("Статус", options=STATUS_LIST, required=True),
                    "total_amount": st.column_config.TextColumn("Сумма", disabled=True)
                },
                hide_index=True,
                use_container_width=True,
                key="edit_order_row",
                num_rows="fixed"
            )
            
            if st.button("🗑️ Удалить заказ", type="secondary"):
                run_query("DELETE FROM orders WHERE id=?", (order_id,))
                st.success("Заказ удален")
                st.rerun()
            
            if not edited_order.equals(edit_df):
                new_row = edited_order.iloc[0]
                client_id = client_map.get(new_row['client_name'])
                exec_date = parse_date_to_db(new_row['execution_date'])
                
                run_query('''
                    UPDATE orders 
                    SET client_id=?, execution_date=?, status=?
                    WHERE id=?
                ''', (client_id, exec_date, new_row['status'], order_id))
                st.success("✅ Изменения сохранены!")
                st.rerun()
        
        st.markdown("---")
        
        # Статистика и просмотр
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

        display_orders = orders_df[['id', 'client_name', 'execution_date', 'status', 'total_amount']].copy()
        display_orders['execution_date'] = display_orders['execution_date'].apply(format_date_display)
        display_orders['total_amount'] = display_orders['total_amount'].apply(lambda x: f"{format_currency(x)} ₽")
        display_orders.columns = ['ID', 'Клиент', 'Дата исполнения', 'Статус', 'Сумма']
        
        st.dataframe(display_orders, use_container_width=True, hide_index=True)
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
        
        # Выбор заказа
        order_selection = st.selectbox("Выберите заказ", orders_df['label'])
        order_id = int(orders_df[orders_df['label'] == order_selection]['id'].iloc[0])
        
        # Получаем client_id для обновления first_order_date
        client_id_result = run_query("SELECT client_id FROM orders WHERE id=?", (order_id,), fetch=True)
        current_client_id = client_id_result['client_id'].iloc[0] if not client_id_result.empty else None

        # Услуги из каталога
        services_cat = run_query("SELECT name FROM services_catalog", fetch=True)
        srv_list = services_cat['name'].tolist() if not services_cat.empty else []
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("#### ➕ Добавить услугу")
            with st.form("add_item_form"):
                service_choice = st.selectbox("Услуга", srv_list if srv_list else ["Нет услуг в каталоге"])
                i_date = st.date_input("Дата оплаты", value=date.today())
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
                        total_res = run_query("SELECT SUM(amount) as total FROM order_items WHERE order_id=?", (order_id,), fetch=True)
                        total = total_res['total'].iloc[0] if not total_res.empty and total_res['total'].iloc[0] else 0.0
                        run_query("UPDATE orders SET total_amount=? WHERE id=?", (total, order_id))
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
                # --- ВЫБОР УСЛУГИ В ЗАКАЗЕ ДЛЯ РЕДАКТИРОВАНИЯ ---
                items_options = ["-- Выберите услугу для редактирования --"] + \
                                [f"#{row['id']} {row['service_name']} ({format_currency(row['amount'])} ₽)" for _, row in items_df.iterrows()]
                
                selected_item_opt = st.selectbox("Редактирование услуги в заказе", items_options)
                
                if selected_item_opt != "-- Выберите услугу для редактирования --":
                    item_id = int(selected_item_opt.split()[0][1:])
                    item_row = items_df[items_df['id'] == item_id].iloc[0].to_frame().T
                    
                    st.markdown("#### ✏️ Редактирование услуги в заказе")
                    
                    edit_item_df = item_row.copy()
                    edit_item_df['payment_date'] = edit_item_df['payment_date'].apply(format_date_display)
                    
                    edited_item = st.data_editor(
                        edit_item_df,
                        column_config={
                            "id": st.column_config.NumberColumn("ID", disabled=True),
                            "service_name": st.column_config.SelectboxColumn("Услуга", options=srv_list, required=True),
                            "payment_date": st.column_config.TextColumn("Дата оплаты"),
                            "amount": st.column_config.NumberColumn("Сумма", format="%.0f"),
                            "hours": st.column_config.NumberColumn("Часы", format="%.1f", step=0.1)
                        },
                        hide_index=True,
                        use_container_width=True,
                        key="edit_item_row",
                        num_rows="fixed"
                    )
                    
                    if st.button("🗑️ Удалить услугу из заказа", type="secondary", key="del_item"):
                        run_query("DELETE FROM order_items WHERE id=?", (item_id,))
                        total_res = run_query("SELECT SUM(amount) as total FROM order_items WHERE order_id=?", (order_id,), fetch=True)
                        total = total_res['total'].iloc[0] if not total_res.empty and total_res['total'].iloc[0] else 0.0
                        run_query("UPDATE orders SET total_amount=? WHERE id=?", (total, order_id))
                        if current_client_id:
                            update_client_first_order_date(current_client_id)
                        st.success("Услуга удалена")
                        st.rerun()
                    
                    if not edited_item.equals(edit_item_df):
                        new_row = edited_item.iloc[0]
                        payment_date_val = parse_date_to_db(new_row['payment_date'])
                        amount_val = float(new_row['amount'])
                        hours_val = float(new_row['hours'])
                        
                        run_query('''
                            UPDATE order_items 
                            SET service_name=?, payment_date=?, amount=?, hours=?
                            WHERE id=?
                        ''', (
                            new_row['service_name'],
                            payment_date_val,
                            amount_val,
                            hours_val,
                            item_id
                        ))
                        
                        total_res = run_query("SELECT SUM(amount) as total FROM order_items WHERE order_id=?", (order_id,), fetch=True)
                        total = total_res['total'].iloc[0] if not total_res.empty and total_res['total'].iloc[0] else 0.0
                        run_query("UPDATE orders SET total_amount=? WHERE id=?", (total, order_id))
                        if current_client_id:
                            update_client_first_order_date(current_client_id)
                        
                        st.success("✅ Изменения сохранены!")
                        st.rerun()
                
                st.markdown("---")
                
                # Просмотр списка услуг
                display_items = items_df.copy()
                display_items['payment_date'] = display_items['payment_date'].apply(format_date_display)
                display_items['amount'] = display_items['amount'].apply(lambda x: f"{format_currency(x)} ₽")
                display_items['hours'] = display_items['hours'].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "0.0")
                display_items.columns = ['ID', 'Услуга', 'Дата оплаты', 'Сумма', 'Часы']
                st.dataframe(display_items, use_container_width=True, hide_index=True)

                total_amount = items_df['amount'].sum()
                st.success(f"💰 **Итого:** {format_currency(total_amount)} ₽")
            else:
                st.info("В этом заказе пока нет услуг")
    else:
        st.info("Сначала создайте заказ")

# --- 5. ОТЧЁТЫ ---
elif choice == "ОТЧЁТЫ":
    st.header("📊 Аналитические Отчёты")
    
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