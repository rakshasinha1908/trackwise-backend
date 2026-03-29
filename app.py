import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_bcrypt import Bcrypt
import jwt
from functools import wraps

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
SECRET_KEY = os.getenv("SECRET_KEY")
app.config['SECRET_KEY'] = SECRET_KEY

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(80), nullable=False)
    note = db.Column(db.String(200))
    date = db.Column(db.String(10), nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "amount": self.amount,
            "category": self.category,
            "note": self.note,
            "date": self.date
        }

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")

        if not token:
            return jsonify({"error": "Token missing"}), 401

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.user_id = data["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401

        except:
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)

    return decorated

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Trackwise API is running 🚀"})

@app.route("/signup", methods=["POST"])
def signup():
    data = request.json

    hashed_pw = bcrypt.generate_password_hash(data["password"]).decode("utf-8")

    user = User(email=data["email"], password=hashed_pw)
    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "User created"})

@app.route("/login", methods=["POST"])
def login():
    data = request.json

    user = User.query.filter_by(email=data["email"]).first()

    if not user or not bcrypt.check_password_hash(user.password, data["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    token = jwt.encode(
    {
        "user_id": user.id,
        "exp": datetime.utcnow() + timedelta(days=1)
    },
    SECRET_KEY,
    algorithm="HS256"
)

    return jsonify({"token": token})

# ✅ Get all expenses
# @app.route("/expenses", methods=["GET"])
@app.route("/expenses", methods=["GET"])
@require_auth
def get_expenses():
    # expenses = Expense.query.all()
    # expenses = Expense.query.filter_by(user_id=1).all()
    expenses = Expense.query.filter_by(user_id=request.user_id).all()
    return jsonify([e.to_dict() for e in expenses])

# ✅ Add new expense
# @app.route("/expenses", methods=["POST"])
@app.route("/expenses", methods=["POST"])
@require_auth
def add_expense():
    data = request.json
    if not data or not data.get("amount") or not data.get("category"):
        return jsonify({"error": "Amount and category are required"}), 400
    
    new_expense = Expense(
        amount=data.get("amount"),
        category=data.get("category"),
        note=data.get("note", ""),
        date=data.get("date", datetime.now().strftime("%Y-%m-%d")),
        # user_id=1
        user_id=request.user_id
    )
    db.session.add(new_expense)
    db.session.commit()
    return jsonify({"message": "Expense added!", "data": new_expense.to_dict()}), 201

# ✅ Update expense by id
@app.route("/expenses/<int:id>", methods=["PUT"])
def update_expense(id):
    expense = Expense.query.get(id)
    if not expense:
        return jsonify({"error": "Expense not found"}), 404

    data = request.json
    expense.amount = data.get("amount", expense.amount)
    expense.category = data.get("category", expense.category)
    expense.note = data.get("note", expense.note)
    expense.date = data.get("date", expense.date)
    db.session.commit()
    return jsonify(expense.to_dict()), 200

# ✅ Delete expense by id
@app.route("/expenses/<int:id>", methods=["DELETE"])
def delete_expense(id):
    expense = Expense.query.get(id)
    if not expense:
        return jsonify({"error": "Expense not found"}), 404

    db.session.delete(expense)
    db.session.commit()
    return jsonify({"success": True, "message": "Expense deleted"}), 200

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, nullable=False)  # future-ready
    # month_key = db.Column(db.String(7), nullable=False)  # YYYY-MM
    month_key = db.Column(db.String(7), nullable=False, index=True)

    income = db.Column(db.Integer, nullable=False)
    savings = db.Column(db.Integer, default=0)

    food = db.Column(db.Integer, nullable=False)
    shopping = db.Column(db.Integer, nullable=False)
    transport = db.Column(db.Integer, nullable=False)
    bills = db.Column(db.Integer, nullable=False)
    others = db.Column(db.Integer, nullable=False)

    inherited_from = db.Column(db.String(7))  # previous month_key
    is_auto_generated = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.String, default=lambda: datetime.now().isoformat())
    updated_at = db.Column(
        db.String,
        default=lambda: datetime.now().isoformat(),
        onupdate=lambda: datetime.now().isoformat()
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "month_key", name="unique_user_month"),
    )


@app.route("/budget/<month_key>", methods=["GET"])
@require_auth
def get_budget(month_key):

    user_id = request.user_id

    budget = Budget.query.filter_by(
        user_id=user_id,
        month_key=month_key
    ).first()

    # ✅ IF EXISTS → RETURN NORMAL
    if budget:
        return jsonify({
            "id": budget.id,
            "month_key": budget.month_key,
            "income": budget.income,
            "savings": budget.savings,
            "categories": {
                "Food": budget.food,
                "Shopping": budget.shopping,
                "Transport": budget.transport,
                "Bills": budget.bills,
                "Others": budget.others,
            },
            "inherited_from": budget.inherited_from,
            "is_auto_generated": budget.is_auto_generated
        })

    # 🔥 IF NOT EXISTS → TRY PREVIOUS MONTH

    from datetime import datetime
    from dateutil.relativedelta import relativedelta

    current = datetime.strptime(month_key, "%Y-%m")
    prev = current - relativedelta(months=1)
    prev_key = prev.strftime("%Y-%m")

    prev_budget = Budget.query.filter_by(
        user_id=user_id,
        month_key=prev_key
    ).first()

    # ✅ IF PREVIOUS EXISTS → COPY IT
    if prev_budget:

        new_budget = Budget(
            user_id=user_id,
            month_key=month_key,
            income=prev_budget.income,
            savings=prev_budget.savings,
            food=prev_budget.food,
            shopping=prev_budget.shopping,
            transport=prev_budget.transport,
            bills=prev_budget.bills,
            others=prev_budget.others,
            inherited_from=prev_key,
            is_auto_generated=True
        )

        # db.session.add(new_budget)
        # db.session.commit()
        from sqlalchemy.exc import IntegrityError

        try:
            db.session.add(new_budget)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            new_budget = Budget.query.filter_by(
            user_id=user_id,
            month_key=month_key
            ).first()

        return jsonify({
            "id": new_budget.id,
            "month_key": new_budget.month_key,
            "income": new_budget.income,
            "savings": new_budget.savings,
            "categories": {
                "Food": new_budget.food,
                "Shopping": new_budget.shopping,
                "Transport": new_budget.transport,
                "Bills": new_budget.bills,
                "Others": new_budget.others,
            },
            "inherited_from": new_budget.inherited_from,
            "is_auto_generated": new_budget.is_auto_generated
        })

    # ❌ IF NOTHING EXISTS → RETURN NULL
    return jsonify(None)
    
@app.route("/budget/<month_key>", methods=["POST"])
@require_auth
def save_budget(month_key):

    user_id = request.user_id

    data = request.json
    if not data or "income" not in data or "categories" not in data:
        return jsonify({"error": "Invalid budget data"}), 400

    existing = Budget.query.filter_by(
        user_id=user_id,
        month_key=month_key
    ).first()

    if existing:
        # UPDATE
        existing.income = data["income"]
        existing.savings = data["savings"]

        existing.food = data["categories"]["Food"]
        existing.shopping = data["categories"]["Shopping"]
        existing.transport = data["categories"]["Transport"]
        existing.bills = data["categories"]["Bills"]
        existing.others = data["categories"]["Others"]

    else:
        # CREATE
        existing = Budget(
            user_id=user_id,
            month_key=month_key,
            income=data["income"],
            savings=data["savings"],

            food=data["categories"]["Food"],
            shopping=data["categories"]["Shopping"],
            transport=data["categories"]["Transport"],
            bills=data["categories"]["Bills"],
            others=data["categories"]["Others"],
        )
        db.session.add(existing)

    db.session.commit()

    return jsonify({"success": True})

# @app.route("/dashboard-kpi/<month_key>")
# def dashboard_kpi(month_key):
@app.route("/dashboard-kpi/<month_key>")
@require_auth
def dashboard_kpi(month_key):

    from datetime import datetime
    import calendar

    user_id = request.user_id

    # -------- PARSE MONTH --------
    year, month = map(int, month_key.split("-"))

    start = datetime(year, month, 1)
    end = datetime(year+1,1,1) if month==12 else datetime(year,month+1,1)


    # -------- CURRENT EXPENSES --------
    txns = Expense.query.filter(
        Expense.user_id == request.user_id,
        Expense.date >= start.strftime("%Y-%m-%d"),
        Expense.date < end.strftime("%Y-%m-%d")
    ).all()

    total_spend = sum(t.amount for t in txns)
    txn_count = len(txns)

    # -------- DAYS --------
    today = datetime.today()
    if today.year==year and today.month==month:
        days = today.day
    else:
        days = calendar.monthrange(year,month)[1]

    avg_day = total_spend/max(days,1)

    # -------- CURRENT BUDGET --------
    budget = Budget.query.filter_by(
        user_id=user_id,
        month_key=month_key
    ).first()

    total_budget = 0
    if budget:
        total_budget = (
            budget.food +
            budget.shopping +
            budget.transport +
            budget.bills +
            budget.others
        )

    budget_used_pct = 0
    if total_budget>0:
        budget_used_pct = (total_spend/total_budget)*100

    # -------- PREVIOUS MONTH KEY --------
    if month==1:
        prev_year,prev_month = year-1,12
    else:
        prev_year,prev_month = year,month-1

    prev_key=f"{prev_year}-{str(prev_month).zfill(2)}"

    # -------- PREVIOUS EXPENSES --------
    prev_start=datetime(prev_year,prev_month,1)
    prev_end=datetime(prev_year+1,1,1) if prev_month==12 else datetime(prev_year,prev_month+1,1)

    prev_txns = Expense.query.filter(
        Expense.user_id == request.user_id,
        Expense.date >= prev_start.strftime("%Y-%m-%d"),
        Expense.date < prev_end.strftime("%Y-%m-%d")
    ).all()

    prev_spend=sum(t.amount for t in prev_txns)
    
    prev_txn_count = len(prev_txns)

    txn_change_pct = 0
    if prev_txn_count > 0:
        txn_change_pct = ((txn_count - prev_txn_count) / prev_txn_count) * 100

    change_pct=0
    if prev_spend>0:
        change_pct=((total_spend-prev_spend)/prev_spend)*100

    # -------- PREVIOUS AVG --------
    prev_days=calendar.monthrange(prev_year,prev_month)[1]
    prev_avg=prev_spend/max(prev_days,1)

    avg_change_pct=0
    if prev_avg>0:
        avg_change_pct=((avg_day-prev_avg)/prev_avg)*100

    # -------- PREVIOUS BUDGET --------
    prev_budget = Budget.query.filter_by(
        user_id=user_id,
        month_key=prev_key
    ).first()

    budget_change_pct=0
    if budget and prev_budget:

        curr_total = (
            budget.food +
            budget.shopping +
            budget.transport +
            budget.bills +
            budget.others
        )

        prev_total = (
            prev_budget.food +
            prev_budget.shopping +
            prev_budget.transport +
            prev_budget.bills +
            prev_budget.others
        )

        if prev_total>0:
            budget_change_pct=((curr_total-prev_total)/prev_total)*100

    # -------- RETURN --------
    return jsonify({
        "total_spend": round(total_spend),
        "avg_day": round(avg_day,1),
        "txn_count": txn_count,
        "budget_used": round(budget_used_pct),
        "change_pct": round(change_pct),
        "avg_change_pct": round(avg_change_pct),
        "budget_change_pct": round(budget_change_pct),
        "txn_change_pct": round(txn_change_pct)
    })
    


# @app.route("/smart-tips/<month_key>")
# def smart_tips(month_key):
@app.route("/smart-tips/<month_key>")
@require_auth
def smart_tips(month_key):

    from datetime import datetime
    import calendar

    user_id= request.user_id

    year,month=map(int,month_key.split("-"))
    start=datetime(year,month,1)

    if month==12:
        end=datetime(year+1,1,1)
    else:
        end=datetime(year,month+1,1)

    txns = Expense.query.filter(
        Expense.user_id == request.user_id,
        Expense.date >= start.strftime("%Y-%m-%d"),
        Expense.date < end.strftime("%Y-%m-%d")
    ).all()

    total_spend=sum(t.amount for t in txns)

    # ---------- DAYS ----------
    today=datetime.today()

    if today.year==year and today.month==month:
        day=today.day
    else:
        day=calendar.monthrange(year,month)[1]

    days_in_month=calendar.monthrange(year,month)[1]

    month_progress=day/days_in_month

    # ---------- CATEGORY TOTALS ----------
    category_spend={}
    for t in txns:
        category_spend[t.category]=category_spend.get(t.category,0)+t.amount

    # ---------- BUDGET ----------
    budget=Budget.query.filter_by(user_id=user_id,month_key=month_key).first()

    tips=[]

    if budget:

        budgets={
            "Food":budget.food,
            "Shopping":budget.shopping,
            "Transport":budget.transport,
            "Bills":budget.bills,
            "Others":budget.others
        }

        total_budget=sum(budgets.values())

        # =============================
        # 1️⃣ TOTAL PACING CHECK
        # =============================
        if total_budget>0:

            usage=total_spend/total_budget

            if usage>month_progress+0.20:
                tips.append({
                    "title":"Spending too fast",
                    "msg":f"You've used {int(usage*100)}% of your budget but only {int(month_progress*100)}% of month passed.",
                    "score":95,
                    "type":"warning"
                })

            elif usage<month_progress-0.20:
                tips.append({
                    "title":"Great pacing",
                    "msg":"Your spending is well controlled this month.",
                    "score":40,
                    "type":"good"
                })

        # =============================
        # 2️⃣ CATEGORY EARLY WARNING
        # =============================
        for cat,spent in category_spend.items():

            b=budgets.get(cat,0)
            if b<=0: continue

            pct=spent/b

            # spent 40% in first 20% month → warning
            if pct>0.4 and month_progress<0.3:

                tips.append({
                    "title":f"{cat} spending high early",
                    "msg":f"You already used {int(pct*100)}% of {cat} budget very early.",
                    "score":90,
                    "type":"danger"
                })

            elif pct>0.8:

                tips.append({
                    "title":f"{cat} budget almost finished",
                    "msg":f"{cat} budget is {int(pct*100)}% used.",
                    "score":85,
                    "type":"warning"
                })

            elif pct<month_progress:

                tips.append({
                    "title":f"{cat} under control",
                    "msg":f"{cat} spending looks healthy.",
                    "score":30,
                    "type":"good"
                })

        # =============================
        # 3️⃣ SAVINGS CHECK
        # =============================
        if budget.savings>0:

            # spendable=budget.income-budget.savings
            spendable = max(budget.income - budget.savings, 0)

            if spendable>0 and total_spend>spendable:

                tips.append({
                    "title":"Savings goal broken",
                    "msg":"You exceeded spendable income. Savings at risk.",
                    "score":100,
                    "type":"danger"
                })

    # ---------- ALWAYS HAVE SOMETHING ----------
    if not budget:
        tips.append({
            "title":"No Budget set",
            "msg":"Add budget to unlock better insights.",
            "score":10,
            "type":"info"
        })
    elif not tips:
        tips.append({
            "title":"Good Start",
            "msg":"Add expenses to unlock smart insights.",
            "score":10,
            "type":"info"
        })

    # ---------- SORT + RETURN TOP MANY ----------
    tips.sort(key=lambda x:x["score"],reverse=True)

    return jsonify(tips[:12])

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)


