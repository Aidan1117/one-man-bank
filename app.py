from datetime import datetime, timedelta
import psycopg2
import requests
import streamlit as st

# --- 讀取 Streamlit Secrets ---
db_url = st.secrets["database"]["url"]
DISCORD_WEBHOOK_URL = st.secrets.get("discord", {}).get("webhook_url", "")


# --- Discord 推播通知函式 ---
def send_discord_notification(message):
  if not DISCORD_WEBHOOK_URL:
    return
  payload = {"content": message}
  try:
    requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
  except Exception as e:
    print(f"Discord 推播失敗: {e}")


# --- 通用資料庫查詢與更新函式 ---
def run_query(query, params=None, fetch=False):
  conn = psycopg2.connect(db_url)
  cursor = conn.cursor()
  cursor.execute(query, params)
  result = None
  if fetch:
    result = cursor.fetchall()
  conn.commit()
  cursor.close()
  conn.close()
  return result


# --- 初始化資料庫表格 ---
def init_db():
  run_query("""
        CREATE TABLE IF NOT EXISTS accounts (
            username TEXT PRIMARY KEY, 
            balance REAL
        )
    """)
  run_query("""
        CREATE TABLE IF NOT EXISTS coupons (
            id SERIAL PRIMARY KEY, 
            owner TEXT, 
            title TEXT, 
            value REAL, 
            is_used INTEGER
        )
    """)
  run_query("""
        CREATE TABLE IF NOT EXISTS history (
            id SERIAL PRIMARY KEY, 
            time TEXT, 
            sender TEXT, 
            receiver TEXT, 
            type TEXT, 
            content TEXT, 
            amount REAL
        )
    """)
  run_query("""
        CREATE TABLE IF NOT EXISTS signins (
            username TEXT,
            year_month TEXT,
            PRIMARY KEY (username, year_month)
        )
    """)
  run_query("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            username TEXT,
            year_month TEXT,
            content TEXT,
            reward_status TEXT DEFAULT '未審核'
        )
    """)

  run_query("""
        INSERT INTO accounts (username, balance) 
        VALUES ('admin', 0) ON CONFLICT (username) DO NOTHING
    """)
  run_query("""
        INSERT INTO accounts (username, balance) 
        VALUES ('albee', 0) ON CONFLICT (username) DO NOTHING
    """)


init_db()


# --- 檢查 Supabase 防睡眠機制 (超過 6 天無活動則發送 Discord 提醒) ---
def check_supabase_sleep_risk():
  try:
    # 取得歷史紀錄中最新的一筆時間
    res = run_query(
        "SELECT time FROM history ORDER BY id DESC LIMIT 1", fetch=True
    )
    if res and res[0][0]:
      last_time_str = res[0][0]
      last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
      now = datetime.now()

      # 如果超過 6 天沒有任何操作紀錄
      if now - last_time >= timedelta(days=6):
        # 檢查今天是否已經發送過防睡眠提醒（避免每次重新整理網頁都轟炸 Discord）
        today_check_key = f"sleep_warn_{now.strftime('%Y-%m-%d')}"
        if today_check_key not in st.session_state:
          send_discord_notification(
              "⚠️ **[Supabase 防睡眠系統提醒]**\n"
              f"距離上次資料庫活動已超過 6 天（上次時間：`{last_time_str}`）。\n"
              "請盡快登入網站進行互動或點擊一下，防止資料庫進入休眠狀態！✨"
          )
          st.session_state[today_check_key] = True
  except Exception as e:
    print(f"防睡眠檢查失敗: {e}")


# 執行防睡眠檢查
check_supabase_sleep_risk()

# --- 網頁版面設定 ---
st.set_page_config(page_title="AA專屬銀行", page_icon="💳", layout="centered")

# --- 自定義 Hello Kitty & Daniel 背景樣式 ---
st.markdown(
    """
    <style>
    .stApp {
        background-image: url("https://i.pinimg.com/236x/f9/5f/8c/f95f8c0080dcef40aa4d8c97b7fab9b5.jpg");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }
    .block-container {
        background-color: rgba(255, 255, 255, 0.88);
        padding: 2.5rem;
        border-radius: 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        margin-top: 2rem;
        margin-bottom: 2rem;
    }
    [data-testid="stSidebar"] {
        background-color: rgba(255, 240, 245, 0.92);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- 登入狀態管理 ---
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False
  st.session_state.username = ""

# --- 登入畫面 ---
if not st.session_state.logged_in:
  st.title("💳 AA專屬銀行登入")
  st.markdown("請輸入帳號密碼以存取您的資產與優惠券。")

  users = {"admin": "1117", "albee": "0417"}

  with st.form("login_form"):
    username_input = st.text_input("帳號 (admin / albee)")
    password_input = st.text_input("密碼", type="password")
    submit_btn = st.form_submit_button("登入")

    if submit_btn:
      if username_input in users and users[username_input] == password_input:
        st.session_state.logged_in = True
        st.session_state.username = username_input

        # 【新功能 1】Albee 登入時發送 Discord 通知
        if username_input == "albee":
          send_discord_notification(
              "👑 **[登入通知]**\n老婆大人 Albee 剛剛登入了專屬寵妻銀行！✨"
          )

        st.rerun()
      else:
        st.error("帳號或密碼錯誤！")

else:
  user = st.session_state.username
  st.sidebar.title(f"歡迎, {'老公 (Admin)' if user=='admin' else '老婆大人 (Albee)'}")

  if st.sidebar.button("登出"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

  res_balance = run_query(
      "SELECT balance FROM accounts WHERE username='albee'", fetch=True
  )
  albee_balance = float(res_balance[0][0]) if res_balance else 0.0

  # ==================== 老婆 (Albee) 視角 ====================
  if user == "albee":
    st.title("👑 老婆的專屬財庫")
    st.metric(label="目前可用寵妻基金餘額", value=f"$ {albee_balance:,.0f}")
    st.divider()

    # 1. 📅 每月專屬簽到
    st.subheader("📅 每月專屬簽到")
    current_ym = datetime.now().strftime("%Y-%m")
    current_month_str = datetime.now().strftime("%m月")

    checked_in = run_query(
        "SELECT 1 FROM signins WHERE username='albee' AND year_month=%s",
        (current_ym,),
        fetch=True,
    )

    if checked_in:
      st.info(
          f"✨ 您已經完成 {current_month_str} 的簽到囉！已領取 1500 寵妻基金。"
      )
    else:
      if st.button(f"點擊進行 {current_month_str} 簽到 (領取 $1500)"):
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_balance = albee_balance + 1500

        run_query(
            "INSERT INTO signins (username, year_month) VALUES ('albee', %s)",
            (current_ym,),
        )
        run_query(
            "UPDATE accounts SET balance = %s WHERE username='albee'",
            (new_balance,),
        )
        run_query(
            """INSERT INTO history (time, sender, receiver, type, content, amount) 
                     VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                time_str,
                "system",
                "albee",
                "簽到獎勵",
                f"{current_month_str}簽到基金",
                1500,
            ),
        )

        send_discord_notification(
            f"🔔 **[寵妻銀行通知]**\n老婆 Albee 已完成 **{current_month_str}**"
            " 簽到！系統已自動撥款 **$1,500** 寵妻基金！"
        )

        st.success(f"🎉 簽到成功！已自動幫您增加 $1,500 寵妻基金！")
        st.rerun()

    st.divider()

    # 2. 💌 每月心願留言板
    st.subheader("💌 每月心願留言板")
    existing_msg = run_query(
        """SELECT id, content, reward_status 
               FROM messages WHERE username='albee' AND year_month=%s""",
        (current_ym,),
        fetch=True,
    )

    with st.form("monthly_message_form"):
      msg_input = st.text_area(
          "本月心願與留言",
          placeholder=(
              "例如: 這陣子辛苦了想去吃高級燒肉 / 想要一個小廢物包"
          ),
      )
      msg_submit = st.form_submit_button("送出/更新本月心願")

      if msg_submit:
        if not msg_input.strip():
          st.error("請輸入留言內容！")
        else:
          if existing_msg:
            run_query(
                "UPDATE messages SET content=%s WHERE id=%s",
                (msg_input, existing_msg[0][0]),
            )
          else:
            run_query(
                """INSERT INTO messages (username, year_month, content, reward_status) 
                         VALUES ('albee', %s, %s, '未審核')""",
                (current_ym, msg_input),
            )

          send_discord_notification(
              "💌 **[寵妻銀行心願通知]**\n老婆 Albee 提出了新的心願留言！\n> "
              f"**心願內容**：{msg_input}\n\n快到後台審核發放獎勵吧！✨"
          )

          st.success("💌 本月心願留言已成功送達給老公！")
          st.rerun()

    if existing_msg:
      st.info(f"目前狀態：本月心願已送出（狀態：{existing_msg[0][2]}）")

    st.divider()

    # 3. 💸 使用基金扣款 (含詳細金額與名目通知)
    st.subheader("💸 使用基金扣款")
    with st.form("spend_balance_form"):
      spend_amt = st.number_input(
          "欲使用的金額",
          min_value=1.0,
          max_value=max(1.0, float(albee_balance)),
          step=1.0,
      )
      spend_reason = st.text_input("用途說明 (例如: 買新衣服/下午茶)")
      spend_submit = st.form_submit_button("確認扣款")

      if spend_submit:
        if spend_amt > albee_balance:
          st.error("餘額不足！")
        else:
          new_balance = albee_balance - spend_amt
          time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

          run_query(
              "UPDATE accounts SET balance = %s WHERE username='albee'",
              (new_balance,),
          )
          run_query(
              """INSERT INTO history (time, sender, receiver, type, content, amount) 
                       VALUES (%s, %s, %s, %s, %s, %s)""",
              (time_str, "albee", "system", "消費扣款", spend_reason, spend_amt),
          )

          # 【新功能 2】基金扣款詳細通知
          send_discord_notification(
              "💸 **[寵妻基金扣款通知]**\n老婆 Albee 剛剛使用了基金！\n"
              f"> 💳 **扣款金額**：`$ {spend_amt:,.0f}`\n"
              f"> 📝 **用途說明**：{spend_reason}\n"
              f"> 💰 **剩餘餘額**：`$ {new_balance:,.0f}`"
          )

          st.success(f"成功扣款 ${spend_amt}！")
          st.rerun()

    st.divider()

    # 4. 🎟️ Coupon 專區 (含 Coupon 名稱與詳細內容通知)
    st.subheader("🎟️ 我的可用 Coupon")
    available_coupons = run_query(
        "SELECT id, title, value FROM coupons WHERE owner='albee' AND is_used=0",
        fetch=True,
    )

    if not available_coupons:
      st.info("目前沒有可用的 Coupon，快跟老公撒嬌索取吧！")
    else:
      for cp in available_coupons:
        cp_id, cp_title, cp_val = cp[0], cp[1], cp[2]
        col1, col2 = st.columns([3, 1])
        with col1:
          st.markdown(f"**🎁 {cp_title}** (價值: ${cp_val})")
        with col2:
          if st.button("使用", key=f"use_cp_{cp_id}"):
            time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            run_query(
                "UPDATE coupons SET is_used = 1 WHERE id = %s", (int(cp_id),)
            )
            run_query(
                """INSERT INTO history (time, sender, receiver, type, content, amount) 
                         VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    time_str,
                    "albee",
                    "system",
                    "使用Coupon",
                    cp_title,
                    cp_val,
                ),
            )

            # 【新功能 3】Coupon 使用詳細通知
            send_discord_notification(
                "🎟️ **[Coupon 核銷通知]**\n老婆 Albee 剛剛使用了優惠券！\n"
                f"> 🎁 **優惠券名稱**：{cp_title}\n"
                f"> 💎 **權益價值估算**：`$ {cp_val:,.0f}`"
            )

            st.success(f"已成功使用優惠券：{cp_title}！")
            st.rerun()

    st.divider()

    # 5. 歷史紀錄
    st.subheader("📜 帳戶歷史紀錄")
    history = run_query(
        """SELECT time, type, content, amount FROM history 
               WHERE sender='albee' OR receiver='albee' ORDER BY id DESC""",
        fetch=True,
    )
    if history:
      history_data = [
          {
              "時間": h[0],
              "類型": h[1],
              "項目/說明": h[2],
              "金額/價值": h[3],
          }
          for h in history
      ]
      st.dataframe(history_data, use_container_width=True)

  # ==================== 老公 (Admin) 視角 ====================
  elif user == "admin":
    st.title("🛠️ 老公的管理後台")
    st.info(f"目前 Albee 帳戶餘額：$ {albee_balance:,.0f}")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["💌 心願留言審核", "💰 轉帳給 Albee", "🎟️ 發放 Coupon", "📜 全局歷史紀錄"]
    )

    with tab1:
      st.subheader("老婆的心願留言與獎勵發放")
      all_msgs = run_query(
          """SELECT id, year_month, content, reward_status 
                 FROM messages WHERE username='albee' ORDER BY id DESC""",
          fetch=True,
      )

      if not all_msgs:
        st.info("目前尚無老婆的心願留言。")
      else:
        for m in all_msgs:
          m_id, m_ym, m_content, m_status = m[0], m[1], m[2], m[3]
          with st.container(border=True):
            st.markdown(f"**📅 月份：{m_ym}** | 狀態：`{m_status}`")
            st.markdown(f"💬 **心願內容**：{m_content}")

            with st.form(f"reward_form_{m_id}"):
              reward_amt = st.number_input(
                  "分配獎勵金額 ($)", min_value=1.0, step=100.0, key=f"amt_{m_id}"
              )
              reward_submit = st.form_submit_button("確認發放獎勵")

              if reward_submit:
                time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                new_balance = albee_balance + reward_amt

                run_query(
                    "UPDATE accounts SET balance = %s WHERE username='albee'",
                    (new_balance,),
                )
                run_query(
                    "UPDATE messages SET reward_status='已發放獎勵' WHERE id=%s",
                    (m_id,),
                )
                month_label = m_ym.split("-")[1] + "月"
                run_query(
                    """INSERT INTO history (time, sender, receiver, type, content, amount) 
                             VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        time_str,
                        "admin",
                        "albee",
                        "留言獎勵",
                        f"{month_label}留言獎勵",
                        reward_amt,
                    ),
                )

                st.success(f"成功發放 ${reward_amt} 給 Albee！")
                st.rerun()

    with tab2:
      st.subheader("轉入額度至 Albee 帳戶")
      with st.form("transfer_form"):
        trans_amt = st.number_input("轉帳金額", min_value=1.0, step=100.0)
        trans_memo = st.text_input("備註 (例如: 本月零用錢/辛苦費)")
        trans_submit = st.form_submit_button("確認轉帳")

        if trans_submit:
          new_balance = albee_balance + trans_amt
          time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

          run_query(
              "UPDATE accounts SET balance = %s WHERE username='albee'",
              (new_balance,),
          )
          run_query(
              """INSERT INTO history (time, sender, receiver, type, content, amount) 
                       VALUES (%s, %s, %s, %s, %s, %s)""",
              (time_str, "admin", "albee", "轉帳入帳", trans_memo, trans_amt),
          )

          st.success(f"成功轉帳 ${trans_amt} 給 Albee！")
          st.rerun()

    with tab3:
      st.subheader("手動產生並發放 Coupon")
      with st.form("coupon_form"):
        cp_title = st.text_input(
            "Coupon 名稱 (例如: 免費按摩一次 / 週末任選大餐)"
        )
        cp_val = st.number_input("權益價值估算 ($)", min_value=0.0, step=50.0)
        cp_submit = st.form_submit_button("發放 Coupon")

        if cp_submit:
          if cp_title.strip() == "":
            st.error("請輸入 Coupon 名稱！")
          else:
            time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            run_query(
                """INSERT INTO coupons (owner, title, value, is_used) 
                         VALUES ('albee', %s, %s, 0)""",
                (cp_title, cp_val),
            )
            run_query(
                """INSERT INTO history (time, sender, receiver, type, content, amount) 
                         VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    time_str,
                    "admin",
                    "albee",
                    "發放Coupon",
                    cp_title,
                    cp_val,
                ),
            )
            st.success(f"成功發放 Coupon：{cp_title}！")
            st.rerun()

    with tab4:
      st.subheader("所有進出與操作紀錄")
      all_history = run_query(
          """SELECT time, sender, receiver, type, content, amount 
                 FROM history ORDER BY id DESC""",
          fetch=True,
      )
      if all_history:
        history_data = [
            {
                "時間": h[0],
                "發送方": h[1],
                "接收方": h[2],
                "類型": h[3],
                "內容": h[4],
                "金額/價值": h[5],
            }
            for h in all_history
        ]
        st.dataframe(history_data, use_container_width=True)
