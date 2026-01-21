import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import re

st.set_page_config(page_title="Studio Admin", layout="wide")

# --- Стили ---
st.markdown("""
<style>
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
}
.stDataEditor a { color: #0066ff; text-decoration: none; }
.stDataEditor a:hover { text-decoration: underline; }
</style>
""", unsafe_allow_html=True)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def format_phone_display(phone_raw: str) -> str:
    """Форматирование телефона для отображения с ссылкой на звонок"""
    if not phone_raw:
        return ""
    digits = re.sub(r'\D', '', phone_raw)
    if len(digits) == 10:
        formatted = f"+7 {digits[:3]} {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"
        return f'<a href="tel:+7{digits}">{formatted}</a>'
    return phone_raw

def parse_phone_input(phone_input: str) -> str:
    """Очистка телефона для сохранения в БД (только 10 цифр)"""
    return re.sub(r'\D', '', phone_input)[-10:] if phone_input else ""

def format_vk_display(vk_id: str) -> str:
    """Форматирование VK для отображения как ссылка"""
    if not vk_id:
        return ""
    return f'<a href="https://vk.com/id{vk_id}" target="_blank">vk.com/id{vk_id}</a>'

def format_tg_display(tg_id: str) -> str:
    """Форматирование Telegram для отображения как ссылка"""
    if not tg_id:
        return ""
    return f'<a href="https://t.me/{tg_id}" target="_blank">@{tg_id}</a>'

def format_currency(x):
    """Форматирование валюты с пробелами"""
    if pd.isna(x) or x is None:
        return "0"
    return f"{int(float(x)):,.0f}".replace(",", " ")

def format_date(d):
    """Форматирование даты в dd.mm.yyyy"""
    if pd.isna(d) or d is None:
        return ""
    try:
        return pd.to_datetime(d).strftime("%d.%m.%Y")
    except:
        return str(d)

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('studio.db')
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON;")
    
    # Таблицы без изменений
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
        st.error(f"Ошибка БД: {e}")
        return None if fetch else False
    finally:
        conn.close()

init_db()

# --- ИНТЕРФЕЙС ---
st.title("🎛️ CRM Студии Звукозаписи")
menu = ["Клиенты и Группы", "Прайс-лист Услуг", "Заказы", "Детализация Заказа", "ОТЧЁТЫ"]
choice = st.sidebar.selectbox("Навигация", menu)

# ==============================================
# 🧑🤝🧑 КЛИЕНТЫ И ГРУППЫ
# ==============================================
if choice == "Клиенты и Группы":
    st.subheader("Клиенты")

    # --- Форма добавления клиента с автоматической маской телефона ---
    if 'phone_input' not in st.session_state:
        st.session_state.phone_input = ""

    def on_phone_change():
        """Автоматическое форматирование телефона при вводе"""
        raw = st.session_state.phone_raw
        digits = re.sub(r'\D', '', raw)
        if len(digits) >= 10:
            st.session_state.phone_input = f"+7 {digits[:3]} {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"
        else:
            st.session_state.phone_input = raw

    with st.expander("➕ Добавить нового клиента"):
        with st.form("add_client"):
            c_name = st.text_input("Имя *", placeholder="Иван Иванов")
            c_sex = st.selectbox("Пол", ["М", "Ж"])
            
            st.text_input("Телефон", key="phone_raw", on_change=on_phone_change,
                          placeholder="+7 999 123-45-67")
            st.caption(f"Форматированный номер: {st.session_state.phone_input}")
            
            c_vk = st.text_input("VK ID (только цифры)", placeholder="123456789")
            c_tg = st.text_input("Telegram username", placeholder="my_username")
            
            # Список групп
            groups_df = run_query("SELECT id, name FROM groups", fetch=True)
            group_options = [""] + groups_df['name'].tolist() if not groups_df.empty else [""]
            c_group = st.selectbox("Группа", group_options)

            if st.form_submit_button("Сохранить клиента"):
                if c_name:
                    # Очищаем телефон для сохранения
                    phone_clean = parse_phone_input(st.session_state.phone_input)
                    # Получаем ID группы
                    group_id = groups_df[groups_df['name'] == c_group]['id'].iloc[0] if c_group else None
                    
                    run_query('''INSERT INTO clients (name, sex, phone, vk_id, tg_id, group_id)
                                 VALUES (?,?,?,?,?,?)''', (c_name, c_sex, phone_clean, c_vk, c_tg, group_id))
                    st.success("✅ Клиент добавлен")
                    st.rerun()
                else:
                    st.error("❌ Введите имя клиента")

    # --- Управление группами ---
    with st.expander("⚙️ Группы клиентов", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            with st.form("add_group"):
                new_group = st.text_input("Название группы")
                if st.form_submit_button("Добавить группу"):
                    if new_group:
                        run_query("INSERT INTO groups (name) VALUES (?)", (new_group,))
                        st.success("Группа добавлена")
                        st.rerun()
        with col2:
            groups_df = run_query("SELECT * FROM groups", fetch=True)
            if not groups_df.empty:
                selected_group = st.selectbox("Выбрать группу для редактирования", groups_df['id'], format_func=lambda x: groups_df[groups_df['id']==x]['name'].iloc[0])
                new_name = st.text_input("Новое название", value=groups_df[groups_df['id']==selected_group]['name'].iloc[0])
                col_edit, col_del = st.columns(2)
                with col_edit:
                    if st.button("✏️ Переименовать", use_container_width=True):
                        run_query("UPDATE groups SET name=? WHERE id=?", (new_name, selected_group))
                        st.success("Группа переименована")
                        st.rerun()
                with col_del:
                    if st.button("🗑️ Удалить", use_container_width=True, type="primary"):
                        run_query("DELETE FROM groups WHERE id=?", (selected_group,))
                        st.success("Группа удалена")
                        st.rerun()

    # --- Таблица клиентов с data_editor ---
    st.markdown("### 📋 Список клиентов")
    search_query = st.text_input("🔍 Поиск по имени, телефону или соцсетям")

    # Получаем сырые данные из БД
    clients_raw = run_query('''
        SELECT c.id, c.name, c.sex, c.phone, c.vk_id, c.tg_id, g.name as group_name, c.first_order_date
        FROM clients c LEFT JOIN groups g ON c.group_id = g.id
        WHERE ? = '' OR LOWER(c.name) LIKE LOWER(?) OR c.phone LIKE ? OR c.vk_id LIKE ? OR c.tg_id LIKE ?
    ''', (search_query, f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'), fetch=True)

    if not clients_raw.empty:
        # Создаём DF для отображения с форматированием
        clients_display = clients_raw.copy()
        clients_display['id'] = clients_display['id'].astype(str)
        clients_display['phone'] = clients_display['phone'].apply(format_phone_display)
        clients_display['vk_id'] = clients_display['vk_id'].apply(format_vk_display)
        clients_display['tg_id'] = clients_display['tg_id'].apply(format_tg_display)
        clients_display['first_order_date'] = clients_display['first_order_date'].apply(format_date)

        # Конфигурация столбцов для data_editor
        column_config = {
            "id": st.column_config.TextColumn("ID", disabled=True),
            "name": st.column_config.TextColumn("Имя", required=True),
            "sex": st.column_config.SelectboxColumn("Пол", options=["М", "Ж"], required=True),
            "phone": st.column_config.TextColumn("Телефон", disabled=False),
            "vk_id": st.column_config.TextColumn("VK", disabled=False),
            "tg_id": st.column_config.TextColumn("Telegram", disabled=False),
            "group_name": st.column_config.SelectboxColumn("Группа", options=[""] + groups_df['name'].tolist() if not groups_df.empty else [""]),
            "first_order_date": st.column_config.TextColumn("Первая оплата", disabled=True)
        }

        # Запускаем data_editor
        edited_clients = st.data_editor(
            clients_display,
            column_config=column_config,
            hide_index=True,
            use_container_width=True,
            key="clients_editor"
        )

        # Сохранение изменений
        if st.button("💾 Сохранить изменения", type="primary"):
            changes_count = 0
            for idx, row in edited_clients.iterrows():
                original = clients_raw.iloc[idx]
                # Проверяем наличие изменений
                if (row['name'] != original['name'] or
                    row['sex'] != original['sex'] or
                    parse_phone_input(row['phone']) != original['phone'] or
                    row['vk_id'] != original['vk_id'] or
                    row['tg_id'] != original['tg_id'] or
                    row['group_name'] != original['group_name']):
                    
                    # Подготавливаем данные для сохранения
                    group_id = groups_df[groups_df['name'] == row['group_name']]['id'].iloc[0] if row['group_name'] else None
                    clean_phone = parse_phone_input(row['phone'])
                    
                    run_query('''UPDATE clients SET name=?, sex=?, phone=?, vk_id=?, tg_id=?, group_id=?
                                 WHERE id=?''', (row['name'], row['sex'], clean_phone, row['vk_id'], row['tg_id'], group_id, int(row['id'])))
                    changes_count +=1
            
            if changes_count >0:
                st.success(f"✅ Обновлено {changes_count} записей")
                st.rerun()
            else:
                st.info("ℹ️ Нет изменений для сохранения")
    else:
        st.info("ℹ️ Клиенты не найдены")

# ==============================================
# 💰 ПРАЙС-ЛИСТ УСЛУГ
# ==============================================
elif choice == "Прайс-лист Услуг":
    st.subheader("Справочник Услуг")
    with st.expander("➕ Добавить новую услугу"):
        with st.form("add_service"):
            s_name = st.text_input("Название услуги")
            s_price = st.number_input("Мин. прайс", min_value=0.0, step=100.0)
            s_desc = st.text_area("Описание")
            if st.form_submit_button("Добавить услугу"):
                if s_name:
                    run_query("INSERT INTO services_catalog (name, min_price, description) VALUES (?,?,?)", (s_name, s_price, s_desc))
                    st.success("✅ Услуга добавлена")
                    st.rerun()

    services_df = run_query("SELECT * FROM services_catalog", fetch=True)
    if not services_df.empty:
        services_df['min_price'] = services_df['min_price'].apply(lambda x: f"{format_currency(x)} ₽")
        st.data_editor(
            services_df,
            column_config={
                "id": st.column_config.TextColumn("ID", disabled=True),
                "name": st.column_config.TextColumn("Название", required=True),
                "min_price": st.column_config.TextColumn("Мин. прайс", disabled=False),
                "description": st.column_config.TextColumn("Описание")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("ℹ️ Услуги еще не добавлены")

# ==============================================
# 📦 ЗАКАЗЫ
# ==============================================
elif choice == "Заказы":
    st.subheader("Управление Заказами")
    status_list = ["В работе", "Выполнен", "Оплачено", "Ожидает оплаты"]

    # Форма создания заказа
    clients_df = run_query("SELECT id, name FROM clients", fetch=True)
    client_map = dict(zip(clients_df['name'], clients_df['id'])) if not clients_df.empty else {}

    with st.expander("➕ Создать новый заказ"):
        with st.form("new_order"):
            if client_map:
                o_client = st.selectbox("Клиент", list(client_map.keys()))
                o_date = st.date_input("Дата исполнения", value=date.today())
                o_status = st.selectbox("Статус", status_list)
                
                if st.form_submit_button("Создать заказ"):
                    c_id = client_map.get(o_client)
                    run_query("INSERT INTO orders (client_id, execution_date, status) VALUES (?,?,?)", (c_id, o_date, o_status))
                    st.success("✅ Заказ создан")
                    st.rerun()
            else:
                st.warning("⚠️ Сначала добавьте клиентов")

    # Таблица заказов с data_editor
    orders_raw = run_query('''
        SELECT o.id, c.name as client_name, o.execution_date, o.status, o.total_amount
        FROM orders o JOIN clients c ON o.client_id = c.id
    ''', fetch=True)

    if not orders_raw.empty:
        orders_display = orders_raw.copy()
        orders_display['id'] = orders_display['id'].astype(str)
        orders_display['execution_date'] = pd.to_datetime(orders_display['execution_date']).dt.date
        orders_display['total_amount'] = orders_display['total_amount'].apply(lambda x: f"{format_currency(x)} ₽")

        edited_orders = st.data_editor(
            orders_display,
            column_config={
                "id": st.column_config.TextColumn("ID", disabled=True),
                "client_name": st.column_config.SelectboxColumn("Клиент", options=list(client_map.keys()), required=True),
                "execution_date": st.column_config.DateColumn("Дата исполнения", format="DD.MM.YYYY", required=True),
                "status": st.column_config.SelectboxColumn("Статус", options=status_list, required=True),
                "total_amount": st.column_config.TextColumn("Сумма", disabled=True)
            },
            hide_index=True,
            use_container_width=True
        )

        if st.button("💾 Сохранить изменения в заказах"):
            changes = 0
            for idx, row in edited_orders.iterrows():
                original = orders_raw.iloc[idx]
                if row['client_name'] != original['client_name'] or str(row['execution_date']) != original['execution_date'] or row['status'] != original['status']:
                    client_id = client_map[row['client_name']]
                    run_query('''UPDATE orders SET client_id=?, execution_date=?, status=? WHERE id=?''', (client_id, str(row['execution_date']), row['status'], int(row['id'])))
                    changes +=1
            if changes>0:
                st.success(f"✅ Обновлено {changes} заказов")
                st.rerun()

# ==============================================
# 📝 ДЕТАЛИЗАЦИЯ ЗАКАЗА
# ==============================================
elif choice == "Детализация Заказа":
    st.subheader("Состав заказа")
    orders_df = run_query("SELECT o.id, c.name FROM orders o JOIN clients c ON o.client_id = c.id", fetch=True)
    if not orders_df.empty:
        order_id = st.selectbox("Выберите заказ", orders_df['id'], format_func=lambda x: f"Заказ #{x} | {orders_df[orders_df['id']==x]['name'].iloc[0]}")
        
        # Таблица услуг с data_editor
        items_raw = run_query("SELECT * FROM order_items WHERE order_id=?", (order_id,), fetch=True)
        if not items_raw.empty:
            items_display = items_raw.copy()
            items_display['id'] = items_display['id'].astype(str)
            items_display['payment_date'] = pd.to_datetime(items_display['payment_date']).dt.date
            items_display['amount'] = items_display['amount'].apply(format_currency)

            edited_items = st.data_editor(
                items_display,
                column_config={
                    "id": st.column_config.TextColumn("ID", disabled=True),
                    "service_name": st.column_config.TextColumn("Услуга", required=True),
                    "payment_date": st.column_config.DateColumn("Дата оплаты", format="DD.MM.YYYY", required=True),
                    "amount": st.column_config.NumberColumn("Сумма", min_value=0, required=True),
                    "hours": st.column_config.NumberColumn("Часы", min_value=0.0, step=0.1, required=True)
                },
                hide_index=True,
                use_container_width=True,
                num_rows="dynamic"
            )

            if st.button("💾 Сохранить состав заказа"):
                updates = 0
                for idx, row in edited_items.iterrows():
                    if row['id'] in items_raw['id'].astype(str).values:
                        orig = items_raw[items_raw['id'] == int(row['id'])].iloc[0]
                        if row['service_name'] != orig['service_name'] or str(row['payment_date']) != orig['payment_date'] or float(row['amount']) != orig['amount'] or float(row['hours']) != orig['hours']:
                            run_query('''UPDATE order_items SET service_name=?, payment_date=?, amount=?, hours=? WHERE id=?''', (row['service_name'], str(row['payment_date']), row['amount'], row['hours'], int(row['id'])))
                            updates +=1
                    else:
                        run_query('''INSERT INTO order_items (order_id, service_name, payment_date, amount, hours) VALUES (?,?,?,?,?)''', (order_id, row['service_name'], str(row['payment_date']), row['amount'], row['hours']))
                        updates +=1
                
                # Обновляем общую сумму заказа
                run_query('''UPDATE orders SET total_amount = (SELECT COALESCE(SUM(amount),0) FROM order_items WHERE order_id=?) WHERE id=?''', (order_id, order_id))
                st.success(f"✅ Обновлено {updates} услуг")
                st.rerun()
        else:
            st.info("ℹ️ В заказе еще нет услуг")

# ==============================================
# 📊 ОТЧЁТЫ
# ==============================================
elif choice == "ОТЧЁТЫ":
    st.header("Аналитические отчёты (по дате оплаты)")
    df = run_query('''
        SELECT oi.payment_date, oi.amount, o.id as order_id, c.name as client_name, g.name as group_name
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN clients c ON o.client_id = c.id
        LEFT JOIN groups g ON c.group_id = g.id
    ''', fetch=True)

    if not df.empty:
        df['payment_date'] = pd.to_datetime(df['payment_date'])
        years = sorted(df['payment_date'].dt.year.unique())
        sel_year = st.selectbox("Выберите год", years, index=len(years)-1)

        # Отчёт новых клиентов по первой оплате
        st.subheader("📈 Новые клиенты по первой оплате")
        new_clients = run_query('''
            SELECT c.name, MIN(oi.payment_date) as first_payment, COUNT(o.id) as orders_count, SUM(oi.amount) as total_sum
            FROM clients c
            JOIN orders o ON c.id = o.client_id
            JOIN order_items oi ON o.id = oi.order_id
            WHERE strftime('%Y', oi.payment_date) = ?
            GROUP BY c.id
            HAVING MIN(oi.payment_date) = (SELECT MIN(oi2.payment_date) FROM order_items oi2 JOIN orders o2 ON oi2.order_id = o2.id WHERE o2.client_id = c.id)
        ''', (str(sel_year),), fetch=True)
        
        if not new_clients.empty:
            new_clients['first_payment'] = new_clients['first_payment'].apply(format_date)
            new_clients['total_sum'] = new_clients['total_sum'].apply(lambda x: f"{format_currency(x)} ₽")
            st.dataframe(new_clients, use_container_width=True)
    else:
        st.warning("⚠️ Нет данных об оплатах")