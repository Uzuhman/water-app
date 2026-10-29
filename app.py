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
    page_title="Water Business Manager",
    page_icon="💧",
    layout="wide"
)

# ==============================================================================
# 🔴 STEP 1: PASTE YOUR GOOGLE SHEET LINK BETWEEN THE QUOTES BELOW:
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1o9IvmiD0rmdImaDHwk4k7zyyq2nZ-XDide8hPimpKQM/edit?gid=1164316564#gid=1164316564"
# ==============================================================================

# --- ADMIN PIN ---
ADMIN_PIN = "1234"

# --- CONNECT TO GOOGLE SHEETS ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


def find_local_key():
    """Finds any Google service account JSON file in the app directory."""
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
    if "PASTE_YOUR_COPIED" in SPREADSHEET_URL:
        st.warning("⚠️ Please paste your Google Sheet URL on Line 18 of app.py!")
        st.stop()

    key_path = find_local_key()

    # 1. Local connection with JSON key
    if key_path:
        gc = gspread.service_account(filename=key_path)
    else:
        # 2. Cloud connection with Streamlit Secrets
        try:
            if "gcp_service_account" in st.secrets:
                creds = Credentials.from_service_account_info(
                    st.secrets["gcp_service_account"],
                    scopes=SCOPES
                )
                gc = gspread.authorize(creds)
            else:
                st.error("⚠️ google_key.json not found in your water_app folder!")
                st.stop()
        except Exception:
            st.error("⚠️ google_key.json not found in your water_app folder!")
            st.stop()

    # Open by URL (100% reliable)
    try:
        sh = gc.open_by_url(SPREADSHEET_URL)
        return sh.worksheet("Sales"), sh.worksheet("Expenses")
    except Exception as e:
        st.error(f"⚠️ Could not open sheet with that link.")
        st.info(
            "Please make sure:\n1. The link is correct.\n2. You clicked 'Share' on the Google Sheet and added the email inside your json key as Editor.")
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


# --- PRIVACY SESSION STATE ---
if "show_balance" not in st.session_state:
    st.session_state.show_balance = False

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("💧 Water Manager (Cloud)")
menu = st.sidebar.radio(
    "Navigation:",
    ["📊 Dashboard & Summary", "💰 Record Sale", "💸 Record Expense", "✏️ Edit / Correct Records",
     "📑 Comprehensive Report & Print"]
)

# ==========================================
# PAGE 1: DASHBOARD
# ==========================================
if menu == "📊 Dashboard & Summary":
    sales_df = get_sales()
    expenses_df = get_expenses()

    total_revenue_all = sales_df['total'].sum() if not sales_df.empty else 0.0
    total_expenses_all = expenses_df['amount'].sum() if not expenses_df.empty else 0.0
    net_available = total_revenue_all - total_expenses_all

    top_col1, top_col2 = st.columns([2, 1])
    with top_col1:
        st.title("Financial Dashboard")
    with top_col2:
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

    if not sales_df.empty:
        sales_df['month'] = pd.to_datetime(sales_df['date']).dt.strftime('%B %Y')
    else:
        sales_df['month'] = []

    if not expenses_df.empty:
        expenses_df['month'] = pd.to_datetime(expenses_df['date']).dt.strftime('%B %Y')
    else:
        expenses_df['month'] = []

    all_months = sorted(list(set(sales_df['month'].dropna().tolist() + expenses_df['month'].dropna().tolist())),
                        reverse=True)
    selected_month = st.selectbox("📅 Filter by Month:", ["All Time"] + all_months)

    if selected_month != "All Time":
        f_sales = sales_df[sales_df['month'] == selected_month]
        f_exp = expenses_df[expenses_df['month'] == selected_month]
    else:
        f_sales = sales_df
        f_exp = expenses_df

    c_cash = f_sales['cash'].sum() if not f_sales.empty else 0.0
    c_transfer = f_sales['transfer'].sum() if not f_sales.empty else 0.0
    c_rev = f_sales['total'].sum() if not f_sales.empty else 0.0
    c_exp = f_exp['amount'].sum() if not f_exp.empty else 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💵 Total Cash", f"₦{c_cash:,.2f}")
    m2.metric("💳 Total Transfer", f"₦{c_transfer:,.2f}")
    m3.metric("📈 Total Revenue", f"₦{c_rev:,.2f}")
    m4.metric("📉 Total Expenses", f"₦{c_exp:,.2f}")

    st.divider()

    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("Sales Breakdown")
        if not f_sales.empty:
            st.dataframe(f_sales[['id', 'date', 'attendant', 'cash', 'transfer', 'total']], use_container_width=True)
        else:
            st.info("No sales recorded.")
    with col_r:
        st.subheader("Expenses Breakdown")
        if not f_exp.empty:
            st.dataframe(f_exp[['id', 'date', 'category', 'description', 'amount']], use_container_width=True)
        else:
            st.info("No expense recorded.")

# ==========================================
# PAGE 2: RECORD SALE
# ==========================================
elif menu == "💰 Record Sale":
    st.header("💰 Record Daily Water Sale")
    with st.form("sales_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            sale_date = st.date_input("Date of Sale", value=date.today())
            attendant = st.text_input("Attendant Name")
        with col2:
            cash = st.number_input("Cash Amount (₦)", min_value=0.0, step=100.0, format="%.2f")
            transfer = st.number_input("Transfer Amount (₦)", min_value=0.0, step=100.0, format="%.2f")

        total_prev = cash + transfer
        st.info(f"**Total Sale: ₦{total_prev:,.2f}**")

        if st.form_submit_button("💾 Save Sale to Cloud"):
            if not attendant:
                st.error("Please enter the attendant's name.")
            elif total_prev <= 0:
                st.error("Sale amount cannot be zero.")
            else:
                with st.spinner("Saving to Google Sheets..."):
                    add_sale(sale_date, attendant, cash, transfer)
                st.success(f"✅ Sale of ₦{total_prev:,.2f} saved to Google Sheet!")

# ==========================================
# PAGE 3: RECORD EXPENSE
# ==========================================
elif menu == "💸 Record Expense":
    st.header("💸 Record Daily Expense")
    with st.form("exp_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            exp_date = st.date_input("Expense Date", value=date.today())
            category = st.selectbox("Expense Category", ["House Expenses", "Maintenance", "General Operations"])
        with col2:
            amount = st.number_input("Amount (₦)", min_value=0.0, step=100.0, format="%.2f")
            description = st.text_input("Description / Reason", placeholder="e.g., Diesel purchase")

        if st.form_submit_button("💾 Save Expense to Cloud"):
            if amount <= 0:
                st.error("Amount must be greater than zero.")
            else:
                with st.spinner("Saving to Google Sheets..."):
                    add_expense(exp_date, category, description, amount)
                st.success(f"✅ Expense of ₦{amount:,.2f} saved to Google Sheet!")

# ==========================================
# PAGE 4: EDIT / CORRECT (PROTECTED)
# ==========================================
elif menu == "✏️ Edit / Correct Records":
    st.header("🔒 Admin Control: Correct or Delete Wrong Entries")
    pin_input = st.text_input("Enter Admin PIN:", type="password")

    if pin_input == ADMIN_PIN:
        st.success("✅ Access Granted!")
        edit_tab1, edit_tab2 = st.tabs(["Correct Sales", "Correct Expenses"])

        with edit_tab1:
            sales = get_sales()
            if not sales.empty:
                sale_ids = sales['id'].tolist()
                selected_sale_id = st.selectbox("Select Sale ID:", sale_ids)
                record = sales[sales['id'] == selected_sale_id].iloc[0]

                with st.form("edit_sale_form"):
                    e_date = st.date_input("Date",
                                           value=datetime.strptime(str(record['date']), "%Y-%m-%d").date() if record[
                                               'date'] else date.today())
                    e_attendant = st.text_input("Attendant", value=str(record['attendant']))
                    e_cash = st.number_input("Cash (₦)", value=float(record['cash']), step=100.0)
                    e_transfer = st.number_input("Transfer (₦)", value=float(record['transfer']), step=100.0)

                    col_b1, col_b2 = st.columns(2)
                    save_edit = col_b1.form_submit_button("🔄 Update Record")
                    delete_rec = col_b2.form_submit_button("🗑️ Delete Record")

                    if save_edit:
                        with st.spinner("Updating Google Sheet..."):
                            update_sale(selected_sale_id, e_date, e_attendant, e_cash, e_transfer)
                        st.success("Updated!")
                        st.rerun()

                    if delete_rec:
                        with st.spinner("Deleting from Google Sheet..."):
                            delete_sale(selected_sale_id)
                        st.warning(f"Sale ID {selected_sale_id} deleted!")
                        st.rerun()
            else:
                st.info("No sales found.")

        with edit_tab2:
            expenses = get_expenses()
            if not expenses.empty:
                exp_ids = expenses['id'].tolist()
                selected_exp_id = st.selectbox("Select Expense ID:", exp_ids)
                record_exp = expenses[expenses['id'] == selected_exp_id].iloc[0]

                with st.form("edit_exp_form"):
                    ee_date = st.date_input("Date",
                                            value=datetime.strptime(str(record_exp['date']), "%Y-%m-%d").date() if
                                            record_exp['date'] else date.today())
                    cat_index = ["House Expenses", "Maintenance", "General Operations"].index(record_exp['category']) if \
                    record_exp['category'] in ["House Expenses", "Maintenance", "General Operations"] else 0
                    ee_cat = st.selectbox("Category", ["House Expenses", "Maintenance", "General Operations"],
                                          index=cat_index)
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
                        st.warning(f"Expense ID {selected_exp_id} deleted!")
                        st.rerun()
            else:
                st.info("No expenses found.")
    elif pin_input:
        st.error("❌ Incorrect Admin PIN.")

# ==========================================
# PAGE 5: PRINT / EXCEL REPORT
# ==========================================
elif menu == "📑 Comprehensive Report & Print":
    st.header("📑 Official Financial Report")
    sales_df = get_sales()
    expenses_df = get_expenses()

    tot_cash = sales_df['cash'].sum() if not sales_df.empty else 0.0
    tot_trans = sales_df['transfer'].sum() if not sales_df.empty else 0.0
    tot_rev = sales_df['total'].sum() if not sales_df.empty else 0.0
    tot_exp = expenses_df['amount'].sum() if not expenses_df.empty else 0.0
    remaining_balance = tot_rev - tot_exp

    summary_data = {
        "Metric": ["Total Cash Generated", "Total Bank Transfers", "TOTAL GROSS REVENUE", "TOTAL EXPENSES",
                   "NET AVAILABLE BALANCE (CARRY-OVER)"],
        "Amount (₦)": [f"₦{tot_cash:,.2f}", f"₦{tot_trans:,.2f}", f"₦{tot_rev:,.2f}", f"₦{tot_exp:,.2f}",
                       f"₦{remaining_balance:,.2f}"]
    }
    summary_df = pd.DataFrame(summary_data)

    st.subheader("1. Financial Summary Overview")
    st.table(summary_df)
    st.divider()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Summary Overview', index=False)
        if not sales_df.empty:
            sales_df.to_excel(writer, sheet_name='Sales Records', index=False)
        if not expenses_df.empty:
            expenses_df.to_excel(writer, sheet_name='Expenses Records', index=False)

    st.download_button(
        label="📥 Download Complete Financial Report (Excel .xlsx)",
        data=output.getvalue(),
        file_name=f"Water_Statement_{date.today().strftime('%Y_%m_%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )