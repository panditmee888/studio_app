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
    if not phone_str or pd.isna(phone_str):
        return ""
    digits = ''.join(filter(str.isdigit, str(phone_str)))
    if digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits
    if len(digits) != 11 or not digits.startswith("7"):
        return phone_str
    return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"

def format_vk_link(vk_id) -> str:
    if not vk_id or pd.isna(vk_id):
        return ""
    vk_id = str(vk_id).strip()
    if vk_id.isdigit():
        return f"https://vk.com/id{vk_id}"
    return f"https://vk.com/{vk_id}"

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
        if isinstance(date_str, str) and '.' in date_str:
            return date_str
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
        if isinstance(date_str, str) and '.' in date_str:
            return datetime.strptime(date_str, "%d.%m.%Y").strftime("%Y-%m-%d")
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
        run_query(
            "UPDATE clients SET first_order_date = ? WHERE id = ?",
            (result['first_payment'].iloc[0], client_id)
        )

# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
# ВАЖНО: функция пересчёта суммы заказа должна быть объявлена ДО её использования!
def _update_order_total(order_id):
    """Пересчитывает total_amount в таблице orders"""
    total_df = run_query("SELECT COALESCE(SUM(amount),0) as t FROM order_items WHERE order_id=?", (order_id,), fetch=True)
    total = total_df.iloc[0]['t']
    run_query("UPDATE orders SET total_amount=? WHERE id=?", (total, order_id))
# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←

def init_db():
    conn = sqlite3.connect('studio.db')
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON;")
    c.execute('''CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, sex TEXT, phone TEXT, vk_id TEXT, tg_id TEXT,
                    group_id INTEGER, first_order_date DATE, FOREIGN KEY (group_id) REFERENCES groups(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS services_catalog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, min_price REAL, description TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, execution_date DATE,
                    status TEXT, total_amount REAL DEFAULT 0, FOREIGN KEY (client_id) REFERENCES clients(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER, service_name TEXT,
                    payment_date DATE, amount REAL, hours REAL,
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

# ======================= ИНТЕРФЕЙС =======================
st.set_page_config(page_title="Studio Admin", layout="wide")
init_db()

st.title("CRM Студии Звукозаписи")

menu = ["Клиенты и Группы", "Прайс-лист Услуг", "Заказы и услуги", "ОТЧЁТЫ"]
choice = st.sidebar.selectbox("Навигация", menu)

# ======================= 1. КЛИЕНТЫ И ГРУППЫ =======================
if choice == "Клиенты и Группы":
    # (твой код без изменений — он идеален)
    # ... (оставь полностью как у тебя был) ...
    # (я не копирую сюда, чтобы не удлинять, но он работает)

    # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
    # ВНИМАНИЕ: весь твой код раздела "Клиенты и Группы" оставляем как есть!
    # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←

# ======================= 2. ПРАЙС-ЛИСТ =======================
elif choice == "Прайс-лист Услуг":
    # (твой код тоже остаётся без изменений)
    pass  # оставь как был

# ======================= 3. ЗАКАЗЫ И УСЛУГИ =======================
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

        # --- Управление услугами ---
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

            # Добавление услуги
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
                        else:
                            amount_val = parse_currency(new_amount)
                            hours_val = float(new_hours.replace(",", ".")) if new_hours.strip() else 0.0

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

            # Редактирование / Удаление услуги
            elif service_mode in ["Редактировать", "Удалить"] and not current_items_df.empty:
                item_labels = [
                    f"{r.service_name} — {format_currency(r.amount)}₽ — {format_date_display(r.payment_date)}"
                    for r in current_items_df.itertuples()
                ]
                sel_label = st.selectbox("Выберите услугу", item_labels, key="sel_item")
                sel_item_id = current_items_df.iloc[item_labels.index(sel_label)]['id']

                row = current_items_df[current_items_df['id'] == sel_item_id].iloc[0]
                edit_df = pd.DataFrame([{
                    "service_name": row["service_name"],
                    "payment_date": pd.to_datetime(row["payment_date"]),
                    "amount": row["amount"],
                    "hours": float(row["hours"]) if pd.notna(row["hours"]) else 0.0
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
                    if st.button("Сохранить изменения услуги", use_container_width=True, type="primary"):
                        r = edited.iloc[0]
                        run_query("""
                            UPDATE order_items SET service_name=?, payment_date=?, amount=?, hours=?
                            WHERE id=?
                        """, (r.service_name, r.payment_date.date(), r.amount, r.hours, sel_item_id))
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

        # Основные кнопки по заказу
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
                st.success(f"**Итого: {format_currency(total)} ₽**")
            else:
                st.info("Услуги ещё не добавлены")
        else:
            st.info("Выберите или создайте заказ → состав появится здесь")

    if order_id:
        st.session_state.last_viewed_order_id = order_id

# ======================= 4. ОТЧЁТЫ =======================
elif choice == "ОТЧЁТЫ":
    st.header("Аналитические Отчёты")
    # ← твой оригинальный код отчётов полностью остаётся здесь →
    # (вставь сюда весь твой блок отчётов без изменений — он уже идеален)
    # Я просто оставлю заглушку, чтобы не удлинять сообщение:
    st.info("Твой блок отчётов работает как и раньше — вставь его сюда полностью")