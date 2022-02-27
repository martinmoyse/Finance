import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    
    """Show portfolio of stocks"""
    holdings = db.execute("SELECT * FROM transactions WHERE user_id =?",session["user_id"])
    symbols = {}
    keys = []
    values = []
    length = 0
    k = len(holdings)
    for i in range(k):
        if not holdings[i].get('symbol') in symbols:
            tmp = {holdings[i].get('symbol') : holdings[i].get('shares')}
            symbols.update(tmp)
        else:
            key = holdings[i].get('symbol')
            if holdings[i].get('action') == "BUY":
                sh = symbols[key] + holdings[i].get('shares')
                tmp = {holdings[i].get('symbol') : sh}
                symbols.update(tmp)
                if sh <= 0:
                    del symbols[key]
            else:
                sh = symbols[key] - holdings[i].get('shares')
                tmp = {holdings[i].get('symbol') : sh}
                symbols.update(tmp)
                if sh <= 0:
                    del symbols[key]
            
        values = list(symbols.values())
        keys = list(symbols.keys())
        length = len(symbols)
        
    to_lookup = list(keys)
    prices = []
    names = []
    k = len(to_lookup)
    total = 0.
    for i in range(k):
        tmp = lookup(to_lookup[i])
        prices.append(tmp.get('price'))
        names.append(tmp.get('name'))
        total += prices[i] * values[i]
    total = round(total,2)
    extract_cash = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])
    cash = round(extract_cash[0].get('cash'),2)
    total += cash
    return render_template("index.html", symbols=symbols, values=values, keys=keys, length=length, prices=prices, cash=cash, total=total, names=names)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        unallocated = db.execute("SELECT cash FROM users WHERE id=?",session["user_id"])
        return render_template("buy.html", unallocated=unallocated)
    else:
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if not symbol or lookup(symbol) == None:
            return apology("Symbol does not exist.")
            
        if shares.isdigit() == False:
            return apology("Please enter positive integer")

        if shares <= '0':
            return apology("You must purchase at least 1 share.")

        stock = lookup(symbol)
        values = stock.values()
        values_list = list(values)
        price = values_list[1]
        symbol= values_list[2]

        user_balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        user_balance = float(user_balance[0].get('cash'))
        amount = price*float(shares)
        balance_new = user_balance - amount
        
        
        if (amount <= user_balance):
            db.execute("UPDATE users SET cash=? WHERE id=?", balance_new, session["user_id"])
            db.execute("INSERT INTO transactions (user_id, symbol, price, shares, action) VALUES(?,?,?,?,?)",session["user_id"], symbol, price, shares,"BUY")
            return redirect("/")
        if (amount > user_balance):
            return apology("insufficient funds")


@app.route("/history")
@login_required
def history():
    history = db.execute("SELECT * FROM transactions WHERE user_id=?",session["user_id"])
    print(history)
    length = len(history)
    return render_template("history.html", history=history, length=length)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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
    if request.method == "GET":
        return render_template("quote.html")

    if request.method == "POST":
        symbol = request.form.get("symbol")
        response = lookup(symbol)
        return render_template("quoted.html", response=response)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        if not request.form.get("username") or not request.form.get("password"):
            return apology("Username and password needed.")

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("missing username")
        elif not password:
            return apology("missing password")
        elif not confirmation:
            return apology("missing password confirmation")
        elif password != confirmation:
            return apology("passwords do not match")

        hash = generate_password_hash(password)

        try:
            db.execute("INSERT INTO users (username, hash, cash) VALUES(?,?,10000.00)", username, hash)
            return redirect("/")
        except:
            return apology("username already exists")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    
    if request.method == "GET":
        holdings = db.execute("SELECT * FROM transactions WHERE user_id =?",session["user_id"])
        symbols = {}
        keys = []
        length = 0
        k = len(holdings)
        for i in range(k):
            if not holdings[i].get('symbol') in symbols:
                tmp = {holdings[i].get('symbol') : holdings[i].get('shares')}
                symbols.update(tmp)
            else:
                key = holdings[i].get('symbol')
                if holdings[i].get('action') == "BUY":
                    sh = symbols[key] + holdings[i].get('shares')
                    tmp = {holdings[i].get('symbol') : sh}
                    symbols.update(tmp)
                    if sh <= 0:
                        del symbols[key]
                else:
                    sh = symbols[key] - holdings[i].get('shares')
                    tmp = {holdings[i].get('symbol') : sh}
                    symbols.update(tmp)
                    if sh <= 0:
                        del symbols[key]
        keys = list(symbols.keys())
        length = len(symbols)
        return render_template("sell.html", length=length, keys=keys)

    if request.method == "POST":
        symbol = request.form.get('symbol')
        shares_to_sell = request.form.get('shares')
        if not symbol or not shares_to_sell:
            return apology("Please enter stock and number of shares.")
        
        if shares_to_sell.isdigit() == False:
            return apology("Please enter positive integer")
        shares_to_sell = int(shares_to_sell)
        
        
        
        
        stock = db.execute("SELECT shares FROM transactions WHERE user_id =? AND symbol =?",session["user_id"], symbol)
        shares = int(stock[0].get('shares'))
        
        if shares_to_sell > shares:
            return apology("You are trying to sell more shares than you currently have.")   
        elif shares_to_sell <= 0:
            return apology("You cannot sell fewer than 1 shares.")
        
        
        tmp = lookup(symbol)
        price = tmp['price']
        profit = price * shares_to_sell
        print(profit) 
        
        tmp2 = db.execute("SELECT cash FROM users  WHERE id=?", session["user_id"])
        cash = tmp2[0].get('cash')
        
        cash_new = cash + profit
        print(cash_new)
        db.execute("UPDATE users SET cash=? WHERE id=?", cash_new, session["user_id"])
        db.execute("INSERT INTO transactions (user_id, symbol, price, shares, action) VALUES(?,?,?,?,?)",session["user_id"], symbol, price, shares_to_sell,"SELL")
        return redirect("/")
        
def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
