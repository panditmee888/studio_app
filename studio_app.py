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
.stDataFrame a { color: #0066ff; text-decoration: none; }
.stDataFrame a:hover { text-decoration: underline; }

/* Стили для st.dataframe с html */
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
th { background-color: #f2f2f2; }
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

    def on_phone_change_callback():
        """Автоматическое форматирование телефона при вводе для поля new_client_phone"""
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
            
            st.text_input("Телефон", key="new_client_phone", on_change=on_phone_change_callback,
                          placeholder="9991234567")
            st.caption(f"Будет сохранено: {st.session_state.phone_input}")
            
            c_vk = st.text_input("VK ID (только цифры)", placeholder="123456789")
            c_tg = st.text_input("Telegram username", placeholder="my_username")
            
            groups_df = run_query("SELECT id, name FROM groups", fetch=True)
            group_options = [""] + groups_df['name'].tolist() if not groups_df.empty else [""]
            c_group = st.selectbox("Группа", group_options)

            if st.form_submit_button("Сохранить клиента"):
                if c_name:
                    phone_clean = parse_phone_input(st.session_state.phone_input)
                    group_id = groups_df[groups_df['name'] == c_group]['id'].iloc[0] if c_group else None
                    
                    run_query('''INSERT INTO clients (name, sex, phone, vk_id, tg_id, group_id)
                                 VALUES (?,?,?,?,?,?)''', (c_name, c_sex, phone_clean, c_vk, c_tg, group_id))
                    st.success("✅ Клиент добавлен")
                    st.session_state.phone_input = "" # Очистка после добавления
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
            groups_df = run_query("SELECT id, name FROM groups", fetch=True)
            if not groups_df.empty:
                selected_group_id = st.selectbox("Выбрать группу для редактирования/удаления", groups_df['id'], format_func=lambda x: groups_df[groups_df['id']==x]['name'].iloc[0])
                new_name = st.text_input("Новое название", value=groups_df[groups_df['id']==selected_group_id]['name'].iloc[0])
                col_edit, col_del = st.columns(2)
                with col_edit:
                    if st.button("✏️ Переименовать", use_container_width=True):
                        run_query("UPDATE groups SET name=? WHERE id=?", (new_name, selected_group_id))
                        st.success("Группа переименована")
                        st.rerun()
                with col_del:
                    if st.button("🗑️ Удалить", use_container_width=True, type="primary"):
                        run_query("DELETE FROM groups WHERE id=?", (selected_group_id,))
                        st.success("Группа удалена")
                        st.rerun()
            else:
                st.info("Групп пока нет")

    # --- Таблица клиентов и форма редактирования ---
    st.markdown("### 📋 Список клиентов")
    search_query = st.text_input("🔍 Поиск по имени, телефону или соцсетям", key="client_search_main")

    clients_raw = run_query('''
        SELECT c.id, c.name, c.sex, c.phone, c.vk_id, c.tg_id, g.name as group_name, c.first_order_date
        FROM clients c LEFT JOIN groups g ON c.group_id = g.id
        WHERE ? = '' OR LOWER(c.name) LIKE LOWER(?) OR c.phone LIKE ? OR LOWER(c.vk_id) LIKE LOWER(?) OR LOWER(c.tg_id) LIKE LOWER(?)
    ''', (search_query, f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'), fetch=True)

    if not clients_raw.empty:
        clients_display = clients_raw.copy()
        clients_display['phone'] = clients_display['phone'].apply(format_phone_display)
        clients_display['vk_id'] = clients_display['vk_id'].apply(format_vk_display)
        clients_display['tg_id'] = clients_display['tg_id'].apply(format_tg_display)
        clients_display['first_order_date'] = clients_display['first_order_date'].apply(format_date)

        st.dataframe(clients_display, use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ Клиенты не найдены")

    st.markdown("### ✏️ Редактировать клиента")
    edit_client_id = st.number_input("ID клиента для редактирования", min_value=0, step=1, key="edit_client_id_input")

    if edit_client_id > 0:
        client_to_edit = run_query("SELECT * FROM clients WHERE id=?", (edit_client_id,), fetch=True)
        if not client_to_edit.empty:
            client_data = client_to_edit.iloc[0]
            with st.form(f"edit_client_form_{edit_client_id}"):
                edit_name = st.text_input("Имя", value=client_data['name'])
                edit_sex = st.selectbox("Пол", ["М", "Ж"], index=["М", "Ж"].index(client_data['sex']))
                
                # Поле телефона для редактирования
                if 'edit_phone_display' not in st.session_state or st.session_state.edit_client_id_form != edit_client_id:
                    st.session_state.edit_phone_display = format_phone_display(client_data['phone']).replace('<a href="tel:+7', '').split('">')[0] if client_data['phone'] else "" # extract raw digits from original formatted
                    st.session_state.edit_client_id_form = edit_client_id

                def on_edit_phone_change_callback():
                    raw = st.session_state.edit_client_phone_raw
                    digits = re.sub(r'\D', '', raw)
                    if len(digits) >= 10:
                        st.session_state.edit_phone_display = f"+7 {digits[:3]} {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"
                    else:
                        st.session_state.edit_phone_display = raw

                st.text_input("Телефон", key="edit_client_phone_raw", on_change=on_edit_phone_change_callback,
                              value=st.session_state.edit_phone_display)
                st.caption(f"Будет сохранено: {st.session_state.edit_phone_display}")

                edit_vk = st.text_input("VK ID", value=client_data['vk_id'])
                edit_tg = st.text_input("Telegram ID", value=client_data['tg_id'])
                
                groups_df = run_query("SELECT id, name FROM groups", fetch=True)
                group_options = [""] + groups_df['name'].tolist() if not groups_df.empty else [""]
                current_group_name = groups_df[groups_df['id'] == client_data['group_id']]['name'].iloc[0] if client_data['group_id'] and not groups_df.empty else ""
                edit_group = st.selectbox("Группа", group_options, index=group_options.index(current_group_name) if current_group_name in group_options else 0)

                if st.form_submit_button("Обновить клиента"):
                    group_id = groups_df[groups_df['name'] == edit_group]['id'].iloc[0] if edit_group else None
                    clean_phone = parse_phone_input(st.session_state.edit_phone_display)
                    
                    run_query('''UPDATE clients SET name=?, sex=?, phone=?, vk_id=?, tg_id=?, group_id=? WHERE id=?''',
                              (edit_name, edit_sex, clean_phone, edit_vk, edit_tg, group_id, edit_client_id))
                    st.success("✅ Клиент обновлен!")
                    st.session_state.edit_client_id_form = -1 # Сброс формы
                    st.rerun()
        else:
            st.error("❌ Клиент с таким ID не найден")
    elif edit_client_id == 0: # Сброс формы, если ID сброшен
        if 'edit_client_id_form' in st.session_state:
            st.session_state.edit_client_id_form = -1


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
        # Для data_editor 'min_price' должна быть числом для редактирования
        # Но для отображения мы хотим форматировать
        # Придется редактировать числом, а отображать в data_editor уже отформатированным
        
        display_services_df = services_df.copy()
        display_services_df['min_price_display'] = services_df['min_price'].apply(lambda x: f"{format_currency(x)} ₽")

        edited_services = st.data_editor(
            display_services_df,
            column_config={
                "id": st.column_config.TextColumn("ID", disabled=True),
                "name": st.column_config.TextColumn("Название", required=True),
                "min_price": st.column_config.NumberColumn("Мин. прайс", min_value=0, step=100, format="%d"),
                "min_price_display": st.column_config.TextColumn("Мин. прайс (отображение)", disabled=True), # Отключили для редактирования
                "description": st.column_config.TextColumn("Описание")
            },
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            key="services_editor"
        )
        
        if st.button("💾 Сохранить изменения в прайс-листе", type="primary"):
            changes = 0
            for idx, row in edited_services.iterrows():
                original = services_df.loc[idx]
                # Сравниваем min_price как числа, а не отформатированную строку
                if (row['name'] != original['name'] or
                    float(row['min_price']) != float(original['min_price']) or # Сравниваем числовые значения
                    row['description'] != original['description']):
                    
                    run_query('''UPDATE services_catalog SET name=?, min_price=?, description=? WHERE id=?''',
                              (row['name'], row['min_price'], row['description'], row['id']))
                    changes += 1
            if changes > 0:
                st.success(f"✅ Обновлено {changes} услуг")
                st.rerun()
            else:
                st.info("ℹ️ Нет изменений для сохранения")

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
                o_client_name = st.selectbox("Клиент", list(client_map.keys()))
                o_date = st.date_input("Дата исполнения", value=date.today())
                o_status = st.selectbox("Статус", status_list)
                
                if st.form_submit_button("Создать заказ"):
                    c_id = client_map.get(o_client_name)
                    run_query("INSERT INTO orders (client_id, execution_date, status) VALUES (?,?,?)", (c_id, o_date, o_status))
                    st.success("✅ Заказ создан")
                    st.rerun()
            else:
                st.warning("⚠️ Сначала добавьте клиентов")

    # Таблица заказов и форма редактирования
    st.markdown("### 📋 Список заказов")
    search_query_orders = st.text_input("🔍 Поиск по имени клиента или статусу", key="order_search_main")
    
    orders_raw = run_query('''
        SELECT o.id, c.name as client_name, o.execution_date, o.status, o.total_amount
        FROM orders o JOIN clients c ON o.client_id = c.id
        WHERE ? = '' OR LOWER(c.name) LIKE LOWER(?) OR LOWER(o.status) LIKE LOWER(?)
    ''', (search_query_orders, f'%{search_query_orders}%', f'%{search_query_orders}%'), fetch=True)

    if not orders_raw.empty:
        orders_display = orders_raw.copy()
        orders_display['execution_date'] = orders_display['execution_date'].apply(format_date)
        orders_display['total_amount'] = orders_display['total_amount'].apply(lambda x: f"{format_currency(x)} ₽")
        
        st.dataframe(orders_display, use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ Заказы не найдены")

    st.markdown("### ✏️ Редактировать заказ")
    edit_order_id = st.number_input("ID заказа для редактирования", min_value=0, step=1, key="edit_order_id_input")

    if edit_order_id > 0:
        order_to_edit = run_query("SELECT o.id, c.id as client_id, c.name as client_name, o.execution_date, o.status, o.total_amount FROM orders o JOIN clients c ON o.client_id = c.id WHERE o.id=?", (edit_order_id,), fetch=True)
        if not order_to_edit.empty:
            order_data = order_to_edit.iloc[0]
            with st.form(f"edit_order_form_{edit_order_id}"):
                edit_client_name = st.selectbox("Клиент", list(client_map.keys()), index=list(client_map.keys()).index(order_data['client_name']))
                edit_date = st.date_input("Дата исполнения", value=pd.to_datetime(order_data['execution_date']).date())
                edit_status = st.selectbox("Статус", status_list, index=status_list.index(order_data['status']))

                if st.form_submit_button("Обновить заказ"):
                    client_id = client_map.get(edit_client_name)
                    run_query('''UPDATE orders SET client_id=?, execution_date=?, status=? WHERE id=?''',
                              (client_id, edit_date, edit_status, edit_order_id))
                    st.success("✅ Заказ обновлен!")
                    st.rerun()
        else:
            st.error("❌ Заказ с таким ID не найден")

# ==============================================
# 📝 ДЕТАЛИЗАЦИЯ ЗАКАЗА
# ==============================================
elif choice == "Детализация Заказа":
    st.subheader("Состав заказа")
    orders_df = run_query("SELECT o.id, c.name, o.execution_date FROM orders o JOIN clients c ON o.client_id = c.id", fetch=True)
    
    if not orders_df.empty:
        order_selection_label = orders_df.apply(lambda x: f"Заказ #{x['id']} - {x['name']} ({format_date(x['execution_date'])})", axis=1)
        selected_order_label = st.selectbox("Выберите заказ", order_selection_label, key="detail_order_selector")
        order_id = int(orders_df[order_selection_label == selected_order_label]['id'].iloc[0])

        srv_list = run_query("SELECT name FROM services_catalog", fetch=True)['name'].tolist() if not run_query("SELECT name FROM services_catalog", fetch=True).empty else []

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("#### ➕ Добавить услугу")
            
            def parse_amount_input(s): return int(s.replace(' ', '')) if s and s.strip() else 0

            with st.form("add_item_form"):
                service_choice = st.selectbox("Услуга", srv_list)
                i_date = st.date_input("Дата оплаты", value=date.today())
                i_amount_raw = st.text_input("Сумма", placeholder="000 000 000", max_chars=12)
                i_hours = st.number_input("Часы", min_value=0.0, step=0.1, format="%.1f")

                if st.form_submit_button("Добавить"):
                    if service_choice and i_amount_raw.strip():
                        try:
                            amount = parse_amount_input(i_amount_raw)
                            run_query('''INSERT INTO order_items (order_id, service_name, payment_date, amount, hours) 
                                         VALUES (?,?,?,?,?)''', (order_id, service_choice, str(i_date), amount, i_hours))
                            # Обновляем total_amount заказа
                            run_query('''UPDATE orders SET total_amount = (SELECT COALESCE(SUM(amount),0) FROM order_items WHERE order_id=?) 
                                         WHERE id=?''', (order_id, order_id))
                            st.success("✅ Услуга добавлена!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Ошибка: {e}")
                    else:
                        st.error("⚠️ Заполните все поля!")

        with col2:
            st.markdown(f"#### 📋 Услуги заказа #{order_id}")
            items_raw = run_query("SELECT * FROM order_items WHERE order_id=?", (order_id,), fetch=True)
            
            if not items_raw.empty:
                items_display_editable = items_raw.copy()
                items_display_editable['id'] = items_display_editable['id'].astype(str)
                items_display_editable['payment_date'] = pd.to_datetime(items_display_editable['payment_date']).dt.date
                items_display_editable['amount'] = items_display_editable['amount'].fillna(0).astype(float)
                items_display_editable['hours'] = items_display_editable['hours'].fillna(0).astype(float)

                edited_items = st.data_editor(
                    items_display_editable,
                    column_config={
                        "id": st.column_config.TextColumn("ID", disabled=True),
                        "order_id": st.column_config.TextColumn("ID Заказа", disabled=True),
                        "service_name": st.column_config.TextColumn("Услуга", required=True),
                        "payment_date": st.column_config.DateColumn("Дата оплаты", format="DD.MM.YYYY", required=True),
                        "amount": st.column_config.NumberColumn("Сумма", format="%d", min_value=0, required=True),
                        "hours": st.column_config.NumberColumn("Часы", format="%.1f", min_value=0, required=True),
                    },
                    hide_index=True,
                    use_container_width=True,
                    num_rows="dynamic",
                    key=f"items_editor_{order_id}"
                )

                if st.button("💾 Сохранить изменения услуг", key=f"save_items_{order_id}"):
                    updates = 0
                    for idx, row in edited_items.iterrows():
                        if row['id'] in items_raw['id'].astype(str).values: # Обновление существующей
                            original = items_raw[items_raw['id'] == int(row['id'])].iloc[0]
                            if (row['service_name'] != original['service_name'] or
                                str(row['payment_date']) != str(original['payment_date']) or
                                float(row['amount']) != float(original['amount']) or
                                float(row['hours']) != float(original['hours'])):
                                
                                run_query('''UPDATE order_items SET service_name=?, payment_date=?, amount=?, hours=? WHERE id=?''',
                                          (row['service_name'], str(row['payment_date']), row['amount'], row['hours'], int(row['id'])))
                                updates += 1
                        elif row['service_name'] and row['amount'] > 0: # Добавление новой (если ID нет, и поля заполнены)
                            run_query('''INSERT INTO order_items (order_id, service_name, payment_date, amount, hours)
                                         VALUES (?,?,?,?,?)''', (order_id, row['service_name'], str(row['payment_date']), row['amount'], row['hours']))
                            updates += 1
                    
                    # Обновляем общую сумму заказа
                    run_query('''UPDATE orders SET total_amount = (SELECT COALESCE(SUM(amount),0) FROM order_items WHERE order_id=?) WHERE id=?''', (order_id, order_id))
                    
                    if updates > 0:
                        st.success(f"✅ Обновлено {updates} услуг")
                        st.rerun()
                    else:
                        st.info("ℹ️ Нет изменений для сохранения")

                st.write("---")
                st.markdown("##### 🗑️ Удалить услугу")
                # Здесь можно добавить selectbox для выбора ID для удаления, если нужно отдельное удаление
                delete_item_id = st.number_input("ID услуги для удаления", min_value=0, step=1, key=f"delete_item_{order_id}")
                if st.button("🗑️ Удалить выбранную услугу", type="primary", key=f"confirm_delete_item_{order_id}"):
                    if delete_item_id > 0:
                        run_query("DELETE FROM order_items WHERE id=?", (delete_item_id,))
                        run_query("UPDATE orders SET total_amount = (SELECT COALESCE(SUM(amount), 0) FROM order_items WHERE order_id=?) WHERE id=?", (order_id, order_id))
                        st.success("✅ Услуга удалена!")
                        st.rerun()
                    else:
                        st.warning("⚠️ Введите ID услуги для удаления")

                # Статистика по заказу
                total_amount = items_raw['amount'].sum() if not items_raw.empty else 0
                st.info(f"💰 Общая сумма по заказу: {format_currency(total_amount)} ₽")
            else:
                st.info("ℹ️ В этом заказе еще нет услуг")
    else:
        st.info("⚠️ Сначала создайте заказ.")

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

    if df is not None and not df.empty:
        df['payment_date'] = pd.to_datetime(df['payment_date'])
        df['year'] = df['payment_date'].dt.year
        df['month'] = df['payment_date'].dt.month
        years = sorted(df['year'].unique())

        selected_year = st.selectbox("Выберите год для отчётов", years, index=len(years)-1, key='report_year_selector')
        df_year = df[df['year'] == selected_year]

        # 1. Заказы по группам
        st.subheader("1. Заказы по группам")
        df_1 = df_year.groupby('group_name').agg(
            Количество=('order_id', 'nunique'), # уникальные заказы
            Сумма=('amount', 'sum'),
            Средний_чек=('amount', 'mean')
        ).reset_index()
        df_1['Сумма'] = df_1['Сумма'].apply(lambda x: f"{format_currency(x)} ₽")
        df_1['Средний_чек'] = df_1['Средний_чек'].apply(lambda x: f"{format_currency(x)} ₽")
        st.dataframe(df_1, use_container_width=True, hide_index=True)

        # 2. Заказы по клиентам
        st.subheader("2. Заказы по клиентам")
        df_2 = df_year.groupby('client_name').agg(
            Количество=('order_id', 'nunique'),
            Сумма=('amount', 'sum')
        ).reset_index().sort_values(by='Сумма', ascending=False)
        df_2['Сумма'] = df_2['Сумма'].apply(lambda x: f"{format_currency(x)} ₽")
        st.dataframe(df_2, use_container_width=True, hide_index=True)

        # 3. Новые клиенты (по первой оплате в выбранном году)
        st.subheader("3. Новые клиенты (по первой оплате в году)")
        new_clients_query = '''
            SELECT c.name, MIN(oi.payment_date) as first_payment_date, COUNT(DISTINCT o.id) as orders_count, SUM(oi.amount) as total_paid
            FROM clients c
            JOIN orders o ON c.id = o.client_id
            JOIN order_items oi ON o.id = oi.order_id
            WHERE strftime('%Y', oi.payment_date) = ?
            GROUP BY c.id
            HAVING MIN(oi.payment_date) = (
                SELECT MIN(oi2.payment_date) FROM order_items oi2 
                JOIN orders o2 ON oi2.order_id = o2.id 
                WHERE o2.client_id = c.id
            )
        '''
        new_clients = run_query(new_clients_query, (str(selected_year),), fetch=True)
        if not new_clients.empty:
            new_clients['first_payment_date'] = new_clients['first_payment_date'].apply(format_date)
            new_clients['total_paid'] = new_clients['total_paid'].apply(lambda x: f"{format_currency(x)} ₽")
            st.dataframe(new_clients, use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ Нет клиентов с первой оплатой в этом году.")

        # 4. Сводка по годам (общая)
        st.subheader("4. Сводка по годам")
        df_4 = df.groupby('year').agg(
            Количество_оплат=('amount', 'count'), # количество оплаченных позиций
            Сумма=('amount', 'sum'),
            Средняя_оплата=('amount', 'mean')
        ).reset_index()
        df_4['Сумма'] = df_4['Сумма'].apply(lambda x: f"{format_currency(x)} ₽")
        df_4['Средняя_оплата'] = df_4['Средняя_оплата'].apply(lambda x: f"{format_currency(x)} ₽")
        st.dataframe(df_4, use_container_width=True, hide_index=True)
        st.bar_chart(df_4, x='year', y='Сумма')

        # 5. Заказы за месяц (детализация)
        st.subheader("5. Заказы за месяц (детализация)")
        selected_month = st.selectbox("Выберите месяц", range(1, 13), index=datetime.now().month - 1, key='report_month_selector')
        df_5 = df_year[df_year['month'] == selected_month].groupby('client_name').agg(
            Количество_оплат=('amount', 'count'),
            Сумма=('amount', 'sum')
        ).reset_index()
        df_5['Сумма'] = df_5['Сумма'].apply(lambda x: f"{format_currency(x)} ₽")
        st.dataframe(df_5, use_container_width=True, hide_index=True)

        # 6. Динамика по месяцам
        st.subheader("6. Динамика по месяцам")
        df_6 = df_year.groupby('month').agg(
            Количество_оплат=('amount', 'count'),
            Сумма=('amount', 'sum'),
            Средняя_оплата=('amount', 'mean')
        ).reset_index()
        df_6['Сумма'] = df_6['Сумма'].apply(lambda x: f"{format_currency(x)} ₽")
        df_6['Средняя_оплата'] = df_6['Средняя_оплата'].apply(lambda x: f"{format_currency(x)} ₽")
        st.dataframe(df_6, use_container_width=True, hide_index=True)
        st.line_chart(df_6, x='month', y='Сумма')

        # 7. Оплаты за последнюю неделю
        st.subheader("7. Оплаты за последнюю неделю")
        week_ago = pd.Timestamp.now() - pd.Timedelta(days=7)
        df_7 = df[df['payment_date'] >= week_ago].copy()
        df_7['payment_date_formatted'] = df_7['payment_date'].apply(format_date)
        report_7 = df_7.groupby(['client_name', 'payment_date_formatted']).agg(
            Сумма=('amount', 'sum')
        ).reset_index()
        report_7['Сумма'] = report_7['Сумма'].apply(format_currency)
        st.dataframe(report_7, use_container_width=True, hide_index=True)

    else:
        st.warning("⚠️ В базе данных пока нет данных об оплатах для формирования отчётов.")