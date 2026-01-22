# --- 1. КЛИЕНТЫ И ГРУППЫ ---
if choice == "Клиенты и Группы":
    st.subheader("Клиенты")

    # Получаем список групп
    groups_df = run_query("SELECT id, name FROM groups", fetch=True)
    group_map = dict(zip(groups_df['name'], groups_df['id'])) if not groups_df.empty else {}
    groups_list = list(group_map.keys())

    # Добавление клиента
    with st.expander("➕ Добавить нового клиента"):
        with st.form("add_client"):
            c_name = st.text_input("Имя *", placeholder="Иванов Иван")
            c_sex = st.selectbox("Пол", ["М", "Ж"])
            c_phone_raw = st.text_input("Телефон", placeholder="+7 999 123-45-67")

            c_vk_raw = st.text_input("VK ID", placeholder="id123456 или username")
            c_tg_raw = st.text_input("Telegram", placeholder="@username")

            c_group = st.selectbox("Группа", ["Без группы"] + groups_list)

            if st.form_submit_button("Сохранить клиента"):
                if c_name.strip():
                    # Очистка / нормализация
                    phone = c_phone_raw.strip()
                    vk = c_vk_raw.strip().replace("https://", "").replace("http://", "").replace("vk.com/", "")
                    tg = c_tg_raw.strip().replace("@", "").replace("t.me/", "").replace("https://", "")

                    g_id = group_map.get(c_group) if c_group != "Без группы" else None

                    run_query('''
                        INSERT INTO clients (name, sex, phone, vk_id, tg_id, group_id)
                        VALUES (?,?,?,?,?,?)
                    ''', (c_name, c_sex, phone, vk, tg, g_id))

                    st.success("✅ Клиент добавлен")
                    st.rerun()
                else:
                    st.error("Введите имя клиента")

    # Отображение таблицы клиентов
    clients = run_query('''
        SELECT c.id, c.name, c.sex, c.phone, c.vk_id, c.tg_id, COALESCE(g.name, 'Без группы') as group_name, c.first_order_date
        FROM clients c
        LEFT JOIN groups g ON c.group_id = g.id
        ORDER BY c.id DESC
    ''', fetch=True)

    if not clients.empty:
        display_df = clients.copy()

        # Форматирование даты
        display_df['first_order_date'] = display_df['first_order_date'].apply(format_date_display)

        # Форматированный телефон как ссылка tel:...
        display_df['phone'] = display_df['phone'].apply(
            lambda x: f"[{format_phone(x)}](tel:+{''.join(filter(str.isdigit, x))})" if x else ""
        )

        # VK — ссылка
        display_df['vk_id'] = display_df['vk_id'].apply(
            lambda x: f"[vk.com/{x}](https://vk.com/{x})" if x else ""
        )

        # Telegram — ссылка
        display_df['tg_id'] = display_df['tg_id'].apply(
            lambda x: f"[t.me/{x}](https://t.me/{x})" if x else ""
        )

        # Переименовываем для таблицы
        display_df.columns = ['ID', 'Имя', 'Пол', 'Телефон', 'VK', 'Telegram', 'Группа', 'Первая оплата']

        st.dataframe(display_df, use_container_width=True, hide_index=True)

    else:
        st.info("Клиенты пока не добавлены")