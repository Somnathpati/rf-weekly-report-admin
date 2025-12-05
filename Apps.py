import streamlit as st
import sqlite3
from datetime import date, datetime, timedelta
import pandas as pd

# =============================
# CONFIG
# =============================

DB_NAME = "weekly_reports.db"

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
# SQLITE HELPERS
# =============================

def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reports(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_date TEXT,
            week_start TEXT,
            week_end TEXT,
            employee TEXT,
            department TEXT,
            theme TEXT,
            work TEXT,
            pending INTEGER,
            justification TEXT,
            updated TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def save_report(submission_date, week_start, week_end, employee, dept, rows: pd.DataFrame):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM reports
        WHERE employee = ?
          AND week_start = ?
          AND week_end = ?
        """,
        (employee, week_start.isoformat(), week_end.isoformat()),
    )

    now = datetime.now().isoformat()

    for r in rows.to_dict("records"):
        work = (r.get("work") or "").strip()
        pending = bool(r.get("pending", False))
        justification = (r.get("justification") or "").strip()
        theme = r.get("theme") or THEMES[0]

        if not work and not pending and not justification:
            continue

        cur.execute(
            """
            INSERT INTO reports (
                submission_date,
                week_start,
                week_end,
                employee,
                department,
                theme,
                work,
                pending,
                justification,
                updated
            )
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                submission_date.isoformat(),
                week_start.isoformat(),
                week_end.isoformat(),
                employee,
                dept,
                theme,
                work,
                1 if pending else 0,
                justification if pending else "",
                now,
            ),
        )

    conn.commit()
    conn.close()


def load_user_week(employee, week_start, week_end):
    conn = get_conn()
    df = pd.read_sql(
        """
        SELECT theme, work, pending, justification
        FROM reports
        WHERE employee = ?
          AND week_start = ?
          AND week_end = ?
        ORDER BY id
        """,
        conn,
        params=[employee, week_start.isoformat(), week_end.isoformat()],
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
    else:
        df["pending"] = df["pending"].astype(bool)
        return df


def read_all_reports():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM reports ORDER BY updated DESC", conn)
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
    return today - timedelta(days=today.weekday() + 7)


def last_sunday():
    return last_monday() + timedelta(days=6)


def get_role_from_url():
    role = "user"
    try:
        params = st.query_params
        if "role" in params:
            r = params["role"]
            if isinstance(r, list):
                r = r[0]
            r = r.lower()
            if r in ["user", "admin"]:
                role = r
    except Exception:
        pass
    return role


# =============================
# APP
# =============================

st.set_page_config("Weekly RF Work Report", layout="wide")
init_db()

role = get_role_from_url()

if role == "admin":
    st.sidebar.title("🧑‍💼 ADMIN PANEL")
    menu = st.sidebar.radio("Menu", ["Submit Weekly Report", "View Reports"])
else:
    st.sidebar.title("👷‍♂️ STAFF SUBMISSION")
    menu = "Submit Weekly Report"


# SUBMIT PAGE
if menu == "Submit Weekly Report":
    st.title("📋 Weekly Work Report")

    col1, col2 = st.columns(2)

    with col1:
        emp = st.selectbox("Employee Name", EMPLOYEES)
        if emp == "Other":
            emp = st.text_input("Enter your name")

    with col2:
        dept = st.selectbox("Department", DEPARTMENTS)

    st.subheader("Report Period")

    submission = st.date_input("Today's Date", date.today())
    wk_start = st.date_input("Week Start (Last Monday)", last_monday())
    wk_end = st.date_input("Week End (Last Sunday)", last_sunday())

    key = f"{emp}_{wk_start}_{wk_end}"

    if "weekkey" not in st.session_state or st.session_state.weekkey != key:
        st.session_state.weekkey = key
        st.session_state.weektable = load_user_week(emp, wk_start, wk_end)

    st.subheader("Work Details")

    edited = st.data_editor(
        st.session_state.weektable,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        column_config={
            "theme": st.column_config.SelectboxColumn("Theme", options=THEMES),
            "work": st.column_config.TextColumn("Work Done"),
            "pending": st.column_config.CheckboxColumn("Pending"),
            "justification": st.column_config.TextColumn("Justification (if pending)"),
        },
    )

    if st.button("✅ Submit / Update Weekly Report"):
        if not emp:
            st.error("Please provide your name")
        else:
            save_report(submission, wk_start, wk_end, emp, dept, edited)
            st.session_state.weektable = edited
            st.success("Weekly Report saved successfully ✅")


# =============================
# ADMIN VIEW
# =============================

if menu == "View Reports":
    st.title("📊 Admin Report Dashboard")

    df = read_all_reports()

    if df.empty:
        st.warning("No reports submitted yet.")
    else:
        col1, col2, col3 = st.columns(3)

        with col1:
            period = st.selectbox(
                "Time Period",
                ["Weekly", "Monthly", "Quarterly", "Half-Yearly", "Yearly", "All"]
            )

        with col2:
            empf = st.selectbox(
                "Employee",
                ["All"] + sorted(df["employee"].unique())
            )

        with col3:
            deptf = st.selectbox(
                "Department",
                ["All"] + sorted(df["department"].unique())
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

        if empf != "All":
            df = df[df["employee"] == empf]

        if deptf != "All":
            df = df[df["department"] == deptf]

        st.metric("Total Activities", len(df))
        st.metric("Pending Tasks", int(df["pending"].sum()))

        st.subheader("By Employee")
        st.dataframe(
            df.groupby("employee").size().reset_index(name="Activities")
        )

        st.subheader("By Theme")
        st.dataframe(
            df.groupby("theme").size().reset_index(name="Activities")
        )

        st.subheader("Detailed Data")
        st.dataframe(df, use_container_width=True)

        # ==== CSV DOWNLOAD ====
        csv_data = df.to_csv(index=False)

        st.download_button(
            label="⬇️ Download filtered CSV",
            data=csv_data,
            file_name=f"weekly_reports_{date.today()}.csv",
            mime="text/csv",
        )
