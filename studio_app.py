import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import plotly.express as px

# --- НАСТРОЙКА БД ---
def init_db():
    conn = sqlite3.connect('studio.db')
    c = conn.cursor()
    # Включаем поддержку внешних ключей
    c.execute("PRAGMA foreign_keys = ON;")
    
    # 5. Вспомогательная таблица Группы
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE)''')
    
    # 1. Таблица клиентов
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
    
    # 4. Таблица Услуг (Прайс-лист)
    c.execute('''CREATE TABLE IF NOT EXISTS services_catalog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    min_price REAL,
                    description TEXT)''')
    
    # 2. Таблица заказов
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER,
                    execution_date DATE,
                    status TEXT,
                    total_amount REAL DEFAULT 0,
                    FOREIGN KEY (client_id) REFERENCES clients(id))''')
    
    # 3. Внутренняя таблица услуг заказа
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
    except Exception as e:
        st.error(f"Ошибка БД: {e}")
    conn.close()

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Studio Admin", layout="wide")
init_db()

st.title("🎛️ CRM Студии Звукозаписи")

# Меню
menu = ["Клиенты и Группы", "Прайс-лист Услуг", "Заказы", "Детализация Заказа", "ОТЧЁТЫ"]
choice = st.sidebar.selectbox("Навигация", menu)

# --- 1. КЛИЕНТЫ И ГРУППЫ ---
if choice == "Клиенты и Группы":
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Группы клиентов")
        with st.form("add_group"):
            new_group = st.text_input("Название группы")
            if st.form_submit_button("Добавить группу"):
                run_query("INSERT INTO groups (name) VALUES (?)", (new_group,))
                st.success("Группа добавлена")
        
        groups_df = run_query("SELECT * FROM groups", fetch=True)
        st.dataframe(groups_df, hide_index=True)

    with col2:
        st.subheader("Клиенты")
        groups_list = groups_df['name'].tolist() if not groups_df.empty else []
        group_map = dict(zip(groups_df['name'], groups_df['id'])) if not groups_df.empty else {}

        with st.expander("Добавить нового клиента"):
            with st.form("add_client"):
                c_name = st.text_input("Имя")
                c_sex = st.selectbox("Пол", ["М", "Ж"])
                c_phone = st.text_input("Телефон")
                c_vk = st.text_input("VK ID")
                c_tg = st.text_input("Telegram ID")
                c_group = st.selectbox("Группа", options=groups_list)
                
                if st.form_submit_button("Сохранить клиента"):
                    g_id = group_map.get(c_group)
                    run_query('''INSERT INTO clients (name, sex, phone, vk_id, tg_id, group_id) 
                                 VALUES (?,?,?,?,?,?)''', (c_name, c_sex, c_phone, c_vk, c_tg, g_id))
                    st.success("Клиент добавлен")

        # Отображение клиентов
        clients_query = '''
        SELECT c.id, c.name, c.sex, c.phone, c.vk_id, c.tg_id, g.name as group_name, c.first_order_date
        FROM clients c LEFT JOIN groups g ON c.group_id = g.id
        '''
        st.dataframe(run_query(clients_query, fetch=True), use_container_width=True)

# --- 2. ПРАЙС-ЛИСТ ---
elif choice == "Прайс-лист Услуг":
    st.subheader("Справочник Услуг")
    with st.form("add_service"):
        s_name = st.text_input("Наименование услуги")
        s_price = st.number_input("Мин. прайс", min_value=0.0)
        s_desc = st.text_area("Описание")
        if st.form_submit_button("Добавить услугу"):
            run_query("INSERT INTO services_catalog (name, min_price, description) VALUES (?,?,?)", 
                      (s_name, s_price, s_desc))
            st.success("Услуга добавлена")
            
    st.dataframe(run_query("SELECT * FROM services_catalog", fetch=True), use_container_width=True)

# --- 3. ЗАКАЗЫ ---
elif choice == "Заказы":
    st.subheader("Управление Заказами")
    
    clients_df = run_query("SELECT id, name FROM clients", fetch=True)
    client_map = dict(zip(clients_df['name'], clients_df['id'])) if not clients_df.empty else {}

    with st.expander("Создать новый заказ"):
        with st.form("new_order"):
            o_client = st.selectbox("Клиент", list(client_map.keys()))
            o_date = st.date_input("Дата исполнения")
            o_status = st.selectbox("Статус", ["В работе", "Выполнен", "Отменен", "Оплачен"])
            
            if st.form_submit_button("Создать заказ"):
                c_id = client_map.get(o_client)
                run_query("INSERT INTO orders (client_id, execution_date, status) VALUES (?,?,?)", 
                          (c_id, o_date, o_status))
                
                # Обновляем дату первого заказа, если она пустая
                run_query('''UPDATE clients SET first_order_date = ? 
                             WHERE id = ? AND first_order_date IS NULL''', (o_date, c_id))
                st.success("Заказ создан! Перейдите в 'Детализация Заказа' для добавления услуг.")

    # Таблица заказов
    orders_sql = '''
    SELECT o.id, c.name as Client, o.execution_date, o.status, o.total_amount 
    FROM orders o JOIN clients c ON o.client_id = c.id
    ORDER BY o.execution_date DESC
    '''
    df_orders = run_query(orders_sql, fetch=True)
    st.dataframe(df_orders, use_container_width=True)

# --- 4. ДЕТАЛИЗАЦИЯ ЗАКАЗА (SERVICES) ---
elif choice == "Детализация Заказа":
    st.subheader("Внутренние услуги заказа")
    
    # Выбор заказа
    orders_df = run_query("SELECT o.id, c.name, o.execution_date FROM orders o JOIN clients c ON o.client_id = c.id", fetch=True)
    if not orders_df.empty:
        orders_df['label'] = orders_df.apply(lambda x: f"Заказ #{x['id']} - {x['name']} ({x['execution_date']})", axis=1)
        order_selection = st.selectbox("Выберите заказ для редактирования", orders_df['label'])
        order_id = orders_df[orders_df['label'] == order_selection]['id'].values[0]

        # Форма добавления услуги в заказ
        services_cat = run_query("SELECT name FROM services_catalog", fetch=True)
        srv_list = services_cat['name'].tolist() if not services_cat.empty else []
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Добавить услугу")
            with st.form("add_item"):
                i_name = st.selectbox("Услуга (из каталога) или введите свою", srv_list + ["Другое"])
                if i_name == "Другое":
                    i_name = st.text_input("Название услуги вручную")
                
                i_date = st.date_input("Дата оплаты")
                i_amount = st.number_input("Сумма", min_value=0.0)
                i_hours = st.number_input("Кол-во часов", min_value=0.0, step=0.5)
                
                if st.form_submit_button("Добавить"):
                    run_query("INSERT INTO order_items (order_id, service_name, payment_date, amount, hours) VALUES (?,?,?,?,?)",
                              (order_id, i_name, i_date, i_amount, i_hours))
                    # Обновляем общую сумму заказа
                    run_query("UPDATE orders SET total_amount = (SELECT SUM(amount) FROM order_items WHERE order_id=?) WHERE id=?", (order_id, order_id))
                    st.rerun()
        
        with col2:
            st.markdown(f"#### Состав заказа #{order_id}")
            items_df = run_query(f"SELECT id, service_name, payment_date, amount, hours FROM order_items WHERE order_id={order_id}", fetch=True)
            st.dataframe(items_df, hide_index=True)
            
            # Удаление
            del_id = st.number_input("ID услуги для удаления", min_value=0, step=1)
            if st.button("Удалить услугу"):
                run_query(f"DELETE FROM order_items WHERE id={del_id}")
                run_query("UPDATE orders SET total_amount = (SELECT SUM(amount) FROM order_items WHERE order_id=?) WHERE id=?", (order_id, order_id))
                st.rerun()

    else:
        st.info("Сначала создайте заказ.")

# --- 5. ОТЧЁТЫ ---
elif choice == "ОТЧЁТЫ":
    st.header("Аналитические Отчёты")
    
    # Подготовка данных
    # Основной датафрейм (Заказы + Клиенты + Группы)
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
        current_year = datetime.now().year
        
        # --- ОТЧЕТ 1: Заказы за год по группам ---
        st.subheader("1. Заказы за год по группам")
        sel_year_1 = st.selectbox("Выберите год (Группы)", years, index=len(years)-1)
        
        df_1 = df[df['year'] == sel_year_1].groupby('group_name').agg(
            Количество=('id', 'count'),
            Сумма=('total_amount', 'sum'),
            Среднее=('total_amount', 'mean')
        ).reset_index()
        st.dataframe(df_1, use_container_width=True)

        # --- ОТЧЕТ 2: Заказы за год по клиентам ---
        st.subheader("2. Заказы за год по клиентам")
        sel_year_2 = st.selectbox("Выберите год (Клиенты)", years, index=len(years)-1, key='y2')
        
        df_2 = df[df['year'] == sel_year_2].groupby('client_name').agg(
            Количество=('id', 'count'),
            Сумма=('total_amount', 'sum')
        ).reset_index().sort_values(by='Сумма', ascending=False)
        st.dataframe(df_2, use_container_width=True)

        # --- ОТЧЕТ 3: Новые клиенты за год ---
        st.subheader("3. Новые клиенты за год")
        # Логика: фильтруем клиентов, у которых first_order_date попадает в выбранный год
        sel_year_3 = st.selectbox("Выберите год (Новые клиенты)", years, index=len(years)-1, key='y3')
        
        # Получаем полные данные о клиентах для этого отчета
        df_new_clients = run_query('''
            SELECT c.name, c.first_order_date, COUNT(o.id) as count, SUM(o.total_amount) as sum
            FROM clients c 
            JOIN orders o ON c.id = o.client_id
            WHERE strftime('%Y', c.first_order_date) = ?
            GROUP BY c.id
        ''', (str(sel_year_3),), fetch=True)
        st.dataframe(df_new_clients, use_container_width=True)

        # --- ОТЧЕТ 4: Заказы по годам (Сводка) ---
        st.subheader("4. Сводка по годам")
        df_4 = df.groupby('year').agg(
            Количество=('id', 'count'),
            Макс_сумма=('total_amount', 'max'),
            Мин_сумма=('total_amount', 'min'),
            Средний_чек=('total_amount', 'mean'),
            Сумма_год=('total_amount', 'sum')
        ).reset_index()
        df_4['Средний_месячный'] = df_4['Сумма_год'] / 12
        st.dataframe(df_4, use_container_width=True)
        st.bar_chart(df_4, x='year', y='Сумма_год')

        # --- ОТЧЕТ 5: Заказы за месяц ---
        st.subheader("5. Заказы за месяц (детализация)")
        c1, c2 = st.columns(2)
        with c1: sel_year_5 = st.selectbox("Год", years, index=len(years)-1, key='y5')
        with c2: sel_month_5 = st.selectbox("Месяц", range(1,13), key='m5')
        
        df_5 = df[(df['year'] == sel_year_5) & (df['month'] == sel_month_5)]
        df_5_res = df_5.groupby('client_name').agg(
            Количество=('id', 'count'),
            Сумма=('total_amount', 'sum')
        ).reset_index()
        st.dataframe(df_5_res, use_container_width=True)

        # --- ОТЧЕТ 6: Заказы за год по месяцам ---
        st.subheader("6. Динамика по месяцам")
        sel_year_6 = st.selectbox("Выберите год", years, index=len(years)-1, key='y6')
        df_6 = df[df['year'] == sel_year_6].groupby('month').agg(
            Количество=('id', 'count'),
            Средний_чек=('total_amount', 'mean'),
            Сумма=('total_amount', 'sum')
        ).reset_index()
        st.dataframe(df_6, use_container_width=True)
        st.line_chart(df_6, x='month', y='Сумма')

        # --- ОТЧЕТ 7: Оплата за неделю ---
        st.subheader("7. Оплаты за последнюю неделю (по Order Items)")
        # Здесь нужно брать дату из order_items
        df_items = run_query('''
            SELECT c.name, oi.payment_date, oi.amount 
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN clients c ON o.client_id = c.id
        ''', fetch=True)
        
        if not df_items.empty:
            df_items['payment_date'] = pd.to_datetime(df_items['payment_date'])
            # Фильтр: текущая дата - 7 дней
            week_ago = pd.Timestamp.now() - pd.Timedelta(days=7)
            df_7 = df_items[df_items['payment_date'] >= week_ago]
            st.dataframe(df_7, use_container_width=True)
        else:
            st.write("Нет данных об оплатах.")
            
    else:
        st.warning("В базе данных пока нет заказов для формирования отчётов.")