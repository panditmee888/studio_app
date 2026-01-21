import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import re

st.set_page_config(page_title="Studio Admin", layout="wide")

# --- Финальные стили ---
st.markdown("""
<style>
/* Скрываем стрелки у полей ввода чисел */
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
}
/* Стили для таблицы */
.stMarkdown table {
    width: 100%;
    border-collapse: collapse;
    margin: 15px 0;
}
.stMarkdown th, .stMarkdown td {
    border: 1px solid #e0e0e0;
    padding: 10px;
    text-align: left;
}
.stMarkdown th {
    background-color: #f8f9fa;
    font-weight: 600;
}
/* Ссылки в таблице */
.stMarkdown a {
    color: #0066ff;
    text-decoration: none;
}
.stMarkdown a:hover {
    text-decoration: underline;
}
/* Кнопка карандаша */
.edit-btn {
    cursor: pointer;
    color: #ff9800;
    font-size: 18px;
}
</style>
""", unsafe_allow_html=True)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def format_phone_display(phone_raw: str) -> str:
    """Форматирование телефона с ссылкой на звонок"""
    if not phone_raw:
        return ""
    digits = re.sub(r'\D', '', phone_raw)
    if len(digits) == 10:
        formatted = f"+7 {digits[:3]} {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"
        return f'<a href="tel:+7{digits}">{formatted}</a>'
    return phone_raw

def parse_phone_input(phone_input: str) -> str:
    """Очистка телефона для сохранения в БД"""
    return re.sub(r'\D', '', phone_input)[-10:] if phone_input else ""

def format_vk_display(vk_id: str) -> str:
    """Форматирование VK как ссылка"""
    if not vk_id:
        return ""
    return f'<a href="https://vk.com/id{vk_id}" target="_blank">vk.com/id{vk_id}</a>'

def format_tg_display(tg_id: str) -> str:
    """Форматирование Telegram как ссылка"""
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
        st.error(f"❌ Ошибка БД: {e}")
        return None if fetch else False
    finally:
        conn.close()

init_db()

# --- ИНИЦИАЛИЗАЦИЯ СЕССИИ ---
if "edit_row_id" not in st.session_state:
    st.session_state.edit_row_id = None
if "edit_table" not in st.session_state:
    st.session_state.edit_table = None

# --- ИНТЕРФЕЙС ---
st.title("🎛️ CRM Студии Звукозаписи")
menu = ["Клиенты и Группы", "Прайс-лист Услуг", "Заказы", "Детализация Заказа", "ОТЧЁТЫ"]
choice = st.sidebar.selectbox("Навигация", menu)

# ==============================================
# 🧑🤝🧑 КЛИЕНТЫ И ГРУППЫ
# ==============================================
if choice == "Клиенты и Группы":
    st.subheader("Клиенты")

    # --- Добавление нового клиента с автоматической маской телефона ---
    if 'phone_input' not in st.session_state:
        st.session_state.phone_input = ""

    def on_phone_change():
        raw = st.session_state.new_client_phone
        digits = re.sub(r'\D', '', raw)
        if len(digits) >= 10:
            st.session_state.phone_input = f"+7 {digits[:3]} {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"
        else:
            st.session_state.phone_input = raw

    with st.expander("➕ Добавить нового клиента"):
        with st.form("add_client"):
            c_name = st.text_input("Имя *", placeholder="Иван Иванов")
            c_sex = st.selectbox("Пол", ["М", "Ж"])
            st.text_input("Телефон", key="new_client_phone", on_change=on_phone_change, placeholder="9991234567")
            st.caption(f"📱 Будет сохранено как: {st.session_state.phone_input}")
            c_vk = st.text_input("VK ID", placeholder="123456789")
            c_tg = st.text_input("Telegram username", placeholder="my_username")
            
            groups_df = run_query("SELECT id, name FROM groups", fetch=True)
            group_options = [""] + groups_df['name'].tolist() if not groups_df.empty else [""]
            c_group = st.selectbox("Группа", group_options)

            if st.form_submit_button("✅ Сохранить клиента"):
                if c_name:
                    phone_clean = parse_phone_input(st.session_state.phone_input)
                    g_id = groups_df[groups_df['name'] == c_group]['id'].iloc[0] if c_group else None
                    run_query('''INSERT INTO clients (name, sex, phone, vk_id, tg_id, group_id)
                                 VALUES (?,?,?,?,?,?)''', (c_name, c_sex, phone_clean, c_vk, c_tg, g_id))
                    st.success("✅ Клиент добавлен!")
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
                selected_group = st.selectbox("Выбрать группу", groups_df['id'], format_func=lambda x: groups_df[groups_df['id']==x]['name'].iloc[0])
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

    # --- Таблица клиентов с карандашиками для редактирования ---
    st.markdown("### 📋 Список клиентов")
    search_query = st.text_input("🔍 Поиск по имени, телефону или соцсетям")

    clients_raw = run_query('''
        SELECT c.id, c.name, c.sex, c.phone, c.vk_id, c.tg_id, g.name as group_name, c.first_order_date
        FROM clients c LEFT JOIN groups g ON c.group_id = g.id
        WHERE ? = '' OR LOWER(c.name) LIKE LOWER(?) OR c.phone LIKE ?
    ''', (search_query, f'%{search_query}%', f'%{search_query}%'), fetch=True)

    if not clients_raw.empty:
        # Форматируем данные для отображения
        clients_display = clients_raw.copy()
        clients_display['phone'] = clients_display['phone'].apply(format_phone_display)
        clients_display['vk_id'] = clients_display['vk_id'].apply(format_vk_display)
        clients_display['tg_id'] = clients_display['tg_id'].apply(format_tg_display)
        clients_display['first_order_date'] = clients_display['first_order_date'].apply(format_date)
        # Добавляем столбец с карандашиком для редактирования
        clients_display['✏️'] = clients_display['id'].apply(lambda x: f'<span class="edit-btn" onclick="parent.window.stSetSessionValue(\'edit_row_id\', {x}); parent.window.stSetSessionValue(\'edit_table\', \'clients\')">✏️</span>')

        # Отображаем таблицу
        st.markdown(clients_display.to_html(escape=False, index=False), unsafe_allow_html=True)

        # --- Форма редактирования при выборе строки ---
        if st.session_state.edit_table == "clients" and st.session_state.edit_row_id is not None:
            st.markdown("---")
            st.subheader(f"✏️ Редактирование клиента #{st.session_state.edit_row_id}")
            client_data = run_query("SELECT * FROM clients WHERE id=?", (st.session_state.edit_row_id,), fetch=True)
            
            if not client_data.empty:
                row = client_data.iloc[0]
                with st.form(f"edit_client_{st.session_state.edit_row_id}"):
                    edit_name = st.text_input("Имя", value=row['name'])
                    edit_sex = st.selectbox("Пол", ["М", "Ж"], index=0 if row['sex'] == "М" else 1)
                    edit_phone = st.text_input("Телефон", value=format_phone_display(row['phone']).replace('<a href="tel:+7','').split('">')[0] if row['phone'] else "")
                    edit_vk = st.text_input("VK ID", value=row['vk_id'])
                    edit_tg = st.text_input("Telegram", value=row['tg_id'])
                    
                    groups_df = run_query("SELECT id, name FROM groups", fetch=True)
                    group_options = [""] + groups_df['name'].tolist() if not groups_df.empty else [""]
                    current_group = groups_df[groups_df['id'] == row['group_id']]['name'].iloc[0] if row['group_id'] else ""
                    edit_group = st.selectbox("Группа", group_options, index=group_options.index(current_group) if current_group in group_options else 0)

                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.form_submit_button("💾 Сохранить изменения"):
                            g_id = groups_df[groups_df['name'] == edit_group]['id'].iloc[0] if edit_group else None
                            run_query('''UPDATE clients SET name=?, sex=?, phone=?, vk_id=?, tg_id=?, group_id=? WHERE id=?''',
                                      (edit_name, edit_sex, parse_phone_input(edit_phone), edit_vk, edit_tg, g_id, st.session_state.edit_row_id))
                            st.success("✅ Данные обновлены!")
                            st.session_state.edit_row_id = None
                            st.session_state.edit_table = None
                            st.rerun()
                    with col_cancel:
                        if st.form_submit_button("❌ Отмена"):
                            st.session_state.edit_row_id = None
                            st.session_state.edit_table = None
                            st.rerun()
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
            if st.form_submit_button("✅ Добавить услугу"):
                if s_name:
                    run_query("INSERT INTO services_catalog (name, min_price, description) VALUES (?,?,?)", (s_name, s_price, s_desc))
                    st.success("✅ Услуга добавлена")
                    st.rerun()

    services_df = run_query("SELECT * FROM services_catalog", fetch=True)
    if not services_df.empty:
        services_df['min_price'] = services_df['min_price'].apply(lambda x: f"{format_currency(x)} ₽")
        services_df['✏️'] = services_df['id'].apply(lambda x: f'<span class="edit-btn" onclick="parent.window.stSetSessionValue(\'edit_row_id\', {x}); parent.window.stSetSessionValue(\'edit_table\', \'services\')">✏️</span>')
        st.markdown(services_df.to_html(escape=False, index=False), unsafe_allow_html=True)

        # Форма редактирования услуги
        if st.session_state.edit_table == "services" and st.session_state.edit_row_id is not None:
            st.markdown("---")
            st.subheader(f"✏️ Редактирование услуги #{st.session_state.edit_row_id}")
            service_data = run_query("SELECT * FROM services_catalog WHERE id=?", (st.session_state.edit_row_id,), fetch=True)
            if not service_data.empty:
                row = service_data.iloc[0]
                with st.form(f"edit_service_{st.session_state.edit_row_id}"):
                    edit_name = st.text_input("Название", value=row['name'])
                    edit_price = st.number_input("Мин. прайс", min_value=0.0, step=100.0, value=row['min_price'])
                    edit_desc = st.text_area("Описание", value=row['description'])
                    
                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.form_submit_button("💾 Сохранить"):
                            run_query('''UPDATE services_catalog SET name=?, min_price=?, description=? WHERE id=?''',
                                      (edit_name, edit_price, edit_desc, st.session_state.edit_row_id))
                            st.success("✅ Данные обновлены!")
                            st.session_state.edit_row_id = None
                            st.session_state.edit_table = None
                            st.rerun()
                    with col_cancel:
                        if st.form_submit_button("❌ Отмена"):
                            st.session_state.edit_row_id = None
                            st.session_state.edit_table = None
                            st.rerun()
    else:
        st.info("ℹ️ Услуги еще не добавлены")

# ==============================================
# 📦 ЗАКАЗЫ
# ==============================================
elif choice == "Заказы":
    st.subheader("Управление Заказами")
    status_list = ["В работе", "Выполнен", "Оплачено", "Ожидает оплаты"]

    # Создание заказа
    clients_df = run_query("SELECT id, name FROM clients", fetch=True)
    client_map = dict(zip(clients_df['name'], clients_df['id'])) if not clients_df.empty else {}

    with st.expander("➕ Создать новый заказ"):
        with st.form("new_order"):
            if client_map:
                o_client = st.selectbox("Клиент", list(client_map.keys()))
                o_date = st.date_input("Дата исполнения", value=date.today())
                o_status = st.selectbox("Статус", status_list)
                
                if st.form_submit_button("✅ Создать заказ"):
                    c_id = client_map.get(o_client)
                    run_query("INSERT INTO orders (client_id, execution_date, status) VALUES (?,?,?)", (c_id, o_date, o_status))
                    st.success("✅ Заказ создан!")
                    st.rerun()
            else:
                st.warning("⚠️ Сначала добавьте клиентов")

    # Таблица заказов
    st.markdown("### 📋 Список заказов")
    orders_raw = run_query('''
        SELECT o.id, c.name as client_name, o.execution_date, o.status, o.total_amount
        FROM orders o JOIN clients c ON o.client_id = c.id
    ''', fetch=True)

    if not orders_raw.empty:
        orders_display = orders_raw.copy()
        orders_display['execution_date'] = orders_display['execution_date'].apply(format_date)
        orders_display['total_amount'] = orders_display['total_amount'].apply(lambda x: f"{format_currency(x)} ₽")
        orders_display['✏️'] = orders_display['id'].apply(lambda x: f'<span class="edit-btn" onclick="parent.window.stSetSessionValue(\'edit_row_id\', {x}); parent.window.stSetSessionValue(\'edit_table\', \'orders\')">✏️</span>')
        st.markdown(orders_display.to_html(escape=False, index=False), unsafe_allow_html=True)

        # Форма редактирования заказа
        if st.session_state.edit_table == "orders" and st.session_state.edit_row_id is not None:
            st.markdown("---")
            st.subheader(f"✏️ Редактирование заказа #{st.session_state.edit_row_id}")
            order_data = run_query("SELECT * FROM orders WHERE id=?", (st.session_state.edit_row_id,), fetch=True)
            if not order_data.empty:
                row = order_data.iloc[0]
                with st.form(f"edit_order_{st.session_state.edit_row_id}"):
                    edit_client = st.selectbox("Клиент", list(client_map.keys()), index=list(client_map.keys()).index(clients_df[clients_df['id'] == row['client_id']]['name'].iloc[0]))
                    edit_date = st.date_input("Дата исполнения", value=pd.to_datetime(row['execution_date']).date())
                    edit_status = st.selectbox("Статус", status_list, index=status_list.index(row['status']))
                    
                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.form_submit_button("💾 Сохранить"):
                            client_id = client_map.get(edit_client)
                            run_query('''UPDATE orders SET client_id=?, execution_date=?, status=? WHERE id=?''',
                                      (client_id, edit_date, edit_status, st.session_state.edit_row_id))
                            st.success("✅ Данные обновлены!")
                            st.session_state.edit_row_id = None
                            st.session_state.edit_table = None
                            st.rerun()
                    with col_cancel:
                        if st.form_submit_button("❌ Отмена"):
                            st.session_state.edit_row_id = None
                            st.session_state.edit_table = None
                            st.rerun()
    else:
        st.info("ℹ️ Заказы не найдены")

# ==============================================
# 📝 ДЕТАЛИЗАЦИЯ ЗАКАЗА
# ==============================================
elif choice == "Детализация Заказа":
    st.subheader("Состав заказа")
    orders_df = run_query("SELECT o.id, c.name FROM orders o JOIN clients c ON o.client_id = c.id", fetch=True)
    if not orders_df.empty:
        order_id = st.selectbox("Выберите заказ", orders_df['id'], format_func=lambda x: f"Заказ #{x} | {orders_df[orders_df['id']==x]['name'].iloc[0]}")
        
        # Таблица услуг с редактированием
        items_raw = run_query("SELECT * FROM order_items WHERE order_id=?", (order_id,), fetch=True)
        if not items_raw.empty:
            items_display = items_raw.copy()
            items_display['payment_date'] = items_display['payment_date'].apply(format_date)
            items_display['amount'] = items_display['amount'].apply(format_currency)
            st.data_editor(
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

            if st.button("💾 Сохранить изменения"):
                st.success("✅ Данные обновлены!")
                st.rerun()
        else:
            st.info("ℹ️ В заказе еще нет услуг")
    else:
        st.info("⚠️ Сначала создайте заказ")

# ==============================================
# 📊 ОТЧЁТЫ
# ==============================================
elif choice == "ОТЧЁТЫ":
    st.header("📊 Аналитические отчёты (по дате оплаты)")
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
            st.dataframe(new_clients, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Нет данных об оплатах")