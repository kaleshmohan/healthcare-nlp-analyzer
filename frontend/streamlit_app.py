import streamlit as st
import requests
import pandas as pd
from collections import defaultdict

st.set_page_config(
    page_title="Healthcare NLP Analyzer",
    page_icon="🏥",
    layout="wide"
)

BACKEND_URL = "http://backend:8000/analyze"

st.markdown("""
<style>
.main > div {
    padding-top: 1.5rem;
}
.metric-card {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 14px;
    padding: 18px 14px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.18);
}
.metric-icon {
    font-size: 30px;
    margin-bottom: 6px;
}
.metric-title {
    font-size: 15px;
    color: #cbd5e1;
    margin-bottom: 8px;
    font-weight: 600;
}
.metric-value {
    font-size: 34px;
    font-weight: 700;
    color: white;
}
.report-box {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 16px;
    margin-top: 10px;
    margin-bottom: 12px;
}
.small-muted {
    color: #94a3b8;
    font-size: 14px;
}
</style>
""", unsafe_allow_html=True)


def group_codes(links):
    codes = defaultdict(list)
    for link in links or []:
        source = link.get("dataSource", "")
        code_id = link.get("id", "")
        if source and code_id:
            codes[source].append(code_id)
    return dict(codes)


def first_code(codes_dict, key):
    values = codes_dict.get(key, [])
    return ", ".join(values[:3]) if values else ""


def parse_result(data):
    documents = data.get("documents", [])
    if not documents:
        return [], [], [], [], [], [], data.get("modelVersion", "")

    doc = documents[0]
    entities = doc.get("entities", [])
    relations = doc.get("relations", [])
    warnings = doc.get("warnings", [])
    model_version = data.get("modelVersion", "")

    diagnoses = []
    medications = []
    symptoms = []
    others = []

    for entity in entities:
        category = entity.get("category", "")
        links = entity.get("links", [])
        codes = group_codes(links)

        record = {
            "Mention": entity.get("text", ""),
            "Normalized Name": entity.get("name", ""),
            "Category": category,
            "Confidence": round(entity.get("confidenceScore", 0), 2),
            "ICD10": first_code(codes, "ICD10"),
            "SNOMEDCT_US": first_code(codes, "SNOMEDCT_US"),
            "UMLS": first_code(codes, "UMLS"),
            "DrugBank": first_code(codes, "DRUGBANK"),
            "All Codes": codes,
        }

        if category in {"Diagnosis", "Condition"}:
            diagnoses.append(record)
        elif category in {"MedicationName"}:
            medications.append(record)
        elif category in {"SymptomOrSign"}:
            symptoms.append(record)
        else:
            others.append(record)

    return diagnoses, medications, symptoms, others, relations, warnings, model_version


def make_summary(diagnoses, medications, symptoms):
    parts = []

    if diagnoses:
        dx_names = [d["Normalized Name"] or d["Mention"] for d in diagnoses]
        parts.append(f"Detected diagnoses: {', '.join(dx_names)}.")

    if medications:
        med_names = [m["Normalized Name"] or m["Mention"] for m in medications]
        parts.append(f"Detected medications: {', '.join(med_names)}.")

    if symptoms:
        sym_names = [s["Normalized Name"] or s["Mention"] for s in symptoms]
        parts.append(f"Detected symptoms/signs: {', '.join(sym_names)}.")

    if not parts:
        return "No major diagnoses, medications, or symptoms were extracted from the note."

    return " ".join(parts)


def display_table(title, rows, preferred_cols):
    st.markdown(f"### {title}")
    if not rows:
        st.info(f"No {title.lower()} found.")
        return
    df = pd.DataFrame(rows)
    show_cols = [c for c in preferred_cols if c in df.columns]
    st.dataframe(df[show_cols], use_container_width=True, hide_index=True)


def metric_card(column, icon, title, value):
    column.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-icon">{icon}</div>
            <div class="metric-title">{title}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


st.title("🏥 Clinical NLP Report")
st.markdown(
    '<div class="small-muted">Paste clinical text, analyze it, and generate a structured clinical extraction report.</div>',
    unsafe_allow_html=True
)

input_text = st.text_area(
    "Clinical text",
    height=220,
    placeholder="Example: The patient was diagnosed with diabetes and prescribed insulin."
)

analyze = st.button("Analyze", type="primary")

if analyze:
    if not input_text.strip():
        st.warning("Please enter some clinical text.")
    else:
        try:
            response = requests.post(
                BACKEND_URL,
                json={"text": input_text},
                timeout=60
            )
            response.raise_for_status()
            data = response.json()

            diagnoses, medications, symptoms, others, relations, warnings, model_version = parse_result(data)
            summary_text = make_summary(diagnoses, medications, symptoms)

            st.markdown("## 📋 Extraction Overview")
            col1, col2, col3, col4 = st.columns(4)
            metric_card(col1, "🩺", "Diagnoses", len(diagnoses))
            metric_card(col2, "💊", "Medications", len(medications))
            metric_card(col3, "🤒", "Symptoms", len(symptoms))
            metric_card(col4, "📊", "Other Entities", len(others))

            st.markdown("## 🧠 Narrative Summary")
            st.markdown(
                f'<div class="report-box">{summary_text}</div>',
                unsafe_allow_html=True
            )

            st.markdown("## 📝 Source Text")
            st.code(input_text, language="text")

            display_table(
                "🩺 Diagnoses",
                diagnoses,
                ["Mention", "Normalized Name", "Confidence", "ICD10", "SNOMEDCT_US", "UMLS"]
            )

            display_table(
                "💊 Medications",
                medications,
                ["Mention", "Normalized Name", "Confidence", "DrugBank", "SNOMEDCT_US", "UMLS"]
            )

            display_table(
                "🤒 Symptoms / Signs",
                symptoms,
                ["Mention", "Normalized Name", "Confidence", "SNOMEDCT_US", "UMLS"]
            )

            with st.expander("📊 Other Extracted Entities"):
                if others:
                    df_others = pd.DataFrame(others)
                    st.dataframe(
                        df_others[["Mention", "Normalized Name", "Category", "Confidence"]],
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No additional entities found.")

            with st.expander("🔗 Relations"):
                if relations:
                    st.json(relations)
                else:
                    st.info("No relations detected.")

            with st.expander("⚠️ Warnings"):
                if warnings:
                    st.json(warnings)
                else:
                    st.info("No warnings.")

            with st.expander("🔍 Raw JSON"):
                st.json(data)

            report_text = f"""
CLINICAL NLP EXTRACTION REPORT

Input Text:
{input_text}

Summary:
{summary_text}

Diagnoses Found: {len(diagnoses)}
Medications Found: {len(medications)}
Symptoms Found: {len(symptoms)}
Other Entities Found: {len(others)}

Model Version:
{model_version}
""".strip()

            st.download_button(
                label="Download Report Summary (.txt)",
                data=report_text,
                file_name="clinical_nlp_report.txt",
                mime="text/plain"
            )

        except requests.exceptions.RequestException as e:
            st.error(f"Request failed: {e}")
        except Exception as e:
            st.error(f"Unexpected error: {e}")