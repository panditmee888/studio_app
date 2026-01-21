import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import plotly.express as px

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def format_date(date_str):
    """Форматирование даты в dd.mm.yyyy"""
    if pd.isna(date_str) or date_str is None:
        return None
    try:
        if isinstance(date_str, str):
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            date_obj = pd.to_datetime(date_str)
        return date_obj.strftime("%d.%m.%Y")
    except:
        return str(date_str)

def parse_date(date_str):
    """Преобразует строку даты в формат БД"""
    if pd.isna(date_str) or not date_str:
        return None
    try:
        if isinstance(date_str, str):
            if '.' in date_str:
                return datetime.strptime(date_str, "%d.%m.%Y").strftime("%Y-%m-%d")
            return date_str
        return date_str.strftime("%Y-%m-%d")
    except:
        return None

def format_currency(amount):
    """Форматирование валюты без дробей, с пробелами"""
    if pd.isna(amount) or amount is None:
        return "0"
    try:
        return f"{int(float(amount)):,.0f}".replace(",", " ")
    except:
        return str(amount)

def parse_currency(amount_str):
    """Преобразует строку с пробелами в число"""
    if not amount_str:
        return 0.0
    try:
        return float(amount_str.replace(" ", "").replace(",", ""))
    except:
        return 0.0

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
        return None if fetch else False

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Studio Admin", layout="wide")
init_db()

st.title("🎛️ CRM Студии Звукозаписи")

menu = ["Клиенты и Группы", "Прайс-лист Услуг", "Заказы", "Детализация Заказа", "ОТЧЁТЫ"]
choice = st.sidebar.selectbox("Навигация", menu)

# --- 1. КЛИЕНТЫ И ГРУППЫ ---
if choice == "Клиенты и Группы":
    st.subheader("Клиенты")
    
    # Форма добавления клиента
    with st.expander("➕ Добавить нового клиента"):
        with st.form("add_client"):
            c_name = st.text_input("Имя")
            c_sex = st.selectbox("Пол", ["М", "Ж"])
            c_phone = st.text_input("Телефон")
            c_vk = st.text_input("VK ID")
            c_tg = st.text_input("Telegram ID")
            
            groups_df = run_query("SELECT id, name FROM groups", fetch=True)
            if not groups_df.empty:
                group_options = groups_df['name'].tolist()
                group_map = dict(zip(groups_df['name'], groups_df['id']))
                c_group = st.selectbox("Группа", options=["Без группы"] + group_options)
            else:
                c_group = None
                st.info("Группы еще не созданы")
            
            if st.form_submit_button("Сохранить клиента"):
                if c_name:
                    g_id = group_map.get(c_group) if c_group and c_group != "Без группы" else None
                    run_query('''INSERT INTO clients (name, sex, phone, vk_id, tg_id, group_id) 
                                 VALUES (?,?,?,?,?,?)''', (c_name, c_sex, c_phone, c_vk, c_tg, g_id))
                    st.success("Клиент добавлен")
                    st.rerun()
                else:
                    st.error("Введите имя клиента")

    # Управление группами (всегда свернутый экспандер)
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
            groups_df = run_query("SELECT * FROM groups", fetch=True)
            if not groups_df.empty:
                for idx, row in groups_df.iterrows():
                    col_a, col_b, col_c = st.columns([3, 1, 1])
                    with col_a:
                        new_name = st.text_input(
                            f"Название", 
                            value=row['name'], 
                            key=f"group_name_{row['id']}"
                        )
                    with col_b:
                        if st.button("Обновить", key=f"update_{row['id']}"):
                            if new_name != row['name']:
                                run_query("UPDATE groups SET name=? WHERE id=?", (new_name, row['id']))
                                st.success(f"Группа обновлена: {new_name}")
                                st.rerun()
                    with col_c:
                        if st.button("Удалить", key=f"delete_{row['id']}"):
                            clients_check = run_query(
                                "SELECT COUNT(*) as count FROM clients WHERE group_id=?", 
                                (row['id'],), 
                                fetch=True
                            )
                            if clients_check['count'].iloc[0] > 0:
                                st.warning(f"Нельзя удалить группу с {clients_check['count'].iloc[0]} клиентами!")
                            else:
                                run_query("DELETE FROM groups WHERE id=?", (row['id'],))
                                st.success(f"Группа удалена: {row['name']}")
                                st.rerun()
            else:
                st.info("Групп пока нет")

    # Поиск и фильтрация
    st.markdown("### 🔍 Поиск и фильтрация")
    search_col1, search_col2 = st.columns([2, 1])
    with search_col1:
        search_query = st.text_input("Поиск по имени, телефону, VK или Telegram", placeholder="Введите текст...")
    with search_col2:
        groups_df = run_query("SELECT name FROM groups", fetch=True)
        groups_list = groups_df['name'].tolist() if not groups_df.empty else []
        filter_group = st.selectbox("Фильтр по группе", ["Все"] + groups_list)

    # Получаем все данные для редактора
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
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
    
    if filter_group != "Все":
        clients_query += ' AND g.name = ?'
        params.append(filter_group)
    
    clients_df = run_query(clients_query, tuple(params), fetch=True)
    
    if not clients_df.empty:
        clients_df['first_order_date'] = clients_df['first_order_date'].apply(format_date)
        
        # Подготовка данных для data_editor
        edited_clients = st.data_editor(
            clients_df,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "name": "Имя",
                "sex": st.column_config.SelectboxColumn(
                    "Пол",
                    options=["М", "Ж"],
                    required=True
                ),
                "phone": "Телефон",
                "vk_id": "VK ID",
                "tg_id": "Telegram ID",
                "group_name": st.column_config.SelectboxColumn(
                    "Группа",
                    options=["Без группы"] + groups_list
                ),
                "first_order_date": st.column_config.DateColumn(
                    "Первая запись",
                    format="DD.MM.YYYY",
                    default=None
                )
            },
            hide_index=True,
            use_container_width=True,
            key="clients_editor"
        )

        # Сохранение изменений
        if not edited_clients.equals(clients_df):
            changed = edited_clients.compare(clients_df)
            if not changed.empty:
                for idx, row in changed.iterrows():
                    client_id = edited_clients.at[idx, 'id']
                    group_name = edited_clients.at[idx, 'group_name']
                    group_id = None
                    if group_name != "Без группы":
                        grp = run_query("SELECT id FROM groups WHERE name=?", (group_name,), fetch=True)
                        group_id = grp['id'].iloc[0] if not grp.empty else None
                    
                    first_order_date = parse_date(edited_clients.at[idx, 'first_order_date'])
                    
                    run_query('''
                        UPDATE clients 
                        SET name=?, sex=?, phone=?, vk_id=?, tg_id=?, group_id=?, first_order_date=?
                        WHERE id=?
                    ''', (
                        edited_clients.at[idx, 'name'],
                        edited_clients.at[idx, 'sex'],
                        edited_clients.at[idx, 'phone'],
                        edited_clients.at[idx, 'vk_id'],
                        edited_clients.at[idx, 'tg_id'],
                        group_id,
                        first_order_date,
                        client_id
                    ))
                st.success("✅ Изменения сохранены!")
                st.rerun()
    else:
        st.info("Клиенты не найдены")

# --- 2. ПРАЙС-ЛИСТ ---
elif choice == "Прайс-лист Услуг":
    st.subheader("Справочник Услуг")
    
    with st.expander("➕ Добавить новую услугу"):
        with st.form("add_service"):
            s_name = st.text_input("Наименование услуги")
            s_price = st.number_input("Мин. прайс", min_value=0.0, step=100.0)
            s_desc = st.text_area("Описание")
            if st.form_submit_button("Добавить услугу"):
                if s_name:
                    run_query("INSERT INTO services_catalog (name, min_price, description) VALUES (?,?,?)", 
                              (s_name, s_price, s_desc))
                    st.success("Услуга добавлена")
                    st.rerun()
    
    services_df = run_query("SELECT * FROM services_catalog", fetch=True)
    
    if not services_df.empty:
        edited_services = st.data_editor(
            services_df,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "name": "Услуга",
                "min_price": st.column_config.NumberColumn(
                    "Мин. прайс",
                    format="%.2f ₽"
                ),
                "description": "Описание"
            },
            hide_index=True,
            use_container_width=True,
            key="services_editor"
        )
        
        if not edited_services.equals(services_df):
            changed = edited_services.compare(services_df)
            if not changed.empty:
                for idx, row in changed.iterrows():
                    run_query('''
                        UPDATE services_catalog 
                        SET name=?, min_price=?, description=?
                        WHERE id=?
                    ''', (
                        edited_services.at[idx, 'name'],
                        edited_services.at[idx, 'min_price'],
                        edited_services.at[idx, 'description'],
                        edited_services.at[idx, 'id']
                    ))
                st.success("✅ Изменения сохранены!")
                st.rerun()
    else:
        st.info("Услуги еще не добавлены")

# --- 3. ЗАКАЗЫ ---
elif choice == "Заказы":
    st.subheader("Управление Заказами")
    
    clients_df = run_query("SELECT id, name FROM clients", fetch=True)
    client_map = dict(zip(clients_df['name'], clients_df['id'])) if not clients_df.empty else {}

    with st.expander("➕ Создать новый заказ"):
        with st.form("new_order"):
            if client_map:
                o_client = st.selectbox("Клиент", list(client_map.keys()))
                o_date = st.date_input("Дата исполнения", value=date.today())
                o_status = st.selectbox("Статус", ["В работе", "Выполнен", "Отменен", "Оплачен"])
                
                if st.form_submit_button("Создать заказ"):
                    c_id = client_map.get(o_client)
                    run_query("INSERT INTO orders (client_id, execution_date, status) VALUES (?,?,?)", 
                              (c_id, o_date, o_status))
                    run_query('''UPDATE clients SET first_order_date = ? 
                                 WHERE id = ? AND first_order_date IS NULL''', (o_date, c_id))
                    st.success("Заказ создан!")
                    st.rerun()
            else:
                st.warning("Сначала добавьте клиентов")

    # Поиск и фильтрация
    st.markdown("### 🔍 Фильтры")
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        order_search = st.text_input("Поиск по клиенту", placeholder="Имя клиента...")
    with filter_col2:
        status_filter = st.selectbox("Статус", ["Все", "В работе", "Выполнен", "Отменен", "Оплачен"])
    with filter_col3:
        date_filter = st.selectbox("Период", ["Все время", "Текущий месяц", "Последние 7 дней"])

    # Формируем запрос
    orders_query = '''
    SELECT 
        o.id, 
        c.name as client_name,
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
        current_month = date.today().replace(day=1)
        orders_query += " AND o.execution_date >= ?"
        params.append(current_month)
    elif date_filter == "Последние 7 дней":
        last_week = date.today() - pd.Timedelta(days=7)
        orders_query += " AND o.execution_date >= ?"
        params.append(last_week)

    orders_df = run_query(orders_query, tuple(params), fetch=True)
    
    if not orders_df.empty:
        # Форматируем для отображения
        display_df = orders_df.copy()
        display_df['execution_date'] = display_df['execution_date'].apply(format_date)
        display_df['total_amount'] = display_df['total_amount'].apply(format_currency)
        
        # Статистика за текущий месяц
        if date_filter == "Текущий месяц":
            current_month_start = date.today().replace(day=1).strftime("%Y-%m-%d")
            stats_df = run_query(
                '''SELECT total_amount, status FROM orders 
                   WHERE execution_date >= ?''',
                (current_month_start,),
                fetch=True
            )
        else:
            stats_df = orders_df

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Всего заказов", len(stats_df))
        with col2:
            total_sum = stats_df['total_amount'].sum() if not stats_df.empty else 0
            st.metric("Общая сумма", f"{int(total_sum):,.0f} ₽".replace(",", " "))
        with col3:
            avg_check = stats_df['total_amount'].mean() if len(stats_df) > 0 else 0
            avg_text = f"{int(avg_check):,.0f} ₽".replace(",", " ") if avg_check > 0 else "—"
            st.metric("Средний чек", avg_text)
        with col4:
            in_work = len(stats_df[stats_df['status'] == 'В работе']) if not stats_df.empty else 0
            st.metric("В работе", in_work)

        # Редактор заказов
        edited_orders = st.data_editor(
            display_df,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "client_name": st.column_config.SelectboxColumn(
                    "Клиент",
                    options=clients_df['name'].tolist(),
                    required=True
                ),
                "execution_date": st.column_config.DateColumn(
                    "Дата исполнения",
                    format="DD.MM.YYYY"
                ),
                "status": st.column_config.SelectboxColumn(
                    "Статус",
                    options=["В работе", "Выполнен", "Отменен", "Оплачен"]
                ),
                "total_amount": st.column_config.TextColumn(
                    "Сумма",
                    disabled=True,
                    help="Редактируется в детализации заказа"
                )
            },
            hide_index=True,
            use_container_width=True,
            key="orders_editor"
        )

        # Сохранение изменений
        if not edited_orders.equals(display_df):
            for idx, row in edited_orders.iterrows():
                orig_row = orders_df[orders_df['id'] == row['id']].iloc[0]
                if (row['client_name'] != orig_row['client_name'] or 
                    row['execution_date'] != orig_row['execution_date'] or 
                    row['status'] != orig_row['status']):
                    
                    client_id = client_map.get(row['client_name'])
                    exec_date = parse_date(row['execution_date'])
                    
                    run_query('''
                        UPDATE orders 
                        SET client_id=?, execution_date=?, status=?
                        WHERE id=?
                    ''', (client_id, exec_date, row['status'], row['id']))
                    
                    # Обновляем first_order_date у клиента при необходимости
                    if not run_query(
                        "SELECT 1 FROM clients WHERE id=? AND first_order_date IS NOT NULL",
                        (client_id,),
                        fetch=True
                    ).empty:
                        run_query('''
                            UPDATE clients 
                            SET first_order_date = ?
                            WHERE id=?
                        ''', (exec_date, client_id))
            
            st.success("✅ Изменения сохранены!")
            st.rerun()
    else:
        st.info("Заказы не найдены")

# --- 4. ДЕТАЛИЗАЦИЯ ЗАКАЗА ---
elif choice == "Детализация Заказа":
    st.subheader("Внутренние услуги заказа")
    
    orders_df = run_query(
        "SELECT o.id, c.name, o.execution_date FROM orders o JOIN clients c ON o.client_id = c.id", 
        fetch=True
    )
    
    if not orders_df.empty:
        orders_df['label'] = orders_df.apply(
            lambda x: f"Заказ #{x['id']} - {x['name']} ({format_date(x['execution_date'])})", 
            axis=1
        )
        order_selection = st.selectbox("Выберите заказ", orders_df['label'])
        order_id = int(orders_df[orders_df['label'] == order_selection]['id'].iloc[0])

        # Форма добавления услуги
        services_cat = run_query("SELECT name FROM services_catalog", fetch=True)
        srv_list = services_cat['name'].tolist() if not services_cat.empty else []
        
        col1, col2 = st.columns(2)
        with col1:
            with st.form("add_item_form"):
                st.write("#### Добавить услугу")
                
                service_choice = st.selectbox("Услуга", srv_list)
                
                i_date = st.date_input("Дата оплаты", value=date.today())
                
                # Поле с маской форматирования
                amount_str = st.text_input(
                    "Сумма ₽", 
                    value="0",
                    placeholder="0"
                )
                
                # Автоформатирование
                clean_amount = amount_str.replace(" ", "").replace(",", "")
                if clean_amount.isdigit():
                    formatted = f"{int(clean_amount):,}".replace(",", " ")
                    if amount_str != formatted:
                        st.session_state.amount_input = formatted
                    i_amount = float(clean_amount)
                else:
                    i_amount = 0.0
                
                i_hours = st.number_input("Кол-во часов", min_value=0.0, step=0.1, value=0.0)
                
                if st.form_submit_button("Добавить услугу"):
                    if service_choice and i_amount > 0:
                        run_query(
                            '''INSERT INTO order_items 
                            (order_id, service_name, payment_date, amount, hours)
                            VALUES (?,?,?,?,?)''',
                            (order_id, service_choice, str(i_date), i_amount, i_hours)
                        )
                        # Обновляем сумму заказа
                        total = run_query(
                            "SELECT SUM(amount) as total FROM order_items WHERE order_id=?",
                            (order_id,),
                            fetch=True
                        )['total'].iloc[0] or 0.0
                        run_query(
                            "UPDATE orders SET total_amount=? WHERE id=?",
                            (total, order_id)
                        )
                        st.success("Услуга добавлена!")
                        st.rerun()
                    else:
                        st.error("Заполните все поля")

        # Редактор услуг заказа
        with col2:
            items_df = run_query(
                '''SELECT id, service_name, payment_date, amount, hours 
                   FROM order_items WHERE order_id=?''',
                (order_id,),
                fetch=True
            )
            
            if not items_df.empty:
                # Форматируем для отображения
                display_items = items_df.copy()
                display_items['payment_date'] = display_items['payment_date'].apply(format_date)
                display_items['amount'] = display_items['amount'].apply(format_currency)
                display_items['hours'] = display_items['hours'].apply(lambda x: f"{x:.1f}")

                edited_items = st.data_editor(
                    display_items,
                    column_config={
                        "id": st.column_config.NumberColumn("ID", disabled=True),
                        "service_name": st.column_config.SelectboxColumn(
                            "Услуга",
                            options=srv_list
                        ),
                        "payment_date": st.column_config.DateColumn(
                            "Дата оплаты",
                            format="DD.MM.YYYY"
                        ),
                        "amount": st.column_config.TextColumn(
                            "Сумма",
                            help="В формате 000 000"
                        ),
                        "hours": st.column_config.NumberColumn(
                            "Часы",
                            format="%.1f",
                            step=0.1
                        )
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="items_editor"
                )

                # Сохранение изменений
                if not edited_items.equals(display_items):
                    for idx, row in edited_items.iterrows():
                        orig = items_df[items_df['id'] == row['id']].iloc[0]
                        
                        # Парсим сумму
                        amount_val = parse_currency(row['amount'])
                        payment_date_val = parse_date(row['payment_date'])
                        hours_val = float(row['hours'])
                        
                        run_query('''
                            UPDATE order_items 
                            SET service_name=?, payment_date=?, amount=?, hours=?
                            WHERE id=?
                        ''', (
                            row['service_name'],
                            payment_date_val,
                            amount_val,
                            hours_val,
                            int(row['id'])
                        ))
                    
                    # Обновляем сумму заказа
                    total = run_query(
                        "SELECT SUM(amount) as total FROM order_items WHERE order_id=?",
                        (order_id,),
                        fetch=True
                    )['total'].iloc[0] or 0.0
                    run_query(
                        "UPDATE orders SET total_amount=? WHERE id=?",
                        (total, order_id)
                    )
                    st.success("✅ Изменения сохранены!")
                    st.rerun()

                # Кнопка удаления
                if st.button("🗑️ Удалить выбранную услугу"):
                    selected = st.session_state.get("items_editor", {}).get("edited_rows", {})
                    if selected:
                        for row_idx in selected:
                            item_id = edited_items.at[row_idx, 'id']
                            run_query("DELETE FROM order_items WHERE id=?", (item_id,))
                        
                        # Обновляем сумму
                        total = run_query(
                            "SELECT SUM(amount) as total FROM order_items WHERE order_id=?",
                            (order_id,),
                            fetch=True
                        )['total'].iloc[0] or 0.0
                        run_query(
                            "UPDATE orders SET total_amount=? WHERE id=?",
                            (total, order_id)
                        )
                        st.rerun()
            else:
                st.info("Нет услуг в заказе")
    else:
        st.info("Сначала создайте заказ")

# --- 5. ОТЧЁТЫ ---
elif choice == "ОТЧЁТЫ":
    st.header("Аналитические Отчёты")
    
    # ... (осталось без изменений, как в предыдущем коде) ...