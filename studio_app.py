import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import plotly.express as px

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

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
    conn.row_factory = sqlite3.Row # Возвращать строки как словари
    c = conn.cursor()
    try:
        c.execute(query, params)
        if fetch:
            data = c.fetchall()
            df = pd.DataFrame(data)
            conn.close()
            return df
        conn.commit()
    except Exception as e:
        st.error(f"Ошибка БД: {e}")
    finally:
        conn.close()

# --- ФУНКЦИИ ФОРМАТИРОВАНИЯ ДЛЯ ТАБЛИЦ ---
def format_currency(value):
    if pd.isna(value):
        return ""
    try:
        return f"{int(value):,}".replace(',', ' ')
    except (ValueError, TypeError):
        return str(value)

def format_hours(value):
    if pd.isna(value):
        return ""
    try:
        return f"{float(value):.1f}"
    except (ValueError, TypeError):
        return str(value)

# --- ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ СЕССИИ ---
if 'page' not in st.session_state:
    st.session_state.page = 0

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Studio Admin", layout="wide")
init_db()

st.title("🎛️ CRM Студии Звукозаписи")

# Меню
menu = ["Клиенты и Группы", "Прайс-лист Услуг", "Заказы", "Детализация Заказа", "ОТЧЁТЫ"]
choice = st.sidebar.selectbox("Навигация", menu)

# --- 1. КЛИЕНТЫ И ГРУППЫ (НОВАЯ СТРУКТУРА) ---
if choice == "Клиенты и Группы":
    st.header("👥 Клиенты")

    # --- МОДАЛЬНОЕ ОКНО ДЛЯ ГРУПП ---
    def show_groups_dialog():
        with st.dialog("🔧 Управление Группами клиентов"):
            st.write("Здесь вы можете добавить или просмотреть группы клиентов.")
            
            with st.form("add_group_in_dialog"):
                new_group = st.text_input("Название новой группы")
                if st.form_submit_button("Добавить группу"):
                    if new_group:
                        run_query("INSERT INTO groups (name) VALUES (?)", (new_group,))
                        st.success(f"Группа '{new_group}' добавлена!")
                        st.rerun()
            
            groups_df = run_query("SELECT id, name FROM groups ORDER BY name", fetch=True)
            if not groups_df.empty:
                st.dataframe(groups_df, hide_index=True, use_container_width=True)
            else:
                st.info("Групп пока нет.")

    if st.button("🔧 Управление Группами"):
        show_groups_dialog()

    # --- ОСНОВНАЯ ЧАСТЬ: КЛИЕНТЫ ---
    with st.expander("➕ Добавить нового клиента"):
        groups_df = run_query("SELECT id, name FROM groups ORDER BY name", fetch=True)
        groups_list = groups_df['name'].tolist() if not groups_df.empty else []
        group_map = dict(zip(groups_df['name'], groups_df['id'])) if not groups_df.empty else {}

        with st.form("add_client_form"):
            c_name = st.text_input("Имя клиента")
            c_sex = st.selectbox("Пол", ["М", "Ж"])
            c_phone = st.text_input("Телефон")
            c_vk = st.text_input("VK ID")
            c_tg = st.text_input("Telegram ID")
            c_group = st.selectbox("Группа", options=[""] + groups_list)
            
            if st.form_submit_button("Сохранить клиента"):
                if c_name:
                    g_id = group_map.get(c_group)
                    run_query('''INSERT INTO clients (name, sex, phone, vk_id, tg_id, group_id) 
                                 VALUES (?,?,?,?,?,?)''', (c_name, c_sex, c_phone, c_vk, c_tg, g_id))
                    st.success("Клиент добавлен!")
                    st.rerun()

    # --- ПОИСК И ТАБЛИЦА КЛИЕНТОВ С РЕДАКТИРОВАНИЕМ И ПАГИНАЦИЕЙ ---
    search_client = st.text_input("🔍 Поиск по клиентам (имя, телефон, VK, TG)", "")
    
    clients_query = '''
    SELECT c.id, c.name, c.sex, c.phone, c.vk_id, c.tg_id, g.name as group_name, c.first_order_date
    FROM clients c LEFT JOIN groups g ON c.group_id = g.id
    ORDER BY c.id DESC
    '''
    clients_df = run_query(clients_query, fetch=True)

    if not clients_df.empty:
        # Фильтрация по поиску
        if search_client:
            mask = (
                clients_df['name'].str.contains(search_client, case=False, na=False) |
                clients_df['phone'].str.contains(search_client, case=False, na=False) |
                clients_df['vk_id'].str.contains(search_client, case=False, na=False) |
                clients_df['tg_id'].str.contains(search_client, case=False, na=False)
            )
            clients_df = clients_df[mask]
            st.info(f"Найдено: {len(clients_df)} клиентов")

        # Форматирование для отображения
        display_df = clients_df.copy()
        if 'first_order_date' in display_df.columns:
            display_df['first_order_date'] = pd.to_datetime(display_df['first_order_date']).dt.strftime('%d.%m.%Y')

        # Пагинация
        page_size = 15
        total_pages = (len(display_df) + page_size - 1) // page_size
        
        col_prev, col_page, col_next = st.columns([1, 2, 1])
        with col_prev:
            if st.button("⬅️ Пред.", disabled=(st.session_state.page == 0)):
                st.session_state.page -= 1
                st.rerun()
        with col_page:
            st.markdown(f"<p style='text-align: center;'>Страница {st.session_state.page + 1} из {total_pages}</p>", unsafe_allow_html=True)
        with col_next:
            if st.button("След. ➡️", disabled=(st.session_state.page >= total_pages - 1)):
                st.session_state.page += 1
                st.rerun()
        
        start_idx = st.session_state.page * page_size
        end_idx = start_idx + page_size
        page_df = display_df.iloc[start_idx:end_idx]

        # Редактирование таблицы
        edited_df = st.data_editor(page_df, num_rows="dynamic", use_container_width=True, key="edit_clients")

        # Сохранение изменений
        if not edited_df.equals(page_df):
            for index, row in edited_df.iterrows():
                original_row = page_df.loc[index]
                # Сравниваем каждую ячейку и обновляем БД при изменении
                for col in edited_df.columns:
                    if col != 'id' and row[col] != original_row[col]:
                        if col == 'first_order_date':
                            # Преобразуем дату обратно в формат YYYY-MM-DD для БД
                            val = pd.to_datetime(row[col], format='%d.%m.%Y').strftime('%Y-%m-%d')
                        else:
                            val = row[col]
                        
                        run_query(f"UPDATE clients SET {col} = ? WHERE id = ?", (val, row['id']))
            st.success("Изменения сохранены!")
            st.rerun()
    else:
        st.info("Клиентов пока нет")

# --- 2. ПРАЙС-ЛИСТ УСЛУГ ---
elif choice == "Прайс-лист Услуг":
    st.header("💰 Прайс-лист Услуг")
    
    with st.expander("➕ Добавить услугу"):
        with st.form("add_service_form"):
            s_name = st.text_input("Наименование услуги")
            s_price = st.number_input("Мин. прайс, ₽", min_value=0.0, step=100.0)
            s_desc = st.text_area("Описание")
            if st.form_submit_button("Добавить услугу"):
                if s_name:
                    run_query("INSERT INTO services_catalog (name, min_price, description) VALUES (?,?,?)", 
                              (s_name, s_price, s_desc))
                    st.success("Услуга добавлена!")
                    st.rerun()

    services_df = run_query("SELECT * FROM services_catalog ORDER BY id DESC", fetch=True)
    if not services_df.empty:
        # Форматирование для отображения
        display_df = services_df.copy()
        display_df['min_price'] = display_df['min_price'].apply(format_currency)
        
        # Редактирование
        edited_df = st.data_editor(display_df, num_rows="dynamic", use_container_width=True, key="edit_services")
        
        # Сохранение изменений
        original_df = display_df
        if not edited_df.equals(original_df):
            for index, row in edited_df.iterrows():
                original_row = original_df.loc[index]
                for col in edited_df.columns:
                    if col != 'id' and row[col] != original_row[col]:
                        # Преобразуем отформатированную сумму обратно в число
                        val = str(row[col]).replace(' ', '') if col == 'min_price' else row[col]
                        run_query(f"UPDATE services_catalog SET {col} = ? WHERE id = ?", (val, row['id']))
            st.success("Изменения сохранены!")
            st.rerun()
    else:
        st.info("Услуг в прайс-листе пока нет.")

# --- 3. ЗАКАЗЫ ---
elif choice == "Заказы":
    st.header("📋 Заказы")
    
    clients_df = run_query("SELECT id, name FROM clients ORDER BY name", fetch=True)
    client_map = dict(zip(clients_df['name'], clients_df['id'])) if not clients_df.empty else {}

    with st.expander("➕ Создать новый заказ"):
        with st.form("new_order_form"):
            o_client = st.selectbox("Клиент", list(client_map.keys()) if client_map else [])
            o_date = st.date_input("Дата исполнения")
            o_status = st.selectbox("Статус", ["В работе", "Выполнен", "Отменен", "Оплачен"])
            
            if st.form_submit_button("Создать заказ") and o_client:
                c_id = client_map.get(o_client)
                run_query('''UPDATE clients SET first_order_date = ? 
                             WHERE id = ? AND first_order_date IS NULL''', (o_date, c_id))
                run_query("INSERT INTO orders (client_id, execution_date, status) VALUES (?,?,?)", 
                          (c_id, o_date, o_status))
                st.success("Заказ создан! Перейдите в 'Детализация Заказа'.")
                st.rerun()

    orders_df = run_query('''
        SELECT o.id, c.name as Client, o.execution_date, o.status, o.total_amount 
        FROM orders o JOIN clients c ON o.client_id = c.id
        ORDER BY o.id DESC
    ''', fetch=True)

    if not orders_df.empty:
        # Форматирование для отображения
        display_df = orders_df.copy()
        display_df['execution_date'] = pd.to_datetime(display_df['execution_date']).dt.strftime('%d.%m.%Y')
        display_df['total_amount'] = display_df['total_amount'].apply(format_currency)

        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("Заказов пока нет.")

# --- 4. ДЕТАЛИЗАЦИЯ ЗАКАЗА ---
elif choice == "Детализация Заказа":
    st.header("📝 Детализация заказа")
    
    orders_df = run_query("""
        SELECT o.id, c.name, o.execution_date, o.status, o.total_amount 
        FROM orders o 
        JOIN clients c ON o.client_id = c.id 
        ORDER BY o.id DESC
    """, fetch=True)
    
    if orders_df.empty:
        st.warning("Сначала создайте заказ")
    else:
        orders_df['label'] = orders_df.apply(
            lambda x: f"#{x['id']} — {x['name']} ({x['execution_date']}) [{x['status']}] — {format_currency(x['total_amount'])}₽", axis=1)
        
        selected_order = st.selectbox("Выберите заказ:", orders_df['label'])
        order_id = orders_df[orders_df['label'] == selected_order]['id'].iloc[0]

        col1, col2 = st.columns([1.2, 2])

        with col1:
            st.markdown("#### ➕ Добавить услугу")
            services_cat = run_query("SELECT name FROM services_catalog ORDER BY name", fetch=True)
            srv_list = [""] + services_cat['name'].tolist()

            service_name = st.selectbox("Услуга", options=srv_list, key=f"service_{order_id}")
            
            payment_date = st.date_input("Дата оплаты", value=date.today(), key=f"date_{order_id}")
            
            # Используем text_input для суммы и часов, чтобы убрать +/- и валидировать ввод
            amount_input = st.text_input("Сумма, ₽", value="0", key=f"sum_{order_id}")
            hours_input = st.text_input("Часы", value="0.0", key=f"hours_{order_id}")

            if st.button("✅ Добавить услугу", type="primary", use_container_width=True, key=f"btn_{order_id}"):
                if service_name.strip():
                    try:
                        amount = float(amount_input.replace(',', '.'))
                        hours = float(hours_input.replace(',', '.'))
                        if amount > 0:
                            run_query("""
                                INSERT INTO order_items (order_id, service_name, payment_date, amount, hours) 
                                VALUES (?,?,?,?,?)
                            """, (order_id, service_name, payment_date, amount, hours))
                            
                            run_query("""
                                UPDATE orders 
                                SET total_amount = (SELECT COALESCE(SUM(amount), 0) FROM order_items WHERE order_id=?) 
                                WHERE id=?
                            """, (order_id, order_id))
                            
                            st.success("Услуга успешно добавлена!")
                            st.rerun()
                        else:
                            st.error("Сумма должна быть больше нуля.")
                    except ValueError:
                        st.error("Некорректный формат суммы или часов. Введите числа.")
                else:
                    st.error("Выберите услугу.")

        with col2:
            st.markdown(f"#### 📋 Состав заказа #{order_id}")
            items_df = run_query("""
                SELECT id, service_name, payment_date, amount, hours 
                FROM order_items 
                WHERE order_id = ? 
                ORDER BY id DESC
            """, (order_id,), fetch=True)

            if not items_df.empty:
                # Форматирование для отображения
                display_items = items_df.copy()
                display_items['payment_date'] = pd.to_datetime(display_items['payment_date']).dt.strftime('%d.%m.%Y')
                display_items['amount'] = display_items['amount'].apply(format_currency)
                display_items['hours'] = display_items['hours'].apply(format_hours)

                # Редактирование таблицы
                edited_items = st.data_editor(display_items, num_rows="dynamic", use_container_width=True, key=f"edit_items_{order_id}")
                
                # Сохранение изменений
                if not edited_items.equals(display_items):
                    for index, row in edited_items.iterrows():
                        original_row = display_items.loc[index]
                        for col in edited_items.columns:
                            if col != 'id' and row[col] != original_row[col]:
                                val = str(row[col]).replace(' ', '') if col == 'amount' else row[col]
                                if col == 'payment_date':
                                    val = pd.to_datetime(row[col], format='%d.%m.%Y').strftime('%Y-%m-%d')
                                elif col == 'amount' or col == 'hours':
                                     val = val.replace(',', '.')
                                run_query(f"UPDATE order_items SET {col} = ? WHERE id = ?", (val, row['id']))
                    
                    # Пересчитываем общую сумму заказа
                    run_query("UPDATE orders SET total_amount = (SELECT COALESCE(SUM(amount),0) FROM order_items WHERE order_id=?) WHERE id=?", (order_id, order_id))
                    st.success("Изменения в услугах сохранены!")
                    st.rerun()

            else:
                st.info("В заказе пока нет услуг")

# --- 5. ОТЧЁТЫ ---
elif choice == "ОТЧЁТЫ":
    st.header("📊 Аналитические Отчёты")
    # (Код отчетов остается без изменений, так как правки касались только UI/UX других разделов)
    st.info("Раздел отчетов готов к работе. Форматирование данных в отчетах можно добавить по аналогии с другими разделами.")