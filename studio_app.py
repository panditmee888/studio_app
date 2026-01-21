import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import plotly.express as px

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ПАГИНАЦИИ ---
def paginate_dataframe(df, items_per_page=10, page_key="page"):
    """Функция для постраничного отображения DataFrame"""
    if df.empty:
        return df, 1, 1
    
    total_items = len(df)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    if total_pages > 1:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            st.write(f"Всего записей: {total_items}")
        with col2:
            page = st.selectbox(
                "Страница",
                range(1, total_pages + 1),
                key=page_key
            )
        with col3:
            st.write(f"из {total_pages}")
    else:
        page = 1
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_df = df.iloc[start_idx:end_idx]
    
    return page_df, page, total_pages

# --- НАСТРОЙКА БД ---
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
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Группы клиентов")
        with st.form("add_group"):
            new_group = st.text_input("Название группы")
            if st.form_submit_button("Добавить группу"):
                if new_group:
                    run_query("INSERT INTO groups (name) VALUES (?)", (new_group,))
                    st.success("Группа добавлена")
                    st.rerun()
        
        groups_df = run_query("SELECT * FROM groups", fetch=True)
        st.dataframe(groups_df, hide_index=True)

    with col2:
        st.subheader("Клиенты")
        groups_list = groups_df['name'].tolist() if not groups_df.empty else []
        group_map = dict(zip(groups_df['name'], groups_df['id'])) if not groups_df.empty else {}

        with st.expander("➕ Добавить нового клиента"):
            with st.form("add_client"):
                c_name = st.text_input("Имя")
                c_sex = st.selectbox("Пол", ["М", "Ж"])
                c_phone = st.text_input("Телефон")
                c_vk = st.text_input("VK ID")
                c_tg = st.text_input("Telegram ID")
                c_group = st.selectbox("Группа", options=groups_list if groups_list else ["Нет групп"])
                
                if st.form_submit_button("Сохранить клиента"):
                    if c_name:
                        g_id = group_map.get(c_group) if c_group != "Нет групп" else None
                        run_query('''INSERT INTO clients (name, sex, phone, vk_id, tg_id, group_id) 
                                     VALUES (?,?,?,?,?,?)''', (c_name, c_sex, c_phone, c_vk, c_tg, g_id))
                        st.success("Клиент добавлен")
                        st.rerun()
                    else:
                        st.error("Введите имя клиента")

        # Поиск клиентов
        st.markdown("### 🔍 Поиск и фильтрация")
        search_col1, search_col2 = st.columns([2, 1])
        with search_col1:
            search_query = st.text_input("Поиск по имени, телефону, VK или Telegram", placeholder="Введите текст для поиска...")
        with search_col2:
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
            st.info(f"Найдено клиентов: {len(clients_df)}")
            page_df, current_page, total_pages = paginate_dataframe(clients_df, items_per_page=15, page_key="clients_page")
            st.dataframe(page_df, use_container_width=True)
            
            if total_pages > 1:
                st.caption(f"Показана страница {current_page} из {total_pages}")
        else:
            if search_query or filter_group != "Все":
                st.warning("По вашему запросу ничего не найдено")
            else:
                st.info("Клиенты еще не добавлены")

# --- 2. ПРАЙС-ЛИСТ ---
elif choice == "Прайс-лист Услуг":
    st.subheader("Справочник Услуг")
    
    with st.expander("➕ Добавить новую услугу"):
        with st.form("add_service"):
            s_name = st.text_input("Наименование услуги")
            s_price = st.number_input("Мин. прайс", min_value=0.0)
            s_desc = st.text_area("Описание")
            if st.form_submit_button("Добавить услугу"):
                if s_name:
                    run_query("INSERT INTO services_catalog (name, min_price, description) VALUES (?,?,?)", 
                              (s_name, s_price, s_desc))
                    st.success("Услуга добавлена")
                    st.rerun()
            
    st.subheader("Список услуг")
    st.dataframe(run_query("SELECT * FROM services_catalog", fetch=True), use_container_width=True)

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
        # Статистика
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Всего заказов", len(df_orders))
        with col2:
            st.metric("Общая сумма", f"{df_orders['total_amount'].sum():,.0f} ₽")
        with col3:
            st.metric("Средний чек", f"{df_orders['total_amount'].mean():,.0f} ₽")
        with col4:
            in_work = len(df_orders[df_orders['status'] == 'В работе'])
            st.metric("В работе", in_work)
        
        page_df, current_page, total_pages = paginate_dataframe(df_orders, items_per_page=15, page_key="orders_page")
        page_df['total_amount'] = page_df['total_amount'].apply(lambda x: f"{x:,.0f} ₽")
        st.dataframe(page_df, use_container_width=True)
        
        if total_pages > 1:
            st.caption(f"Показана страница {current_page} из {total_pages}")
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
                service_choice = st.selectbox("Услуга (из каталога) или введите свою", srv_list + ["Другое"])
                
                if service_choice == "Другое":
                    custom_service = st.text_input("Название услуги вручную", key="custom_service_input")
                    final_service_name = custom_service
                else:
                    final_service_name = service_choice
                
                i_date = st.date_input("Дата оплаты", value=date.today())
                i_amount = st.number_input("Сумма", min_value=0.0, step=100.0)
                i_hours = st.number_input("Кол-во часов", min_value=0.0, step=0.5)
                
                submitted = st.form_submit_button("Добавить услугу")
                if submitted:
                    if final_service_name and i_amount > 0:
                        try:
                            run_query(
                                "INSERT INTO order_items (order_id, service_name, payment_date, amount, hours) VALUES (?,?,?,?,?)",
                                (order_id, final_service_name, str(i_date), float(i_amount), float(i_hours))
                            )
                            run_query(
                                "UPDATE orders SET total_amount = (SELECT COALESCE(SUM(amount), 0) FROM order_items WHERE order_id=?) WHERE id=?",
                                (order_id, order_id)
                            )
                            st.success(f"✅ Услуга '{final_service_name}' добавлена в заказ!")
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
                st.dataframe(items_df, hide_index=True)
                st.info(f"💰 Общая сумма: {items_df['amount'].sum():,.2f} руб.")
                
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
        st.dataframe(df_1, use_container_width=True)

        # Отчет 2: Заказы за год по клиентам
        st.subheader("2. Заказы за год по клиентам")
        sel_year_2 = st.selectbox("Выберите год (Клиенты)", years, index=len(years)-1, key='y2')
        
        df_2 = df[df['year'] == sel_year_2].groupby('client_name').agg(
            Количество=('id', 'count'),
            Сумма=('total_amount', 'sum')
        ).reset_index().sort_values(by='Сумма', ascending=False)
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
        st.dataframe(df_5_res, use_container_width=True)

        # Отчет 6: Динамика по месяцам
        st.subheader("6. Динамика по месяцам")
        sel_year_6 = st.selectbox("Выберите год", years, index=len(years)-1, key='y6')
        df_6 = df[df['year'] == sel_year_6].groupby('month').agg(
            Количество=('id', 'count'),
            Средний_чек=('total_amount', 'mean'),
            Сумма=('total_amount', 'sum')
        ).reset_index()
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
            st.dataframe(df_7, use_container_width=True)
        else:
            st.write("Нет данных об оплатах.")
    else:
        st.warning("В базе данных пока нет заказов для формирования отчётов.")