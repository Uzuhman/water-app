import streamlit as st
import pandas as pd
from datetime import date, datetime
import io
import os
import glob
import gspread
from google.oauth2.service_account import Credentials

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="COR Mission House Water Sales Record",
    page_icon="💧",
    layout="wide"
)

# ==============================================================================
# SPREADSHEET URL
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1o9IvmiD0rmdImaDHwk4k7zyyq2nZ-XDide8hPimpKQM/edit?gid=0#gid=0"
# Note: Ensure your actual Google Sheet URL is preserved above!
# ==============================================================================

ADMIN_PIN = "1234"

# --- CONNECT TO GOOGLE SHEETS ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def find_local_key():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for name in ["google_key.json", "google_key.json.json", "google_key"]:
        path = os.path.join(current_dir, name)
        if os.path.exists(path):
            return path
    json_files = glob.glob(os.path.join(current_dir, "*.json"))
    if json_files:
        return json_files[0]
    return None

@st.cache_resource
def get_sheets():
    key_path = find_local_key()
    if key_path:
        gc = gspread.service_account(filename=key_path)
    else:
        try:
            if "gcp_service_account" in st.secrets:
                creds = Credentials.from_service_account_info(
                    st.secrets["gcp_service_account"],
                    scopes=SCOPES
                )
                gc = gspread.authorize(creds)
            else:
                st.error("⚠️ Credentials missing in cloud secrets.")
                st.stop()
        except Exception:
            st.error("⚠️ Could not load cloud credentials.")
            st.stop()

    try:
        sh = gc.open_by_url(SPREADSHEET_URL)
        return sh.worksheet("Sales"), sh.worksheet("Expenses")
    except Exception as e:
        st.error(f"⚠️ Could not open Google Sheet. Check link and sharing permissions.")
        st.stop()

sales_sheet, expenses_sheet = get_sheets()

# --- HELPER FUNCTIONS FOR GOOGLE SHEETS ---
def get_sales():
    records = sales_sheet.get_all_records()
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=['id', 'date', 'attendant', 'cash', 'transfer', 'total'])
    df['cash'] = pd.to_numeric(df['cash'], errors='coerce').fillna(0.0)
    df['transfer'] = pd.to_numeric(df['transfer'], errors='coerce').fillna(0.0)
    df['total'] = pd.to_numeric(df['total'], errors='coerce').fillna(0.0)
    return df

def get_expenses():
    records = expenses_sheet.get_all_records()
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=['id', 'date', 'category', 'description', 'amount'])
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
    return df

def add_sale(sale_date, attendant, cash, transfer):
    df = get_sales()
    next_id = int(df['id'].max() + 1) if not df.empty and pd.notnull(df['id'].max()) else 1
    total = cash + transfer
    sales_sheet.append_row([next_id, str(sale_date), attendant.strip(), cash, transfer, total])

def update_sale(sale_id, sale_date, attendant, cash, transfer):
    cell = sales_sheet.find(str(sale_id), in_column=1)
    if cell:
        row = cell.row
        total = cash + transfer
        sales_sheet.update(f"B{row}:F{row}", [[str(sale_date), attendant.strip(), cash, transfer, total]])

def delete_sale(sale_id):
    cell = sales_sheet.find(str(sale_id), in_column=1)
    if cell:
        sales_sheet.delete_rows(cell.row)

def add_expense(exp_date, category, description, amount):
    df = get_expenses()
    next_id = int(df['id'].max() + 1) if not df.empty and pd.notnull(df['id'].max()) else 1
    expenses_sheet.append_row([next_id, str(exp_date), category, description.strip(), amount])

def update_expense(exp_id, exp_date, category, description, amount):
    cell = expenses_sheet.find(str(exp_id), in_column=1)
    if cell:
        row = cell.row
        expenses_sheet.update(f"B{row}:E{row}", [[str(exp_date), category, description.strip(), amount]])

def delete_expense(exp_id):
    cell = expenses_sheet.find(str(exp_id), in_column=1)
    if cell:
        expenses_sheet.delete_rows(cell.row)

# --- SESSION STATES ---
if "show_balance" not in st.session_state:
    st.session_state.show_balance = False
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False
if "pending_sale" not in st.session_state:
    st.session_state.pending_sale = None
if "pending_expense" not in st.session_state:
    st.session_state.pending_expense = None

# --- SIDEBAR BRANDING & NAVIGATION ---
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", width=140)

st.sidebar.title("COR Mission House")
st.sidebar.caption("Water Sales Management")

menu = st.sidebar.radio(
    "Navigation:",
    ["📊 Dashboard", "💰 Record Sale", "💸 Record Expense", "✏️ Edit / Correct Records", "📑 Comprehensive Report & Print"]
)

# ==========================================
# PAGE 1: CLEAN DASHBOARD
# ==========================================
if menu == "📊 Dashboard":
    sales_df = get_sales()
    expenses_df = get_expenses()

    total_revenue_all = sales_df['total'].sum() if not sales_df.empty else 0.0
    total_expenses_all = expenses_df['amount'].sum() if not expenses_df.empty else 0.0
    net_available = total_revenue_all - total_expenses_all

    # Header with Logo & Privacy Balance
    head_col1, head_col2 = st.columns([3, 1])
    with head_col1:
        if os.path.exists("logo.png"):
            c_logo, c_title = st.columns([1, 6])
            with c_logo:
                st.image("logo.png", width=75)
            with c_title:
                st.subheader("COR Mission House Water Sales Record")
                st.caption("Live Operations & Revenue Overview")
        else:
            st.title("COR Mission House Water Sales Record")

    with head_col2:
        st.markdown("**💰 Available Balance (Remaining):**")
        if st.session_state.show_balance:
            st.markdown(f"### ₦{net_available:,.2f}")
            if st.button("🙈 Hide Balance"):
                st.session_state.show_balance = False
                st.rerun()
        else:
            st.markdown("### ₦ ••••••••••")
            if st.button("👁️ Show Balance"):
                st.session_state.show_balance = True
                st.rerun()

    st.divider()

    # Tables
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("Recent Sales Breakdown")
        if not sales_df.empty:
            st.dataframe(sales_df[['id', 'date', 'attendant', 'cash', 'transfer', 'total']].tail(15), use_container_width=True)
        else:
            st.info("No sales records yet.")
    with col_r:
        st.subheader("Recent Expenses Breakdown")
        if not expenses_df.empty:
            st.dataframe(expenses_df[['id', 'date', 'category', 'description', 'amount']].tail(15), use_container_width=True)
        else:
            st.info("No expense records yet.")

# ==========================================
# PAGE 2: RECORD SALE (TWO-STEP VERIFICATION)
# ==========================================
elif menu == "💰 Record Sale":
    st.header("💰 Record Daily Water Sale")

    # If already verified & submitted
    if st.session_state.pending_sale is not None:
        ps = st.session_state.pending_sale
        st.warning("⚠️ **Please verify and confirm this sale before it is saved to Cloud:**")
        st.markdown(f"""
        - **Date:** {ps['date']}
        - **Attendant:** **{ps['attendant']}**
        - **Cash Amount:** ₦{ps['cash']:,.2f}
        - **Transfer Amount:** ₦{ps['transfer']:,.2f}
        - **TOTAL REVENUE:** **₦{ps['total']:,.2f}**
        """)
        c_conf, c_canc = st.columns(2)
        if c_conf.button("✅ Confirm & Save to Cloud", use_container_width=True):
            with st.spinner("Saving to Google Sheets..."):
                add_sale(ps['date'], ps['attendant'], ps['cash'], ps['transfer'])
            st.success(f"✅ Confirmed! Sale of ₦{ps['total']:,.2f} saved successfully.")
            st.session_state.pending_sale = None
            st.rerun()

        if c_canc.button("❌ Edit / Cancel", use_container_width=True):
            st.session_state.pending_sale = None
            st.rerun()
    else:
        with st.form("sales_form"):
            col1, col2 = st.columns(2)
            with col1:
                sale_date = st.date_input("Date of Sale", value=date.today())
                attendant = st.text_input("Attendant Name")
            with col2:
                cash = st.number_input("Cash Amount (₦)", min_value=0.0, step=100.0, format="%.2f")
                transfer = st.number_input("Transfer Amount (₦)", min_value=0.0, step=100.0, format="%.2f")

            total_prev = cash + transfer
            st.info(f"**Total Sale Preview: ₦{total_prev:,.2f}**")

            submit_sale = st.form_submit_button("💾 Save to Cloud")
            if submit_sale:
                if not attendant:
                    st.error("Please enter the attendant's name.")
                elif total_prev <= 0:
                    st.error("Sale amount cannot be zero.")
                else:
                    # Put into verification state
                    st.session_state.pending_sale = {
                        "date": sale_date,
                        "attendant": attendant,
                        "cash": cash,
                        "transfer": transfer,
                        "total": total_prev
                    }
                    st.rerun()

# ==========================================
# PAGE 3: RECORD EXPENSE (TWO-STEP VERIFICATION)
# ==========================================
elif menu == "💸 Record Expense":
    st.header("💸 Record Daily Expense")

    if st.session_state.pending_expense is not None:
        pe = st.session_state.pending_expense
        st.warning("⚠️ **Please verify and confirm this expense before it is saved to Cloud:**")
        st.markdown(f"""
        - **Date:** {pe['date']}
        - **Category:** **{pe['category']}**
        - **Description:** {pe['description'] or 'N/A'}
        - **TOTAL AMOUNT SPENT:** **₦{pe['amount']:,.2f}**
        """)
        c_conf, c_canc = st.columns(2)
        if c_conf.button("✅ Confirm & Save to Cloud", use_container_width=True):
            with st.spinner("Saving to Google Sheets..."):
                add_expense(pe['date'], pe['category'], pe['description'], pe['amount'])
            st.success(f"✅ Confirmed! Expense of ₦{pe['amount']:,.2f} saved successfully.")
            st.session_state.pending_expense = None
            st.rerun()

        if c_canc.button("❌ Edit / Cancel", use_container_width=True):
            st.session_state.pending_expense = None
            st.rerun()
    else:
        with st.form("exp_form"):
            col1, col2 = st.columns(2)
            with col1:
                exp_date = st.date_input("Expense Date", value=date.today())
                category = st.selectbox("Expense Category", ["House Expenses", "Maintenance", "General Operations"])
            with col2:
                amount = st.number_input("Amount (₦)", min_value=0.0, step=100.0, format="%.2f")
                description = st.text_input("Description / Reason", placeholder="e.g., Diesel purchase")

            submit_exp = st.form_submit_button("💾 Save to Cloud")
            if submit_exp:
                if amount <= 0:
                    st.error("Amount must be greater than zero.")
                else:
                    st.session_state.pending_expense = {
                        "date": exp_date,
                        "category": category,
                        "description": description,
                        "amount": amount
                    }
                    st.rerun()

# ==========================================
# PAGE 4: EDIT / CORRECT (PIN CLEARS UPON LOGIN)
# ==========================================
elif menu == "✏️ Edit / Correct Records":
    st.header("🔒 Admin Portal: Correct or Delete Wrong Entries")

    # If not authenticated, prompt for PIN
    if not st.session_state.admin_authenticated:
        with st.form("admin_login_form"):
            entered_pin = st.text_input("Enter Admin PIN to Unlock:", type="password")
            login_btn = st.form_submit_button("🔓 Unlock Portal")
            if login_btn:
                if entered_pin == ADMIN_PIN:
                    st.session_state.admin_authenticated = True
                    st.success("Access Granted!")
                    st.rerun()
                else:
                    st.error("❌ Incorrect Admin PIN.")
    else:
        # Authenticated: PIN is gone, Show Log Out / Lock Button
        top_c1, top_c2 = st.columns([3, 1])
        top_c1.success("🔓 Admin Session Active")
        if top_c2.button("🔒 Lock & Exit Admin"):
            st.session_state.admin_authenticated = False
            st.rerun()

        edit_tab1, edit_tab2 = st.tabs(["Correct Sales", "Correct Expenses"])

        # Tab 1: Sales
        with edit_tab1:
            sales = get_sales()
            if not sales.empty:
                # Descriptive Dropdown
                sales_options = {
                    f"ID: {row['id']} | {row['date']} | {row['attendant']} | ₦{row['total']:,.2f}": row['id']
                    for _, row in sales.iterrows()
                }
                selected_label = st.selectbox("Select Sale Record to Edit/Delete:", list(sales_options.keys()))
                selected_sale_id = sales_options[selected_label]
                record = sales[sales['id'] == selected_sale_id].iloc[0]

                with st.form("edit_sale_form"):
                    e_date = st.date_input("Date", value=datetime.strptime(str(record['date']), "%Y-%m-%d").date() if record['date'] else date.today())
                    e_attendant = st.text_input("Attendant", value=str(record['attendant']))
                    e_cash = st.number_input("Cash (₦)", value=float(record['cash']), step=100.0)
                    e_transfer = st.number_input("Transfer (₦)", value=float(record['transfer']), step=100.0)

                    col_b1, col_b2 = st.columns(2)
                    save_edit = col_b1.form_submit_button("🔄 Update Record")
                    delete_rec = col_b2.form_submit_button("🗑️ Delete Record")

                    if save_edit:
                        with st.spinner("Updating Google Sheet..."):
                            update_sale(selected_sale_id, e_date, e_attendant, e_cash, e_transfer)
                        st.success("Record updated!")
                        st.rerun()

                    if delete_rec:
                        with st.spinner("Deleting from Google Sheet..."):
                            delete_sale(selected_sale_id)
                        st.warning(f"Sale record deleted!")
                        st.rerun()
            else:
                st.info("No sales to display.")

        # Tab 2: Expenses
        with edit_tab2:
            expenses = get_expenses()
            if not expenses.empty:
                # Descriptive Dropdown
                exp_options = {
                    f"ID: {row['id']} | {row['date']} | {row['category']} | {row['description']} | ₦{row['amount']:,.2f}": row['id']
                    for _, row in expenses.iterrows()
                }
                selected_exp_label = st.selectbox("Select Expense Record to Edit/Delete:", list(exp_options.keys()))
                selected_exp_id = exp_options[selected_exp_label]
                record_exp = expenses[expenses['id'] == selected_exp_id].iloc[0]

                with st.form("edit_exp_form"):
                    ee_date = st.date_input("Date", value=datetime.strptime(str(record_exp['date']), "%Y-%m-%d").date() if record_exp['date'] else date.today())
                    cat_index = ["House Expenses", "Maintenance", "General Operations"].index(record_exp['category']) if record_exp['category'] in ["House Expenses", "Maintenance", "General Operations"] else 0
                    ee_cat = st.selectbox("Category", ["House Expenses", "Maintenance", "General Operations"], index=cat_index)
                    ee_desc = st.text_input("Description", value=str(record_exp['description']))
                    ee_amt = st.number_input("Amount (₦)", value=float(record_exp['amount']), step=100.0)

                    col_eb1, col_eb2 = st.columns(2)
                    save_exp = col_eb1.form_submit_button("🔄 Update Expense")
                    del_exp = col_eb2.form_submit_button("🗑️ Delete Expense")

                    if save_exp:
                        with st.spinner("Updating Google Sheet..."):
                            update_expense(selected_exp_id, ee_date, ee_cat, ee_desc, ee_amt)
                        st.success("Expense updated!")
                        st.rerun()

                    if del_exp:
                        with st.spinner("Deleting from Google Sheet..."):
                            delete_expense(selected_exp_id)
                        st.warning(f"Expense record deleted!")
                        st.rerun()
            else:
                st.info("No expenses to display.")

# ==========================================
# PAGE 5: COMPREHENSIVE REPORT & PRINT (WITH MONTH FILTER)
# ==========================================
elif menu == "📑 Comprehensive Report & Print":
    st.header("📑 COR Mission House - Financial Statements")
    st.write("Generate and export full monthly statements including revenue, expenses, and carry-over balance.")

    sales_df = get_sales()
    expenses_df = get_expenses()

    # Create month grouping
    if not sales_df.empty:
        sales_df['month'] = pd.to_datetime(sales_df['date']).dt.strftime('%B %Y')
    else:
        sales_df['month'] = []

    if not expenses_df.empty:
        expenses_df['month'] = pd.to_datetime(expenses_df['date']).dt.strftime('%B %Y')
    else:
        expenses_df['month'] = []

    all_months = sorted(list(set(sales_df['month'].dropna().tolist() + expenses_df['month'].dropna().tolist())), reverse=True)
    selected_month = st.selectbox("📅 Select Statement Month:", ["All Time"] + all_months)

    # Filter data
    if selected_month != "All Time":
        rep_sales = sales_df[sales_df['month'] == selected_month]
        rep_expenses = expenses_df[expenses_df['month'] == selected_month]
    else:
        rep_sales = sales_df
        rep_expenses = expenses_df

    # Calculations
    tot_cash = rep_sales['cash'].sum() if not rep_sales.empty else 0.0
    tot_trans = rep_sales['transfer'].sum() if not rep_sales.empty else 0.0
    tot_rev = rep_sales['total'].sum() if not rep_sales.empty else 0.0
    tot_exp = rep_expenses['amount'].sum() if not rep_expenses.empty else 0.0
    remaining_balance = tot_rev - tot_exp

    st.subheader(f"Financial Statement Overview ({selected_month})")
    summary_data = {
        "Financial Indicator": [
            "Total Physical Cash Handled",
            "Total Bank Transfers",
            "TOTAL GROSS REVENUE",
            "TOTAL EXPENDITURE",
            "NET AVAILABLE BALANCE (CARRY-OVER)"
        ],
        "Amount (₦)": [
            f"₦{tot_cash:,.2f}",
            f"₦{tot_trans:,.2f}",
            f"₦{tot_rev:,.2f}",
            f"₦{tot_exp:,.2f}",
            f"₦{remaining_balance:,.2f}"
        ]
    }
    summary_df = pd.DataFrame(summary_data)
    st.table(summary_df)

    st.divider()

    # Detailed breakdowns for this specific month
    c_s, c_e = st.columns(2)
    with c_s:
        st.write(f"**Sales Detail ({selected_month}):**")
        st.dataframe(rep_sales[['date', 'attendant', 'cash', 'transfer', 'total']], use_container_width=True)
    with c_e:
        st.write(f"**Expenses Detail ({selected_month}):**")
        st.dataframe(rep_expenses[['date', 'category', 'description', 'amount']], use_container_width=True)

    # Excel Download
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Summary Overview', index=False)
        if not rep_sales.empty:
            rep_sales.to_excel(writer, sheet_name='Sales Statement', index=False)
        if not rep_expenses.empty:
            rep_expenses.to_excel(writer, sheet_name='Expenses Statement', index=False)

    sanitized_month = selected_month.replace(" ", "_")
    st.download_button(
        label=f"📥 Download Official {selected_month} Statement (Excel .xlsx)",
        data=output.getvalue(),
        file_name=f"COR_Water_Statement_{sanitized_month}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
