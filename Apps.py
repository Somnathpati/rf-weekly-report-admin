import streamlit as st
import psycopg2
from datetime import date, datetime, timedelta
import pandas as pd

# =============================
# CONFIG
# =============================

THEMES = [
    "1. AI-Driven Multilingual Content Localization & Accessible Digital Outreach through Integrated Multichannel Platforms",
    "2. AI-Based Crop Health Detection App and WhatsApp Bot",
    "3. Tele-Consultation Platform Enhancements – Advancing AI-integrated, multilingual, voice-enabled helpline and advisory services",
    "4. Development of Animal Digital Information System",
    "5. FPO Management App – Development and Refinement",
    "6. 24/7 Weather-Based Marine Fisheries Advisories (Machli App)",
    "7. Domain-Specific Data Management Tools (Web Scraping + GIS/ML)",
    "8. Livelihood Advisory Podcasts via Internet Radio",
    "9. RF Livelihood Video Learning App",
    "10. Rural Yellow Pages App – Development & Scale",
    "11. Digital Farm Management System (DFMS)",
    "12. RF Super App – Integrated Delivery",
    "13. E-Learning & Knowledge Dissemination",
    "14. Cloud Migration & Infrastructure Enhancements",
    "15. Early Warning & Disaster Resilience",
    "16. Tech for Social Good",
    "17. Data-Driven Impact Measurement",
    "18. WebKMS + Multilingual AI",
    "19. Geo-Spatial Vulnerability Mapping",
    "20. Water Harvesting Structure Mapping",
    "21. NDVI-Based Crop Yield",
    "22. Multi-Hazard Risk Mapping",
    "23. AGB Estimation",
    "24. Change Detection Monitoring",
    "25. Climate Modeling & Forecasting",
    "26. GIS-Based M&E",
    "27. Spatial Decision Support",
    "28. IT Documentation & Support",
]

EMPLOYEES = [
    "Somnath Pati",
    "Abhrajit Das",
    "Bablu Prasad",
    "Rajak Manjothi",
    "Kushal Kuantia",
    "Priyanka Sharma",
    "Shivam Periwal",
    "Selvaraj",
    "Other",
]

DEPARTMENTS = ["Dissemination", "KMS", "GIS", "Platform", "Other"]


# =============================
# SUPABASE DATABASE HELPERS
# =============================

def get_conn():
    """
    Connect to Supabase Postgres using credentials stored in st.secrets.

    st.secrets should contain:

    [supabase]
    host = "YOUR_HOST"
    port = 5432
    database = "YOUR_DB"
    user = "YOUR_USER"
    password = "YOUR_PASSWORD"
    """
    sb = st.secrets["supabase"]
    conn = psycopg2.connect(
        host=sb["host"],
        port=sb.get("port", 5432),
        dbname=sb["database"],
        user=sb["user"],
        password=sb["password"],
        sslmode="require"  # important for Supabase
    )
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            submission_date DATE,
            week_start DATE,
            week_end DATE,
            employee TEXT,
            department TEXT,
            theme TEXT,
            work TEXT,
            pending INTEGER,
            justification TEXT,
            updated TIMESTAMPTZ
        )
        """
    )
    conn.commit()
    cur.close()
    conn.close()


def save_report(submission_date, week_start, week_end, employee, dept, rows: pd.DataFrame):
    """
    One person + one week = one report.
    We delete existing entries for that (employee, week_start, week_end)
    then insert the new set of rows.
    """
    conn = get_conn()
    cur = conn.cursor()

    # Delete old rows for this employee + week
    cur.execute(
        """
        DELETE FROM reports
        WHERE employee = %s AND week_start = %s AND week_end = %s
        """,
        (employee, week_start, week_end),
    )

    # Insert new rows
    now = datetime.utcnow()
    for r in rows.to_dict("records"):
        work_text = (r.get("work") or "").strip()
        is_pending = bool(r.get("pending", False))
        justification = (r.get("justification") or "").strip()
        theme = r.get("theme") or THEMES[0]

        # Skip completely empty rows
        if not work_text and not is_pending and not justification:
            continue

        cur.execute(
            """
            INSERT INTO reports
            (submission_date, week_start, week_end,
             employee, department,
             theme, work, pending, justification, updated)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                submission_date,
                week_start,
                week_end,
                employee,
                dept,
                theme,
                work_text,
                1 if is_pending else 0,
                justification if is_pending else "",
                now,
            ),
        )

    conn.commit()
    cur.close()
    conn.close()


def load_user_week(employee, week_start, week_end):
    """Load all rows for this person + week; if none, return 1 empty row."""
    conn = get_conn()
    query = """
        SELECT theme, work, pending, justification
        FROM reports
        WHERE employee = %s AND week_start = %s AND week_end = %s
        ORDER BY id
    """
    df = pd.read_sql(query, conn, params=[employee, week_start, week_end])
    conn.close()

    if df.empty:
        df = pd.DataFrame(
            [
                {
                    "theme": THEMES[0],
                    "work": "",
                    "pending": False,
                    "justification": "",
                }
            ]
        )
    else:
        df["pending"] = df["pending"].astype(bool)

    return df


def read_all_reports():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM reports", conn)
    conn.close()

    if not df.empty:
        for col in ["submission_date", "week_start", "week_end"]:
            df[col] = pd.to_datetime(df[col]).dt.date

    return df


# =============================
# DATE HELPERS
# =============================

def last_monday():
    today = date.today()
    return today - timedelta(days=today.weekday() + 7)


def last_sunday():
    return last_monday() + timedelta(days=6)


# =============================
# ROLE (USER vs ADMIN) FROM URL
# =============================

def get_role_from_url():
    """
    Read ?role=user or ?role=admin from URL using st.query_params.
    Default = user
    """
    role = "user"
    try:
        params = st.query_params
        if "role" in params:
            candidate = params["role"]
            if isinstance(candidate, list):
                candidate = candidate[0]
            candidate = candidate.lower()
            if candidate in ("user", "admin"):
                role = candidate
    except Exception:
        role = "user"
    return role


# =============================
# STREAMLIT APP
# =============================

st.set_page_config("Weekly RF Work Report", layout="wide")
init_db()  # ensure table exists at startup

role = get_role_from_url()

if role == "admin":
    st.sidebar.title("🧑‍💻 Admin Dashboard")
    menu = st.sidebar.radio("Menu", ["Submit Weekly Report", "View Reports"])
else:
    st.sidebar.title("👨‍🌾 Weekly Submission")
    menu = "Submit Weekly Report"  # user cannot see reports


# =============================
# PAGE 1 – SUBMIT WEEKLY REPORT
# =============================

if menu == "Submit Weekly Report":
    st.title("📋 Weekly Work Report")

    col1, col2 = st.columns(2)

    with col1:
        emp = st.selectbox("Employee", EMPLOYEES)
        if emp == "Other":
            emp = st.text_input("Enter your name")

    with col2:
        dept = st.selectbox("Department", DEPARTMENTS)

    st.markdown("### Report Dates")

    submission_date = st.date_input("Submission Date", value=date.today())
    wk_start = st.date_input("Week Start (last Monday)", value=last_monday())
    wk_end = st.date_input("Week End (last Sunday)", value=last_sunday())

    # Unique key for that employee + week
    week_key = f"{emp}_{wk_start}_{wk_end}"

    if "week_key" not in st.session_state or st.session_state.week_key != week_key:
        st.session_state.week_key = week_key
        st.session_state.week_table = load_user_week(emp, wk_start, wk_end)

    st.markdown("### Your activities for this week")

    edited = st.data_editor(
        st.session_state.week_table,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        column_config={
            "theme": st.column_config.SelectboxColumn("Theme", options=THEMES),
            "work": st.column_config.TextColumn("Work Done"),
            "pending": st.column_config.CheckboxColumn("Pending"),
            "justification": st.column_config.TextColumn("Justification (if pending)"),
        },
        key="weekly_editor",
    )

    if st.button("✅ Submit / Update Weekly Report"):
        if not emp:
            st.error("Please enter your name.")
        else:
            save_report(submission_date, wk_start, wk_end, emp, dept, edited)
            st.session_state.week_table = edited
            st.success("Your weekly report has been saved/updated successfully! ✅")


# =============================
# PAGE 2 – ADMIN REPORT VIEW
# =============================

if menu == "View Reports":
    st.title("📊 Reports Dashboard")

    df = read_all_reports()

    if df.empty:
        st.warning("No submissions yet.")
    else:
        col1, col2, col3 = st.columns(3)

        with col1:
            period = st.selectbox(
                "Period",
                ["Weekly", "Monthly", "Quarterly", "Half-Yearly", "Yearly", "All"],
            )

        with col2:
            emp_filter = st.selectbox(
                "Employee", ["All"] + sorted(df["employee"].unique())
            )

        with col3:
            dept_filter = st.selectbox(
                "Department", ["All"] + sorted(df["department"].unique())
            )

        today = date.today()

        if period != "All":
            if period == "Weekly":
                start = today - timedelta(days=6)
            elif period == "Monthly":
                start = today.replace(day=1)
            elif period == "Quarterly":
                start = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
            elif period == "Half-Yearly":
                start = date(today.year, 1 if today.month <= 6 else 7, 1)
            elif period == "Yearly":
                start = date(today.year, 1, 1)

            df = df[df["submission_date"] >= start]

        if emp_filter != "All":
            df = df[df["employee"] == emp_filter]

        if dept_filter != "All":
            df = df[df["department"] == dept_filter]

        st.subheader("Summary")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Total Activities", len(df))
        with c2:
            st.metric("Pending Tasks", int(df["pending"].sum()))

        st.subheader("By Employee")
        st.dataframe(
            df.groupby("employee")
            .size()
            .reset_index(name="Activities")
        )

        st.subheader("By Theme")
        st.dataframe(
            df.groupby("theme")
            .size()
            .reset_index(name="Activities")
        )

        st.subheader("Detailed Records")
        st.dataframe(df)

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download CSV",
            csv_bytes,
            "weekly_reports.csv",
            mime="text/csv",
        )
