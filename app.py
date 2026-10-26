"""APAAR ID based Student Data Management & Verification Platform  (SIH PS 26263 prototype)
Run:  streamlit run app.py
"""
import os
import pandas as pd
import streamlit as st

from core import db, validation, anomaly, qr, auth, seed, apaar_mock
from core.db import CURRENT_YEAR

st.set_page_config(page_title="APAAR Student Data Platform", page_icon="🎓", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1.5rem;}
[data-testid="stSidebar"] {background: linear-gradient(180deg,#312E81 0%,#4F46E5 60%,#7C3AED 100%);}
[data-testid="stSidebar"] * {color: #ffffff !important;}
[data-testid="stSidebar"] .stButton button {background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.4);}
[data-testid="stMetric"] {background:#fff; border-left:6px solid #4F46E5; border-radius:14px;
    padding:14px 16px; box-shadow:0 4px 14px rgba(79,70,229,.12);}
[data-testid="stMetric"]:nth-child(2n) {border-left-color:#F59E0B;}
[data-testid="stMetricValue"] {color:#312E81;}
.hero {background: linear-gradient(120deg,#4F46E5,#7C3AED 55%,#EC4899); color:#fff; padding:22px 28px;
    border-radius:18px; margin-bottom:18px; box-shadow:0 8px 24px rgba(124,58,237,.30);}
.hero h1 {color:#fff; margin:0; font-size:2rem;}
.hero p {margin:4px 0 0 0; opacity:.92;}
.hero .tag {display:inline-block; background:rgba(255,255,255,.22); border-radius:20px; padding:2px 12px;
    font-size:.78rem; margin-right:6px; margin-top:10px;}
h2, h3 {color:#312E81;}
div[data-testid="stVerticalBlockBorderWrapper"] {border-radius:14px; border-color:#C7D2FE; background:#fff;}
.stButton button[kind="primary"] {background:linear-gradient(90deg,#4F46E5,#7C3AED); border:none; border-radius:10px;}
</style>
""", unsafe_allow_html=True)


def hero(title, sub, tags=()):
    chips = "".join(f'<span class="tag">{t}</span>' for t in tags)
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{sub}</p>{chips}</div>', unsafe_allow_html=True)


if not os.path.exists(db.DB_PATH):
    seed.run()
db.init_db()

SAMPLE_DIR = os.path.join(db.DATA_DIR, "sample_uploads")


def mask(a: str) -> str:
    return f"{a[:4]}••••••{a[-2:]}" if a and len(a) == 12 else a


# ───────────────────────── Login ─────────────────────────
def login_view():
    hero("🎓 APAAR-based Student Data Platform",
         "Verified, duplicate-free student records for AICTE-approved institutions",
         ["AICTE", "SIH PS 26263", "Synthetic data only", "Explainable AI flags"])
    t1, t2 = st.tabs(["🔐 Login", "🧑‍🎓 Student sign-up"])
    with t1:
        with st.form("login"):
            u = st.text_input("Username (students: your 12-digit APAAR ID)")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Login", type="primary"):
                user = auth.authenticate(u, p)
                if user:
                    st.session_state.user = user
                    db.log(user["username"], user["role"], "LOGIN")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
    with t2:
        st.caption("Optional – students can create their own account with APAAR ID + date of birth "
                   "(mock of the APAAR OTP verification) and submit their own admission details.")
        with st.form("signup"):
            a = st.text_input("APAAR ID (12 digits)")
            d = st.text_input("Date of birth (YYYY-MM-DD)")
            p1 = st.text_input("Create password (min 6 characters)", type="password")
            if st.form_submit_button("Create student account", type="primary"):
                c = db.get_conn()
                rec = apaar_mock.lookup(c, a.strip())
                if not rec or rec["dob"] != d.strip():
                    st.error("Details do not match the APAAR registry.")
                elif len(p1) < 6:
                    st.error("Password must be at least 6 characters.")
                elif c.execute("SELECT 1 FROM users WHERE username=?", (a.strip(),)).fetchone():
                    st.error("An account already exists for this APAAR ID. Please log in.")
                else:
                    db.add_user(c, a.strip(), p1, "student")
                    c.commit()
                    db.log(a.strip(), "student", "STUDENT_SIGNUP", mask(a.strip()))
                    st.success("Account created. Go to the Login tab and sign in with your APAAR ID.")
    with st.expander("Demo credentials"):
        st.table(pd.DataFrame([
            ["admin", "aicte123", "AICTE officer – sees everything"],
            ["clg012", "college123", "College (CLG012) – has the sample upload file"],
            ["clg001 … clg011", "college123", "Other colleges (clg001 approves student submissions below)"],
            ["employer", "verifier123", "Employer / verifier – only QR verification"],
        ], columns=["Username", "Password", "Role"]))
        dp = os.path.join(db.DATA_DIR, "demo_students.csv")
        if os.path.exists(dp):
            st.markdown("**Demo students** (username = APAAR ID)")
            st.dataframe(pd.read_csv(dp, dtype=str), hide_index=True, width="stretch")


# ───────────────────────── Step 3: Upload ─────────────────────────
def page_upload(user):
    inst = user["inst_id"]
    c = db.get_conn()
    row = c.execute("SELECT * FROM institutions WHERE inst_id=?", (inst,)).fetchone()
    st.header("Upload student data")
    st.write(f"**{row['name']}** ({inst}) · {row['state']} · Approved intake: **{row['approved_intake']}** · Year: **{CURRENT_YEAR}**")

    c1, c2 = st.columns(2)
    with c1:
        st.download_button("⬇ CSV template", open(os.path.join(SAMPLE_DIR, "template.csv"), "rb").read(), "template.csv")
    with c2:
        sp = os.path.join(SAMPLE_DIR, "CLG012_sample_upload.csv")
        if inst == "CLG012" and os.path.exists(sp):
            st.download_button("⬇ Sample file with deliberate errors", open(sp, "rb").read(), "CLG012_sample_upload.csv")

    f = st.file_uploader("Upload CSV (apaar_id, name, branch, category, nri, oci, fn, supernumerary)", type="csv")
    if f is None:
        return
    try:
        df = pd.read_csv(f, dtype=str)
        issues, clean, summ = validation.validate(df, inst, CURRENT_YEAR, c)
    except Exception as e:
        st.error(str(e))
        return
    db.log(user["username"], "college", "VALIDATE_UPLOAD", f"{inst}: {summ}")

    m = st.columns(5)
    m[0].metric("Rows", summ["total"])
    m[1].metric("Accepted", summ["clean"])
    m[2].metric("Errors", summ["errors"])
    m[3].metric("Warnings", summ["warnings"])
    m[4].metric("Intake alert", "YES" if summ["flags"] else "No")

    if issues.empty:
        st.success("No issues found.")
    else:
        st.subheader("Validation report")
        issues = issues.assign(meaning=issues["code"].map(validation.CODES))
        st.dataframe(issues, width="stretch", hide_index=True)
        st.download_button("⬇ Download report", issues.to_csv(index=False).encode(), "validation_report.csv")
        st.caption("ERROR = row rejected · WARNING = stored but needs review · FLAG = batch level alert for AICTE")

    if st.button(f"Submit {summ['clean']} valid rows to AICTE repository", type="primary", disabled=summ["clean"] == 0):
        n = validation.commit(clean, inst, CURRENT_YEAR, c)
        db.log(user["username"], "college", "SUBMIT_DATA", f"{inst}: {n} rows stored, {summ['errors']} rejected")
        st.success(f"{n} records stored. Rejected rows must be corrected and re-uploaded.")


# ───────────────────────── Step 4: Dashboard ─────────────────────────
def page_dashboard(user):
    c = db.get_conn()
    stats = anomaly.institution_stats(c, CURRENT_YEAR)
    if user["role"] == "college":
        stats = stats[stats.inst_id == user["inst_id"]]
    st.header("Admissions monitoring dashboard" if user["role"] == "aicte" else "My institution dashboard")

    if user["role"] == "aicte":
        states = ["All"] + sorted(stats.state.unique())
        sel = st.selectbox("State", states)
        if sel != "All":
            stats = stats[stats.state == sel]

    k = st.columns(4)
    k[0].metric("Institutions", len(stats))
    k[1].metric("Students on record", int(stats.enrolled.sum()))
    k[2].metric("Institutions above intake", int((stats.excess > 0).sum()))
    k[3].metric("Double-enrolled students", int(stats.cross_dups.sum()) if user["role"] == "aicte" else int(stats.cross_dups.sum()))

    chart = stats.set_index("inst_id")[["intake", "regular"]].rename(columns={"intake": "Approved intake", "regular": "Regular enrolled"})
    st.subheader("Approved intake vs actual regular enrolment")
    st.bar_chart(chart, color=["#4F46E5", "#F59E0B"])

    st.subheader("Institution table")
    view = stats[["inst_id", "college", "state", "intake", "regular", "supernumerary", "excess", "cross_dups"]].rename(
        columns={"inst_id": "ID", "college": "College", "state": "State", "intake": "Intake", "regular": "Regular",
                 "supernumerary": "Supernumerary", "excess": "Excess over intake", "cross_dups": "Double enrolled"})
    st.dataframe(view.style.map(lambda v: "background-color:#fecaca;color:#991b1b;font-weight:600" if isinstance(v, (int, float)) and v > 0 else "",
                                subset=["Excess over intake", "Double enrolled"]),
                 width="stretch", hide_index=True)

    dup = pd.read_sql(
        "SELECT s.apaar_id, s.name, GROUP_CONCAT(s.inst_id) AS institutions FROM students s WHERE s.year=? "
        "GROUP BY s.apaar_id HAVING COUNT(DISTINCT s.inst_id)>1", c, params=(CURRENT_YEAR,))
    if user["role"] == "college":
        dup = dup[dup.institutions.str.contains(user["inst_id"])]
    with st.expander(f"Students enrolled in more than one institution ({len(dup)})"):
        dup["apaar_id"] = dup["apaar_id"].map(mask)
        st.dataframe(dup, width="stretch", hide_index=True)


# ───────────────────────── Step 7: Anomalies ─────────────────────────
def page_anomaly(user):
    st.header("Anomaly detection")
    st.caption("Robust z-score vs peer institutions gives the reason; Isolation Forest gives an overall outlier score. "
               "Flags are decision-support only – final action stays with AICTE officials.")
    c = db.get_conn()
    res = anomaly.detect(anomaly.institution_stats(c, CURRENT_YEAR))
    flagged = res[res.anomaly]
    st.metric("Institutions flagged", len(flagged))
    for r in flagged.itertuples():
        with st.container(border=True):
            st.markdown(f"**{r.inst_id} · {r.college}** ({r.state}) — outlier score `{r.iso_score:.2f}`")
            for reason in r.reasons.split(" | "):
                st.write("• " + reason)
    st.subheader("Outlier score for all institutions")
    st.bar_chart(res.set_index("inst_id")["iso_score"], color="#EF4444")


# ───────────────────────── Step 5: Records + QR ─────────────────────────
def page_records(user):
    st.header("Student records & verifiable QR")
    c = db.get_conn()
    if user["role"] == "college":
        inst = user["inst_id"]
    else:
        opts = [r[0] for r in c.execute("SELECT inst_id FROM institutions ORDER BY inst_id")]
        inst = st.selectbox("Institution", opts)
    df = pd.read_sql("SELECT apaar_id,name,branch,category,nri,oci,fn,supernumerary,consent FROM students "
                     "WHERE inst_id=? AND year=?", c, params=(inst, CURRENT_YEAR))
    if df.empty:
        st.info("No student records yet for this institution.")
        return
    q = st.text_input("Search by name or APAAR ID")
    if q:
        df = df[df.name.str.contains(q, case=False) | df.apaar_id.str.contains(q)]
    show = df.assign(apaar_id=df.apaar_id.map(mask))
    st.dataframe(show.head(300), width="stretch", hide_index=True)

    st.subheader("Generate QR for a student")
    if df.empty:
        return
    pick = st.selectbox("Student", df.head(200).apply(lambda r: f"{r['apaar_id']} · {r['name']}", axis=1))
    apaar = pick.split(" · ")[0]
    rec = df[df.apaar_id == apaar].iloc[0]
    token = qr.make_token(apaar, inst, CURRENT_YEAR)
    c1, c2 = st.columns([1, 2])
    c1.image(qr.qr_png(token), width=220)
    c2.code(token)
    c2.caption("Verifier opens 'Verify Student' and scans / pastes this code. Data is shown only if the student has consented.")
    consent = c2.checkbox("Student consent given (simulated – real flow would go through APAAR / DigiLocker)",
                          value=bool(rec["consent"]), key=f"cons_{apaar}")
    if consent != bool(rec["consent"]):
        c.execute("UPDATE students SET consent=? WHERE apaar_id=? AND inst_id=? AND year=?",
                  (int(consent), apaar, inst, CURRENT_YEAR))
        c.commit()
        db.log(user["username"], user["role"], "CONSENT_CHANGE", f"{mask(apaar)} -> {consent}")
        st.rerun()


# ───────────────────────── Verification ─────────────────────────
def page_verify(user):
    st.header("Verify a student record")
    token = st.text_input("Paste QR code text", placeholder="APAAR.123456789012.CLG001.2026.abcdef123456")
    if not token:
        return
    parsed = qr.parse_token(token)
    if not parsed:
        db.log(user["username"], user["role"], "VERIFY_FAILED", "invalid/tampered token")
        st.error("❌ Invalid or tampered QR code. Do not trust this record.")
        return
    apaar, inst, year = parsed
    c = db.get_conn()
    r = c.execute("SELECT s.*, i.name AS college FROM students s JOIN institutions i ON i.inst_id=s.inst_id "
                  "WHERE s.apaar_id=? AND s.inst_id=? AND s.year=?", (apaar, inst, year)).fetchone()
    if not r:
        db.log(user["username"], user["role"], "VERIFY_NOT_FOUND", mask(apaar))
        st.error("❌ Signature is valid but no matching enrolment record exists.")
        return
    if not r["consent"]:
        db.log(user["username"], user["role"], "VERIFY_CONSENT_DENIED", mask(apaar))
        st.warning("🔒 Student has not given consent to share this record. A consent request would be sent via APAAR.")
        return
    db.log(user["username"], user["role"], "VERIFY_OK", f"{mask(apaar)} @ {inst}")
    st.success("✅ Verified – enrolment record is authentic")
    st.table(pd.DataFrame({"Field": ["APAAR ID", "Name", "Institution", "Branch", "Admission year"],
                           "Value": [mask(apaar), r["name"], r["college"], r["branch"], year]}))
    st.caption("Only minimum necessary fields are shown. This access has been written to the audit log.")


# ───────────────────────── Student portal (optional self-service) ─────────────────────────
def page_student(user):
    c = db.get_conn()
    apaar = user["username"]
    rec = apaar_mock.lookup(c, apaar)
    if not rec:
        st.error("APAAR ID not found in registry.")
        return
    st.header("Student portal")
    st.write(f"**{rec['name']}** · APAAR ID `{mask(apaar)}`")
    tab1, tab2, tab3 = st.tabs(["📝 Submit my details", "📄 My submissions", "🔒 Consent & QR"])
    insts = pd.read_sql("SELECT inst_id,name FROM institutions ORDER BY inst_id", c)
    labels = {r.inst_id: f"{r.inst_id} · {r.name}" for r in insts.itertuples()}

    with tab1:
        st.caption("Optional – use this if your college has not uploaded your record or to correct it. "
                   "Your college must approve it before it enters the AICTE repository.")
        inst = st.selectbox("Institution", list(labels), format_func=labels.get)
        name = st.text_input("Name as per admission record", value=rec["name"])
        c1, c2 = st.columns(2)
        branch = c1.selectbox("Branch", seed.BRANCHES)
        cat = c2.selectbox("Category", seed.CATS)
        k = st.columns(3)
        nri, oci, fn = k[0].checkbox("NRI"), k[1].checkbox("OCI"), k[2].checkbox("Foreign National")
        doc = st.file_uploader("Proof (admission letter / ID card) – PDF, PNG or JPG, max 2 MB",
                               type=["pdf", "png", "jpg", "jpeg"])
        if st.button("Submit to my college", type="primary"):
            if doc is not None and doc.size > 2 * 1024 * 1024:
                st.error("File is larger than 2 MB.")
            else:
                sup = int(nri or oci or fn)
                row = pd.DataFrame([{"apaar_id": apaar, "name": name, "branch": branch, "category": cat,
                                     "nri": int(nri), "oci": int(oci), "fn": int(fn), "supernumerary": sup}])
                issues, clean, _ = validation.validate(row, inst, CURRENT_YEAR, c)
                issues = issues[issues.severity != "FLAG"]
                if (issues.severity == "ERROR").any():
                    st.error("Your submission has problems:")
                    st.dataframe(issues.assign(meaning=issues.code.map(validation.CODES)), hide_index=True, width="stretch")
                    db.log(apaar, "student", "SUBMISSION_REJECTED", ", ".join(issues.code))
                else:
                    for w in issues.itertuples():
                        st.warning(w.reason)
                    c.execute("DELETE FROM submissions WHERE apaar_id=? AND year=? AND status='PENDING'", (apaar, CURRENT_YEAR))
                    c.execute("INSERT INTO submissions(apaar_id,name,inst_id,year,branch,category,nri,oci,fn,supernumerary,"
                              "doc_name,doc_blob,status,ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'PENDING',datetime('now','localtime'))",
                              (apaar, name, inst, CURRENT_YEAR, branch, cat, int(nri), int(oci), int(fn), sup,
                               doc.name if doc else None, doc.getvalue() if doc else None))
                    c.commit()
                    db.log(apaar, "student", "SUBMISSION_SENT", f"to {inst}")
                    st.success(f"Sent to {labels[inst]} for approval.")

    with tab2:
        sub = pd.read_sql("SELECT ts,inst_id,branch,category,doc_name,status,remark FROM submissions "
                          "WHERE apaar_id=? ORDER BY id DESC", c, params=(apaar,))
        if sub.empty:
            st.info("You have not submitted anything yet.")
        else:
            st.dataframe(sub, hide_index=True, width="stretch")

    with tab3:
        recs = pd.read_sql("SELECT s.inst_id, i.name AS college, s.year, s.consent FROM students s "
                           "JOIN institutions i ON i.inst_id=s.inst_id WHERE s.apaar_id=? ORDER BY s.year DESC",
                           c, params=(apaar,))
        if recs.empty:
            st.info("No approved enrolment record yet. After your college approves your submission, your QR and consent switch appear here.")
        for r in recs.itertuples():
            with st.container(border=True):
                a, b = st.columns([1, 2])
                token = qr.make_token(apaar, r.inst_id, r.year)
                a.image(qr.qr_png(token), width=190)
                b.markdown(f"**{r.college}** ({r.inst_id}) · {r.year}")
                b.code(token)
                on = b.checkbox("Allow verifiers to see my enrolment record", value=bool(r.consent), key=f"sc_{r.inst_id}_{r.year}")
                if on != bool(r.consent):
                    c.execute("UPDATE students SET consent=? WHERE apaar_id=? AND inst_id=? AND year=?",
                              (int(on), apaar, r.inst_id, r.year))
                    c.commit()
                    db.log(apaar, "student", "CONSENT_CHANGE", f"{r.inst_id} -> {on}")
                    st.rerun()


def page_submissions(user):
    c = db.get_conn()
    inst = user["inst_id"]
    st.header("Student self-submissions")
    df = pd.read_sql("SELECT * FROM submissions WHERE inst_id=? ORDER BY CASE status WHEN 'PENDING' THEN 0 ELSE 1 END, id DESC",
                     c, params=(inst,))
    pending = df[df.status == "PENDING"]
    st.metric("Pending approvals", len(pending))
    if pending.empty:
        st.info("No pending student submissions.")
    for r in pending.itertuples():
        with st.container(border=True):
            tags = [t for t, v in (("NRI", r.nri), ("OCI", r.oci), ("FN", r.fn)) if v]
            st.markdown(f"**{r.name}** · `{mask(r.apaar_id)}` · {r.branch} · {r.category}"
                        f"{' · ' + '/'.join(tags) if tags else ''}  \nSubmitted {r.ts}")
            if isinstance(r.doc_blob, (bytes, bytearray)):
                st.download_button(f"⬇ {r.doc_name}", bytes(r.doc_blob), r.doc_name, key=f"d{r.id}")
            else:
                st.caption("No proof document attached.")
            remark = st.text_input("Remark (required to reject)", key=f"rm{r.id}")
            a, b = st.columns(2)
            if a.button("✅ Approve & add to repository", key=f"ap{r.id}", type="primary"):
                row = pd.DataFrame([{"apaar_id": r.apaar_id, "name": r.name, "branch": r.branch, "category": r.category,
                                     "nri": r.nri, "oci": r.oci, "fn": r.fn, "supernumerary": r.supernumerary}])
                issues, clean, _ = validation.validate(row, inst, CURRENT_YEAR, c)
                if (issues.severity == "ERROR").any():
                    st.error("Cannot approve: " + "; ".join(issues[issues.severity == "ERROR"].reason))
                else:
                    validation.commit(clean, inst, CURRENT_YEAR, c)
                    c.execute("UPDATE submissions SET status='APPROVED', remark=? WHERE id=?", (remark, r.id))
                    c.commit()
                    db.log(user["username"], "college", "SUBMISSION_APPROVED", f"{mask(r.apaar_id)} @ {inst}")
                    st.rerun()
            if b.button("❌ Reject", key=f"rj{r.id}"):
                if not remark.strip():
                    st.error("Please write a remark so the student knows what to fix.")
                else:
                    c.execute("UPDATE submissions SET status='REJECTED', remark=? WHERE id=?", (remark, r.id))
                    c.commit()
                    db.log(user["username"], "college", "SUBMISSION_REJECTED", f"{mask(r.apaar_id)} @ {inst}")
                    st.rerun()
    done = df[df.status != "PENDING"]
    with st.expander(f"History ({len(done)})"):
        if not done.empty:
            st.dataframe(done.assign(apaar_id=done.apaar_id.map(mask))[["ts", "apaar_id", "name", "branch", "status", "remark"]],
                         hide_index=True, width="stretch")


# ───────────────────────── Step 6: Audit ─────────────────────────
def page_audit(user):
    st.header("Audit log")
    c = db.get_conn()
    df = pd.read_sql("SELECT ts,username,role,action,detail FROM audit_log ORDER BY id DESC LIMIT 500", c)
    st.dataframe(df, width="stretch", hide_index=True)
    st.download_button("⬇ Export", df.to_csv(index=False).encode(), "audit_log.csv")


PAGES = {"Upload Student Data": page_upload, "Dashboard": page_dashboard, "Anomaly Detection": page_anomaly,
         "Student Records & QR": page_records, "Student Portal": page_student, "Student Submissions": page_submissions, "Verify Student": page_verify, "Audit Log": page_audit}

user = st.session_state.get("user")
if not user:
    login_view()
else:
    st.sidebar.markdown(f"**{user['username']}**  \nRole: `{user['role']}`")
    page = st.sidebar.radio("Menu", auth.ROLE_PAGES[user["role"]])
    if st.sidebar.button("Logout"):
        db.log(user["username"], user["role"], "LOGOUT")
        st.session_state.clear()
        st.rerun()
    st.sidebar.caption("AI flags are decision-support only. Final decisions rest with AICTE.")
    hero("🎓 APAAR Student Data Platform", f"{page}  ·  Admission year {CURRENT_YEAR}",
         [user["role"].upper(), "Secure · Audited · Consent-based"])
    PAGES[page](user)
