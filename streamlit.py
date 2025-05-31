import streamlit as st
import pandas as pd
import altair as alt
import time

# ─── PAGE CONFIGURATION ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="SQL Data Analytics Agent",
    layout="wide",             # use full‐width layout
    initial_sidebar_state="auto"
)

# ─── INJECT CUSTOM CSS ────────────────────────────────────────────────────────
# (applies gradient background, rounded corners, and slide‐up animation)
st.markdown(
    """
    <style>
    /* Global reset */
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }

    /* Body & container styling */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        min-height: 100vh;
        display: flex;
        justify-content: center;
        align-items: flex-start;
        padding: 20px;
    }
    .container {
        background: white;
        border-radius: 20px;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
        width: 100%;
        max-width: 1400px;
        animation: slideUp 0.6s ease-out;
        display: flex;
    }
    @keyframes slideUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* SIDEBAR: override default to remove its own background & padding */
    .css-1d391kg {  /* this class targets stSidebar (Streamlit auto‐generated) */
        background-color: transparent !important;
        padding: 0 !important;
        border: none !important;
    }
    .sidebar-content {
        width: 300px;
        background: #fff;
        border-right: 1px solid #e9ecef;
        display: flex;
        flex-direction: column;
        padding: 20px;
    }
    .sidebar-content h1 {
        font-size: 1.5rem;
        margin-bottom: 20px;
        text-align: center;
        color: #2c3e50;
        font-weight: 300;
    }
    .spacer {
        flex-grow: 1;
    }

    /* Collapsible query section styling */
    .query-section {
        background: #f8f9fa;
        border-radius: 15px;
        border: 2px solid #e9ecef;
        padding: 20px;
        transition: all 0.3s ease;
    }
    .query-section:hover {
        border-color: #3498db;
        box-shadow: 0 10px 25px rgba(52, 152, 219, 0.1);
    }
    .query-section label {
        display: block;
        margin-bottom: 8px;
        font-weight: 600;
        color: #555;
    }
    .query-section textarea, .query-section select {
        width: 100%;
        padding: 12px 15px;
        border: 2px solid #ddd;
        border-radius: 10px;
        font-size: 1rem;
        margin-bottom: 20px;
        transition: all 0.3s ease;
        font-family: inherit;
    }
    .query-section textarea {
        resize: vertical;
        min-height: 120px;
        font-family: 'Courier New', monospace;
    }
    .query-section textarea:focus,
    .query-section select:focus {
        outline: none;
        border-color: #3498db;
        box-shadow: 0 0 10px rgba(52, 152, 219, 0.2);
    }

    /* BUTTON */
    .btn {
        background: linear-gradient(135deg, #3498db, #2980b9);
        color: white !important;
        border: none !important;
        padding: 15px 30px !important;
        border-radius: 10px !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        cursor: pointer !important;
        transition: all 0.3s ease !important;
        width: 100% !important;
        text-align: center !important;
    }
    .btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(52, 152, 219, 0.3);
    }
    .btn:active {
        transform: translateY(0);
    }
    .btn:disabled {
        background: #aaa !important;
        cursor: not-allowed !important;
    }

    /* STATUS MESSAGES */
    .status {
        padding: 15px !important;
        border-radius: 10px !important;
        margin-top: 20px !important;
        margin-bottom: 0 !important;
        font-weight: 600 !important;
    }
    .status-loading {
        background: #e3f2fd !important;
        color: #1976d2 !important;
        border-left: 5px solid #1976d2 !important;
    }
    .status-error {
        background: #ffebee !important;
        color: #c62828 !important;
        border-left: 5px solid #c62828 !important;
    }
    .status-success {
        background: #e8f5e8 !important;
        color: #2e7d32 !important;
        border-left: 5px solid #2e7d32 !important;
    }

    /* MAIN CONTENT */
    .main-content {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
        margin: 20px;
    }
    .results-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
        height: 100%;
        width: 100%;
    }
    .sql-display {
        background: #2c3e50;
        color: #ecf0f1;
        padding: 20px;
        border-radius: 10px;
        font-family: 'Courier New', monospace;
        font-size: 0.9rem;
        line-height: 1.5;
        overflow-x: auto;
        margin-bottom: 20px;
        max-height: 20%;
        width: 100%;
    }
    .data-table {
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0;
        background: white;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08);
    }
    .data-table th {
        background: linear-gradient(135deg, #3498db, #2980b9);
        color: white;
        padding: 15px;
        text-align: left;
        font-weight: 600;
    }
    .data-table td {
        padding: 12px 15px;
        border-bottom: 1px solid #eee;
    }
    .data-table tr:hover {
        background: #f8f9fa;
    }

    .chart-container {
        background: white;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08);
        width: 100%;
        height: 100%;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── LAYOUT: FLEX CONTAINER ────────────────────────────────────────────────────
# We’ll place everything inside a single “div.container” so the CSS above can apply.
# Use st.markdown() with <div class="container"> … </div> wrappers.

st.markdown('<div class="container">', unsafe_allow_html=True)

# ─── SIDEBAR EMULATION ────────────────────────────────────────────────────────
# Streamlit’s native sidebar sits outside the main <div> – we want everything in a single flex container.
# Therefore, create a “sidebar” column manually inside our container using st.columns().
col_sidebar, col_main = st.columns([1, 3], gap="small")

with col_sidebar:
    st.markdown('<div class="sidebar-content">', unsafe_allow_html=True)
    st.markdown('<h1>SQL Agent</h1>', unsafe_allow_html=True)

    # Spacer to push the expander to the bottom
    st.markdown('<div class="spacer"></div>', unsafe_allow_html=True)

    # Collapsible query section (using Streamlit Expander inside a styled wrapper)
    st.markdown('<details>', unsafe_allow_html=True)
    st.markdown(
        '<summary class="summary-title">Business Question</summary>', 
        unsafe_allow_html=True
    )

    # Inside <details>, render the form inputs and button
    st.markdown('<div class="query-section">', unsafe_allow_html=True)
    question = st.text_area("Enter your question:", value="Which 10 products have generated the most revenue?", key="question")
    database = st.selectbox("Database:", ["Northwind", "Chinook", "Sakila"], key="database")
    run_btn = st.button("Analyze", key="analyze")
    status_placeholder = st.empty()  # for status messages
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</details>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ─── MAIN CONTENT AREA ────────────────────────────────────────────────────────
with col_main:
    st.markdown('<div class="main-content">', unsafe_allow_html=True)

    # Placeholder for results (initially hidden)
    results_container = st.container()

    # If “Analyze” was clicked, simulate the query and show results
    if run_btn:
        # 1) Show loading status
        status_placeholder.markdown('<div class="status status-loading">Running analysis...</div>', unsafe_allow_html=True)
        time.sleep(1)  # simulate processing delay

        # 2) Generate mock SQL & data (same as your HTML example)
        if "revenue" in question.lower():
            sql_code = (
                "SELECT p.ProductName, \n"
                "       ROUND(SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)), 2) AS Revenue\n"
                "FROM Products p\n"
                "JOIN OrderDetails od ON p.ProductID = od.ProductID\n"
                "GROUP BY p.ProductID, p.ProductName\n"
                "ORDER BY Revenue DESC\n"
                "LIMIT 10;"
            )
            data = [
                {"ProductName": "Côte de Blaye", "Revenue": 150000},
                {"ProductName": "Thüringer Rostbratwurst", "Revenue": 88000},
                {"ProductName": "Raclette Courdavault", "Revenue": 76000},
                {"ProductName": "Camembert Pierrot", "Revenue": 50000},
                {"ProductName": "Gnocchi di nonna Alice", "Revenue": 50000},
                {"ProductName": "Perth Pasties", "Revenue": 44000},
                {"ProductName": "Tarte au sucre", "Revenue": 47000},
                {"ProductName": "Manjimup Dried Apples", "Revenue": 44000},
                {"ProductName": "Carnarvon Tigers", "Revenue": 36000},
                {"ProductName": "Ikura", "Revenue": 32000},
            ]
        else:
            sql_code = ""
            data = []

        # 3) Show success status and clear after a moment
        status_placeholder.markdown('<div class="status status-success">Analysis done.</div>', unsafe_allow_html=True)
        time.sleep(1.5)
        status_placeholder.empty()

        # 4) Render the “results grid”:
        with results_container:
            st.markdown('<div class="results-grid">', unsafe_allow_html=True)

            # ─── LEFT PANEL: SQL Display & Data Table ────────────────────────────
            left_col, right_col = st.columns([1, 1], gap="small")
            with left_col:
                # SQL block
                st.markdown(f'<div class="sql-display"><pre>{sql_code}</pre></div>', unsafe_allow_html=True)

                # Data table
                if data:
                    df = pd.DataFrame(data)
                    # Format revenue with thousands separators
                    df["Revenue"] = df["Revenue"].map(lambda x: f"{x:,}")
                    table_html = (
                        '<table class="data-table"><thead><tr>'
                        + "".join(f"<th>{col}</th>" for col in df.columns)
                        + "</tr></thead><tbody>"
                    )
                    for _, row in df.iterrows():
                        table_html += "<tr>" + "".join(f"<td>{row[col]}</td>" for col in df.columns) + "</tr>"
                    table_html += "</tbody></table>"

                    st.markdown(table_html, unsafe_allow_html=True)
                else:
                    st.markdown("<p>No data.</p>", unsafe_allow_html=True)

            # ─── RIGHT PANEL: Chart ────────────────────────────────────────────────
            with right_col:
                if data:
                    df_chart = pd.DataFrame(data)
                    # Shorten long product names for the x‐axis
                    df_chart["ShortName"] = df_chart["ProductName"].apply(
                        lambda s: s if len(s) <= 10 else s[:10] + "..."
                    )

                    chart = (
                        alt.Chart(df_chart)
                        .mark_bar(color="rgba(52, 152, 219, 0.6)", stroke="rgba(52, 152, 219, 1)")
                        .encode(
                            x=alt.X("ShortName", sort=None, title=None),
                            y=alt.Y("Revenue:Q", title="Revenue"),
                            tooltip=["ProductName", "Revenue"],
                        )
                        .properties(width="100%", height=400)
                        .configure_axis(
                            labelFontSize=10,
                            titleFontSize=12,
                            grid=False,
                        )
                        .configure_view(strokeWidth=0)
                    )
                    st.altair_chart(chart, use_container_width=True)
                else:
                    st.markdown("<p style='text-align:center;'>No chart available.</p>", unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
