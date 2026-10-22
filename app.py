import os
import re
import hmac
import base64
import hashlib
import secrets
import smtplib
import textwrap

from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import streamlit as st

import streamlit.components.v1 as components

from supabase import create_client

try:
    from groq import Groq
except ImportError:
    Groq = None


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="CampusHelps | Student Portal",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "campus_users.db"


# =========================================================
# STYLING
# =========================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --bg: #050806;
    --panel: #0b120d;
    --green: #53ffad;
    --muted: #8ca899;
    --border: rgba(83,255,173,.22);
}
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp {
    background: radial-gradient(ellipse at 50% 0%, rgba(35,120,76,.14), transparent 45%), #050806;
    color: #e9fff2;
}
[data-testid="stHeader"] { background: rgba(5,8,6,.88); }
[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#080e0a,#050806);
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] * { color: #d8f5e3; }
.block-container { max-width: 1350px; padding-top: 2rem; padding-bottom: 3rem; }
h1, h2, h3 { color: #f1fff6 !important; letter-spacing: -.035em; }
p, label { color: #c1d9ca; }
.brand { display:flex; align-items:center; gap:12px; margin-bottom:24px; }
.brand-icon {
    width:48px; height:48px; display:flex; align-items:center; justify-content:center;
    border:1px solid var(--green); border-radius:13px; background:#0b1b12;
    box-shadow:0 0 22px rgba(83,255,173,.17); color:var(--green); font-size:25px;
}
.brand-name { color:var(--green); font:500 19px 'DM Mono', monospace; }
.brand-sub, .eyebrow, .stat-label { font-family:'DM Mono', monospace; }
.brand-sub { color:#779987; font-size:10px; letter-spacing:.1em; margin-top:4px; }
.eyebrow { color:var(--green); font-size:11px; letter-spacing:.15em; }
.hero {
    border:1px solid rgba(83,255,173,.4); border-radius:20px; padding:34px; margin-bottom:24px;
    background:radial-gradient(ellipse at 95% 10%,rgba(83,255,173,.12),transparent 40%), linear-gradient(135deg,#0b1710,#070b08);
    box-shadow:0 0 30px rgba(83,255,173,.06);
}
.hero h1 { font-size:clamp(30px,4vw,46px); line-height:1.2; margin:17px 0; }
.hero p { color:#b2cdbb; line-height:1.8; }
.chip {
    display:inline-block; border:1px solid rgba(83,255,173,.3); background:rgba(83,255,173,.06);
    color:#a2ffd0; border-radius:6px; padding:7px 10px; margin:0 5px 5px 0;
    font:11px 'DM Mono', monospace;
}
.panel, .stat-card, .service-card {
    border:1px solid var(--border); border-radius:15px;
    background:linear-gradient(145deg,#0c1710,#080e0a); padding:21px; margin-bottom:14px;
}
.stat-label { color:#86a994; font-size:10px; margin-bottom:12px; }
.stat-value { color:#f0fff5; font-size:20px; font-weight:750; }
.stat-note { color:var(--green); font-size:12px; margin-top:8px; }
.service-icon { font-size:23px; margin-bottom:12px; }
.service-title { color:#edfff3; font-size:15px; font-weight:700; margin-bottom:7px; }
.service-desc { color:#91ad9a; font-size:12px; line-height:1.7; }
.stButton > button {
    border-radius:9px; border:1px solid rgba(83,255,173,.32);
    background:rgba(83,255,173,.05); color:#dffff0; font-weight:600; min-height:42px;
    transition:all .2s ease;
}
.stButton > button:hover {
    border-color:var(--green); background:rgba(83,255,173,.13); color:white;
    box-shadow:0 0 17px rgba(83,255,173,.1);
}
.stTextInput input, .stTextArea textarea {
    background:#09110c !important; color:#eafff1 !important;
    border:1px solid rgba(83,255,173,.25) !important; border-radius:9px !important;
}
[data-testid="stChatMessage"] {
    background:rgba(10,19,13,.92); border:1px solid rgba(83,255,173,.15);
    border-radius:14px; padding:15px;
}
[data-testid="stChatInput"] {
    border:1px solid rgba(83,255,173,.32); border-radius:12px; background:#0a110d;
}
[data-testid="stExpander"] { border:1px solid var(--border); border-radius:10px; }
hr { border-color:rgba(83,255,173,.15); }
footer { visibility:hidden; }
.login-wrap {
    border:1px solid rgba(83,255,173,.36); border-radius:20px; padding:30px;
    background:radial-gradient(ellipse at 50% 0%,rgba(83,255,173,.10),transparent 65%), linear-gradient(145deg,#0b140e,#070b08);
    box-shadow:0 0 35px rgba(83,255,173,.07);
}
.login-caption { color:#8ca899; font:11px 'DM Mono', monospace; letter-spacing:.12em; }
@media(max-width:768px) { .hero { padding:23px 19px; } .login-wrap { padding:20px; } }
</style>
""", unsafe_allow_html=True)


# =========================================================
# DATABASE AND PASSWORD SECURITY
# =========================a===============================

@st.cache_resource
def get_supabase_client():
    """Create a server-side Supabase client using Streamlit Secrets."""
    url = get_secret_value("SUPABASE_URL")
    # Keep the server-side secret key only in Streamlit Secrets; never expose it in UI.
    key = get_secret_value("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError(
            "Supabase is not configured. Add SUPABASE_URL and SUPABASE_SECRET_KEY "
            "to Streamlit Cloud → Settings → Secrets."
        )
    return create_client(url, key)


def init_db():
    # Tables are created once in the Supabase SQL Editor, not at app startup.
    return None


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_bytes(16)
    password_hash = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return (
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(password_hash).decode("ascii"),
    )


def verify_password(password, salt_text, hash_text):
    try:
        salt = base64.b64decode(salt_text, validate=True)
        expected_hash = base64.b64decode(hash_text, validate=True)
        _, calculated_hash = hash_password(password, salt)
        return hmac.compare_digest(base64.b64decode(calculated_hash), expected_hash)
    except (ValueError, TypeError):
        return False


def register_user(username, email, password):
    username = username.strip()
    email = email.strip().lower()

    if not re.fullmatch(r"[A-Za-z0-9_]{3,24}", username):
        return False, "Username must be 3–24 characters and contain only letters, numbers, or underscores."
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return False, "Enter a valid email address."
    if len(password) < 8:
        return False, "Password must contain at least 8 characters."
    if len(password) > 128:
        return False, "Password is too long."

    salt_text, password_hash = hash_password(password)
    try:
        db = get_supabase_client()
        # Friendly duplicate check; database unique constraints remain the final guard.
        existing_username = db.table("students").select("id").ilike("username", username).limit(1).execute().data
        existing_email = db.table("students").select("id").ilike("email", email).limit(1).execute().data
        if existing_username or existing_email:
            return False, "That username or email is already registered."
        db.table("students").insert({
            "username": username,
            "email": email,
            "salt": salt_text,
            "password_hash": password_hash,
        }).execute()
        return True, "Account created successfully. You can now sign in."
    except Exception:
        return False, "We couldn't create your account. Check the Supabase connection and try again."


def authenticate_user(identifier, password):
    identifier = identifier.strip()
    try:
        db = get_supabase_client()
        rows = db.table("students").select("id, username, email, salt, password_hash").ilike("username", identifier).limit(1).execute().data
        if not rows:
            rows = db.table("students").select("id, username, email, salt, password_hash").ilike("email", identifier).limit(1).execute().data
        user = rows[0] if rows else None
        if user and verify_password(password, user["salt"], user["password_hash"]):
            return {"id": user["id"], "username": user["username"], "email": user["email"]}
    except Exception:
        return None
    return None


def get_secret_value(name, default=""):
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default
    return value or os.getenv(name, default)


# =========================================================
# EMAIL PASSWORD RECOVERY
# =========================================================

def send_reset_code(email, code):
    smtp_email = get_secret_value("SMTP_EMAIL")
    smtp_password = get_secret_value("SMTP_APP_PASSWORD")
    if not smtp_email or not smtp_password:
        return False, "Email recovery is not configured. Add SMTP_EMAIL and SMTP_APP_PASSWORD to your Streamlit secrets."

    message = EmailMessage()
    message["Subject"] = "CampusHelps password reset code"
    message["From"] = smtp_email
    message["To"] = email
    message.set_content(
        f"Your CampusHelps password reset code is: {code}\n\n"
        "This code expires in 10 minutes. If you did not request a reset, ignore this email."
    )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(smtp_email, smtp_password)
            server.send_message(message)
        return True, "A reset code has been sent to your registered email."
    except Exception:
        return False, "We could not send the email. Check SMTP_EMAIL and your Gmail App Password in Streamlit secrets."


def request_password_reset(email):
    email = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return False, "Enter a valid email address."

    try:
        db = get_supabase_client()
        rows = db.table("students").select("email").ilike("email", email).limit(1).execute().data
    except Exception:
        return False, "We couldn't connect to the account database. Please try again later."

    if not rows:
        return True, "If that email is registered, a reset code will be sent."

    code = f"{secrets.randbelow(1_000_000):06d}"
    code_hash = hashlib.sha256(f"{email}:{code}".encode()).hexdigest()
    expiry = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    try:
        db.table("password_reset_codes").upsert({
            "email": email, "code_hash": code_hash, "expires_at": expiry, "attempts": 0
        }, on_conflict="email").execute()
    except Exception:
        return False, "We couldn't save the reset request. Please try again."

    ok, message = send_reset_code(email, code)
    if not ok:
        try:
            db.table("password_reset_codes").delete().eq("email", email).execute()
        except Exception:
            pass
        return False, message
    return True, message


def complete_password_reset(email, code, new_password):
    email = email.strip().lower()
    if len(new_password) < 8:
        return False, "New password must contain at least 8 characters."
    if len(new_password) > 128:
        return False, "Password is too long."

    try:
        db = get_supabase_client()
        rows = db.table("password_reset_codes").select("code_hash, expires_at, attempts").eq("email", email).limit(1).execute().data
        row = rows[0] if rows else None
    except Exception:
        return False, "We couldn't connect to the account database. Please try again."

    if not row:
        return False, "Request a new reset code first."
    if row["attempts"] >= 5:
        db.table("password_reset_codes").delete().eq("email", email).execute()
        return False, "Too many incorrect attempts. Request a new code."

    try:
        expiry = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        expiry = datetime.min.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expiry:
        db.table("password_reset_codes").delete().eq("email", email).execute()
        return False, "That code has expired. Request a new one."

    expected = hashlib.sha256(f"{email}:{code.strip()}".encode()).hexdigest()
    if not hmac.compare_digest(expected, row["code_hash"]):
        db.table("password_reset_codes").update({"attempts": row["attempts"] + 1}).eq("email", email).execute()
        return False, "Incorrect code. Check your email and try again."

    salt_text, password_hash = hash_password(new_password)
    try:
        db.table("students").update({"salt": salt_text, "password_hash": password_hash}).ilike("email", email).execute()
        db.table("password_reset_codes").delete().eq("email", email).execute()
    except Exception:
        return False, "We couldn't update your password. Please try again."
    return True, "Password updated. You can now sign in."


init_db()


# =========================================================
# SESSION STATE
# =========================================================

defaults = {
    "authenticated": False,
    "user": None,
    "messages": [],
    "page": "Overview",
    "auth_view": "Sign In",
    "auth_notice": "",
    "pending_prompt": None,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# LOGIN AND REGISTRATION PAGE
# =========================================================

def render_auth_page():
    if st.session_state.auth_view == "Forgot Password":
        st.markdown('<div class="login-wrap">', unsafe_allow_html=True)
        st.markdown("## Reset your password")
        st.write("A one-time code will be sent to your registered email.")

        with st.form("request_reset_form"):
            reset_email = st.text_input("Registered email", placeholder="you@example.com", max_chars=254)
            send_code = st.form_submit_button("SEND RESET CODE", use_container_width=True)

        if send_code:
            ok, message = request_password_reset(reset_email)
            if ok:
                st.session_state.reset_email = reset_email.strip().lower()
                st.success(message)
            else:
                st.error(message)

        if st.session_state.get("reset_email"):
            st.markdown("### Enter your code and new password")
            with st.form("complete_reset_form"):
                reset_code = st.text_input("6-digit verification code", max_chars=6)
                new_password = st.text_input("New password", type="password", max_chars=128)
                confirm_password = st.text_input("Confirm new password", type="password", max_chars=128)
                finish = st.form_submit_button("UPDATE PASSWORD", use_container_width=True)

            if finish:
                if new_password != confirm_password:
                    st.error("The passwords do not match.")
                elif not re.fullmatch(r"\d{6}", reset_code.strip()):
                    st.error("Enter the 6-digit verification code.")
                else:
                    ok, message = complete_password_reset(
                        st.session_state.reset_email, reset_code, new_password
                    )
                    if ok:
                        st.session_state.auth_notice = message
                        st.session_state.auth_view = "Sign In"
                        st.session_state.pop("reset_email", None)
                        st.rerun()
                    else:
                        st.error(message)

        if st.button("← Back to sign in"):
            st.session_state.auth_view = "Sign In"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    left, right = st.columns([1.05, 0.95], gap="large")

    with left:
        st.markdown(textwrap.dedent("""
            <div style="padding:22px 5px;">
              <div style="font:11px 'DM Mono',monospace;letter-spacing:.16em;color:#53ffad;">
                ● CAMPUS SUPPORT SYSTEM / ONLINE
              </div>
              <div style="font-size:clamp(34px,5vw,58px);font-weight:800;line-height:1.12;margin-top:24px;color:#f1fff6;">
                Your campus.<br><span style="color:#53ffad;">Your command center.</span>
              </div>
              <p style="color:#a8c1b1;line-height:1.9;margin-top:20px;">
                One secure space for academic guidance, college services,
                technical questions, and everyday student support.
              </p>
              <div style="margin-top:25px;">
                <span class="chip">AI ASSISTANT</span>
                <span class="chip">STUDENT SERVICES</span>
                <span class="chip">SECURE ACCOUNTS</span>
              </div>
              <div style="border-left:2px solid #53ffad;padding:12px 16px;margin-top:35px;background:rgba(83,255,173,.035);">
                <div style="font:11px 'DM Mono',monospace;color:#53ffad;">SYSTEM MESSAGE</div>
                <p style="font-size:13px;margin-bottom:0;">Sign in to access your personal CampusHelps workspace.</p>
              </div>
            </div>
        """), unsafe_allow_html=True)

    with right:
        st.markdown('<div class="login-wrap">', unsafe_allow_html=True)
        st.markdown(textwrap.dedent("""
            <div style="text-align:center;padding:5px 0 20px;">
              <svg viewBox="0 0 160 135" width="105" role="img" aria-label="CampusHelps logo">
                <path d="M80 7 L135 27 L131 77 Q122 108 80 127 Q38 108 29 77 L25 27 Z"
                      fill="#0b1710" stroke="#53ffad" stroke-width="2.4"/>
                <path d="M49 48 L80 35 L111 48 L80 62 Z" fill="none" stroke="#53ffad" stroke-width="3"/>
                <path d="M59 56 V76 Q80 91 101 76 V56" fill="none" stroke="#53ffad" stroke-width="3"/>
                <path d="M111 49 V72" stroke="#53ffad" stroke-width="3"/>
                <circle cx="111" cy="77" r="4" fill="#53ffad"/>
              </svg>
              <div style="font:500 21px 'DM Mono',monospace;color:#53ffad;">CAMPUSHELPS</div>
              <div class="login-caption" style="margin-top:7px;">STUDENT ACCESS PORTAL</div>
            </div>
        """), unsafe_allow_html=True)

        if st.session_state.auth_notice:
            st.success(st.session_state.auth_notice)
            st.session_state.auth_notice = ""

        tab_login, tab_register = st.tabs(["Sign In", "Create Account"])

        with tab_login:
            st.markdown("### Welcome back")
            st.caption("Sign in to continue to your dashboard.")
            with st.form("login_form"):
                login_identifier = st.text_input("Username or email", max_chars=254)
                login_password = st.text_input("Password", type="password", max_chars=128)
                login_submit = st.form_submit_button("SIGN IN →", use_container_width=True)

            if login_submit:
                if not login_identifier.strip() or not login_password:
                    st.error("Enter your username/email and password.")
                else:
                    user = authenticate_user(login_identifier, login_password)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.session_state.page = "Overview"
                        st.session_state.messages = []
                        st.rerun()
                    else:
                        st.error("Invalid username/email or password.")

            if st.button("Forgot password?", key="forgot_password_link", use_container_width=True):
                st.session_state.auth_view = "Forgot Password"
                st.rerun()

        with tab_register:
            st.markdown("### Create your account")
            st.caption("Register to access your student workspace.")
            with st.form("register_form"):
                new_username = st.text_input("Username", max_chars=24)
                new_email = st.text_input("Email address", max_chars=254)
                new_password = st.text_input("Create password", type="password", max_chars=128)
                confirm_password = st.text_input("Confirm password", type="password", max_chars=128)
                register_submit = st.form_submit_button("CREATE ACCOUNT →", use_container_width=True)

            if register_submit:
                if not all([new_username.strip(), new_email.strip(), new_password, confirm_password]):
                    st.error("Please complete all fields.")
                elif new_password != confirm_password:
                    st.error("The passwords do not match.")
                else:
                    success, message = register_user(new_username, new_email, new_password)
                    if success:
                        st.session_state.auth_notice = message
                        st.rerun()
                    else:
                        st.error(message)

        st.markdown("""
            <p style="text-align:center;color:#779383;font-size:11px;">
                YOUR ACCOUNT IS PROTECTED BY PASSWORD HASHING.<br>
                Never share your password with anyone.
            </p>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# COLLEGE KNOWLEDGE BASE
# =========================================================

FAQS = [
    {"title": "Admissions", "keywords": ["admission", "apply", "application", "eligibility"],
     "answer": "Check the official college admission notification for eligibility, required documents, and application deadlines."},
    {"title": "Fees and Scholarships", "keywords": ["fees", "fee", "scholarship", "payment", "refund"],
     "answer": "Fees and scholarship eligibility vary by institution. Check official notices and portals and keep payment receipts."},
    {"title": "Examinations", "keywords": ["exam", "hall ticket", "result", "revaluation", "kt"],
     "answer": "For exam timetables, hall tickets, results, and revaluation, check your college or university examination portal."},
    {"title": "Attendance", "keywords": ["attendance", "absent", "shortage"],
     "answer": "Attendance requirements depend on your institution. Check your student handbook or department notice."},
    {"title": "Placements and Internships", "keywords": ["placement", "internship", "career", "recruitment"],
     "answer": "Prepare your resume, practise technical skills, and check your Training and Placement Cell for current opportunities."},
    {"title": "Student Documents", "keywords": ["certificate", "bonafide", "transcript", "migration"],
     "answer": "Contact your college office for certificate applications, required documents, fees, and processing time."},
    {"title": "Study Help", "keywords": ["study", "assignment", "project", "viva", "coding", "gate"],
     "answer": "I can help explain concepts, prepare study plans, practise viva questions, and debug code. Tell me your topic."},
]


# =========================================================
# GROQ AI
# =========================================================

def get_api_key():
    return get_secret_value("GROQ_API_KEY")


def fallback_answer(question):
    q = question.lower().strip()
    if q in ["hi", "hello", "hey", "good morning", "good evening"]:
        return "Hi! 👋 I'm CampusHelps. Ask me about academics, college services, programming, careers, or general questions."

    best_item = None
    best_score = 0
    for item in FAQS:
        score = sum(1 for keyword in item["keywords"] if keyword in q)
        if score > best_score:
            best_item, best_score = item, score

    if best_item:
        return best_item["answer"]
    return "I don't have a reliable built-in answer for that question. Try asking about exams, fees, scholarships, placements, or study help."



def get_ai_reply(messages):
    api_key = get_api_key()

    if not api_key:
        return (
            "Groq API key is missing. Check GROQ_API_KEY in Streamlit Cloud Secrets.",
            "Configuration error",
        )

    if Groq is None:
        return (
            "The Groq Python package is not available. Check that groq is listed in requirements.txt.",
            "Dependency error",
        )

    try:
        client = Groq(api_key=api_key, timeout=30.0)

        conversation = [
            {
                "role": "system",
                "content": (
                    "You are CampusHelps, a friendly student-support assistant. "
                    "Answer questions about academics, programming, technology, "
                    "study plans, careers, and student services in clear, "
                    "beginner-friendly language. Never invent college-specific "
                    "fees, deadlines, policies, results, or official contacts. "
                    "Tell users to verify institution-specific information "
                    "through official sources. Never ask for passwords or bank details."
                ),
            }
        ]

        # Send only valid chat messages to Groq.
        for message in messages[-12:]:
            if message.get("role") in ("user", "assistant"):
                content = message.get("content", "")
                if isinstance(content, str) and content.strip():
                    conversation.append({
                        "role": message["role"],
                        "content": content,
                    })

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=conversation,
            temperature=0.3,
            max_completion_tokens=1200,
        )

        answer = response.choices[0].message.content

        if answer and answer.strip():
            return answer.strip(), "Campus AI"

        return (
            "The AI model returned an empty response. Please try again.",
            "Empty AI response",
        )

    except Exception as error:
        # Log the actual error in Streamlit Cloud logs.
        print(f"CampusHelps Groq error: {type(error).__name__}: {error}")

        return (
            "Campus AI could not complete your request. "
            f"Error type: {type(error).__name__}. "
            "Please check the Streamlit Cloud logs for details.",
            "AI error",
        )



# =========================================================
# NAVIGATION HELPERS
# =========================================================

def navigate_to_chat(question):
    """Open the AI chat and queue a topic-specific question."""
    st.session_state.pending_prompt = question
    st.session_state.page = "Ask CampusHelps"
    # Keep the keyed sidebar radio in sync with programmatic navigation.
    st.session_state.dashboard_navigation = "Ask CampusHelps"


# =========================================================
# CHAT PAGE
# =========================================================


def render_chat():
    import streamlit.components.v1 as components

    st.markdown(
        '<div class="eyebrow">SYSTEM / STUDENT SUPPORT / CHAT</div>',
        unsafe_allow_html=True,
    )
    st.title("AI Command Center")
    st.write(
        "Ask about academics, college services, technology, "
        "careers, or general topics."
    )

    # Show suggested prompts when there is no conversation.
    if not st.session_state.messages:
        st.markdown("""
            <div class="panel">
                <div class="eyebrow">● TERMINAL READY</div>
                <h3>What are we solving today?</h3>
                <p>Choose a suggested question or type your own.</p>
            </div>
        """, unsafe_allow_html=True)

        suggestions = [
            "Explain machine learning in simple words.",
            "Help me prepare a study plan.",
            "How can I prepare for internships?",
            "Explain Python functions with an example.",
        ]

        columns = st.columns(2)

        for index, suggestion in enumerate(suggestions):
            with columns[index % 2]:
                if st.button(
                    "↗ " + suggestion,
                    key=f"prompt_{index}",
                    use_container_width=True,
                ):
                    st.session_state.pending_prompt = suggestion
                    st.rerun()

    # Display all previous questions and answers.
    for message in st.session_state.messages:
        avatar = "🤖" if message["role"] == "assistant" else "👤"

        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

            if message["role"] == "assistant":
                source = message.get("source")
                if source:
                    st.caption(f"Response source: {source}")

    # Read typed prompts and suggested prompts.
    pending = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

    prompt = st.chat_input("Ask CampusHelps anything...")

    if pending:
        prompt = pending

    if prompt and prompt.strip():
        prompt = prompt.strip()

        # Save the user's question.
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
        })

        try:
            with st.spinner("CampusHelps is preparing your answer..."):
                answer, source = get_ai_reply(
                    st.session_state.messages
                )

            # Save the answer and its source.
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "source": source,
            })

        except Exception:
            st.error(
                "Campus AI could not generate a response. "
                "Please try again."
            )
            st.rerun()

        # Re-render the complete conversation.
        st.rerun()

    # Attempt to scroll the page to the newest chat message.
   

components.html(
    """
    <script>
    function scrollToLatestMessage() {
        try {
            const doc = window.parent.document;
            const messages = doc.querySelectorAll(
                '[data-testid="stChatMessage"]'
            );

            if (messages.length > 0) {
                messages[messages.length - 1].scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });
            }
        } catch (error) {
            // Scrolling is optional.
        }
    }

    setTimeout(scrollToLatestMessage, 300);
    </script>
    """,
    height=0,
)

# =========================================================
# SIDEBAR AND NAVIGATION
# =========================================================

with st.sidebar:
    st.markdown("""
        <div class="brand">
            <div class="brand-icon">⌘</div>
            <div>
                <div class="brand-name">CampusHelps</div>
                <div class="brand-sub">AI Student Terminal</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">● SYSTEM NAVIGATION</div>', unsafe_allow_html=True)

    pages = ["Overview", "Ask CampusHelps", "Student Services","My Profile", "About"]
    current_page = st.session_state.page
    if current_page not in pages:
        current_page = "Overview"

    page = st.radio(
        "Navigation", pages, index=pages.index(current_page),
        key="dashboard_navigation", label_visibility="collapsed",
    )
    st.session_state.page = page
    st.divider()

    

user = st.session_state.get("user")

if isinstance(user, dict) and user.get("username"):
    st.write(f"Signed in as {user['username']}")
else:
    st.write("Signed in to CampusHelps")

if get_api_key() and Groq is not None:
    st.success("AI assistant enabled")
else:
    st.info("Knowledge-base mode")


    
if st.button("＋ New Chat", use_container_width=True):
    st.session_state.messages = []
    st.session_state.pending_prompt = None
    st.session_state.page = "Ask CampusHelps"

    if "dashboard_navigation" in st.session_state:
        st.session_state.dashboard_navigation = "Ask CampusHelps"

    st.rerun()


    if st.button("↪ Sign Out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.messages = []
        st.session_state.pending_prompt = None
        st.session_state.page = "Overview"
        st.session_state.auth_view = "Sign In"
        st.session_state.pop("reset_email", None)
        st.rerun()

    st.divider()
    st.caption("Verify official college information with trusted sources. Never share your password in chat.")


# =========================================================
# OVERVIEW PAGE
# =========================================================

page = st.session_state.page

if page == "Overview":
    st.markdown('<div class="eyebrow">SYSTEM ONLINE / WELCOME TO YOUR CAMPUS</div>', unsafe_allow_html=True)
    st.markdown("""
        <div class="hero">
            <span class="chip">⌘ CAMPUS AI</span>
            <span class="chip">● SYSTEM ONLINE</span>
            <h1>Your campus.<br><span style="color:#53ffad;">Your command center.</span></h1>
            <p>One intelligent space for student support, academic guidance, college services, technology questions, and everyday problem-solving.</p>
            <p style="font:11px 'DM Mono',monospace;color:#53ffad;">&gt; STUDENT SUPPORT SYSTEM INITIALISED</p>
        </div>
    """, unsafe_allow_html=True)

    stats = [
        ("01", "Admissions", "Application guidance"),
        ("02", "Academics", "Study and exam support"),
        ("03", "Student Life", "Campus services"),
        ("04", "Campus AI", "AI-powered assistance"),
    ]
    columns = st.columns(4)
    for col, (number, title, note) in zip(columns, stats):
        with col:
            st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-label">MODULE_{number}</div>
                    <div class="stat-value">{title}</div>
                    <div class="stat-note">↗ {note}</div>
                </div>
            """, unsafe_allow_html=True)

    st.markdown("## Explore the modules")
    services = [
        ("📝", "Admissions", "Eligibility, applications, and documents."),
        ("💳", "Fees and Scholarships", "Payment guidance and financial aid."),
        ("📚", "Exams and Academics", "Exam processes and study help."),
        ("🚀", "Careers and Placements", "Internships and placement guidance."),
        ("🏫", "Campus Facilities", "Hostel, transport, library, and labs."),
        ("📄", "Student Documents", "Certificates and administration."),
    ]
    rows = [st.columns(3), st.columns(3)]
    for index, (icon, title, description) in enumerate(services):
        with rows[index // 3][index % 3]:
            st.markdown(f"""
                <div class="service-card">
                    <div class="service-icon">{icon}</div>
                    <div class="service-title">{title}</div>
                    <div class="service-desc">{description}</div>
                </div>
            """, unsafe_allow_html=True)
            st.button(
                "Open module →", key=f"module_{index}", use_container_width=True,
                on_click=navigate_to_chat,
                args=(f"Help me with {title.lower()}. Give practical steps and mention what must be verified with my college.",),
            )

    st.markdown("## Quick actions")
    first, second = st.columns(2)
    with first:
        st.button("↗ Explain a technical concept", use_container_width=True,
                  on_click=navigate_to_chat,
                  args=("Explain a technical concept in simple words, with a simple example.",))
    with second:
        st.button("↗ Help me plan my studies", use_container_width=True,
                  on_click=navigate_to_chat,
                  args=("Help me plan my studies. Ask about my subjects and available study time if needed.",))


# =========================================================
# CHAT PAGE
# =========================================================

elif page == "Ask CampusHelps":
    render_chat()


# =========================================================
# STUDENT SERVICES PAGE
# =========================================================

elif page == "Student Services":
    st.markdown('<div class="eyebrow">SYSTEM / CAMPUS DIRECTORY</div>', unsafe_allow_html=True)
    st.title("Student Services")
    st.write("Browse common student-support topics. Confirm current rules through official college sources.")
    for index, item in enumerate(FAQS):
        with st.expander("⌘  " + item["title"]):
            st.write(item["answer"])
            st.button(
                f"Ask AI about {item['title']}", key=f"faq_{index}",
                on_click=navigate_to_chat,
                args=(f"Tell me about {item['title'].lower()}. Give clear, practical, beginner-friendly guidance, steps to follow, and what to verify with official college sources.",),
            )


# =========================================================
# ABOUT PAGE
# =========================================================

elif page == "My Profile":
    st.title("👤 My Profile")
    st.caption("Manage your student information.")

    try:
        supabase = get_supabase_client()
        user_id = st.session_state.user["id"]

        response = (
            supabase.table("students")
            .select(
                "full_name, department, academic_year, division, phone"
            )
            .eq("id", user_id)
            .single()
            .execute()
        )

        profile = response.data or {}

        departments = [
            "Select Department",
            "Computer Engineering",
            "Information Technology",
            "Electronics",
            "Mechanical",
            "Civil",
            "Other",
        ]

        years = [
            "Select Year",
            "First Year",
            "Second Year",
            "Third Year",
            "Final Year",
        ]

        saved_department = profile.get("department") or ""
        saved_year = profile.get("academic_year") or ""

        department_index = (
            departments.index(saved_department)
            if saved_department in departments
            else 0
        )

        year_index = (
            years.index(saved_year)
            if saved_year in years
            else 0
        )

        with st.form("student_profile_form"):
            full_name = st.text_input(
                "Full Name",
                value=profile.get("full_name") or "",
                placeholder="Enter your full name",
            )

            department = st.selectbox(
                "Department",
                departments,
                index=department_index,
            )

            academic_year = st.selectbox(
                "Academic Year",
                years,
                index=year_index,
            )

            division = st.text_input(
                "Division",
                value=profile.get("division") or "",
                placeholder="e.g. A",
            )

            phone = st.text_input(
                "Phone Number",
                value=profile.get("phone") or "",
                placeholder="Enter your phone number",
            )

            save_profile = st.form_submit_button(
                "💾 Save Profile",
                use_container_width=True,
            )

        if save_profile:
            if not full_name.strip():
                st.warning("Please enter your full name.")
            elif phone.strip() and not phone.strip().isdigit():
                st.warning("Please enter a valid phone number using digits only.")
            elif phone.strip() and len(phone.strip()) != 10:
                st.warning("Please enter a 10-digit phone number.")
            else:
                update_data = {
                    "full_name": full_name.strip(),
                    "department": (
                        department
                        if department != "Select Department"
                        else None
                    ),
                    "academic_year": (
                        academic_year
                        if academic_year != "Select Year"
                        else None
                    ),
                    "division": division.strip() or None,
                    "phone": phone.strip() or None,
                }

                (
                    supabase.table("students")
                    .update(update_data)
                    .eq("id", user_id)
                    .execute()
                )

                st.success("Your profile has been saved successfully!")
                st.rerun()

    except Exception:
        st.error(
            "Unable to load or save your profile. "
            "Please check your Supabase connection and try again."
        )

elif page == "About":
    st.markdown('<div class="eyebrow">SYSTEM / PROJECT INFORMATION</div>', unsafe_allow_html=True)
    st.title("Built for student support.")
    st.markdown("""
        <div class="panel">
            <div class="eyebrow">PROJECT: CAMPUSHELPS</div>
            <h3>An AI-powered college helpdesk</h3>
            <p style="line-height:1.8;">
                CampusHelps combines student-support guidance with a Groq-powered AI assistant.
                It uses Python, Streamlit, and a local SQLite database for registered accounts.
            </p>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("### Account security")
    st.markdown("""
- Passwords are stored as salted password hashes, not plain text.
- Database operations use parameterised SQL queries.
- Student accounts are separate from the Groq API key.
- Email verification is used for password recovery.
    """)
    st.info("For public deployment, configure secrets securely and use persistent database storage. Local SQLite storage may not persist reliably across hosted app restarts or redeployments.")


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")
st.markdown("""
    <div style="text-align:center;color:#779383;font:11px 'DM Mono',monospace;line-height:1.8;">
        CAMPUSHELPS // STUDENT SUPPORT SYSTEM<br>
        PYTHON + STREAMLIT + GROQ AI
    </div>
""", unsafe_allow_html=True)
