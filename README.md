# APAAR ID based Student Data Management & Verification Platform
SIH problem statement 26263 – working prototype (synthetic data only).

## Run (3 commands)  — theme is set in .streamlit/config.toml
```
pip install -r requirements.txt
python -m core.seed        # optional: rebuilds database + sample CSV (app also does it on first run)
streamlit run app.py
```

## Demo logins
| Username | Password | Role |
|---|---|---|
| admin | aicte123 | AICTE officer |
| clg012 | college123 | College (has sample upload file) |
| clg001 … clg011 | college123 | Other colleges |
| employer | verifier123 | Employer / verifier |
| APAAR ID (see demo_students.csv or login-page expander) | student123 | Student (optional self-service) |

## 5-minute demo script
1. Login **clg012** -> Upload -> download "Sample file with deliberate errors" -> upload it.
   Validation report shows: missing ID, invalid format, ID not in registry, duplicate in file,
   student already enrolled in CLG003, NRI+OCI conflict, name mismatch, intake exceeded.
   Click Submit -> only valid rows are stored.
2. Login **admin** -> Dashboard: intake vs enrolment chart, red cells for excess / double enrolment.
3. Anomaly Detection: CLG003 (excess), CLG007 (abnormal NRI share), CLG002 & CLG005 (double enrolment), each with reasons.
4. Student Records & QR: pick a student, tick consent, show the signed QR.
5. Login **employer** -> Verify Student -> paste QR text. Without consent -> blocked. Tampered code -> rejected.
6. **Student self-service (optional):** Login page -> *Student sign-up* tab (APAAR ID + DOB from `data/demo_students.csv`, set a password),
   or login directly with a demo student ID / `student123`. Student Portal -> pick college, fill details, attach proof -> Submit.
   Then login **clg001** -> *Student Submissions* -> view proof -> Approve (record moves into repository) or Reject with remark.
   Student can now see the QR and the consent switch under *Consent & QR*.
7. Admin -> Audit Log: every upload, verification, consent change is recorded.

## Project structure
```
app.py                 Streamlit UI (all pages)
core/db.py             Step 1  SQLite schema, audit logging
core/apaar_mock.py     Step 1  mock APAAR registry (replace with real API in production)
core/validation.py     Step 2  validation engine (E01-E07, W01-W02, F01)
core/anomaly.py        Step 7  robust z-score + Isolation Forest
core/auth.py           Step 6  login + role based access
core/qr.py             Step 5  HMAC signed QR token
core/seed.py           synthetic data generator with planted problems
data/sample_uploads/   template.csv, CLG012_sample_upload.csv
```

## Validation codes
E01 missing ID · E02 bad format · E03 not in registry · E04 duplicate in file · E05 enrolled in another institution ·
E06 inconsistent category · E07 invalid flag · W01 name mismatch · W02 supernumerary without category ·
F01 admissions above approved intake.

## Honest limitations (say this in the PPT as "Phase 2")
- APAAR registry is a mock; production uses the real APAAR / DigiLocker API.
- Consent is simulated with a checkbox; production uses APAAR consent flow.
- SQLite + Streamlit for prototype; production: PostgreSQL, FastAPI, SSO, encryption at rest.
- Change SECRET in core/qr.py and move it to an environment variable before any real use.
- AI flags are decision-support only; final decisions stay with AICTE officials.
