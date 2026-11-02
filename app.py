from datetime import datetime
import streamlit as st

# --- 建立 Streamlit 內建雲端資料庫連線 ---
conn = st.connection("postgresql", type="sql")


# --- 初始化資料庫表格 ---
def init_db():
  # 建立帳戶餘額表
  conn.query(
      """
        CREATE TABLE IF NOT EXISTS accounts (
            username TEXT PRIMARY KEY, 
            balance REAL
        )
    """,
      ttl=0,
  )

  # 建立 Coupon 表
  conn.query(
      """
        CREATE TABLE IF NOT EXISTS coupons (
            id SERIAL PRIMARY KEY, 
            owner TEXT, 
            title TEXT, 
            value REAL, 
            is_used INTEGER
        )
    """,
      ttl=0,
  )

  # 建立歷史紀錄表
  conn.query(
      """
        CREATE TABLE IF NOT EXISTS history (
            id SERIAL PRIMARY KEY, 
            time TEXT, 
            sender TEXT, 
            receiver TEXT, 
            type TEXT, 
            content TEXT, 
            amount REAL
        )
    """,
      ttl=0,
  )

  # 初始化預設帳號 (admin, wife)，若已存在則略過
  conn.query(
      """
        INSERT INTO accounts (username, balance) 
        VALUES ('admin', 0) 
        ON CONFLICT (username) DO NOTHING
    """,
      ttl=0,
  )
  conn.query(
      """
        INSERT INTO accounts (username, balance) 
        VALUES ('wife', 0) 
        ON CONFLICT (username) DO NOTHING
    """,
      ttl=0,
  )


# 執行初始化
init_db()

# --- 網頁版面設定 ---
st.set_page_config(page_title="專屬寵妻銀行", page_icon="💳", layout="centered")

# --- 登入狀態管理 ---
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False
  st.session_state.username = ""

# --- 登入畫面 ---
if not st.session_state.logged_in:
  st.title("💳 專屬私人銀行登入")
  st.markdown("請輸入帳號密碼以存取您的資產與優惠券。")

  users = {"admin": "1234", "wife": "5678"}

  with st.form("login_form"):
    username_input = st.text_input("帳號 (admin / wife)")
    password_input = st.text_input("密碼", type="password")
    submit_btn = st.form_submit_button("登入")

    if submit_btn:
      if username_input in users and users[username_input] == password_input:
        st.session_state.logged_in = True
        st.session_state.username = username_input
        st.rerun()
      else:
        st.error("帳號或密碼錯誤！")

else:
  user = st.session_state.username
  st.sidebar.title(f"歡迎, {'老公 (Admin)' if user=='admin' else '老婆大人'}")

  if st.sidebar.button("登出"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

  # --- 查詢目前老婆餘額 ---
  df_balance = conn.query(
      "SELECT balance FROM accounts WHERE username='wife'", ttl=0
  )
  wife_balance = float(df_balance.iloc[0]["balance"]) if not df_balance.empty else 0.0

  # ==================== 老婆視角 ====================
  if user == "wife":
    st.title("👑 老婆的專屬財庫")

    st.metric(label="目前可用寵妻基金餘額", value=f"$ {wife_balance:,.0f}")
    st.divider()

    # 1. 使用餘額扣款區
    st.subheader("💸 使用基金扣款")
    with st.form("spend_balance_form"):
      spend_amt = st.number_input(
          "欲使用的金額",
          min_value=1.0,
          max_value=max(1.0, float(wife_balance)),
          step=1.0,
      )
      spend_reason = st.text_input("用途說明 (例如: 買新衣服/下午茶)")
      spend_submit = st.form_submit_button("確認扣款")

      if spend_submit:
        if spend_amt > wife_balance:
          st.error("餘額不足！")
        else:
          new_balance = wife_balance - spend_amt
          time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

          # 更新餘額與寫入歷史
          conn.query(
              "UPDATE accounts SET balance = :bal WHERE username='wife'",
              params={"bal": new_balance},
              ttl=0,
          )
          conn.query(
              """
                    INSERT INTO history (time, sender, receiver, type, content, amount) 
                    VALUES (:time, :sender, :receiver, :type, :content, :amount)
                """,
              params={
                  "time": time_str,
                  "sender": "wife",
                  "receiver": "system",
                  "type": "消費扣款",
                  "content": spend_reason,
                  "amount": spend_amt,
              },
              ttl=0,
          )

          st.success(f"成功扣款 ${spend_amt}！")
          st.rerun()

    st.divider()

    # 2. Coupon 專區
    st.subheader("🎟️ 我的可用 Coupon")
    df_coupons = conn.query(
        "SELECT id, title, value FROM coupons WHERE owner='wife' AND is_used=0",
        ttl=0,
    )

    if df_coupons.empty:
      st.info("目前沒有可用的 Coupon，快跟老公撒嬌索取吧！")
    else:
      for _, cp in df_coupons.iterrows():
        cp_id, cp_title, cp_val = cp["id"], cp["title"], cp["value"]
        col1, col2 = st.columns([3, 1])
        with col1:
          st.markdown(f"**🎁 {cp_title}** (面額/價值: ${cp_val})")
        with col2:
          if st.button("使用", key=f"use_cp_{cp_id}"):
            time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.query(
                "UPDATE coupons SET is_used = 1 WHERE id = :id",
                params={"id": int(cp_id)},
                ttl=0,
            )
            conn.query(
                """
                        INSERT INTO history (time, sender, receiver, type, content, amount) 
                        VALUES (:time, :sender, :receiver, :type, :content, :amount)
                    """,
                params={
                    "time": time_str,
                    "sender": "wife",
                    "receiver": "system",
                    "type": "使用Coupon",
                    "content": cp_title,
                    "amount": cp_val,
                },
                ttl=0,
            )
            st.success(f"已成功使用優惠券：{cp_title}！")
            st.rerun()

    st.divider()

    # 3. 歷史紀錄
    st.subheader("📜 帳戶與優惠券歷史紀錄")
    df_history = conn.query(
        """
            SELECT time, type, content, amount 
            FROM history 
            WHERE sender='wife' OR receiver='wife' 
            ORDER BY id DESC
        """,
        ttl=0,
    )
    if not df_history.empty:
      history_data = []
      for _, h in df_history.iterrows():
        history_data.append({
            "時間": h["time"],
            "類型": h["type"],
            "項目/說明": h["content"],
            "金額/價值": h["amount"],
        })
      st.dataframe(history_data, use_container_width=True)
    else:
      st.write("尚無歷史紀錄。")

  # ==================== 老公 (Admin) 視角 ====================
  elif user == "admin":
    st.title("🛠️ 老公的管理後台")
    st.info(f"目前老婆帳戶餘額：$ {wife_balance:,.0f}")

    tab1, tab2, tab3 = st.tabs(
        ["💰 轉帳給老婆", "🎟️ 發放 Coupon", "📜 全局歷史紀錄"]
    )

    # Tab 1: 轉帳
    with tab1:
      st.subheader("轉入額度至老婆帳戶")
      with st.form("transfer_form"):
        trans_amt = st.number_input("轉帳金額", min_value=1.0, step=100.0)
        trans_memo = st.text_input("備註 (例如: 本月零用錢/辛苦費)")
        trans_submit = st.form_submit_button("確認轉帳")

        if trans_submit:
          new_balance = wife_balance + trans_amt
          time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

          conn.query(
              "UPDATE accounts SET balance = :bal WHERE username='wife'",
              params={"bal": new_balance},
              ttl=0,
          )
          conn.query(
              """
                    INSERT INTO history (time, sender, receiver, type, content, amount) 
                    VALUES (:time, :sender, :receiver, :type, :content, :amount)
                """,
              params={
                  "time": time_str,
                  "sender": "admin",
                  "receiver": "wife",
                  "type": "轉帳入帳",
                  "content": trans_memo,
                  "amount": trans_amt,
              },
              ttl=0,
          )

          st.success(f"成功轉帳 ${trans_amt} 給老婆！")
          st.rerun()

    # Tab 2: 發放 Coupon
    with tab2:
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
            conn.query(
                """
                        INSERT INTO coupons (owner, title, value, is_used) 
                        VALUES ('wife', :title, :val, 0)
                    """,
                params={"title": cp_title, "val": cp_val},
                ttl=0,
            )
            conn.query(
                """
                        INSERT INTO history (time, sender, receiver, type, content, amount) 
                        VALUES (:time, :sender, :receiver, :type, :content, :amount)
                    """,
                params={
                    "time": time_str,
                    "sender": "admin",
                    "receiver": "wife",
                    "type": "發放Coupon",
                    "content": cp_title,
                    "amount": cp_val,
                },
                ttl=0,
            )
            st.success(f"成功發放 Coupon：{cp_title}！")
            st.rerun()

    # Tab 3: 全局歷史紀錄
    with tab3:
      st.subheader("所有進出與操作紀錄")
      df_all_history = conn.query(
          """
            SELECT time, sender, receiver, type, content, amount 
            FROM history 
            ORDER BY id DESC
        """,
          ttl=0,
      )
      if not df_all_history.empty:
        history_data = []
        for _, h in df_all_history.iterrows():
          history_data.append({
              "時間": h["time"],
              "發送方": h["sender"],
              "接收方": h["receiver"],
              "類型": h["type"],
              "內容": h["content"],
              "金額/價值": h["amount"],
          })
        st.dataframe(history_data, use_container_width=True)
      else:
        st.write("尚無歷史紀錄。")
