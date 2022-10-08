import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd
from datetime import datetime


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    portfolios = db.execute("SELECT * FROM portfolios WHERE user_id = ?", user_id)
    data = db.execute("SELECT * FROM users WHERE id = ?", user_id)
    cash = data[0]["cash"]
    total_cash = 0
    for portfolio in portfolios:
        total_cash += portfolio["total"]

    return render_template("layout.html", portfolios=portfolios, cash=cash, lookup=lookup, usd=usd, total_cash=total_cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        symbol = symbol.upper()

        shares = request.form.get("shares")

        # datetime object containing current date and time
        time = datetime.now()

        if not symbol:
            return apology("Invalid Symbol", 400)

        check = lookup(symbol)
        if check == None:
            return apology("Invalid Symbol", 400)

        if not shares:
            return apology("Invalid Number of Shares", 400)
        else:
            shares = int(shares)

        if shares < 1:
            return apology("Invalid Number of Shares")

        price = check["price"]
        total_price = float(price * shares)

        user_id = session["user_id"]
        data = db.execute("SELECT * FROM users WHERE id = ?", user_id)
        cash = data[0]["cash"]

        if total_price > cash:
            return apology("Insufficient Funds")
        else:
            db.execute("INSERT INTO history (user_id, shares, price, transaction_date, symbol) VALUES(?, ?, ?, ?, ?)",
            user_id, shares, price, time, symbol)
            cash -= total_price
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, user_id)

        portfolios = db.execute("SELECT * FROM portfolios WHERE user_id = ?", user_id)
        count = 0

        for i in range(len(portfolios)):
            if (portfolios[i]["symbol"] == symbol):
                count += 1

        if count == 0:
            db.execute("INSERT INTO portfolios (user_id, symbol, shares, total) VALUES(?, ?, ?, ?)",
            user_id, symbol, shares, total_price)
        else:
            for portfolio in portfolios:
                if portfolio["symbol"] == symbol:
                    shares += int(portfolio["shares"])
                    total_price += float(portfolio["total"])
                    db.execute("UPDATE portfolios SET shares = ? WHERE symbol = ?", shares, symbol)
                    db.execute("UPDATE portfolios SET total = ? WHERE symbol = ?", total_price, symbol)
                    break

        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    history_table = db.execute("SELECT * FROM history WHERE user_id = ?", user_id)
    return render_template("/history.html", history_table=history_table)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Must Provide Username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Must Provide Password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("Invalid Username and/or Password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("Invalid Symbol", 400)

        check = lookup(symbol)
        if check == None:
            return apology("Invalid Symbol", 400)
        else:
            name = check["name"]
            price = check["price"]
            stock = check["symbol"]

        return render_template("quoted.html", name=name, price=price, stock=stock, usd=usd)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Ensure username was submitted
        if not username:
            return apology("Must Provide Username", 400)

        # Ensure password was submitted
        elif not password:
            return apology("Must Provide Password", 400)

        elif not confirmation:
            return apology("Please Confrim Password", 400)

        if password != confirmation:
            return apology("Dasswords Do Not Match", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        if len(rows) != 0:
            return apology("Username Taken", 400)

        hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)

        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash)

        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]
    portfolios = db.execute("SELECT * FROM portfolios WHERE user_id = ?", user_id)
    data = db.execute("SELECT * FROM users WHERE id = ?", user_id)

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        time = datetime.now()

        if not symbol:
            return apology("Invalid Symbol", 400)

        if not shares:
            return apology("Invalid Number of Shares", 400)
        else:
            shares = int(shares)

        if shares < 1:
            return apology("Invalid Number of Shares", 400)

        for portfolio in portfolios:
            if portfolio["symbol"] == symbol:
                shares_owned = portfolio["shares"]
                price = portfolio["total"]

        if shares_owned < shares:
            return apology("Not Enough Shares Owned", 400)

        check = lookup(symbol)
        share_price = check["price"]
        shares_owned -= shares
        total_price = shares_owned * share_price
        price -= total_price
        cash = data[0]["cash"]
        cash += price
        db.execute("UPDATE portfolios SET shares = ? WHERE symbol = ?", shares_owned, symbol)
        db.execute("UPDATE portfolios SET total = ? WHERE symbol = ?", total_price, symbol)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, user_id)
        db.execute("DELETE FROM portfolios WHERE shares = 0")
        db.execute("INSERT INTO history (user_id, shares, price, transaction_date, symbol) VALUES(?, ?, ?, ?, ?)",
        user_id, (shares * -1), share_price, time, symbol)
        return redirect("/")
    else:

        return render_template("sell.html", portfolios=portfolios)
