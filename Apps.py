import streamlit as st
import psycopg2
import pandas as pd
from datetime import date, datetime, timedelta
from io import StringIO

# =============================
# APP CONFIG
# =============================

st.set_page_config(
    page_title="RF Weekly Work Report",
    layout="wide"
)

# =============================
# CONSTANTS
# =============================

THEMES = [
    "1. AI-Driven Multilingual Content Localization & Accessible Digital Outreach through Integrated Multichannel Platforms",
    "2. AI-Based Crop Health Detection App and WhatsApp Bot",
    "3. Tele-Consultation Platform Enhancements – AI-integrated, multilingual, voice-enabled helpline",
    "4. Development of Animal Digital Information System",
    "5. FPO Management App – Development and Refinement",
    "6. 24/7 Weather-Based Marine Fisheries Advisories (Machli App)",
    "7. Domain-Specific Data Management Tools (Web Scraping + GIS/ML)",
    "8. Livelihood Advisory Podcasts via Internet Radio",
    "9. RF Livelihood Video Learning App",
    "10. Rural Yellow Pages App – Development & Scale",
    "11. Digital Farm Management System (DFMS) – Predictive Advisory",
    "12. RF Super App – Integrated Service Delivery",
    "13. E-Learning & Knowledge Dissemination",
    "14. Cloud Migration & Infrastructure Enhancements",
    "15. Early Warning Systems & Disaster Resilience",
    "16. Tech for Social Good & Knowledge Empowerment",
    "17. Data-Driven Impact: Measuring Success in Tech-based Outreach",
    "18. Web-Based Knowledge Management System (WebKMS) + Multilingual AI",
    "19. Geo-Spatial Vulnerability Mapping for Inclusive Development",
    "20. Monitoring & Mapping Water Harvesting Structures",
    "21. NDVI-Based Crop Yield Computation",
    "22. Multi-Hazard Risk Mapping & Early Warning Systems",
    "23. Above Ground Biomass (AGB) Estimation",
    "24. Change Detection & Environmental Monitoring",
    "25. Climate-Responsive Modelling & Forecasting",
    "26. Tech-Enabled Monitoring & Evaluation using Mobile-Based GIS",
    "27. Spatial Decision Support & Risk Intelligence (WebKMS + GIS/RS)",
    "28. IT Documentation, Digital Infrastructure Support & Other Support",
]

EMPLOYEES = [
    "Somnath Pati",
    "Abhrajit Das",
    "Bablu Prasad",
    "Rajak Manjothi",
    "Kushal Kuantia",
    "Priyanka Sharma",
    "Shivam",
    "Selvaraj",
    "Other",
]

DEPARTMENTS = [
    "Dissemination",
    "KMS",
    "GIS",
    "Platform",
    "Other",
]

TABLE_NAME = "rf_weekly_reports"


# =============================
# SUPABASE CONNECTION
# =============================

def get_conn():
    """Connect to Supabase Postgres using DSN from secrets."""
    if "supabase" not in st.secrets or "dsn" not in st.secrets["supabase"]:
        st.error(
            "❌ Supabase DSN not found in secrets.\n\n"
            "Go to 'Edit secrets' and add:\n\n"
            "[supabase]\n"
            'dsn = "postgresql://postgres.XXXX:YYYY@aws-0-REGION.pooler.supabase.com:6543/postgres"'
        )
        st.stop()

    dsn = st.secrets["supabase"]["dsn"]
    return psycopg2.connect(dsn, sslmode="require")


def init_db():
    """Create table if it does not exist."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id SERIAL PRIMARY KEY,
            submission_date DATE,
            week_start DATE,
            week_end DATE,
            employee TEXT,
            department TEXT,
            theme TEXT,
            work TEXT,
            pending BOOLEAN,
            justification TEXT,
            updated TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


# =============================
# DB HELPERS
# =============================

def save_report(submission_date, week_start, week_end, employee, department, rows: pd.DataFrame):
    """
    Save weekly report for one employee and one week.
    Old entries for that employee+week are deleted first (so update works).
    """
    conn = get_conn()
    cur = conn.cursor()

    # Remove existing rows for this employee-week
    cur.execute(
        f"""
        DELETE FROM {TABLE_NAME}
        WHERE employee = %s
          AND week_start = %s
          AND week_end = %s
        """,
        (employee, week_start, week_end),
    )

    now = datetime.utcnow()

    for r in rows.to_dict("records"):
        theme = r.get("theme") or THEMES[0]
        work = (r.get("work") or "").strip()
        pending = bool(r.get("pending", False))
        justification = (r.get("justification") or "").strip()

        # Skip completely empty rows
        if not work and not pending and not justification:
            continue

        cur.execute(
            f"""
            INSERT INTO {TABLE_NAME} (
                submission_date, week_start, week_end,
                employee, department, theme, work,
                pending, justification, updated
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                submission_date,
                week_start,
                week_end,
                employee,
                department,
                theme,
                work,
                pending,
                justification if pending else "",
                now,
            ),
        )

    conn.commit()
    cur.close()
    conn.close()


def load_user_week(employee, week_start, week_end) -> pd.DataFrame:
    """Load existing weekly report for an employee+week, or give one default row."""
    conn = get_conn()
    df = pd.read_sql(
        f"""
        SELECT theme, work, pending, justification
        FROM {TABLE_NAME}
        WHERE employee = %s
          AND week_start = %s
          AND week_end = %s
        ORDER BY id
        """,
        conn,
        params=[employee, week_start, week_end],
    )
    conn.close()

    if df.empty:
        return pd.DataFrame(
            [
                {
                    "theme": THEMES[0],
                    "work": "",
                    "pending": False,
                    "justification": "",
                }
            ]
        )

    df["pending"] = df["pending"].astype(bool)
    return df


def read_all_reports() -> pd.DataFrame:
    """Read all reports for admin dashboard."""
    conn = get_conn()
    df = pd.read_sql(
        f"SELECT * FROM {TABLE_NAME} ORDER BY updated DESC",
        conn,
    )
    conn.close()

    if not df.empty:
        for c in ["submission_date", "week_start", "week_end"]:
            df[c] = pd.to_datetime(df[c]).dt.date

    return df


# =============================
# DATE & ROLE HELPERS
# =============================

def last_monday():
    today = date.today()
    # Last week's Monday
    return today - timedelta(days=today.weekday() + 7)


def last_sunday():
    return last_monday() + timedelta(days=6)


def get_role_from_url():
    """?role=user or ?role=admin"""
    try:
        params = st.query_params
    except Exception:
        return "user"

    role_val = params.get("role", ["user"])
    if isinstance(role_val, list):
        role_val = role_val[0]

    role_val = (role_val or "").lower()
    return "admin" if role_val == "admin" else "user"


# =============================
# INIT DB
# =============================

init_db()

# =============================
# LAYOUT: SIDEBAR & MENU
# =============================

role = get_role_from_url()

if role == "admin":
    st.sidebar.title("🧑‍💼 Admin Panel")
    menu = st.sidebar.radio("Menu", ["Submit Weekly Report", "View Reports"])
else:
    st.sidebar.title("👷‍♂️ Weekly Report")
    menu = "Submit Weekly Report"


# =============================
# SUBMIT PAGE (USER + ADMIN)
# =============================

if menu == "Submit Weekly Report":
    st.title("📋 Weekly Work Report (Supabase-backed)")

    col1, col2 = st.columns(2)

    with col1:
        employee = st.selectbox("Choose Your Name", EMPLOYEES)
        if employee == "Other":
            employee = st.text_input("Enter your name")

    with col2:
        department = st.selectbox("Select Your Department", DEPARTMENTS)

    st.subheader("Report Period")
    submission_date = st.date_input("Submission Date", date.today())
    week_start = st.date_input("Week Start (Last Monday)", last_monday())
    week_end = st.date_input("Week End (Last Sunday)", last_sunday())

    # Load existing week data for that employee
    key = f"{employee}_{week_start}_{week_end}"
    if "week_key" not in st.session_state or st.session_state.week_key != key:
        st.session_state.week_key = key
        st.session_state.week_table = load_user_week(employee, week_start, week_end)

    st.subheader("Theme-wise Work Details")

    edited = st.data_editor(
        st.session_state.week_table,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        column_config={
            "theme": st.column_config.SelectboxColumn("Theme", options=THEMES),
            "work": st.column_config.TextColumn("Work Done (max 5000 chars)"),
            "pending": st.column_config.CheckboxColumn("Pending?"),
            "justification": st.column_config.TextColumn("Justification (if pending)"),
        },
    )

    if st.button("✅ Submit / Update Weekly Report"):
        if not employee or employee.strip() == "":
            st.error("Please enter your name.")
        else:
            save_report(
                submission_date,
                week_start,
                week_end,
                employee.strip(),
                department,
                edited,
            )
            st.session_state.week_table = edited
            st.success("✅ Weekly report saved in Supabase (will not be lost on redeploy).")


# =============================
# ADMIN VIEW PAGE
# =============================

if menu == "View Reports":
    st.title("📊 Admin Dashboard – Combined Reports (Supabase)")

    df = read_all_reports()

    if df.empty:
        st.warning("No reports submitted yet.")
    else:
        # Filters
        col1, col2, col3 = st.columns(3)

        with col1:
            period = st.selectbox(
                "Time Period",
                ["All", "Weekly", "Monthly", "Quarterly", "Half-Yearly", "Yearly"],
            )

        with col2:
            emp_filter = st.selectbox(
                "Employee",
                ["All"] + sorted(df["employee"].unique()),
            )

        with col3:
            dept_filter = st.selectbox(
                "Department",
                ["All"] + sorted(df["department"].unique()),
            )

        today = date.today()

        if period != "All":
            if period == "Weekly":
                start_date = today - timedelta(days=6)
            elif period == "Monthly":
                start_date = today.replace(day=1)
            elif period == "Quarterly":
                start_date = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
            elif period == "Half-Yearly":
                start_date = date(today.year, 1 if today.month <= 6 else 7, 1)
            elif period == "Yearly":
                start_date = date(today.year, 1, 1)

            df = df[df["submission_date"] >= start_date]

        if emp_filter != "All":
            df = df[df["employee"] == emp_filter]

        if dept_filter != "All":
            df = df[df["department"] == dept_filter]

        # High-level metrics
        st.metric("Total Activity Rows", len(df))
        st.metric("Pending Tasks", int(df["pending"].sum()) if "pending" in df else 0)

        st.subheader("By Employee")
        st.dataframe(
            df.groupby("employee").size().reset_index(name="Activities"),
            use_container_width=True,
        )

        st.subheader("By Theme")
        st.dataframe(
            df.groupby("theme").size().reset_index(name="Activities"),
            use_container_width=True,
        )

        st.subheader("Detailed Data")
        st.dataframe(df, use_container_width=True)

        # Combined CSV for current filter
        csv_buf = StringIO()
        df.to_csv(csv_buf, index=False)

        st.download_button(
            "⬇ Download Combined CSV (Current Filters)",
            csv_buf.getvalue(),
            file_name=f"rf_weekly_report_{date.today()}.csv",
            mime="text/csv",
        )
