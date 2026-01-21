import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, timedelta

# --- КОНСТАНТЫ ---
STATUS_LIST = ["В работе", "Ожидает оплаты", "Выполнен", "Оплачен"]

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def format_phone(phone_str):
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

def format_vk(vk_str):
    if not vk_str or pd.isna(vk_str):
        return ""
    vk = str(vk_str).strip().replace("https://", "").replace("http://", "")
    if vk.startswith("vk.com/"):
        return vk
    if vk.startswith("id") and vk[2:].isdigit():
        return f"vk.com/{vk}"
    if vk.isdigit():
        return f"vk.com/id{vk}"
    return f"vk.com/{vk}"

def format_telegram(tg_str):
    if not tg_str or pd.isna(tg_str):
        return ""
    tg = str(tg_str).strip().replace("https://", "").replace("http://", "").replace("@", "")
    if tg.startswith("t.me/"):
        return tg
    return f"t.me/{tg}"

def format_date_display(date_str):
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
    if pd.isna(amount) or amount is None:
        return "0"
    try:
        return f"{int(float(amount)):,}".replace(",", " ")
    except:
        return str(amount)

def parse_currency(amount_str):
    if not amount_str or pd.isna(amount_str):
        return 0.0
    try:
        clean = str(amount_str).replace(" ", "").replace(",", "").replace("₽", "").strip()
        return float(clean) if clean else 0.0
    except:
        return 0.0

def update_client_first_order_date(client_id):
    result = run_query('''
        SELECT MIN(oi.payment_date) as first_payment
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE o.client_id = ? AND oi.payment_date IS NOT NULL
    ''', (client_id,), fetch=True)
    
    if not result.empty and result['first_payment'].iloc[0]:
        run_query("UPDATE clients SET first_order_date = ? WHERE id = ?",
                  (result['first_payment'].iloc[0], client_id))

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

# ===========================================
# --- 1. КЛИЕНТЫ И ГРУППЫ ---
# ===========================================
if choice == "Клиенты и Группы":
    st.subheader("Клиенты")
    
    groups_df = run_query("SELECT id, name FROM groups", fetch=True)
    groups_list = groups_df['name'].tolist() if not groups_df.empty else []
    group_map = dict(zip(groups_df['name'], groups_df['id'])) if not groups_df.empty else {}
    
    # Добавление клиента
    with st.expander("➕ Добавить нового клиента"):
        with st.form("add_client"):
            c_name = st.text_input("Имя *")
            c_sex = st.selectbox("Пол", ["М", "Ж"])
            c_phone = st.text_input("Телефон", placeholder="+7 999 123-45-67")
            c_vk = st.text_input("VK ID", placeholder="id123456789")
            c_tg = st.text_input("Telegram", placeholder="username")
            c_group = st.selectbox("Группа", ["Без группы"] + groups_list)
            
            if st.form_submit_button("Сохранить"):
                if c_name:
                    g_id = group_map.get(c_group) if c_group != "Без группы" else None
                    run_query('''INSERT INTO clients (name, sex, phone, vk_id, tg_id, group_id) 
                                 VALUES (?,?,?,?,?,?)''', (c_name, c_sex, c_phone, c_vk, c_tg, g_id))
                    st.success("✅ Клиент добавлен!")
                    st.rerun()
                else:
                    st.error("Введите имя")

    # Управление группами
    with st.expander("⚙️ Группы клиентов"):
        col1, col2 = st.columns(2)
        with col1:
            with st.form("add_group"):
                new_group = st.text_input("Новая группа")
                if st.form_submit_button("Добавить"):
                    if new_group:
                        run_query("INSERT INTO groups (name) VALUES (?)", (new_group,))
                        st.rerun()
        with col2:
            if not groups_df.empty:
                del_group = st.selectbox("Удалить группу", groups_df['name'].tolist())
                if st.button("🗑️ Удалить группу"):
                    g_id = group_map.get(del_group)
                    check = run_query("SELECT COUNT(*) as c FROM clients WHERE group_id=?", (g_id,), fetch=True)
                    if check['c'].iloc[0] > 0:
                        st.warning("Нельзя удалить группу с клиентами!")
                    else:
                        run_query("DELETE FROM groups WHERE id=?", (g_id,))
                        st.rerun()

    # Поиск
    st.markdown("### 🔍 Поиск")
    col_s1, col_s2 = st.columns([2, 1])
    with col_s1:
        search_q = st.text_input("Поиск по имени/телефону/VK/Telegram", placeholder="Введите текст...")
    with col_s2:
        filter_group = st.selectbox("Группа", ["Все"] + groups_list)

    # Запрос
    query = '''SELECT c.id, c.name, c.sex, c.phone, c.vk_id, c.tg_id, 
                      COALESCE(g.name, 'Без группы') as group_name, c.first_order_date
               FROM clients c LEFT JOIN groups g ON c.group_id = g.id WHERE 1=1'''
    params = []
    
    if search_q:
        query += ''' AND (LOWER(c.name) LIKE ? OR c.phone LIKE ? OR 
                          LOWER(c.vk_id) LIKE ? OR LOWER(c.tg_id) LIKE ?)'''
        p = f'%{search_q.lower()}%'
        params.extend([p, p, p, p])
    if filter_group != "Все":
        query += ' AND g.name = ?'
        params.append(filter_group)
    
    query += ' ORDER BY c.id DESC'
    clients_df = run_query(query, tuple(params), fetch=True)
    
    if not clients_df.empty:
        # Форматируем для отображения
        display_df = clients_df.copy()
        display_df['phone'] = display_df['phone'].apply(format_phone)
        display_df['vk_id'] = display_df['vk_id'].apply(format_vk)
        display_df['tg_id'] = display_df['tg_id'].apply(format_telegram)
        display_df['first_order_date'] = display_df['first_order_date'].apply(format_date_display)
        display_df.columns = ['ID', 'Имя', 'Пол', 'Телефон', 'VK', 'Telegram', 'Группа', 'Первая оплата']
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        st.info(f"Найдено: {len(clients_df)}")
        
        # Редактирование
        st.markdown("### ✏️ Редактирование клиента")
        client_options = [f"#{r['id']} - {r['name']}" for _, r in clients_df.iterrows()]
        selected = st.selectbox("Выберите клиента", [""] + client_options)
        
        if selected:
            sel_id = int(selected.split(" - ")[0].replace("#", ""))
            row = clients_df[clients_df['id'] == sel_id].iloc[0]
            
            with st.form("edit_client"):
                col1, col2 = st.columns(2)
                with col1:
                    e_name = st.text_input("Имя", value=row['name'])
                    e_sex = st.selectbox("Пол", ["М", "Ж"], index=0 if row['sex'] == "М" else 1)
                    e_phone = st.text_input("Телефон", value=row['phone'] or "")
                with col2:
                    e_vk = st.text_input("VK ID", value=row['vk_id'] or "")
                    e_tg = st.text_input("Telegram", value=row['tg_id'] or "")
                    e_group = st.selectbox("Группа", ["Без группы"] + groups_list,
                                           index=(groups_list.index(row['group_name']) + 1) if row['group_name'] in groups_list else 0)
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.form_submit_button("💾 Сохранить", use_container_width=True):
                        g_id = group_map.get(e_group) if e_group != "Без группы" else None
                        run_query('''UPDATE clients SET name=?, sex=?, phone=?, vk_id=?, tg_id=?, group_id=? 
                                     WHERE id=?''', (e_name, e_sex, e_phone, e_vk, e_tg, g_id, sel_id))
                        st.success("✅ Сохранено!")
                        st.rerun()
                with c2:
                    if st.form_submit_button("🗑️ Удалить", use_container_width=True, type="secondary"):
                        run_query("DELETE FROM clients WHERE id=?", (sel_id,))
                        st.success("🗑️ Удалено!")
                        st.rerun()
    else:
        st.info("Клиенты не найдены")

# ===========================================
# --- 2. ПРАЙС-ЛИСТ ---
# ===========================================
elif choice == "Прайс-лист Услуг":
    st.subheader("Справочник Услуг")
    
    with st.expander("➕ Добавить услугу"):
        with st.form("add_service"):
            s_name = st.text_input("Название услуги")
            s_price = st.text_input("Мин. прайс ₽", placeholder="10 000")
            s_desc = st.text_area("Описание")
            
            if st.form_submit_button("Добавить"):
                if s_name:
                    run_query("INSERT INTO services_catalog (name, min_price, description) VALUES (?,?,?)",
                              (s_name, parse_currency(s_price), s_desc))
                    st.success("✅ Услуга добавлена!")
                    st.rerun()
    
    services_df = run_query("SELECT * FROM services_catalog", fetch=True)
    
    if not services_df.empty:
        display_df = services_df.copy()
        display_df['min_price'] = display_df['min_price'].apply(lambda x: f"{format_currency(x)} ₽")
        display_df.columns = ['ID', 'Услуга', 'Мин. прайс', 'Описание']
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        st.markdown("### ✏️ Редактирование услуги")
        srv_options = [f"#{r['id']} - {r['name']}" for _, r in services_df.iterrows()]
        selected = st.selectbox("Выберите услугу", [""] + srv_options)
        
        if selected:
            sel_id = int(selected.split(" - ")[0].replace("#", ""))
            row = services_df[services_df['id'] == sel_id].iloc[0]
            
            with st.form("edit_service"):
                e_name = st.text_input("Название", value=row['name'])
                e_price = st.text_input("Мин. прайс ₽", value=format_currency(row['min_price']))
                