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

def format_vk_link(vk_id) -> str:
    """Формирует правильную ссылку на VK"""
    if not vk_id or pd.isna(vk_id):
        return ""
    vk_id = str(vk_id).strip()
    # Если только цифры — значит, это id
    if vk_id.isdigit():
        return f"https://vk.com/id{vk_id}"
    return f"https://vk.com/{vk_id}"

def format_vk(vk_str):
    """Форматирование VK ID для отображения"""
    if not vk_str or pd.isna(vk_str):
        return ""
    vk = str(vk_str).strip()
    vk = vk.replace("https://", "").replace("http://", "")
    if vk.startswith("vk.com/"):
        return vk
    if vk.startswith("id") and vk[2:].isdigit():
        return f"vk.com/{vk}"
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
    """Инициализация базы данных"""
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
    """Выполняет SQL запрос"""
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

# --- УПРАВЛЕНИЕ КЛИЕНТАМИ ---
    with st.expander("➕ Управление клиентами"):
        action = st.radio("Выберите действие", ["Добавить", "Редактировать", "Удалить"], horizontal=True)

        # Загрузка клиентов
        clients_df = run_query('''
            SELECT c.id, c.name, c.sex, c.phone, c.vk_id, c.tg_id,
                   COALESCE(g.name, 'Без группы') as group_name,
                   c.first_order_date
            FROM clients c
            LEFT JOIN groups g ON c.group_id = g.id
            ORDER BY c.id DESC
        ''', fetch=True)

        if action == "Добавить":
            with st.form("add_client_form"):
                name = st.text_input("Имя *", placeholder="Иван Иванов")
                sex = st.selectbox("Пол", ["М", "Ж"])
                phone = st.text_input("Телефон", placeholder="+7 999 123-45-67")
                vk = st.text_input("VK ID", placeholder="username или id12345")
                tg = st.text_input("Telegram", placeholder="username или @username")
                group = st.selectbox("Группа", ["Без группы"] + group_list)

                if st.form_submit_button("Добавить"):
                    if name.strip():
                        vk_clean = vk.strip().replace("https://vk.com/", "").replace("vk.com/", "")
                        tg_clean = tg.strip().replace("@", "").replace("https://t.me/", "")
                        group_id = group_map.get(group) if group != "Без группы" else None

                        run_query('''
                            INSERT INTO clients (name, sex, phone, vk_id, tg_id, group_id)
                            VALUES (?,?,?,?,?,?)
                        ''', (name.strip(), sex, phone.strip(), vk_clean, tg_clean, group_id))
                        st.success("✅ Клиент добавлен.")
                        st.rerun()
                    else:
                        st.error("Имя обязательно!")

        elif action in ["Редактировать", "Удалить"]:
            if clients_df.empty:
                st.info("Нет клиентов для действия.")
            else:
                client_opts = [f"#{row['id']} {row['name']}" for _, row in clients_df.iterrows()]
                selected_label = st.selectbox("Выберите клиента", client_opts)
                selected_id = int(selected_label.split()[0][1:])
                selected = clients_df[clients_df['id'] == selected_id].iloc[0]
                edit_df = pd.DataFrame([selected])
                edit_df['first_order_date'] = edit_df['first_order_date'].apply(format_date_display)

                result_df = st.data_editor(
                    edit_df[['id', 'name', 'sex', 'phone', 'vk_id', 'tg_id', 'group_name', 'first_order_date']],
                    hide_index=True,
                    column_config={
                        "id": st.column_config.NumberColumn("ID", disabled=True),
                        "name": st.column_config.TextColumn("Имя"),
                        "sex": st.column_config.SelectboxColumn("Пол", options=["М", "Ж"]),
                        "phone": st.column_config.TextColumn("Телефон"),
                        "vk_id": st.column_config.TextColumn("VK ID"),
                        "tg_id": st.column_config.TextColumn("Telegram"),
                        "group_name": st.column_config.SelectboxColumn("Группа", options=["Без группы"] + group_list),
                        "first_order_date": st.column_config.TextColumn("Первая оплата"),
                    },
                    use_container_width=True,
                    key="client_edit_editor"
                )

                if action == "Редактировать":
                    if not result_df.equals(edit_df):
                        new_row = result_df.iloc[0]
                        f_date = parse_date_to_db(new_row['first_order_date'])
                        g_id = group_map.get(new_row['group_name']) if new_row['group_name'] != "Без группы" else None

                        run_query(
                            '''
                            UPDATE clients SET name=?, sex=?, phone=?, vk_id=?, tg_id=?, group_id=?, first_order_date=?
                            WHERE id=?
                            ''',
                            (
                                new_row['name'], new_row['sex'], new_row['phone'],
                                new_row['vk_id'], new_row['tg_id'], g_id, f_date, new_row['id']
                            )
                        )
                        st.success("✅ Изменения сохранены!")
                        st.rerun()
                    else:
                        st.info("Нет изменений")

                elif action == "Удалить":
                    if st.button("🗑️ Подтвердить удаление клиента"):
                        run_query("DELETE FROM clients WHERE id=?", (selected_id,))
                        st.success("✅ Клиент удалён")
                        st.rerun()

    # --- Группы ---
    with st.expander("⚙️ Управление группами"):
        col1, col2 = st.columns([3, 2])
        with col1:
            with st.form("add_group_form"):
                g_new = st.text_input("Название новой группы")
                if st.form_submit_button("Добавить группу"):
                    if g_new.strip():
                        run_query("INSERT INTO groups (name) VALUES (?)", (g_new.strip(),))
                        st.success("✅ Группа добавлена")
                        st.rerun()
                    else:
                        st.error("Название не должно быть пустым")

        with col2:
            if not groups_df.empty:
                for idx, row in groups_df.iterrows():
                    col_a, col_b, col_c = st.columns([3, 1, 1])
                    with col_a:
                        group_name = st.text_input("Группа", value=row['name'], key=f"g_{row['id']}", label_visibility="collapsed")
                    with col_b:
                        if st.button("💾", key=f"g_save_{row['id']}") and group_name.strip() != row['name']:
                            run_query("UPDATE groups SET name=? WHERE id=?", (group_name.strip(), row['id']))
                            st.success("Обновлено")
                            st.rerun()
                    with col_c:
                        if st.button("🗑️", key=f"g_del_{row['id']}"):
                            client_check = run_query("SELECT COUNT(*) as n FROM clients WHERE group_id=?", (row['id'],), fetch=True)
                            if client_check.iloc[0]['n'] > 0:
                                st.error("В группе есть клиенты. Удаление невозможно.")
                            else:
                                run_query("DELETE FROM groups WHERE id=?", (row['id'],))
                                st.success("Удалено")
                                st.rerun()
            else:
                st.info("Группы пока не созданы.")

    # Поиск и фильтрация
    st.markdown("### 🔍 Поиск и фильтрация")
    search_col1, search_col2 = st.columns([2, 1])
    with search_col1:
        search_query = st.text_input("Поиск по имени, телефону, VK или Telegram", placeholder="Введите текст...")
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
        
        # Подготовка ссылок и отображаемых текстов
        display_df = clients_df_data.copy()

        # Телефон
        display_df['Телефон (текст)'] = display_df['phone'].apply(format_phone)  # +7 999 999-99-99
        display_df['Телефон (ссылка)'] = display_df['phone'].apply(
            lambda x: f"tel:+7{''.join(filter(str.isdigit, str(x)))}" if x else ""
        )

        # VK
        display_df['VK (текст)'] = display_df['vk_id'].fillna("")
        display_df['VK (ссылка)'] = display_df['vk_id'].apply(format_vk_link)

        # Telegram
        display_df['tg_id'] = display_df['tg_id'].fillna("")
        display_df['Telegram (текст)'] = display_df['tg_id']
        display_df['Telegram (ссылка)'] = display_df['tg_id'].apply(lambda x: f"https://t.me/{x}" if x else "")

        # Другое
        display_df['Имя'] = display_df['name']
        display_df['Пол'] = display_df['sex']
        display_df['Группа'] = display_df['group_name']
        display_df['Первая оплата'] = display_df['first_order_date'].apply(format_date_display)

        # Удалим NaN из ссылок
        display_df['Телефон (ссылка)'] = display_df['Телефон (ссылка)'].fillna("")
        display_df['VK (ссылка)'] = display_df['VK (ссылка)'].fillna("")
        display_df['Telegram (ссылка)'] = display_df['Telegram (ссылка)'].fillna("")

        st.data_editor(
            display_df[[
                'id', 'Имя', 'Пол',
                'Телефон (ссылка)', 'VK (ссылка)', 'Telegram (ссылка)',
                'Группа', 'Первая оплата'
            ]].rename(columns={
                'id': 'ID',
                'Телефон (ссылка)': 'Телефон',
                'VK (ссылка)': 'VK',
                'Telegram (ссылка)': 'Telegram',
            }),
            column_config={
                "Телефон": st.column_config.LinkColumn("Телефон"),
                "VK": st.column_config.LinkColumn("VK"),
                "Telegram": st.column_config.LinkColumn("Telegram"),
            },
            column_order=[
                "ID", "Имя", "Пол",
                "Телефон", 
                "VK", 
                "Telegram", 
                "Группа", "Первая оплата"
            ],
            hide_index=True,
            use_container_width=True,
            disabled=True,
            key="clients_readonly_editor"
        )
        
        st.markdown("---")
        
        # Редактирование клиентов с выбором строки
        st.markdown("### ✏️ Редактирование клиента")
        
        # Создаём список для выбора
        client_options = [f"#{row['id']} {row['name']}" for _, row in clients_df_data.iterrows()]
        selected_client = st.selectbox("Выберите клиента для редактирования", client_options, key="client_select")
        
        if selected_client:
            # Получаем ID выбранного клиента
            selected_id = int(selected_client.split()[0][1:])
            selected_row = clients_df_data[clients_df_data['id'] == selected_id].iloc[0]
            
            # Создаём таблицу с одной строкой
            edit_df = pd.DataFrame([selected_row])
            edit_df['first_order_date'] = edit_df['first_order_date'].apply(format_date_display)
            
            st.info(f"Редактирование: #{selected_id} {selected_row['name']}")
            
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
                key="single_client_editor"
            )
            
            # Проверяем изменения
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
                    selected_id
                ))
                st.success("✅ Изменения сохранены!")
                st.rerun()
    else:
        st.info("Клиенты не найдены")

# --- 2. ПРАЙС-ЛИСТ ---
elif choice == "Прайс-лист Услуг":
    st.subheader("📦 Прайс-лист Услуг")

    services_df = run_query("SELECT * FROM services_catalog ORDER BY id DESC", fetch=True)

    with st.expander("➕ Управление услугами"):
        action = st.radio("Выберите действие", ["Добавить", "Редактировать", "Удалить"], horizontal=True)

        if action == "Добавить":
            with st.form("add_service_form"):
                s_name = st.text_input("Название услуги")
                s_price = st.text_input("Мин. прайс ₽", placeholder="Например, 10 000")
                s_desc = st.text_area("Описание")

                if st.form_submit_button("Добавить услугу"):
                    if s_name.strip():
                        price = parse_currency(s_price)
                        run_query(
                            "INSERT INTO services_catalog (name, min_price, description) VALUES (?,?,?)",
                            (s_name.strip(), price, s_desc.strip())
                        )
                        st.success("✅ Услуга добавлена")
                        st.rerun()
                    else:
                        st.error("Название услуги обязательно")

        elif action in ["Редактировать", "Удалить"]:
            if services_df.empty:
                st.warning("Нет доступных услуг для выбранного действия.")
            else:
                service_options = [f"#{row['id']} {row['name']}" for _, row in services_df.iterrows()]
                selected_service = st.selectbox("Выберите услугу", service_options, key="edit_service_select")

                selected_id = int(selected_service.split()[0][1:])
                selected_row = services_df[services_df['id'] == selected_id].iloc[0]

                edit_df = pd.DataFrame([selected_row])

                st.markdown(f"**{action} услугу со следующими параметрами:**")

                edited_row = st.data_editor(
                    edit_df,
                    hide_index=True,
                    column_config={
                        "id": st.column_config.NumberColumn("ID", disabled=True),
                        "name": st.column_config.TextColumn("Название"),
                        "min_price": st.column_config.NumberColumn("Мин. прайс ₽", format="%.0f"),
                        "description": st.column_config.TextColumn("Описание")
                    },
                    use_container_width=True,
                    key="service_editor"
                )

                if action == "Редактировать":
                    if not edited_row.equals(edit_df):
                        new_row = edited_row.iloc[0]
                        run_query('''
                            UPDATE services_catalog 
                            SET name=?, min_price=?, description=?
                            WHERE id=?
                        ''', (
                            new_row['name'],
                            new_row['min_price'],
                            new_row['description'],
                            selected_id
                        ))
                        st.success("✅ Изменения сохранены!")
                        st.rerun()

                elif action == "Удалить":
                    if st.button("🗑️ Подтвердить удаление"):
                        run_query("DELETE FROM services_catalog WHERE id=?", (selected_id,))
                        st.success("✅ Услуга удалена")
                        st.rerun()

    st.markdown("### 📋 Список всех услуг")
    services_df = run_query("SELECT * FROM services_catalog", fetch=True)
    if not services_df.empty:
        disp_df = services_df.copy()
        disp_df['min_price'] = disp_df['min_price'].apply(lambda x: f"{format_currency(x)} ₽")
        disp_df.columns = ['ID', 'Название', 'Мин. прайс', 'Описание']
        st.dataframe(disp_df, use_container_width=True, hide_index=True)
    else:
        st.info("Пока нет ни одной услуги.")

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
        
        # Статистика за текущий месяц (по дате оплаты!)
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

        # Таблица заказов для отображения
        display_orders = orders_df[['id', 'client_name', 'execution_date', 'status', 'total_amount']].copy()
        display_orders['execution_date'] = display_orders['execution_date'].apply(format_date_display)
        display_orders['total_amount'] = display_orders['total_amount'].apply(lambda x: f"{format_currency(x)} ₽")
        display_orders.columns = ['ID', 'Клиент', 'Дата исполнения', 'Статус', 'Сумма']
        
        st.dataframe(display_orders, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Редактирование заказов с выбором строки
        st.markdown("### ✏️ Редактирование заказа")
        
        # Создаём список для выбора
        order_options = [f"#{row['id']} {row['client_name']}" for _, row in orders_df.iterrows()]
        selected_order = st.selectbox("Выберите заказ для редактирования", order_options, key="order_select")
        
        if selected_order:
            # Получаем ID выбранного заказа
            selected_id = int(selected_order.split()[0][1:])
            selected_row = orders_df[orders_df['id'] == selected_id].iloc[0]
            
            # Создаём таблицу с одной строкой
            edit_df = orders_df[orders_df['id'] == selected_id][['id', 'client_id', 'client_name', 'execution_date', 'status', 'total_amount']].copy()
            edit_df['execution_date'] = edit_df['execution_date'].apply(format_date_display)
            
            st.info(f"Редактирование: Заказ #{selected_id} {selected_row['client_name']}")
            
            edited_order = st.data_editor(
                edit_df,
                column_config={
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "client_id": st.column_config.NumberColumn("ID клиента", disabled=True),
                    "client_name": st.column_config.SelectboxColumn(
                        "Клиент",
                        options=client_names,
                        required=True
                    ),
                    "execution_date": st.column_config.TextColumn("Дата исполнения"),
                    "status": st.column_config.SelectboxColumn(
                        "Статус",
                        options=STATUS_LIST,
                        required=True
                    ),
                    "total_amount": st.column_config.NumberColumn("Сумма", disabled=True)
                },
                hide_index=True,
                use_container_width=True,
                key="single_order_editor"
            )

            if not edited_order.equals(edit_df):
                new_row = edited_order.iloc[0]
                client_id = client_map.get(new_row['client_name'])
                exec_date = parse_date_to_db(new_row['execution_date'])
                
                run_query('''
                    UPDATE orders 
                    SET client_id=?, execution_date=?, status=?
                    WHERE id=?
                ''', (client_id, exec_date, new_row['status'], selected_id))
                
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
            lambda x: f"#{x['id']} {x['name']} ({format_date_display(x['execution_date'])})", 
            axis=1
        )
        order_selection = st.selectbox("Выберите заказ", orders_df['label'])
        order_id = int(orders_df[orders_df['label'] == order_selection]['id'].iloc[0])
        
        # Получаем client_id для обновления first_order_date
        client_id_result = run_query("SELECT client_id FROM orders WHERE id=?", (order_id,), fetch=True)
        current_client_id = client_id_result['client_id'].iloc[0] if not client_id_result.empty else None

        # Услуги из каталога
        services_cat = run_query("SELECT name FROM services_catalog", fetch=True)
        srv_list = services_cat['name'].tolist() if not services_cat.empty else []
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### ➕ Добавить услугу")
            with st.form("add_item_form"):
                service_choice = st.selectbox("Услуга", srv_list if srv_list else ["Нет услуг в каталоге"])
                i_date = st.date_input("Дата оплаты", value=date.today())
                
                # Поле суммы с форматированием
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
                        # Обновляем сумму заказа
                        total_res = run_query(
                            "SELECT SUM(amount) as total FROM order_items WHERE order_id=?",
                            (order_id,),
                            fetch=True
                        )
                        total = total_res['total'].iloc[0] if not total_res.empty and total_res['total'].iloc[0] else 0.0
                        run_query("UPDATE orders SET total_amount=? WHERE id=?", (total, order_id))
                        
                        # Обновляем first_order_date клиента
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
                # Форматируем для отображения
                display_items = items_df.copy()
                display_items['payment_date'] = display_items['payment_date'].apply(format_date_display)
                display_items['amount'] = display_items['amount'].apply(lambda x: f"{format_currency(x)} ₽")
                display_items['hours'] = display_items['hours'].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "0.0")
                display_items.columns = ['ID', 'Услуга', 'Дата оплаты', 'Сумма', 'Часы']
                
                st.dataframe(display_items, use_container_width=True, hide_index=True)

                # Итого
                total_amount = items_df['amount'].sum()
                st.success(f"💰 **Итого:** {format_currency(total_amount)} ₽")
                
                st.markdown("---")
                st.markdown("#### ✏️ Редактирование услуги")
                
                # Создаём список для выбора
                item_options = [f"#{row['id']} {row['service_name']} ({format_date_display(row['payment_date'])})" 
                               for _, row in items_df.iterrows()]
                selected_item = st.selectbox("Выберите услугу для редактирования", item_options, key="item_select")
                
                if selected_item:
                    # Получаем ID выбранной услуги
                    selected_id = int(selected_item.split()[0][1:])
                    
                    # Создаём таблицу с одной строкой
                    edit_df = items_df[items_df['id'] == selected_id].copy()
                    
                    st.info(f"Редактирование: {selected_item}")
                    
                    edited_item = st.data_editor(
                        edit_df,
                        column_config={
                            "id": st.column_config.NumberColumn("ID", disabled=True),
                            "service_name": st.column_config.SelectboxColumn(
                                "Услуга",
                                options=srv_list,
                                required=True
                            ),
                            "payment_date": st.column_config.TextColumn("Дата оплаты"),
                            "amount": st.column_config.NumberColumn("Сумма", format="%.0f"),
                            "hours": st.column_config.NumberColumn("Часы", format="%.1f", step=0.1)
                        },
                        hide_index=True,
                        use_container_width=True,
                        key="single_item_editor"
                    )

                    if not edited_item.equals(edit_df):
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
                            selected_id
                        ))
                        
                        # Обновляем сумму заказа
                        total_res = run_query(
                            "SELECT SUM(amount) as total FROM order_items WHERE order_id=?",
                            (order_id,),
                            fetch=True
                        )
                        total = total_res['total'].iloc[0] if not total_res.empty and total_res['total'].iloc[0] else 0.0
                        run_query("UPDATE orders SET total_amount=? WHERE id=?", (total, order_id))
                        
                        # Обновляем first_order_date клиента
                        if current_client_id:
                            update_client_first_order_date(current_client_id)
                        
                        st.success("✅ Изменения сохранены!")
                        st.rerun()
            else:
                st.info("В этом заказе пока нет услуг")
    else:
        st.info("Сначала создайте заказ")

# --- 5. ОТЧЁТЫ ---
elif choice == "ОТЧЁТЫ":
    st.header("📊 Аналитические Отчёты")

    # Основной запрос — по дате оплаты!
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
        
        # Копия для графика
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