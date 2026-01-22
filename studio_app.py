import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, timedelta
import re

# --- КОНСТАНТЫ ---
STATUS_LIST = ["В работе", "Ожидает оплаты", "Выполнен", "Оплачен"]

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
@st.cache_data(ttl=30)
def load_groups():
    return run_query("SELECT id, name FROM groups ORDER BY id DESC", fetch=True)

def format_phone(phone_str):
    """
    Форматирование номера: 7XXXXXXXXXX → +7 (XXX) XXX-XX-XX
    """
    if not phone_str or pd.isna(phone_str):
        return ""
    digits = ''.join(filter(str.isdigit, str(phone_str)))
    if digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits  # если не хватает кода
    if len(digits) != 11 or not digits.startswith("7"):
        return phone_str  # вернём как есть

    return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
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
        
# Вспомогательная функция пересчёта суммы заказа
def _update_order_total(order_id):
    total_df = run_query("SELECT COALESCE(SUM(amount),0) as t FROM order_items WHERE order_id=?", (order_id,), fetch=True)
    total = total_df.iloc[0]['t']
    run_query("UPDATE orders SET total_amount=? WHERE id=?", (total, order_id))

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

menu = ["Клиенты и Группы", "Прайс-лист Услуг", "Заказы и услуги", "ОТЧЁТЫ"]
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
        action = st.radio("Выберите действие", ["Добавить", "Редактировать", "Удалить"], horizontal=True, key="client_action_radio")

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
            with st.form("add_client"):
                # 👇 Часть 1 — Имя, Пол, Группа — в одной строке
                col1, col2, col3 = st.columns([3,1,2])
                with col1:
                    c_name = st.text_input("Имя *", placeholder="Иван Иванов")
                with col2:
                    c_sex = st.selectbox("Пол", ["М", "Ж"])
                with col3:
                    if groups_list:
                        c_group = st.selectbox("Группа", options=["Без группы"] + groups_list)
                    else:
                        c_group = "Без группы"
                        st.info("Группы еще не созданы")

                # 👇 Часть 2 — Телефон, VK и Telegram в одну строку
                col4, col5, col6 = st.columns(3)
                with col4:
                    c_phone_raw = st.text_input(
                    "Телефон", 
                    placeholder="Введите номер телефона",
                    help="Введите номер в любом формате. Сохраняется как 7XXXXXXXXXX, отображается с маской."
                )
                with col5:
                    c_vk_raw = st.text_input("VK ID", placeholder="id123456 или username")
                with col6:
                    c_tg_raw = st.text_input("Telegram", placeholder="username (без @)")
                
                # 👇 Кнопка
                if st.form_submit_button("Сохранить клиента"):
                    if c_name:
                        if not c_phone_raw:
                            st.error("Введите номер телефона")
                        else:
                            import re
                            digits_only = re.sub(r'\D', '', c_phone_raw)
        
                            if digits_only.startswith("8") and len(digits_only) == 11:
                                digits_only = "7" + digits_only[1:]
                            if len(digits_only) == 10:
                                digits_only = "7" + digits_only
                            if len(digits_only) != 11 or not digits_only.startswith("7"):
                                st.error("❌ Введите корректный номер: 11 цифр, начиная с 7 (например: 79991234567)")
                                st.stop()
                            phone = digits_only
        
                            vk = c_vk_raw.strip() if c_vk_raw else ""
                            tg = c_tg_raw.strip().replace("@", "").replace("t.me/", "") if c_tg_raw else ""
                            g_id = group_map.get(c_group) if c_group != "Без группы" else None
        
                            run_query('''INSERT INTO clients 
                                (name, sex, phone, vk_id, tg_id, group_id) 
                                VALUES (?,?,?,?,?,?)''', 
                                (c_name, c_sex, phone, vk, tg, g_id))
        
                            st.success("✅ Клиент добавлен!")
                            st.rerun()
                    else:
                        st.error("Введите имя клиента")


        elif action in ["Редактировать", "Удалить"]:
            if clients_df.empty:
                st.info("Нет клиентов для действия.")
            else:
                client_options = [f"#{row['id']} {row['name']}" for _, row in clients_df.iterrows()]
                selected_client = st.selectbox("Выберите клиента для редактирования", client_options, key="client_select")
        
                if selected_client:
                    # Получаем ID выбранного клиента
                    selected_id = int(selected_client.split()[0][1:])
                    selected_row = clients_df[clients_df['id'] == selected_id].iloc[0]
            
                    # Создаём таблицу с одной строкой
                    edit_df = pd.DataFrame([selected_row])
                    edit_df['first_order_date'] = edit_df['first_order_date'].apply(format_date_display)
            
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

                if action == "Редактировать":
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

                elif action == "Удалить":
                    if st.button("🗑️ Подтвердить удаление клиента"):
                        run_query("DELETE FROM clients WHERE id=?", (selected_id,))
                        st.success("✅ Клиент удалён")
                        st.rerun()

    # --- Управление группами ---
    with st.expander("🏷️ Управление группами", expanded=False):
        # Выбор действия
        col_action_l, col_action_r = st.columns([2, 3])
        with col_action_l:
            action = st.radio("Выберите действие", ["Добавить", "Редактировать", "Удалить"], horizontal=True, key="group_action_radio")
        with col_action_r:
            st.markdown("#### 📋 Список всех групп")
    
        groups_df = load_groups()  # (можно повторить — кеш используется)
    
        # Две колонки общей работы
        col_l, col_r = st.columns([2, 3])
    
        # --- ДОБАВИТЬ ---
        if action == "Добавить":
            with col_l:
                with st.form("add_group_form"):
                    new_group_name = st.text_input("Название группы *", placeholder="Например: Постоянные, VIP")
    
                    if st.form_submit_button("Сохранить группу"):
                        if new_group_name.strip():
                            check = run_query("SELECT id FROM groups WHERE name=?", (new_group_name.strip(),), fetch=True)
                            if not check.empty:
                                st.error("❌ Группа с таким названием уже существует")
                            else:
                                run_query("INSERT INTO groups (name) VALUES (?)", (new_group_name.strip(),))
                                st.toast("✅ Группа добавлена!", icon="✅")
                                st.cache_data.clear()  # обнуляем кэш
                                st.session_state["group_rerun"] = True
                        else:
                            st.warning("Введите название группы")
    
            # Отображаем список справа (в col_r)
            with col_r:
                groups_display = groups_df.copy()
                groups_display.columns = ['ID', 'Название группы']
                st.dataframe(groups_display, use_container_width=True, hide_index=True)
    
        # --- РЕДАКТИРОВАТЬ / УДАЛИТЬ ---
        elif action in ["Редактировать", "Удалить"]:
            with col_l:
                if groups_df.empty:
                    st.info("Нет групп для действия.")
                else:
                    group_options = [f"#{row['id']} {row['name']}" for _, row in groups_df.iterrows()]
                    selected_group = st.selectbox("Выберите группу", group_options, key="group_select")
    
                    if selected_group:
                        selected_id = int(selected_group.split()[0][1:])
                        selected_row = groups_df[groups_df['id'] == selected_id].iloc[0]
                        edit_df = pd.DataFrame([selected_row])
    
                        if action == "Редактировать":
                            edited = st.data_editor(
                                edit_df,
                                column_config={
                                    "id": st.column_config.NumberColumn("ID", disabled=True),
                                    "name": st.column_config.TextColumn("Название группы"),
                                },
                                hide_index=True,
                                use_container_width=True,
                                key="group_editor"
                            )
    
                            if not edited.equals(edit_df):
                                new_name = edited.iloc[0]["name"].strip()
                                if not new_name:
                                    st.error("❌ Название не может быть пустым")
                                else:
                                    exists = run_query("SELECT id FROM groups WHERE name=? AND id!=?", (new_name, selected_id), fetch=True)
                                    if not exists.empty:
                                        st.error("❌ Такое название уже есть")
                                    else:
                                        run_query("UPDATE groups SET name=? WHERE id=?", (new_name, selected_id))
                                        st.toast("✅ Группа обновлена!", icon="✅")
                                        st.cache_data.clear()
                                        st.session_state["group_rerun"] = True
    
                        elif action == "Удалить":
                            st.warning(f"Вы собираетесь удалить группу: **{selected_row['name']}**")
                            clients_check = run_query("SELECT COUNT(*) as count FROM clients WHERE group_id=?", (selected_id,), fetch=True)
                            has_clients = clients_check.iloc[0]["count"] > 0 if not clients_check.empty else False
    
                            if has_clients:
                                st.error("❌ В группе есть клиенты. Удаление невозможно.")
                            else:
                                if st.button("🗑️ Подтвердить удаление группы"):
                                    run_query("DELETE FROM groups WHERE id=?", (selected_id,))
                                    st.toast("✅ Группа удалена!", icon="🧹")
                                    st.cache_data.clear()
                                    st.session_state["group_rerun"] = True
    
    # 👈 После всех блоков — если сработал флаг, перезагрузить
    if st.session_state.get("group_rerun"):
        del st.session_state["group_rerun"]
        st.rerun()


    # Поиск и фильтрация

    search_col1, search_col2 = st.columns([2, 1])
    with search_col1:
        search_query = st.text_input("Поиск по имени, телефону, VK или Telegram", placeholder="Введите текст...")
    with search_col2:
        filter_group = st.selectbox("Фильтр по группе", ["Все"] + groups_list)

    # Получаем всех клиентов
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
    ORDER BY c.id DESC
    '''
    clients_df_data = run_query(clients_query, fetch=True)

    # --- Фильтрация на стороне Python (регистронезависимая, поддержка кириллицы) ---
    if not clients_df_data.empty:

        if search_query.strip():
            search_query_lower = search_query.strip().lower()

            # Приводим к строке и применяем str.contains(..., case=False)
            clients_df_data = clients_df_data[
                clients_df_data['name'].astype(str).str.lower().str.contains(search_query_lower, na=False) |
                clients_df_data['phone'].astype(str).str.contains(search_query, na=False) |
                clients_df_data['vk_id'].astype(str).str.lower().str.contains(search_query_lower, na=False) |
                clients_df_data['tg_id'].astype(str).str.lower().str.contains(search_query_lower, na=False)
            ]

        if filter_group != "Все":
            clients_df_data = clients_df_data[
                clients_df_data["group_name"] == filter_group
            ]



    if not clients_df_data.empty:
        
        # Подготовка ссылок и отображаемых текстов
        display_df = clients_df_data.copy()

        # Телефон
        display_df['Телефон'] = display_df['phone'].apply(format_phone)  # +7 999 999-99-99

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
        display_df['VK (ссылка)'] = display_df['VK (ссылка)'].fillna("")
        display_df['Telegram (ссылка)'] = display_df['Telegram (ссылка)'].fillna("")

        st.data_editor(
            display_df[[
                'id', 'Имя', 'Пол',
                'Телефон', 'VK (ссылка)', 'Telegram (ссылка)',
                'Группа', 'Первая оплата'
            ]].rename(columns={
                'id': 'ID',
                'VK (ссылка)': 'VK',
                'Telegram (ссылка)': 'Telegram',
            }),
            column_config={
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


# --- 3. ЗАКАЗЫ И УСЛУГИ (НОВАЯ КРАСИВАЯ ВЕРСИЯ) ---

elif choice == "Заказы и услуги":
    st.subheader("Заказы и услуги")

    # Справочники
    clients_df = run_query("SELECT id, name FROM clients ORDER BY name", fetch=True)
    client_options = clients_df['name'].tolist() if not clients_df.empty else []
    client_map = dict(zip(clients_df['name'], clients_df['id'])) if not clients_df.empty else {}

    services_df = run_query("SELECT name FROM services_catalog ORDER BY name", fetch=True)
    service_options = services_df['name'].tolist() if not services_df.empty else []

    col_left, col_right = st.columns([1.8, 1.2])

    with col_left:
        st.markdown("### Управление заказом")

        order_mode = st.radio(
            "Действие с заказом",
            ["Добавить", "Редактировать", "Удалить"],
            horizontal=True,
            key="order_mode"
        )

        selected_client_name = st.selectbox(
            "Клиент",
            options=["— Выберите клиента —"] + client_options,
            key="order_client"
        )

        col_date, col_status = st.columns(2)
        with col_date:
            execution_date = st.date_input("Дата исполнения", value=date.today(), key="order_date")
        with col_status:
            status = st.selectbox("Статус", STATUS_LIST, key="order_status")

        order_id = None
        if order_mode in ["Редактировать", "Удалить"] and selected_client_name != "— Выберите клиента —":
            client_id = client_map.get(selected_client_name)
            if client_id:
                orders_df = run_query("""
                    SELECT o.id, o.execution_date, o.status 
                    FROM orders o WHERE o.client_id = ? 
                    ORDER BY o.execution_date DESC
                """, (client_id,), fetch=True)

                if not orders_df.empty:
                    order_labels = [
                        f"№{row['id']} | {format_date_display(row['execution_date'])} | {row['status']}"
                        for _, row in orders_df.iterrows()
                    ]
                    selected_label = st.selectbox("Выберите заказ", order_labels, key="sel_existing_order")
                    order_id = int(selected_label.split()[0][1:-1])
                else:
                    st.info("У этого клиента пока нет заказов")

        with st.expander("Управление услугами в заказе", expanded=True):
            service_mode = st.radio(
                "Действие с услугой",
                ["Добавить", "Редактировать", "Удалить"],
                horizontal=True,
                key="service_mode"
            )

            current_items_df = pd.DataFrame()
            if order_id:
                current_items_df = run_query("""
                    SELECT id, service_name, payment_date, amount, hours 
                    FROM order_items WHERE order_id = ?
                """, (order_id,), fetch=True)

            if service_mode == "Добавить":
                with st.form("form_add_service", clear_on_submit=True):
                    st.markdown("**Новая услуга**")
                    c1, c2 = st.columns(2)
                    with c1:
                        new_service = st.selectbox("Услуга", service_options, key="add_srv")
                        new_amount = st.text_input("Сумма ₽", placeholder="15 000", key="add_amount")
                    with c2:
                        new_pay_date = st.date_input("Дата оплаты", value=date.today(), key="add_paydate")
                        new_hours = st.text_input("Часы", value="0.0", key="add_hours")

                    if st.form_submit_button("Добавить услугу", use_container_width=True, type="primary"):
                        if selected_client_name == "— Выберите клиента —":
                            st.error("Выберите клиента")
                            st.stop()

                        amount_val = parse_currency(new_amount)
                        hours_val = float(new_hours.replace(",", ".")) if new_hours.strip() else 0.0

                        # Если заказа ещё нет — создаём
                        if not order_id:
                            cid = client_map[selected_client_name]
                            run_query("""
                                INSERT INTO orders (client_id, execution_date, status) 
                                VALUES (?, ?, ?)
                            """, (cid, execution_date.strftime("%Y-%m-%d"), status))
                            new_id_df = run_query("SELECT last_insert_rowid() as id", fetch=True)
                            order_id = new_id_df.iloc[0]['id']

                        run_query("""
                            INSERT INTO order_items (order_id, service_name, payment_date, amount, hours)
                            VALUES (?, ?, ?, ?, ?)
                        """, (order_id, new_service, new_pay_date.strftime("%Y-%m-%d"), amount_val, hours_val))

                        _update_order_total(order_id)
                        update_client_first_order_date(client_map[selected_client_name])
                        st.success("Услуга добавлена!")
                        st.rerun()

            elif service_mode in ["Редактировать", "Удалить"] and not current_items_df.empty:
                item_labels = [
                    f"{r.service_name} — {format_currency(r.amount)}₽ — {format_date_display(r.payment_date)}"
                    for r in current_items_df.itertuples()
                ]
                sel_label = st.selectbox("Услуга", item_labels, key="sel_item")
                sel_idx = item_labels.index(sel_label)
                sel_item_id = current_items_df.iloc[sel_idx]['id']

                row = current_items_df[current_items_df['id'] == sel_item_id].iloc[0]
                edit_df = pd.DataFrame([{
                    "service_name": row["service_name"],
                    "payment_date": pd.to_datetime(row["payment_date"]),
                    "amount": row["amount"],
                    "hours": row["hours"]
                }])

                edited = st.data_editor(
                    edit_df,
                    column_config={
                        "service_name": st.column_config.SelectboxColumn("Услуга", options=service_options),
                        "payment_date": st.column_config.DateColumn("Дата оплаты"),
                        "amount": st.column_config.NumberColumn("Сумма ₽", format="%.0f"),
                        "hours": st.column_config.NumberColumn("Часы", format="%.2f")
                    },
                    hide_index=True,
                    use_container_width=True
                )

                if service_mode == "Редактировать":
                    if st.button("Сохранить изменения", use_container_width=True, type="primary"):
                        r = edited.iloc[0]
                        run_query("""
                            UPDATE order_items SET service_name=?, payment_date=?, amount=?, hours=?
                            WHERE id=?
                        """, (r.service_name, r.payment_date, r.amount, r.hours, sel_item_id))
                        _update_order_total(order_id)
                        st.success("Услуга обновлена")
                        st.rerun()

                if service_mode == "Удалить":
                    if st.button("Удалить услугу", use_container_width=True, type="secondary"):
                        run_query("DELETE FROM order_items WHERE id=?", (sel_item_id,))
                        _update_order_total(order_id)
                        st.success("Услуга удалена")
                        st.rerun()

            elif service_mode in ["Редактировать", "Удалить"]:
                st.info("Нет услуг для редактирования/удаления")

        # Кнопки действий по заказу
        if order_mode == "Добавить":
            if st.button("Создать заказ", use_container_width=True, type="primary"):
                if selected_client_name == "— Выберите клиента —":
                    st.error("Выберите клиента")
                else:
                    cid = client_map[selected_client_name]
                    run_query("""
                        INSERT INTO orders (client_id, execution_date, status) VALUES (?, ?, ?)
                    """, (cid, execution_date.strftime("%Y-%m-%d"), status))
                    st.success("Заказ создан!")
                    st.rerun()

        elif order_mode == "Редактировать" and order_id:
            if st.button("Сохранить изменения заказа", use_container_width=True, type="primary"):
                run_query("""
                    UPDATE orders SET execution_date=?, status=? WHERE id=?
                """, (execution_date.strftime("%Y-%m-%d"), status, order_id))
                st.success("Заказ обновлён")
                st.rerun()

        elif order_mode == "Удалить" and order_id:
            st.warning("Удалить весь заказ со всеми услугами?")
            if st.button("Подтвердить удаление", type="secondary"):
                run_query("DELETE FROM orders WHERE id=?", (order_id,))
                st.success("Заказ удалён")
                st.rerun()

    # Правая колонка — всегда состав заказа
    with col_right:
        st.markdown("### Состав заказа")

        display_id = order_id or st.session_state.get("last_viewed_order_id")
        if display_id:
            items = run_query("""
                SELECT service_name, payment_date, amount, hours 
                FROM order_items WHERE order_id = ? ORDER BY payment_date
            """, (display_id,), fetch=True)

            total_row = run_query("SELECT total_amount FROM orders WHERE id=?", (display_id,), fetch=True)
            total = total_row.iloc[0]['total_amount'] if not total_row.empty else 0

            if not items.empty:
                disp = items.copy()
                disp['payment_date'] = disp['payment_date'].apply(format_date_display)
                disp['amount'] = disp['amount'].apply(lambda x: f"{format_currency(x)} ₽")
                disp['hours'] = disp['hours'].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "—")

                st.dataframe(
                    disp.rename(columns={
                        "service_name": "Услуга",
                        "payment_date": "Оплата",
                        "amount": "Сумма",
                        "hours": "Часы"
                    })[["Услуга", "Оплата", "Сумма", "Часы"]],
                    use_container_width=True,
                    hide_index=True
                )
                st.markdown(f"**Итого: {format_currency(total)} ₽**")
            else:
                st.info("Услуги ещё не добавлены")
        else:
            st.info("Выберите заказ — состав появится здесь")

    # Сохраняем последний просмотренный заказ для правой колонки
    if order_id:
        st.session_state.last_viewed_order_id = order_id





# --- 4. ОТЧЁТЫ (остаётся без изменений) ---
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