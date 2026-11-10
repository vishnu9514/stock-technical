from __future__ import annotations

import os
import json
from datetime import date, datetime, time, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd
import streamlit as st


def _get_json(base_url: str, path: str, params: dict[str, str] | None = None):
    query = f"?{urlencode(params)}" if params else ""
    headers = {}
    if api_key := os.environ.get("KPI_API_KEY"):
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(f"{base_url.rstrip('/')}{path}{query}", headers=headers)
    with urlopen(request, timeout=15) as response:
        import json

        return json.load(response)


def _post_json(base_url: str, path: str, body: dict):
    headers = {"Content-Type": "application/json"}
    if api_key := os.environ.get("KPI_API_KEY"):
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def main() -> None:
    st.set_page_config(page_title="Engineering KPIs", layout="wide")
    st.title("Software Development KPI Monitoring")
    base_url = os.environ.get("KPI_API_URL", "http://127.0.0.1:8000")
    try:
        initial = _get_json(base_url, "/api/kpis/dashboard")
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        st.error(f"KPI API is unavailable at {base_url}: {error}")
        st.code("uvicorn kpi.api:app --reload", language="powershell")
        return

    all_measurements = initial["measurements"]
    projects = sorted({item["project_id"] for item in all_measurements})
    project = st.selectbox("Project", ["All projects", *projects])
    start_default = date.today() - timedelta(days=90)
    date_range = st.date_input("Date range", value=(start_default, date.today()))
    if not isinstance(date_range, tuple) or len(date_range) != 2:
        st.info("Select a start and end date.")
        return
    start = datetime.combine(date_range[0], time.min, tzinfo=timezone.utc).isoformat()
    end = datetime.combine(date_range[1] + timedelta(days=1), time.min, tzinfo=timezone.utc).isoformat()
    params = {"start": start, "end": end}
    if project != "All projects":
        params["project_id"] = project

    try:
        dashboard = _get_json(base_url, "/api/kpis/dashboard", params)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        st.error(f"Could not load the KPI dashboard: {error}")
        return
    rows = dashboard["measurements"]
    statuses = st.columns(5)
    statuses[0].metric("Total KPIs", dashboard["total_kpis"])
    statuses[1].metric("Excellent", dashboard["excellent_kpis"])
    statuses[2].metric("Warning", dashboard["warning_kpis"])
    statuses[3].metric("Critical", dashboard["critical_kpis"])
    statuses[4].metric("No data / target", sum(row["status"] == "NO_DATA" for row in rows))

    st.subheader("Engineering area scores")
    area_columns = st.columns(4)
    area_names = [
        "Software Quality",
        "Development Speed",
        "Reliability and Performance",
        "Engineering Productivity",
    ]
    for column, area in zip(area_columns, area_names):
        value = dashboard["area_scores"].get(area)
        column.metric(area, f"{value:.1f} / 100" if value is not None else "N/A")
    st.caption("Scores are capped, direction-aware actual-to-target ratios. Areas without configured targets show N/A.")

    with st.expander("Configure project-specific KPI targets"):
        try:
            catalog = _get_json(base_url, "/api/kpis/catalog")
            choices = {item["name"]: item for item in catalog}
            with st.form("kpi_target_form"):
                selected_name = st.selectbox("KPI", list(choices))
                project_default = project if project != "All projects" else ""
                target_project = st.text_input("Project identifier", value=project_default)
                st.caption(f"Better direction: {choices[selected_name]['direction']}")
                target_value = st.text_input("Target value (optional, for score only)")
                excellent = st.text_input("Excellent threshold")
                good = st.text_input("Good threshold")
                warning = st.text_input("Warning threshold")
                valid_from = st.date_input("Target effective from", value=date.today())
                submitted = st.form_submit_button("Save target")
                if submitted:
                    if not target_project.strip():
                        st.error("Enter a project identifier.")
                    elif not all(value.strip() for value in (excellent, good, warning)):
                        st.error("Enter all three status thresholds; targets are never defaulted.")
                    else:
                        try:
                            body = {
                                "project_id": target_project.strip(),
                                "kpi_id": choices[selected_name]["id"],
                                "target_value": float(target_value) if target_value.strip() else None,
                                "direction": choices[selected_name]["direction"],
                                "thresholds": {
                                    "excellent": float(excellent),
                                    "good": float(good),
                                    "warning": float(warning),
                                },
                                "valid_from": datetime.combine(
                                    valid_from, time.min, tzinfo=timezone.utc
                                ).isoformat(),
                            }
                            _post_json(base_url, "/api/kpis/targets", body)
                            st.success("Project KPI target saved.")
                        except (ValueError, HTTPError, URLError, TimeoutError, OSError) as error:
                            detail = error.read().decode() if isinstance(error, HTTPError) else str(error)
                            st.error(f"Could not save KPI target: {detail}")
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            st.error(f"Could not load the KPI catalog: {error}")

    st.subheader("KPI measurements")
    frame = pd.DataFrame(rows)
    if frame.empty:
        st.info("No measurements exist for this project and date range. No historical values have been fabricated.")
    else:
        displayed = frame[
            ["project_id", "area", "name", "period_end", "actual_value", "target_value", "status", "source"]
        ].rename(columns={
            "project_id": "Project",
            "area": "Area",
            "name": "KPI",
            "period_end": "Period end",
            "actual_value": "Actual",
            "target_value": "Target",
            "status": "Status",
            "source": "Data source",
        })
        st.dataframe(displayed, use_container_width=True, hide_index=True)
        st.download_button(
            "Export measurements to CSV",
            data=displayed.to_csv(index=False).encode("utf-8"),
            file_name="software_development_kpis.csv",
            mime="text/csv",
        )

        selected = st.selectbox(
            "Drill into KPI",
            sorted(frame["name"].dropna().unique()),
        )
        selected_row = frame.loc[frame["name"] == selected].iloc[0]
        trend_params = {"project_id": selected_row["project_id"], "kpi_id": selected_row["kpi_id"], "period": "weekly", **params}
        try:
            weekly = _get_json(base_url, "/api/kpis/trends", trend_params)
            st.caption("Weekly trend")
            trend_frame = pd.DataFrame(weekly)
            if not trend_frame.empty:
                trend_frame["period"] = pd.to_datetime(trend_frame["period"])
                st.line_chart(trend_frame.set_index("period")["actual_value"])
            else:
                st.info("No weekly history for this KPI in the selected range.")

            monthly = _get_json(base_url, "/api/kpis/trends", {**trend_params, "period": "monthly"})
            st.caption("Monthly comparison")
            monthly_frame = pd.DataFrame(monthly)
            if not monthly_frame.empty:
                st.bar_chart(monthly_frame.set_index("period")["actual_value"])
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            st.error(f"Could not load KPI trends: {error}")

        st.subheader("Alerts")
        try:
            alert_params = {} if project == "All projects" else {"project_id": project}
            alert_data = _get_json(base_url, "/api/kpis/alerts", alert_params)
            if alert_data:
                st.dataframe(pd.DataFrame(alert_data), use_container_width=True, hide_index=True)
            else:
                st.info("No warning or critical KPI alerts.")
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            st.error(f"Could not load KPI alerts: {error}")
