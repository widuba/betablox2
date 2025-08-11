from __future__ import annotations
import os, random, json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FloatField, IntegerField, FileField
from wtforms.validators import DataRequired, Email, Length, NumberRange
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, scoped_session

SITE_NAME = "BETA BLOCKZ"
INVITE_CODE = "DUKESLOVESCURRY"
HOUSE_EDGE = 0.10

BETA_PER_SOL = 100.0
def sol_to_beta(sol: float) -> float: return float(sol or 0.0) * BETA_PER_SOL
def fmt_beta(v: float) -> str: return f"{v:,.2f} BETA"

VIP_THRESHOLDS_BETA = [
    (25000, "Diamond 3"),
    (10000, "Diamond 2"),
    ( 7500, "Diamond 1"),
    ( 6250, "Platinum 3"),
    ( 5000, "Platinum 2"),
    ( 3750, "Platinum 1"),
    ( 2500, "Gold"),
    ( 1250, "Silver"),
    (  500, "Bronze"),
]
def compute_vip(total_wagered_sol: float) -> str:
    total_beta = sol_to_beta(total_wagered_sol or 0.0)
    for threshold, name in sorted(VIP_THRESHOLDS_BETA, key=lambda x: x[0], reverse=True):
        if total_beta >= threshold:
            return name
    return "None"
def vip_progress(total_wagered_sol: float):
    total_beta = sol_to_beta(total_wagered_sol or 0.0)
    tiers = sorted(VIP_THRESHOLDS_BETA, key=lambda x: x[0])
    current = "None"; cur_thr = 0; nxt_thr = None
    for thr, name in tiers:
        if total_beta >= thr:
            current = name; cur_thr = thr
        else:
            nxt_thr = thr; break
    if nxt_thr is None: return current, 100.0, cur_thr, cur_thr
    span = max(1.0, nxt_thr - cur_thr)
    pct = 100.0 * max(0.0, min(1.0, (total_beta - cur_thr) / span))
    return current, pct, cur_thr, nxt_thr

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@betablockz.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key")

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
# --- TEMP: make login/forms work in hosted envs ---
app.config["WTF_CSRF_ENABLED"] = False     # disable CSRF just to confirm the issue
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False
# --------------------------------------------------
app.jinja_env.globals.update(fmt_beta=fmt_beta, vip_progress=vip_progress)

engine = create_engine("sqlite:///beta_blockz.db", connect_args={"check_same_thread": False})
SessionLocal = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    wallet_address = Column(String, unique=True, nullable=True)
    balance_sol = Column(Float, default=0.0)
    total_wagered = Column(Float, default=0.0)
    vip_tier = Column(String, default="None")
    bonus_due = Column(Float, default=0.0)
    claim_code = Column(String, nullable=True)
    claim_amount = Column(Float, default=0.0)
    claim_claimed_at = Column(DateTime, nullable=True)
    role = Column(String, default="user")
    created_at = Column(DateTime, default=datetime.utcnow)
    txns = relationship("Transaction", back_populates="user")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String)
    amount = Column(Float, default=0.0)
    meta = Column(Text)
    status = Column(String, default="completed")
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="txns")

class WalletPool(Base):
    __tablename__ = "wallet_pool"
    id = Column(Integer, primary_key=True)
    address = Column(String, unique=True, nullable=False)
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_at = Column(DateTime, nullable=True)

Base.metadata.create_all(engine)

# Seed admin
db = SessionLocal()
if not db.query(User).filter_by(email=ADMIN_EMAIL).first():
    db.add(User(email=ADMIN_EMAIL, username="admin", password_hash=generate_password_hash(ADMIN_PASSWORD), role="admin"))
    db.commit()
db.close()

# Forms
class SignupForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=24)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    invite = StringField("Invite Code", validators=[DataRequired()])
    submit = SubmitField("Create account")

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")

class RedeemForm(FlaskForm):
    wallet_to = StringField("Wallet to redeem to", validators=[DataRequired(), Length(min=20, max=80)])
    amount = FloatField("Amount (SOL)", validators=[DataRequired(), NumberRange(min=0.0001)])
    submit = SubmitField("Submit redeem request")

class UploadWalletsForm(FlaskForm):
    csvfile = FileField("CSV with a 'wallet' column", validators=[DataRequired()])
    submit = SubmitField("Upload")

class AdjustBalanceForm(FlaskForm):
    set_amount = FloatField("Set balance to")
    add_amount = FloatField("Add amount")
    sub_amount = FloatField("Subtract amount")
    set_wager = FloatField("Set total wagered to")
    add_wager = FloatField("Add to total wagered")
    sub_wager = FloatField("Subtract from total wagered")
    set_bonus = FloatField("Set bonus due to")
    add_bonus = FloatField("Add to bonus due")
    sub_bonus = FloatField("Subtract from bonus due")
    set_claim_code = StringField("Set claim code (per-user)")
    set_claim_amount = FloatField("Set claim amount")
    submit = SubmitField("Apply")

class DiceForm(FlaskForm):
    bet = FloatField("Bet (SOL)", validators=[DataRequired(), NumberRange(min=0.0001)])
    target_under = IntegerField("Roll under (2–99)", validators=[DataRequired(), NumberRange(min=2, max=99)])
    submit = SubmitField("Roll")

class MinesForm(FlaskForm):
    bet = FloatField("Bet (SOL)", validators=[DataRequired(), NumberRange(min=0.0001)])
    mines = IntegerField("Mines (1–24)", validators=[DataRequired(), NumberRange(min=1, max=24)])
    submit = SubmitField("Open 1 tile")

# Helpers
def current_user():
    uid = session.get("uid")
    if not uid: return None
    s = SessionLocal(); u = s.query(User).get(uid); s.close(); return u

def login_required(view):
    def w(*a, **k):
        if not current_user(): return redirect(url_for("login"))
        return view(*a, **k)
    w.__name__ = view.__name__
    return w

def admin_required(view):
    def w(*a, **k):
        u = current_user()
        if not u or u.role != "admin":
            flash("Admin only.", "error"); return redirect(url_for("dashboard"))
        return view(*a, **k)
    w.__name__ = view.__name__
    return w

def assign_next_wallet(user_id:int):
    s = SessionLocal()
    w = s.query(WalletPool).filter(WalletPool.assigned_user_id==None).order_by(WalletPool.id.asc()).first()
    if not w: s.close(); return None
    w.assigned_user_id = user_id; w.assigned_at = datetime.utcnow()
    s.commit(); addr = w.address; s.close(); return addr

# PnL/Wager per-bet pairing
def compute_user_stats(user_id: int):
    s = SessionLocal()
    now = datetime.utcnow()
    windows = {
        "last_24h": now - timedelta(hours=24),
        "last_7d":  now - timedelta(days=7),
        "last_30d": now - timedelta(days=30),
    }
    out = {k: {"wagered": 0.0, "pnl": 0.0} for k in windows.keys()}
    txns = s.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.type == "wager"
    ).order_by(Transaction.created_at.asc()).all()
    i = 0; n = len(txns)
    while i < n:
        t = txns[i]; amt = float(t.amount or 0.0)
        if amt < 0:
            bet_time = t.created_at; bet = -amt; payout = 0.0
            if i + 1 < n:
                t2 = txns[i+1]
                if t2.created_at >= bet_time:
                    payout = float(t2.amount or 0.0); i += 1
            for key, since in windows.items():
                if bet_time >= since:
                    out[key]["wagered"] += bet
                    out[key]["pnl"] += (-bet + payout)
        i += 1
    s.close(); return out

# Routes
@app.route("/")
def home():
    u = current_user()
    if u: return redirect(url_for("dashboard"))
    return render_template("home.html", site_name=SITE_NAME)

@app.route("/signup", methods=["GET","POST"])
def signup():
    if current_user(): return redirect(url_for("dashboard"))
    form = SignupForm()
    if form.validate_on_submit():
        if form.invite.data.strip() != INVITE_CODE:
            flash("Invalid invite code.", "error"); return render_template("signup.html", form=form, site_name=SITE_NAME)
        s = SessionLocal()
        if s.query(User).filter_by(email=form.email.data.lower()).first():
            flash("Email already in use.", "error"); s.close(); return render_template("signup.html", form=form, site_name=SITE_NAME)
        if s.query(User).filter_by(username=form.username.data).first():
            flash("Username already taken.", "error"); s.close(); return render_template("signup.html", form=form, site_name=SITE_NAME)
        u = User(email=form.email.data.lower(), username=form.username.data, password_hash=generate_password_hash(form.password.data), role="user", balance_sol=0.0)
        s.add(u); s.commit()
        addr = assign_next_wallet(u.id)
        if addr: u.wallet_address = addr; s.commit()
        s.close(); flash("Account created. Please log in.", "success"); return redirect(url_for("login"))
    return render_template("signup.html", form=form, site_name=SITE_NAME)

@app.route("/login", methods=["GET","POST"])
def login():
    if current_user(): return redirect(url_for("dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        s = SessionLocal(); u = s.query(User).filter_by(email=form.email.data.lower()).first()
        if u and check_password_hash(u.password_hash, form.password.data):
            session["uid"] = u.id; s.close(); return redirect(url_for("dashboard"))
        s.close(); flash("Invalid credentials.", "error")
    return render_template("login.html", form=form, site_name=SITE_NAME)

@app.route("/logout")
def logout():
    session.pop("uid", None); return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    u = current_user()
    s = SessionLocal(); tx = s.query(Transaction).filter_by(user_id=u.id).order_by(Transaction.created_at.desc()).limit(30).all(); s.close()
    return render_template("dashboard.html", user=u, txns=tx, site_name=SITE_NAME)

@app.route("/redeem", methods=["POST"])
@login_required
def redeem():
    u = current_user(); form = RedeemForm()
    if form.validate_on_submit():
        amount = float(form.amount.data)
        if amount <= 0: flash("Amount must be positive.", "error"); return redirect(url_for("dashboard"))
        s = SessionLocal(); uu = s.query(User).get(u.id)
        if uu.balance_sol < amount: s.close(); flash("Insufficient balance.", "error"); return redirect(url_for("dashboard"))
        uu.balance_sol -= amount
        s.add(Transaction(user_id=u.id, type="redeem", amount=-amount, meta=json.dumps({"wallet_to": form.wallet_to.data, "note":"manual payout up to 24h"}), status="pending"))
        s.commit(); s.close()
        flash("Redeem request submitted. Manual processing up to 24 hours.", "success")
    else:
        flash("Invalid redeem form.", "error")
    return redirect(url_for("dashboard"))

@app.route("/game/dice", methods=["GET","POST"])
@login_required
def game_dice():
    u = current_user(); form = DiceForm(); result = None
    if form.validate_on_submit():
        bet = float(form.bet.data); target = int(form.target_under.data)
        if bet <= 0 or target < 2 or target > 99: flash("Invalid bet/target.", "error"); return redirect(url_for("game_dice"))
        s = SessionLocal(); uu = s.query(User).get(u.id)
        if uu.balance_sol < bet: s.close(); flash("Insufficient balance.", "error"); return redirect(url_for("game_dice"))
        uu.balance_sol -= bet
        uu.total_wagered = (uu.total_wagered or 0.0) + bet
        uu.vip_tier = compute_vip(uu.total_wagered)
        s.add(Transaction(user_id=u.id, type="wager", amount=-bet, meta=json.dumps({"game":"dice","target":target})))
        p = target / 100.0; fair = 1.0 / p; mult = fair * (1.0 - HOUSE_EDGE)
        roll = max(1, min(100, 1 + int(random.random() * 100)))
        win = (roll < target)
        payout = bet * mult if win else 0.0
        if payout > 0:
            uu.balance_sol += payout
            s.add(Transaction(user_id=u.id, type="wager", amount=payout, meta=json.dumps({"game":"dice","roll":roll,"result":"win","mult":round(mult,4)})))
        else:
            s.add(Transaction(user_id=u.id, type="wager", amount=0.0, meta=json.dumps({"game":"dice","roll":roll,"result":"lose","mult":round(mult,4)})))
        s.commit(); s.close()
        result = {"roll": roll, "win": win, "mult": mult, "payout": payout}
    return render_template("game_dice.html", form=form, user=u, result=result, site_name=SITE_NAME)

@app.route("/game/mines", methods=["GET","POST"])
@login_required
def game_mines():
    u = current_user(); form = MinesForm(); result = None
    if form.validate_on_submit():
        bet = float(form.bet.data); mines = int(form.mines.data)
        if bet <= 0 or mines < 1 or mines > 24: flash("Invalid bet/mines.", "error"); return redirect(url_for("game_mines"))
        s = SessionLocal(); uu = s.query(User).get(u.id)
        if uu.balance_sol < bet: s.close(); flash("Insufficient balance.", "error"); return redirect(url_for("game_mines"))
        uu.balance_sol -= bet
        uu.total_wagered = (uu.total_wagered or 0.0) + bet
        uu.vip_tier = compute_vip(uu.total_wagered)
        s.add(Transaction(user_id=u.id, type="wager", amount=-bet, meta=json.dumps({"game":"mines","mines":mines})))
        BOARD = 25; safe = BOARD - mines; p_safe = safe / BOARD
        fair = 1.0 / p_safe; mult = fair * (1.0 - HOUSE_EDGE)
        hit_safe = (random.random() < p_safe)
        payout = bet * mult if hit_safe else 0.0
        if payout > 0:
            uu.balance_sol += payout
            s.add(Transaction(user_id=u.id, type="wager", amount=payout, meta=json.dumps({"game":"mines","result":"safe","mult":round(mult,4)})))
        else:
            s.add(Transaction(user_id=u.id, type="wager", amount=0.0, meta=json.dumps({"game":"mines","result":"mine","mult":round(mult,4)})))
        s.commit(); s.close()
        result = {"safe": hit_safe, "mult": mult, "payout": payout}
    return render_template("game_mines.html", form=form, user=u, result=result, site_name=SITE_NAME)

@app.route("/claim", methods=["POST"])
@login_required
def claim_code():
    u = current_user()
    code = (request.form.get("claim_code") or "").strip()
    if not code:
        flash("Enter a code.", "error"); return redirect(url_for("dashboard"))
    s = SessionLocal(); uu = s.query(User).get(u.id)
    if not uu.claim_code or uu.claim_code != code:
        s.close(); flash("Invalid code.", "error"); return redirect(url_for("dashboard"))
    if uu.claim_claimed_at is not None:
        s.close(); flash("Code already claimed.", "error"); return redirect(url_for("dashboard"))
    amt = float(uu.claim_amount or 0.0)
    if amt <= 0:
        s.close(); flash("No claim amount set.", "error"); return redirect(url_for("dashboard"))
    uu.balance_sol = (uu.balance_sol or 0.0) + amt
    uu.claim_claimed_at = datetime.utcnow()
    s.add(Transaction(user_id=uu.id, type="bonus", amount=amt, meta=json.dumps({"note":"claimed with code"}), status="completed"))
    s.commit(); s.close()
    flash(f"Claimed {amt:.4f} to your balance.", "success")
    return redirect(url_for("dashboard"))

@app.route("/admin")
def admin_index():
    u = current_user()
    if not u or u.role != "admin":
        flash("Admin only.", "error"); return redirect(url_for("dashboard"))
    s = SessionLocal()
    users = s.query(User).order_by(User.created_at.desc()).all()
    pending = s.query(Transaction).filter_by(status="pending").order_by(Transaction.created_at.asc()).all()
    s.close()
    return render_template("admin/index.html", users=users, pending=pending, site_name=SITE_NAME)

@app.route("/admin/user/<int:user_id>", methods=["GET","POST"])
def admin_user(user_id):
    u = current_user()
    if not u or u.role != "admin":
        flash("Admin only.", "error"); return redirect(url_for("dashboard"))
    s = SessionLocal()
    user = s.query(User).get(user_id)
    if not user:
        s.close(); flash("User not found.", "error"); return redirect(url_for("admin_index"))
    form = AdjustBalanceForm()
    if form.validate_on_submit():
        if form.set_amount.data is not None: user.balance_sol = float(form.set_amount.data)
        if form.add_amount.data is not None: user.balance_sol += float(form.add_amount.data)
        if form.sub_amount.data is not None:
            user.balance_sol -= float(form.sub_amount.data)
            if user.balance_sol < 0: user.balance_sol = 0.0
        if form.set_wager.data is not None: user.total_wagered = max(0.0, float(form.set_wager.data))
        if form.add_wager.data is not None: user.total_wagered = max(0.0, (user.total_wagered or 0.0) + float(form.add_wager.data))
        if form.sub_wager.data is not None: user.total_wagered = max(0.0, (user.total_wagered or 0.0) - float(form.sub_wager.data))
        user.vip_tier = compute_vip(user.total_wagered or 0.0)
        if form.set_bonus.data is not None: user.bonus_due = max(0.0, float(form.set_bonus.data))
        if form.add_bonus.data is not None: user.bonus_due = max(0.0, (user.bonus_due or 0.0) + float(form.add_bonus.data))
        if form.sub_bonus.data is not None: user.bonus_due = max(0.0, (user.bonus_due or 0.0) - float(form.sub_bonus.data))
        if form.set_claim_code.data is not None:
            user.claim_code = (form.set_claim_code.data or '').strip() or None
            user.claim_claimed_at = None
        if form.set_claim_amount.data is not None:
            user.claim_amount = max(0.0, float(form.set_claim_amount.data))
        s.commit(); flash("Updated.", "success"); s.close(); return redirect(url_for("admin_user", user_id=user_id))
    txns = s.query(Transaction).filter_by(user_id=user_id).order_by(Transaction.created_at.desc()).all()
    stats = compute_user_stats(user_id)
    s.close()
    return render_template("admin/user.html", u=user, txns=txns, form=form, stats=stats, site_name=SITE_NAME)

@app.route("/admin/user/<int:user_id>/credit_bonus")
def admin_credit_bonus(user_id):
    u = current_user()
    if not u or u.role != "admin":
        flash("Admin only.", "error"); return redirect(url_for("dashboard"))
    s = SessionLocal()
    usr = s.query(User).get(user_id)
    if not usr:
        s.close(); flash("User not found.", "error"); return redirect(url_for("admin_index"))
    bonus = float(usr.bonus_due or 0.0)
    if bonus > 0:
        usr.balance_sol = (usr.balance_sol or 0.0) + bonus
        usr.bonus_due = 0.0
        s.add(Transaction(user_id=usr.id, type="bonus", amount=bonus, meta=json.dumps({"note":"admin credited bonus"}), status="completed"))
        s.commit(); flash(f"Credited {bonus:.4f} to user and reset bonus due.", "success")
    else:
        flash("No bonus due to credit.", "error")
    s.close(); return redirect(url_for("admin_user", user_id=user_id))

@app.route("/admin/tx/<int:tx_id>/<string:action>")
def admin_tx_action(tx_id, action):
    u = current_user()
    if not u or u.role != "admin":
        flash("Admin only.", "error"); return redirect(url_for("dashboard"))
    s = SessionLocal(); tx = s.query(Transaction).get(tx_id)
    if not tx: s.close(); flash("Transaction not found.", "error"); return redirect(url_for("admin_index"))
    usr = s.query(User).get(tx.user_id)
    if action == "complete":
        tx.status = "completed"; s.commit(); flash("Marked completed. Send SOL manually.", "success")
    elif action == "reject":
        if tx.type == "redeem" and tx.status == "pending":
            usr.balance_sol += (-tx.amount) if tx.amount < 0 else tx.amount
        tx.status = "rejected"; s.commit(); flash("Redeem rejected. Refunded.", "success")
    else:
        flash("Unknown action.", "error")
    s.close(); return redirect(url_for("admin_index"))

@app.route("/admin/upload_wallets", methods=["GET","POST"])
def admin_upload_wallets():
    u = current_user()
    if not u or u.role != "admin":
        flash("Admin only.", "error"); return redirect(url_for("dashboard"))
    if request.method == "POST":
        file = request.files.get("csvfile")
        if not file:
            flash("No file.", "error"); return redirect(url_for("admin_index"))
        import csv, io
        s = SessionLocal()
        f = io.StringIO(file.stream.read().decode("utf-8")); reader = csv.DictReader(f)
        added = 0
        for row in reader:
            addr = (row.get("wallet") or "").strip()
            if not addr: continue
            if s.query(WalletPool).filter_by(address=addr).first(): continue
            s.add(WalletPool(address=addr)); added += 1
        s.commit(); s.close(); flash(f"Uploaded {added} wallet(s).", "success"); return redirect(url_for("admin_index"))
    form = UploadWalletsForm()
    return render_template("admin/upload_wallets.html", form=form, site_name=SITE_NAME)

@app.template_filter("dt")
def format_dt(v): return "-" if not v else v.strftime("%Y-%m-%d %H:%M:%S")

if __name__ == "__main__":
    import os
    port_str = os.environ.get("PORT")
    try:
        port = int(port_str) if port_str else 8000
    except ValueError:
        port = 8000

    print(f"Starting on port {port}", flush=True)
    app.run(host="0.0.0.0", port=port, debug=True)

