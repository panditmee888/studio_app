import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import plotly.express as px

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def format_date_display(date_str):
    """Форматирование даты в dd.mm.yyyy для отображения"""
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
    """Преобразует строку даты в формат БД (YYYY-MM-DD)"""
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
    """Форматирование валюты без дробей, с пробелами"""
    if pd.isna(amount) or amount is None:
        return "0"
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)

def parse_currency(amount_str):
    """Преобразует строку с пробелами в число"""
    if not amount_str or pd.isna(amount_str):
        return 0.0
    try:
        clean = str(amount_str).replace(" ", "").replace(",", "").replace("₽", "").strip()
        return float(clean) if clean else 0.0
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
    
    # Получаем группы для выбора
    groups_df = run_query("SELECT id, name FROM groups", fetch=True)
    groups_list = groups_df['name'].tolist() if not groups_df.empty else []
    group_map = dict(zip(groups_df['name'], groups_df['id'])) if not groups_df.empty else {}
    
    # Форма добавления клиента
    with st.expander("➕ Добавить нового клиента"):
        with st.form("add_client"):
            c_name = st.text_input("Имя")
            c_sex = st.selectbox("Пол", ["М", "Ж"])
            c_phone = st.text_input("Телефон")
            c_vk = st.text_input("VK ID")
            c_tg = st.text_input("Telegram ID")
            
            if groups_list:
                c_group = st.selectbox("Группа", options=["Без группы"] + groups_list)
            else:
                c_group = "Без группы"
                st.info("Группы еще не созданы")
            
            if st.form_submit_button("Сохранить клиента"):
                if c_name:
                    g_id = group_map.get(c_group) if c_group != "Без группы" else None
                    run_query('''INSERT INTO clients (name, sex, phone, vk_id, tg_id, group_id) 
                                 VALUES (?,?,?,?,?,?)''', (c_name, c_sex, c_phone, c_vk, c_tg, g_id))
                    st.success("Клиент добавлен")
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
                                st.success(f"Группа обновлена")
                                st.rerun()
                    with col_c:
                        if st.button("🗑️", key=f"delete_{row['id']}", help="Удалить"):
                            clients_check = run_query(
                                "SELECT COUNT(*) as count FROM clients WHERE group_id=?", 
                                (row['id'],), 
                                fetch=True
                            )
                            if not clients_check.empty and clients_check['count'].iloc[0] > 0:
                                st.warning(f"Нельзя удалить группу с клиентами!")
                            else:
                                run_query("DELETE FROM groups WHERE id=?", (row['id'],))
                                st.success(f"Группа удалена")
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

    # Формируем запрос
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
        
        # Преобразуем даты для отображения
        clients_df_data['first_order_date'] = clients_df_data['first_order_date'].apply(format_date_display)
        
        # Редактируемая таблица
        edited_clients = st.data_editor(
            clients_df_data,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "name": st.column_config.TextColumn("Имя", width="medium"),
                "sex": st.column_config.SelectboxColumn("Пол", options=["М", "Ж"], width="small"),
                "phone": st.column_config.TextColumn("Телефон", width="medium"),
                "vk_id": st.column_config.TextColumn("VK ID", width="medium"),
                "tg_id": st.column_config.TextColumn("Telegram", width="medium"),
                "group_name": st.column_config.SelectboxColumn(
                    "Группа", 
                    options=["Без группы"] + groups_list,
                    width="medium"
                ),
                "first_order_date": st.column_config.TextColumn("Первый заказ", width="medium")
            },
            hide_index=True,
            use_container_width=True,
            key="clients_editor"
        )

        # Проверяем изменения и сохраняем
        if not edited_clients.equals(clients_df_data):
            for idx in range(len(edited_clients)):
                orig_row = clients_df_data.iloc[idx]
                new_row = edited_clients.iloc[idx]
                
                if not orig_row.equals(new_row):
                    client_id = int(new_row['id'])
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
                "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "name": st.column_config.TextColumn("Услуга", width="large"),
                "min_price": st.column_config.NumberColumn(
                    "Мин. прайс ₽",
                    format="%.0f",
                    width="medium"
                ),
                "description": st.column_config.TextColumn("Описание", width="large")
            },
            hide_index=True,
            use_container_width=True,
            key="services_editor"
        )
        
        if not edited_services.equals(services_df):
            for idx in range(len(edited_services)):
                orig_row = services_df.iloc[idx]
                new_row = edited_services.iloc[idx]
                
                if not orig_row.equals(new_row):
                    run_query('''
                        UPDATE services_catalog 
                        SET name=?, min_price=?, description=?
                        WHERE id=?
                    ''', (
                        new_row['name'],
                        new_row['min_price'],
                        new_row['description'],
                        int(new_row['id'])
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

    with st.expander("➕ Создать новый заказ"):
        with st.form("new_order"):
            if client_names:
                o_client = st.selectbox("Клиент", client_names)
                o_date = st.date_input("Дата исполнения", value=date.today())
                o_status = st.selectbox("Статус", ["В работе", "Выполнен", "Отменен", "Оплачен"])
                
                if st.form_submit_button("Создать заказ"):
                    c_id = client_map.get(o_client)
                    run_query("INSERT INTO orders (client_id, execution_date, status) VALUES (?,?,?)", 
                              (c_id, o_date.strftime("%Y-%m-%d"), o_status))
                    run_query('''UPDATE clients SET first_order_date = ? 
                                 WHERE id = ? AND first_order_date IS NULL''', (o_date.strftime("%Y-%m-%d"), c_id))
                    st.success("Заказ создан!")
                    st.rerun()
            else:
                st.warning("Сначала добавьте клиентов")

    # Фильтры
    st.markdown("### 🔍 Фильтры")
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        order_search = st.text_input("Поиск по клиенту", placeholder="Имя клиента...")
    with filter_col2:
        status_filter = st.selectbox("Статус", ["Все", "В работе", "Выполнен", "Отменен", "Оплачен"])
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
        from datetime import timedelta
        last_week = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
        orders_query += " AND o.execution_date >= ?"
        params.append(last_week)

    orders_query += " ORDER BY o.id DESC"
    orders_df = run_query(orders_query, tuple(params), fetch=True)
    
    if not orders_df.empty:
        # Добавляем имя клиента для отображения
        orders_df['client_name'] = orders_df['client_id'].map(client_map_reverse)
        
        # Статистика за текущий месяц
        current_month_start = date.today().replace(day=1).strftime("%Y-%m-%d")
        stats_df = run_query(
            '''SELECT total_amount, status FROM orders 
               WHERE execution_date >= ?''',
            (current_month_start,),
            fetch=True
        )

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Всего заказов (месяц)", len(stats_df) if not stats_df.empty else 0)
        with col2:
            total_sum = stats_df['total_amount'].sum() if not stats_df.empty else 0
            st.metric("Общая сумма", f"{int(total_sum):,} ₽".replace(",", " "))
        with col3:
            avg_check = stats_df['total_amount'].mean() if not stats_df.empty and len(stats_df) > 0 else 0
            avg_text = f"{int(avg_check):,} ₽".replace(",", " ") if avg_check > 0 else "—"
            st.metric("Средний чек", avg_text)
        with col4:
            in_work = len(stats_df[stats_df['status'] == 'В работе']) if not stats_df.empty else 0
            st.metric("В работе", in_work)

        # Подготовка данных для редактора
        display_df = orders_df[['id', 'client_name', 'execution_date', 'status', 'total_amount']].copy()
        display_df['execution_date'] = display_df['execution_date'].apply(format_date_display)
        display_df['total_amount'] = display_df['total_amount'].apply(lambda x: format_currency(x) + " ₽")

        # Редактор заказов
        edited_orders = st.data_editor(
            display_df,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "client_name": st.column_config.SelectboxColumn(
                    "Клиент",
                    options=client_names,
                    width="medium"
                ),
                "execution_date": st.column_config.TextColumn(
                    "Дата исполнения",
                    width="medium"
                ),
                "status": st.column_config.SelectboxColumn(
                    "Статус",
                    options=["В работе", "Выполнен", "Отменен", "Оплачен"],
                    width="medium"
                ),
                "total_amount": st.column_config.TextColumn(
                    "Сумма",
                    disabled=True,
                    width="medium"
                )
            },
            hide_index=True,
            use_container_width=True,
            key="orders_editor"
        )

        # Сохранение изменений
        if not edited_orders.equals(display_df):
            for idx in range(len(edited_orders)):
                orig_row = display_df.iloc[idx]
                new_row = edited_orders.iloc[idx]
                
                if not orig_row.equals(new_row):
                    order_id = int(new_row['id'])
                    client_id = client_map.get(new_row['client_name'])
                    exec_date = parse_date_to_db(new_row['execution_date'])
                    
                    run_query('''
                        UPDATE orders 
                        SET client_id=?, execution_date=?, status=?
                        WHERE id=?
                    ''', (client_id, exec_date, new_row['status'], order_id))
            
            st.success("✅ Изменения сохранены!")
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

        # Получаем услуги из каталога
        services_cat = run_query("SELECT name FROM services_catalog", fetch=True)
        srv_list = services_cat['name'].tolist() if not services_cat.empty else []
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### ➕ Добавить услугу")
            with st.form("add_item_form"):
                service_choice = st.selectbox("Услуга", srv_list if srv_list else ["Нет услуг в каталоге"])
                i_date = st.date_input("Дата оплаты", value=date.today())
                
                # Поле суммы с форматированием
                amount_str = st.text_input("Сумма ₽", value="0", placeholder="Введите сумму...")
                clean_amount = amount_str.replace(" ", "").replace(",", "").replace("₽", "")
                try:
                    i_amount = float(clean_amount) if clean_amount else 0.0
                except:
                    i_amount = 0.0
                
                i_hours = st.number_input("Кол-во часов", min_value=0.0, step=0.5, value=0.0)
                
                if st.form_submit_button("Добавить услугу"):
                    if service_choice and i_amount > 0:
                        run_query(
                            '''INSERT INTO order_items 
                            (order_id, service_name, payment_date, amount, hours)
                            VALUES (?,?,?,?,?)''',
                            (order_id, service_choice, i_date.strftime("%Y-%m-%d"), i_amount, i_hours)
                        )
                        # Обновляем сумму заказа
                        total_res = run_query(
                            "SELECT SUM(amount) as total FROM order_items WHERE order_id=?",
                            (order_id,),
                            fetch=True
                        )
                        total = total_res['total'].iloc[0] if not total_res.empty and total_res['total'].iloc[0] else 0.0
                        run_query("UPDATE orders SET total_amount=? WHERE id=?", (total, order_id))
                        st.success("Услуга добавлена!")
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
                # Форматируем для отображения
                display_items = items_df.copy()
                display_items['payment_date'] = display_items['payment_date'].apply(format_date_display)
                display_items['amount'] = display_items['amount'].apply(format_currency)
                display_items['hours'] = display_items['hours'].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "0.0")

                edited_items = st.data_editor(
                    display_items,
                    column_config={
                        "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                        "service_name": st.column_config.SelectboxColumn(
                            "Услуга",
                            options=srv_list,
                            width="large"
                        ),
                        "payment_date": st.column_config.TextColumn(
                            "Дата оплаты",
                            width="medium"
                        ),
                        "amount": st.column_config.TextColumn(
                            "Сумма",
                            width="medium"
                        ),
                        "hours": st.column_config.TextColumn(
                            "Часы",
                            width="small"
                        )
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="items_editor"
                )

                # Сохранение изменений
                if not edited_items.equals(display_items):
                    for idx in range(len(edited_items)):
                        orig_row = display_items.iloc[idx]
                        new_row = edited_items.iloc[idx]
                        
                        if not orig_row.equals(new_row):
                            item_id = int(new_row['id'])
                            amount_val = parse_currency(new_row['amount'])
                            payment_date_val = parse_date_to_db(new_row['payment_date'])
                            try:
                                hours_val = float(new_row['hours'].replace(",", "."))
                            except:
                                hours_val = 0.0
                            
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
                    
                    # Обновляем сумму заказа
                    total_res = run_query(
                        "SELECT SUM(amount) as total FROM order_items WHERE order_id=?",
                        (order_id,),
                        fetch=True
                    )
                    total = total_res['total'].iloc[0] if not total_res.empty and total_res['total'].iloc[0] else 0.0
                    run_query("UPDATE orders SET total_amount=? WHERE id=?", (total, order_id))
                    st.success("✅ Изменения сохранены!")
                    st.rerun()

                # Итого
                total_amount = items_df['amount'].sum()
                st.info(f"💰 **Итого:** {format_currency(total_amount)} ₽")
                
                # Удаление услуги
                st.markdown("---")
                del_cols = st.columns([2, 1])
                with del_cols[0]:
                    del_id = st.selectbox("Выберите услугу для удаления", items_df['id'].tolist())
                with del_cols[1]:
                    if st.button("🗑️ Удалить", use_container_width=True):
                        run_query("DELETE FROM order_items WHERE id=?", (del_id,))
                        total_res = run_query(
                            "SELECT SUM(amount) as total FROM order_items WHERE order_id=?",
                            (order_id,),
                            fetch=True
                        )
                        total = total_res['total'].iloc[0] if not total_res.empty and total_res['total'].iloc[0] else 0.0
                        run_query("UPDATE orders SET total_amount=? WHERE id=?", (total, order_id))
                        st.success("Услуга удалена!")
                        st.rerun()
            else:
                st.info("В этом заказе пока нет услуг")
    else:
        st.info("Сначала создайте заказ")

# --- 5. ОТЧЁТЫ ---
elif choice == "ОТЧЁТЫ":
    st.header("📊 Аналитические Отчёты")
    
    main_query = '''
    SELECT o.id, o.execution_date, o.total_amount, c.name as client_name, c.first_order_date, g.name as group_name
    FROM orders o 
    JOIN clients c ON o.client_id = c.id
    LEFT JOIN groups g ON c.group_id = g.id
    '''
    df = run_query(main_query, fetch=True)
    
    if not df.empty:
        df['execution_date'] = pd.to_datetime(df['execution_date'])
        df['year'] = df['execution_date'].dt.year
        df['month'] = df['execution_date'].dt.month
        df['month_name'] = df['execution_date'].dt.strftime('%B')

        years = sorted(df['year'].unique())
        
        # Отчет 1
        st.subheader("1. Заказы за год по группам")
        sel_year_1 = st.selectbox("Выберите год", years, index=len(years)-1, key='y1')
        
        df_1 = df[df['year'] == sel_year_1].groupby('group_name').agg(
            Количество=('id', 'count'),
            Сумма=('total_amount', 'sum'),
            Среднее=('total_amount', 'mean')
        ).reset_index()
        df_1['Сумма'] = df_1['Сумма'].apply(lambda x: f"{int(x):,}".replace(",", " "))
        df_1['Среднее'] = df_1['Среднее'].apply(lambda x: f"{int(x):,}".replace(",", " "))
        st.dataframe(df_1, use_container_width=True, hide_index=True)

        # Отчет 2
        st.subheader("2. Заказы за год по клиентам")
        sel_year_2 = st.selectbox("Выберите год", years, index=len(years)-1, key='y2')
        
        df_2 = df[df['year'] == sel_year_2].groupby('client_name').agg(
            Количество=('id', 'count'),
            Сумма=('total_amount', 'sum')
        ).reset_index().sort_values(by='Сумма', ascending=False)
        df_2['Сумма'] = df_2['Сумма'].apply(lambda x: f"{int(x):,}".replace(",", " "))
        st.dataframe(df_2, use_container_width=True, hide_index=True)

        # Отчет 3
        st.subheader("3. Новые клиенты за год")
        sel_year_3 = st.selectbox("Выберите год", years, index=len(years)-1, key='y3')
        
        df_new_clients = run_query('''
            SELECT c.name, c.first_order_date, COUNT(o.id) as count, SUM(o.total_amount) as sum
            FROM clients c 
            JOIN orders o ON c.id = o.client_id
            WHERE strftime('%Y', c.first_order_date) = ?
            GROUP BY c.id
        ''', (str(sel_year_3),), fetch=True)
        
        if not df_new_clients.empty:
            df_new_clients['first_order_date'] = df_new_clients['first_order_date'].apply(format_date_display)
            df_new_clients['sum'] = df_new_clients['sum'].apply(lambda x: f"{int(x):,}".replace(",", " "))
            st.dataframe(df_new_clients, use_container_width=True, hide_index=True)
        else:
            st.info("Нет новых клиентов за этот год")

        # Отчет 4
        st.subheader("4. Сводка по годам")
        df_4 = df.groupby('year').agg(
            Количество=('id', 'count'),
            Макс_сумма=('total_amount', 'max'),
            Мин_сумма=('total_amount', 'min'),
            Средний_чек=('total_amount', 'mean'),
            Сумма_год=('total_amount', 'sum')
        ).reset_index()
        df_4['Средний_месячный'] = df_4['Сумма_год'] / 12
        
        # Сохраняем числовые значения для графика
        df_4_chart = df_4[['year', 'Сумма_год']].copy()
        
        df_4['Макс_сумма'] = df_4['Макс_сумма'].apply(lambda x: f"{int(x):,}".replace(",", " "))
        df_4['Мин_сумма'] = df_4['Мин_сумма'].apply(lambda x: f"{int(x):,}".replace(",", " "))
        df_4['Средний_чек'] = df_4['Средний_чек'].apply(lambda x: f"{int(x):,}".replace(",", " "))
        df_4['Сумма_год'] = df_4['Сумма_год'].apply(lambda x: f"{int(x):,}".replace(",", " "))
        df_4['Средний_месячный'] = df_4['Средний_месячный'].apply(lambda x: f"{int(x):,}".replace(",", " "))
        st.dataframe(df_4, use_container_width=True, hide_index=True)
        
        st.bar_chart(df_4_chart.set_index('year'))

        # Отчет 5
        st.subheader("5. Заказы за месяц (детализация)")
        c1, c2 = st.columns(2)
        with c1: 
            sel_year_5 = st.selectbox("Год", years, index=len(years)-1, key='y5')
        with c2: 
            sel_month_5 = st.selectbox("Месяц", range(1,13), index=date.today().month-1, key='m5')
        
        df_5 = df[(df['year'] == sel_year_5) & (df['month'] == sel_month_5)]
        df_5_res = df_5.groupby('client_name').agg(
            Количество=('id', 'count'),
            Сумма=('total_amount', 'sum')
        ).reset_index()
        df_5_res['Сумма'] = df_5_res['Сумма'].apply(lambda x: f"{int(x):,}".replace(",", " "))
        st.dataframe(df_5_res, use_container_width=True, hide_index=True)

        # Отчет 6
        st.subheader("6. Динамика по месяцам")
        sel_year_6 = st.selectbox("Выберите год", years, index=len(years)-1, key='y6')
        df_6 = df[df['year'] == sel_year_6].groupby('month').agg(
            Количество=('id', 'count'),
            Средний_чек=('total_amount', 'mean'),
            Сумма=('total_amount', 'sum')
        ).reset_index()
        
        df_6_chart = df_6[['month', 'Сумма']].copy()
        
        df_6['Средний_чек'] = df_6['Средний_чек'].apply(lambda x: f"{int(x):,}".replace(",", " "))
        df_6['Сумма'] = df_6['Сумма'].apply(lambda x: f"{int(x):,}".replace(",", " "))
        st.dataframe(df_6, use_container_width=True, hide_index=True)
        
        st.line_chart(df_6_chart.set_index('month'))

        # Отчет 7
        st.subheader("7. Оплаты за последнюю неделю")
        df_items = run_query('''
            SELECT c.name, oi.payment_date, SUM(oi.amount) as total_amount
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN clients c ON o.client_id = c.id
            WHERE oi.payment_date >= date('now','-7 days')
            GROUP BY c.name, oi.payment_date
            ORDER BY oi.payment_date DESC
        ''', fetch=True)
        
        if not df_items.empty:
            df_items['payment_date'] = df_items['payment_date'].apply(format_date_display)
            df_items['total_amount'] = df_items['total_amount'].apply(lambda x: f"{int(x):,}".replace(",", " "))
            st.dataframe(df_items, use_container_width=True, hide_index=True)
        else:
            st.info("Нет оплат за последнюю неделю")
    else:
        st.warning("В базе данных пока нет заказов для формирования отчётов.")