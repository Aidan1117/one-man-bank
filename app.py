import sqlite3
from datetime import datetime
import streamlit as st

# --- Database init ---
def init_db():
    conn = sqlite3.connect("bank.db", check_same_thread=False)
    c = conn.cursor()
    # Create account balance table
    c.execute(
        """CREATE TABLE IF NOT EXISTS accounts 
                 (username TEXT PRIMARY KEY, balance REAL)"""
    )
    # Build Coupon table
    c.execute(
        """CREATE TABLE IF NOT EXISTS coupons 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT, title TEXT, value REAL, is_used INTEGER)"""
    )
    # Create history table
    c.execute(
        """CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, sender TEXT, receiver TEXT, type TEXT, content TEXT, amount REAL)"""
    )
    # Init default account (admin, albee)
    c.execute(
        "INSERT OR IGNORE INTO accounts (username, balance) VALUES ('admin', 0)"
    )
    c.execute(
        "INSERT OR IGNORE INTO accounts (username, balance) VALUES ('albee', 0)"
    )
    conn.commit()
    return conn


conn = init_db()
c = conn.cursor()

# --- Web page latouy setting ---
st.set_page_config(page_title="AA銀行", page_icon="💳", layout="centered")

# --- Login status management ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

# --- login page ---
if not st.session_state.logged_in:
    st.title("💳 AA專屬銀行登入")
    st.markdown("請輸入帳號密碼以存取您的資產與優惠券。")

    # Coding account n password (admin / albee)
    # Modify password here
    users = {"admin": "1117", "albee": "0417"}

    with st.form("login_form"):
        username_input = st.text_input("帳號 (admin / albee)")
        password_input = st.text_input("密碼", type="password")
        submit_btn = st.form_submit_button("登入")

        if submit_btn:
            if (
                username_input in users
                and users[username_input] == password_input
            ):
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

    # --- Search account balance ---
    c.execute("SELECT balance FROM accounts WHERE username='albee'")
    wife_balance = c.fetchone()[0]

    # ==================== Albee POV ====================
    if user == "albee":
        st.title("👑 Albee的專屬財庫")

        # 顯示餘額大卡片
        st.metric(label="目前可用寵妻基金餘額", value=f"$ {wife_balance:,.0f}")

        st.divider()

        # 1. Spending account balance
        st.subheader("💸 使用基金扣款")
        with st.form("spend_balance_form"):
            spend_amt = st.number_input(
                "欲使用的金額", min_value=1.0, max_value=float(wife_balance), step=1.0
            )
            spend_reason = st.text_input("用途說明 (例如: 買新衣服/下午茶)")
            spend_submit = st.form_submit_button("確認扣款")

            if spend_submit:
                if spend_amt > wife_balance:
                    st.error("餘額不足！")
                else:
                    new_balance = wife_balance - spend_amt
                    c.execute(
                        "UPDATE accounts SET balance = ? WHERE username='albee'",
                        (new_balance,),
                    )
                    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    c.execute(
                        "INSERT INTO history (time, sender, receiver, type, content, amount) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            time_str,
                            "albee",
                            "system",
                            "消費扣款",
                            spend_reason,
                            spend_amt,
                        ),
                    )
                    conn.commit()
                    st.success(f"成功扣款 ${spend_amt}！")
                    st.rerun()

        st.divider()

        # 2. Coupon section
        st.subheader("🎟️ 我的可用 Coupon")
        c.execute(
            "SELECT id, title, value FROM coupons WHERE owner='albee' AND is_used=0"
        )
        available_coupons = c.fetchall()

        if not available_coupons:
            st.info("目前沒有可用的 Coupon，快跟老公撒嬌索取吧！")
        else:
            for cp in available_coupons:
                cp_id, cp_title, cp_val = cp
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**🎁 {cp_title}** (面額/價值: ${cp_val})")
                with col2:
                    if st.button("使用", key=f"use_cp_{cp_id}"):
                        # Mark used coupon
                        c.execute(
                            "UPDATE coupons SET is_used = 1 WHERE id = ?",
                            (cp_id,),
                        )
                        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        c.execute(
                            "INSERT INTO history (time, sender, receiver, type, content, amount) VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                time_str,
                                "albee",
                                "system",
                                "使用Coupon",
                                cp_title,
                                cp_val,
                            ),
                        )
                        conn.commit()
                        st.success(f"已成功使用優惠券：{cp_title}！")
                        st.rerun()

        st.divider()

        # 3. Account activity history
        st.subheader("📜 帳戶與優惠券歷史紀錄")
        c.execute(
            "SELECT time, type, content, amount FROM history WHERE sender='albee' OR receiver='albee' ORDER BY id DESC"
        )
        history = c.fetchall()
        if history:
            history_data = []
            for h in history:
                history_data.append(
                    {
                        "時間": h[0],
                        "類型": h[1],
                        "項目/說明": h[2],
                        "金額/價值": h[3],
                    }
                )
            st.dataframe(history_data, use_container_width=True)
        else:
            st.write("尚無歷史紀錄。")

    # ==================== Admin POV ====================
    elif user == "admin":
        st.title("🛠️ 老公的管理後台")
        st.info(f"目前老婆帳戶餘額：$ {wife_balance:,.0f}")

        tab1, tab2, tab3 = st.tabs(
            ["💰 轉帳給老婆", "🎟️ 發放 Coupon", "📜 全局歷史紀錄"]
        )

        # Tab 1: Balance transfer
        with tab1:
            st.subheader("轉入額度至老婆帳戶")
            with st.form("transfer_form"):
                trans_amt = st.number_input(
                    "轉帳金額", min_value=1.0, step=100.0
                )
                trans_memo = st.text_input("備註 (例如: 本月零用錢/辛苦費)")
                trans_submit = st.form_submit_button("確認轉帳")

                if trans_submit:
                    new_balance = wife_balance + trans_amt
                    c.execute(
                        "UPDATE accounts SET balance = ? WHERE username='albee'",
                        (new_balance,),
                    )
                    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    c.execute(
                        "INSERT INTO history (time, sender, receiver, type, content, amount) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            time_str,
                            "admin",
                            "albee",
                            "轉帳入帳",
                            trans_memo,
                            trans_amt,
                        ),
                    )
                    conn.commit()
                    st.success(f"成功轉帳 ${trans_amt} 給老婆！")
                    st.rerun()

        # Tab 2: Issue coupon
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
                        c.execute(
                            "INSERT INTO coupons (owner, title, value, is_used) VALUES ('albee', ?, ?, 0)",
                            (cp_title, cp_val),
                        )
                        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        c.execute(
                            "INSERT INTO history (time, sender, receiver, type, content, amount) VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                time_str,
                                "admin",
                                "albee",
                                "發放Coupon",
                                cp_title,
                                cp_val,
                            ),
                        )
                        conn.commit()
                        st.success(f"成功發放 Coupon：{cp_title}！")
                        st.rerun()

        # Tab 3: Global activity history
        with tab3:
            st.subheader("所有進出與操作紀錄")
            c.execute(
                "SELECT time, sender, receiver, type, content, amount FROM history ORDER BY id DESC"
            )
            history = c.fetchall()
            if history:
                history_data = []
                for h in history:
                    history_data.append(
                        {
                            "時間": h[0],
                            "發送方": h[1],
                            "接收方": h[2],
                            "類型": h[3],
                            "內容": h[4],
                            "金額/價值": h[5],
                        }
                    )
                st.dataframe(history_data, use_container_width=True)
            else:
                st.write("尚無歷史紀錄。")
