import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import plotly.express as px

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def format_date(date_str):
    """Форматирование даты в dd.mm.yyyy"""
    if pd.isna(date_str) or date_str is None:
        return ""
    try:
        if isinstance(date_str, str):
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            date_obj = pd.to_datetime(date_str)
        return date_obj.strftime("%d.%m.%Y")
    except:
        return str(date_str)

def format_currency(amount):
    """Форматирование валюты без дробей, с пробелами"""
    if pd.isna(amount) or amount is None:
        return "0"
    try:
        return f"{int(float(amount)):,.0f}".replace(",", " ")
    except:
        return str(amount)

def paginate_with_arrows(df, items_per_page=15, page_key="page"):
    """Постраничный просмотр с кнопками вперёд/назад"""
    if df.empty:
        return df, 1, 1
    
    total_items = len(df)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    # Если страница одна, просто возвращаем данные
    if total_pages <= 1:
        return df, 1, 1
    
    # Получаем текущую страницу из сессии
    if page_key not in st.session_state:
        st.session_state[page_key] = 1
    
    current_page = st.session_state[page_key]
    
    # Кнопки навигации
    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
    with col1:
        if st.button("⬅️ Назад", disabled=(current_page <= 1), use_container_width=True):
            st.session_state[page_key] = max(1, current_page - 1)
            st.rerun()
    with col2:
        st.write(f"Страница {current_page} из {total_pages}")
    with col3:
        if st.button("Вперёд ➡️", disabled=(current_page >= total_pages), use_container_width=True):
            st.session_state[page_key] = min(total_pages, current_page + 1)
            st.rerun()
    with col4:
        st.write(f"Записей: {total_items}")
    
    # Вычисляем срез данных
    start_idx = (current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_df = df.iloc[start_idx:end_idx]
    
    return page_df, current_page, total_pages

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
            
            # Получаем список групп для выбора
            groups_df = run_query("SELECT id, name FROM groups", fetch=True)
            if not groups_df.empty:
                group_options = groups_df['name'].tolist()
                group_map = dict(zip(groups_df['name'], groups_df['id']))
                c_group = st.selectbox("Группа", options=group_options)
            else:
                c_group = None
                st.info("Группы еще не созданы")
            
            if st.form_submit_button("Сохранить клиента"):
                if c_name:
                    g_id = group_map.get(c_group) if c_group else None
                    run_query('''INSERT INTO clients (name, sex, phone, vk_id, tg_id, group_id) 
                                 VALUES (?,?,?,?,?,?)''', (c_name, c_sex, c_phone, c_vk, c_tg, g_id))
                    st.success("Клиент добавлен")
                    st.rerun()
                else:
                    st.error("Введите имя клиента")

    # Кнопка для открытия модального окна с группами
    if st.button("⚙️ Управление группами клиентов"):
        st.session_state.show_groups = True
    
    # Модальное окно с группами
    if st.session_state.get("show_groups", False):
        with st.expander("⚙️ Группы клиентов", expanded=True):
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
                    st.dataframe(groups_df, hide_index=True)
                else:
                    st.info("Групп пока нет")
            
            if st.button("Закрыть"):
                st.session_state.show_groups = False
                st.rerun()

    # Поиск и фильтрация клиентов
    st.markdown("### 🔍 Поиск и фильтрация")
    search_col1, search_col2 = st.columns([2, 1])
    with search_col1:
        search_query = st.text_input("Поиск по имени, телефону, VK или Telegram", placeholder="Введите текст для поиска...")
    with search_col2:
        # Получаем список групп для фильтра
        groups_df = run_query("SELECT name FROM groups", fetch=True)
        groups_list = groups_df['name'].tolist() if not groups_df.empty else []
        filter_group = st.selectbox("Фильтр по группе", ["Все"] + groups_list)

    # Отображение клиентов с поиском
    clients_query = '''
    SELECT c.id, c.name, c.sex, c.phone, c.vk_id, c.tg_id, g.name as group_name, c.first_order_date
    FROM clients c LEFT JOIN groups g ON c.group_id = g.id
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
    
    clients_query += ' ORDER BY c.id DESC'
    
    clients_df = run_query(clients_query, tuple(params), fetch=True)
    
    if not clients_df.empty:
        # Применяем форматирование к столбцам
        clients_df['first_order_date'] = clients_df['first_order_date'].apply(format_date)
        
        # Отображаем количество найденных
        st.info(f"Найдено клиентов: {len(clients_df)}")
        
        # Используем пагинацию с кнопками вперёд/назад
        page_df, current_page, total_pages = paginate_with_arrows(clients_df, items_per_page=15, page_key="clients_page")
        
        # Отображаем таблицу
        st.dataframe(page_df, use_container_width=True)
        
        # Кнопка для редактирования (Double-Click эмуляция)
        st.markdown("### ✏️ Редактирование записи")
        st.info("Для редактирования записи выберите её ID из таблицы выше")
        edit_id = st.number_input("ID клиента для редактирования", min_value=0, step=1)
        
        if edit_id > 0:
            # Получаем данные клиента
            client_data = run_query("SELECT * FROM clients WHERE id=?", (edit_id,), fetch=True)
            if not client_data.empty:
                with st.expander(f"Редактирование клиента #{edit_id}"):
                    with st.form("edit_client"):
                        c_name = st.text_input("Имя", value=client_data['name'].iloc[0])
                        c_sex = st.selectbox("Пол", ["М", "Ж"], index=0 if client_data['sex'].iloc[0] == "М" else 1)
                        c_phone = st.text_input("Телефон", value=client_data['phone'].iloc[0])
                        c_vk = st.text_input("VK ID", value=client_data['vk_id'].iloc[0])
                        c_tg = st.text_input("Telegram ID", value=client_data['tg_id'].iloc[0])
                        
                        # Группы для выбора
                        groups_df = run_query("SELECT id, name FROM groups", fetch=True)
                        if not groups_df.empty:
                            group_options = groups_df['name'].tolist()
                            group_map = dict(zip(groups_df['name'], groups_df['id']))
                            current_group_id = client_data['group_id'].iloc[0]
                            current_group_name = ""
                            if current_group_id:
                                group_name_result = run_query("SELECT name FROM groups WHERE id=?", (current_group_id,), fetch=True)
                                if not group_name_result.empty:
                                    current_group_name = group_name_result['name'].iloc[0]
                            
                            c_group = st.selectbox("Группа", options=group_options, 
                                                  index=group_options.index(current_group_name) if current_group_name in group_options else 0)
                        else:
                            c_group = None
                        
                        if st.form_submit_button("Обновить клиента"):
                            g_id = group_map.get(c_group) if c_group else None
                            run_query('''UPDATE clients SET name=?, sex=?, phone=?, vk_id=?, tg_id=?, group_id=? 
                                         WHERE id=?''', (c_name, c_sex, c_phone, c_vk, c_tg, g_id, edit_id))
                            st.success("Клиент обновлен!")
                            st.rerun()
            else:
                st.error("Клиент с таким ID не найден")
    else:
        if search_query or filter_group != "Все":
            st.warning("По вашему запросу ничего не найдено")
        else:
            st.info("Клиенты еще не добавлены")

# --- 2. ПРАЙС-ЛИСТ ---
elif choice == "Прайс-лист Услуг":
    st.subheader("Справочник Услуг")
    
    # Форма добавления услуги (без "Другое")
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
    
    st.subheader("Список услуг")
    services_df = run_query("SELECT * FROM services_catalog", fetch=True)
    
    if not services_df.empty:
        # Форматируем сумму
        services_df['min_price'] = services_df['min_price'].apply(format_currency)
        
        # Отображаем таблицу
        st.dataframe(services_df, use_container_width=True)
        
        # Редактирование услуги
        st.markdown("### ✏️ Редактирование услуги")
        edit_id = st.number_input("ID услуги для редактирования", min_value=0, step=1)
        
        if edit_id > 0:
            service_data = run_query("SELECT * FROM services_catalog WHERE id=?", (edit_id,), fetch=True)
            if not service_data.empty:
                with st.expander(f"Редактирование услуги #{edit_id}"):
                    with st.form("edit_service"):
                        s_name = st.text_input("Наименование услуги", value=service_data['name'].iloc[0])
                        s_price = st.number_input("Мин. прайс", min_value=0.0, step=100.0, value=float(service_data['min_price'].iloc[0]))
                        s_desc = st.text_area("Описание", value=service_data['description'].iloc[0])
                        
                        if st.form_submit_button("Обновить услугу"):
                            run_query('''UPDATE services_catalog SET name=?, min_price=?, description=? 
                                         WHERE id=?''', (s_name, s_price, s_desc, edit_id))
                            st.success("Услуга обновлена!")
                            st.rerun()
            else:
                st.error("Услуга с таким ID не найдена")
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
                    st.success("Заказ создан! Перейдите в 'Детализация Заказа' для добавления услуг.")
                    st.rerun()
            else:
                st.warning("Сначала добавьте клиентов")

    # Поиск и фильтрация заказов
    st.markdown("### 🔍 Поиск и фильтрация")
    search_col1, search_col2, search_col3 = st.columns([2, 1, 1])
    
    with search_col1:
        order_search = st.text_input("Поиск по имени клиента", placeholder="Введите имя клиента...")
    with search_col2:
        status_filter = st.selectbox("Статус", ["Все", "В работе", "Выполнен", "Отменен", "Оплачен"])
    with search_col3:
        date_filter = st.selectbox("Период", ["Все время", "Последние 30 дней", "Последние 7 дней", "Сегодня"])

    # Таблица заказов
    orders_sql = '''
    SELECT o.id, c.name as Client, o.execution_date, o.status, o.total_amount 
    FROM orders o JOIN clients c ON o.client_id = c.id
    WHERE 1=1
    '''
    
    params = []
    
    if order_search:
        orders_sql += ' AND LOWER(c.name) LIKE LOWER(?)'
        params.append(f'%{order_search}%')
    
    if status_filter != "Все":
        orders_sql += ' AND o.status = ?'
        params.append(status_filter)
    
    if date_filter == "Последние 30 дней":
        orders_sql += ' AND o.execution_date >= date("now", "-30 days")'
    elif date_filter == "Последние 7 дней":
        orders_sql += ' AND o.execution_date >= date("now", "-7 days")'
    elif date_filter == "Сегодня":
        orders_sql += ' AND o.execution_date = date("now")'
    
    orders_sql += ' ORDER BY o.execution_date DESC'
    
    df_orders = run_query(orders_sql, tuple(params), fetch=True)
    
    if not df_orders.empty:
        # Форматируем столбцы
        df_orders['execution_date'] = df_orders['execution_date'].apply(format_date)
        df_orders['total_amount'] = df_orders['total_amount'].apply(format_currency)
        
        # Статистика
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Всего заказов", len(df_orders))
        with col2:
            # Для статистики нужно оригинальные числа
            original_df = run_query(orders_sql, tuple(params), fetch=True)
            total_sum = original_df['total_amount'].sum()
            st.metric("Общая сумма", f"{int(total_sum):,.0f} ₽".replace(",", " "))
        with col3:
            avg_check = original_df['total_amount'].mean()
            st.metric("Средний чек", f"{int(avg_check):,.0f} ₽".replace(",", " "))
        with col4:
            in_work = len(original_df[original_df['status'] == 'В работе'])
            st.metric("В работе", in_work)
        
        # Пагинация с кнопками
        page_df, current_page, total_pages = paginate_with_arrows(df_orders, items_per_page=15, page_key="orders_page")
        st.dataframe(page_df, use_container_width=True)
        
        # Редактирование заказа
        st.markdown("### ✏️ Редактирование заказа")
        edit_id = st.number_input("ID заказа для редактирования", min_value=0, step=1)
        
        if edit_id > 0:
            order_data = run_query("SELECT * FROM orders WHERE id=?", (edit_id,), fetch=True)
            if not order_data.empty:
                with st.expander(f"Редактирование заказа #{edit_id}"):
                    with st.form("edit_order"):
                        # Получаем список клиентов для выбора
                        clients_df = run_query("SELECT id, name FROM clients", fetch=True)
                        client_options = clients_df['name'].tolist()
                        client_map = dict(zip(clients_df['name'], clients_df['id']))
                        
                        current_client_id = order_data['client_id'].iloc[0]
                        client_name_result = run_query("SELECT name FROM clients WHERE id=?", (current_client_id,), fetch=True)
                        current_client_name = client_name_result['name'].iloc[0] if not client_name_result.empty else ""
                        
                        o_client = st.selectbox("Клиент", options=client_options, 
                                               index=client_options.index(current_client_name) if current_client_name in client_options else 0)
                        o_date = st.date_input("Дата исполнения", value=datetime.strptime(order_data['execution_date'].iloc[0], "%Y-%m-%d").date())
                        o_status = st.selectbox("Статус", ["В работе", "Выполнен", "Отменен", "Оплачен"], 
                                               index=["В работе", "Выполнен", "Отменен", "Оплачен"].index(order_data['status'].iloc[0]))
                        
                        if st.form_submit_button("Обновить заказ"):
                            c_id = client_map.get(o_client)
                            run_query('''UPDATE orders SET client_id=?, execution_date=?, status=? 
                                         WHERE id=?''', (c_id, o_date, o_status, edit_id))
                            st.success("Заказ обновлен!")
                            st.rerun()
            else:
                st.error("Заказ с таким ID не найден")
    else:
        if order_search or status_filter != "Все" or date_filter != "Все время":
            st.warning("По вашему запросу заказы не найдены")
        else:
            st.info("Заказы еще не созданы")

# --- 4. ДЕТАЛИЗАЦИЯ ЗАКАЗА ---
elif choice == "Детализация Заказа":
    st.subheader("Внутренние услуги заказа")
    
    orders_df = run_query("SELECT o.id, c.name, o.execution_date FROM orders o JOIN clients c ON o.client_id = c.id", fetch=True)
    if not orders_df.empty:
        orders_df['label'] = orders_df.apply(lambda x: f"Заказ #{x['id']} - {x['name']} ({x['execution_date']})", axis=1)
        order_selection = st.selectbox("Выберите заказ для редактирования", orders_df['label'])
        order_id = int(orders_df[orders_df['label'] == order_selection]['id'].values[0])

        services_cat = run_query("SELECT name FROM services_catalog", fetch=True)
        srv_list = services_cat['name'].tolist() if not services_cat.empty else []
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Добавить услугу")
            with st.form("add_item_form"):
                # Убираем "Другое", только выбор из каталога
                service_choice = st.selectbox("Услуга (из каталога)", srv_list)
                
                i_date = st.date_input("Дата оплаты", value=date.today())
                # Убираем значки +/-
                i_amount = st.number_input("Сумма", min_value=0.0, step=100.0, value=0.0)
                # Убираем значки +/-
                i_hours = st.number_input("Кол-во часов", min_value=0.0, step=0.1, value=0.0, format="%.1f")
                
                submitted = st.form_submit_button("Добавить услугу")
                if submitted:
                    if service_choice and i_amount > 0:
                        try:
                            run_query(
                                "INSERT INTO order_items (order_id, service_name, payment_date, amount, hours) VALUES (?,?,?,?,?)",
                                (order_id, service_choice, str(i_date), float(i_amount), float(i_hours))
                            )
                            run_query(
                                "UPDATE orders SET total_amount = (SELECT COALESCE(SUM(amount), 0) FROM order_items WHERE order_id=?) WHERE id=?",
                                (order_id, order_id)
                            )
                            st.success(f"✅ Услуга '{service_choice}' добавлена в заказ!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка при добавлении: {e}")
                    else:
                        st.error("⚠️ Заполните название услуги и сумму")
        
        with col2:
            st.markdown(f"#### Состав заказа #{order_id}")
            items_df = run_query(
                "SELECT id, service_name, payment_date, amount, hours FROM order_items WHERE order_id=?",
                (order_id,),
                fetch=True
            )
            
            if not items_df.empty:
                # Форматируем столбцы
                items_df['payment_date'] = items_df['payment_date'].apply(format_date)
                items_df['amount'] = items_df['amount'].apply(format_currency)
                items_df['hours'] = items_df['hours'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "0.0")
                
                st.dataframe(items_df, hide_index=True)
                
                # Статистика
                original_items = run_query(
                    "SELECT amount FROM order_items WHERE order_id=?",
                    (order_id,),
                    fetch=True
                )
                total_amount = original_items['amount'].sum()
                st.info(f"💰 Общая сумма: {int(total_amount):,.0f} ₽".replace(",", " "))
                
                # Удаление услуги
                with st.form("delete_item_form"):
                    del_id = st.selectbox("Выберите ID услуги для удаления", items_df['id'].tolist())
                    if st.form_submit_button("🗑️ Удалить услугу"):
                        run_query("DELETE FROM order_items WHERE id=?", (del_id,))
                        run_query(
                            "UPDATE orders SET total_amount = (SELECT COALESCE(SUM(amount), 0) FROM order_items WHERE order_id=?) WHERE id=?",
                            (order_id, order_id)
                        )
                        st.success("Услуга удалена!")
                        st.rerun()
            else:
                st.info("В этом заказе еще нет услуг")
    else:
        st.info("Сначала создайте заказ.")

# --- 5. ОТЧЁТЫ ---
elif choice == "ОТЧЁТЫ":
    st.header("Аналитические Отчёты")
    
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
        
        # Отчет 1: Заказы за год по группам
        st.subheader("1. Заказы за год по группам")
        sel_year_1 = st.selectbox("Выберите год (Группы)", years, index=len(years)-1)
        
        df_1 = df[df['year'] == sel_year_1].groupby('group_name').agg(
            Количество=('id', 'count'),
            Сумма=('total_amount', 'sum'),
            Среднее=('total_amount', 'mean')
        ).reset_index()
        # Форматируем сумму
        df_1['Сумма'] = df_1['Сумма'].apply(lambda x: f"{int(x):,.0f}".replace(",", " "))
        df_1['Среднее'] = df_1['Среднее'].apply(lambda x: f"{int(x):,.0f}".replace(",", " "))
        st.dataframe(df_1, use_container_width=True)

        # Отчет 2: Заказы за год по клиентам
        st.subheader("2. Заказы за год по клиентам")
        sel_year_2 = st.selectbox("Выберите год (Клиенты)", years, index=len(years)-1, key='y2')
        
        df_2 = df[df['year'] == sel_year_2].groupby('client_name').agg(
            Количество=('id', 'count'),
            Сумма=('total_amount', 'sum')
        ).reset_index().sort_values(by='Сумма', ascending=False)
        # Форматируем сумму
        df_2['Сумма'] = df_2['Сумма'].apply(lambda x: f"{int(x):,.0f}".replace(",", " "))
        st.dataframe(df_2, use_container_width=True)

        # Отчет 3: Новые клиенты за год
        st.subheader("3. Новые клиенты за год")
        sel_year_3 = st.selectbox("Выберите год (Новые клиенты)", years, index=len(years)-1, key='y3')
        
        df_new_clients = run_query('''
            SELECT c.name, c.first_order_date, COUNT(o.id) as count, SUM(o.total_amount) as sum
            FROM clients c 
            JOIN orders o ON c.id = o.client_id
            WHERE strftime('%Y', c.first_order_date) = ?
            GROUP BY c.id
        ''', (str(sel_year_3),), fetch=True)
        
        if not df_new_clients.empty:
            # Форматируем дату и сумму
            df_new_clients['first_order_date'] = df_new_clients['first_order_date'].apply(format_date)
            df_new_clients['sum'] = df_new_clients['sum'].apply(lambda x: f"{int(x):,.0f}".replace(",", " "))
            st.dataframe(df_new_clients, use_container_width=True)

        # Отчет 4: Сводка по годам
        st.subheader("4. Сводка по годам")
        df_4 = df.groupby('year').agg(
            Количество=('id', 'count'),
            Макс_сумма=('total_amount', 'max'),
            Мин_сумма=('total_amount', 'min'),
            Средний_чек=('total_amount', 'mean'),
            Сумма_год=('total_amount', 'sum')
        ).reset_index()
        df_4['Средний_месячный'] = df_4['Сумма_год'] / 12
        # Форматируем столбцы
        df_4['Макс_сумма'] = df_4['Макс_сумма'].apply(lambda x: f"{int(x):,.0f}".replace(",", " "))
        df_4['Мин_сумма'] = df_4['Мин_сумма'].apply(lambda x: f"{int(x):,.0f}".replace(",", " "))
        df_4['Средний_чек'] = df_4['Средний_чек'].apply(lambda x: f"{int(x):,.0f}".replace(",", " "))
        df_4['Сумма_год'] = df_4['Сумма_год'].apply(lambda x: f"{int(x):,.0f}".replace(",", " "))
        df_4['Средний_месячный'] = df_4['Средний_месячный'].apply(lambda x: f"{int(x):,.0f}".replace(",", " "))
        st.dataframe(df_4, use_container_width=True)
        st.bar_chart(df_4, x='year', y='Сумма_год')

        # Отчет 5: Заказы за месяц
        st.subheader("5. Заказы за месяц (детализация)")
        c1, c2 = st.columns(2)
        with c1: sel_year_5 = st.selectbox("Год", years, index=len(years)-1, key='y5')
        with c2: sel_month_5 = st.selectbox("Месяц", range(1,13), key='m5')
        
        df_5 = df[(df['year'] == sel_year_5) & (df['month'] == sel_month_5)]
        df_5_res = df_5.groupby('client_name').agg(
            Количество=('id', 'count'),
            Сумма=('total_amount', 'sum')
        ).reset_index()
        # Форматируем сумму
        df_5_res['Сумма'] = df_5_res['Сумма'].apply(lambda x: f"{int(x):,.0f}".replace(",", " "))
        st.dataframe(df_5_res, use_container_width=True)

        # Отчет 6: Динамика по месяцам
        st.subheader("6. Динамика по месяцам")
        sel_year_6 = st.selectbox("Выберите год", years, index=len(years)-1, key='y6')
        df_6 = df[df['year'] == sel_year_6].groupby('month').agg(
            Количество=('id', 'count'),
            Средний_чек=('total_amount', 'mean'),
            Сумма=('total_amount', 'sum')
        ).reset_index()
        # Форматируем столбцы
        df_6['Средний_чек'] = df_6['Средний_чек'].apply(lambda x: f"{int(x):,.0f}".replace(",", " "))
        df_6['Сумма'] = df_6['Сумма'].apply(lambda x: f"{int(x):,.0f}".replace(",", " "))
        st.dataframe(df_6, use_container_width=True)
        st.line_chart(df_6, x='month', y='Сумма')

        # Отчет 7: Оплаты за неделю
        st.subheader("7. Оплаты за последнюю неделю")
        df_items = run_query('''
            SELECT c.name, oi.payment_date, oi.amount 
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN clients c ON o.client_id = c.id
        ''', fetch=True)
        
        if not df_items.empty:
            df_items['payment_date'] = pd.to_datetime(df_items['payment_date'])
            week_ago = pd.Timestamp.now() - pd.Timedelta(days=7)
            df_7 = df_items[df_items['payment_date'] >= week_ago]
            # Форматируем дату и сумму
            df_7['payment_date'] = df_7['payment_date'].apply(format_date)
            df_7['amount'] = df_7['amount'].apply(lambda x: f"{int(x):,.0f}".replace(",", " "))
            st.dataframe(df_7, use_container_width=True)
        else:
            st.write("Нет данных об оплатах.")
    else:
        st.warning("В базе данных пока нет заказов для формирования отчётов.")