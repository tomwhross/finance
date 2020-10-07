import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, validate_transaction

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

    # get the user's current cash on hand
    user_cash_data = db.execute(
        "SELECT cash FROM users WHERE id = :user_id;", user_id=session["user_id"]
    )

    # get the user's current stock data
    user_stock_data = db.execute(
        "SELECT symbol, name, SUM(shares) AS 'shares' FROM shares WHERE user_id = :user_id GROUP BY symbol, name ORDER BY symbol desc;",
        user_id=session["user_id"],
    )

    # if the user current owns any stocks
    # set a running total of their current stock worth
    # lookup the current value (price) of their stocks
    # update the running totals (per stock and for all stocks)
    if user_stock_data:
        total_stock_price = 0
        for stock in user_stock_data:
            current_stock_price = lookup(stock["symbol"])["price"]
            stock["price"] = usd(current_stock_price)
            stock["total"] = usd(current_stock_price * stock["shares"])
            total_stock_price = (
                total_stock_price + current_stock_price * stock["shares"]
            )
        total = user_cash_data[0]["cash"] + total_stock_price
    else:
        total = user_cash_data[0]["cash"]

    return render_template(
        "index.html",
        cash_amount=usd(user_cash_data[0]["cash"]),
        total_amount=usd(total),
        user_stock_data=user_stock_data,
    )


@app.route("/add_funds", methods=["GET", "POST"])
@login_required
def add_funds():
    """Add to cash on hand"""

    user_cash_data = db.execute(
        "SELECT cash FROM users WHERE id = :user_id;", user_id=session["user_id"]
    )

    cash_amount = user_cash_data[0]["cash"]
    if request.method == "GET":
        return render_template("add_funds.html", current_cash=usd(cash_amount))

    # if POST
    funds_to_add = request.form.get("amount")
    db.execute(
        "UPDATE users SET cash = (cash + :cash_amount) WHERE id = :user_id;",
        cash_amount=funds_to_add,
        user_id=session["user_id"],
    )

    return redirect("/")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # render the buy template on GET
    if request.method == "GET":
        return render_template("buy.html")

    # if POST

    # get the symbol and number of shares from the form
    symbol = request.form.get("symbol")
    shares = request.form.get("shares")

    error_message = validate_transaction(symbol, shares)
    if error_message:
        return apology(*error_message)

    # lookup the stock based on the symbol
    stock_data = lookup(symbol)

    # report to the user if the stock is not found based on the symbol
    if not stock_data:
        return apology("stock not found", 418)

    user_cash_data = db.execute(
        "SELECT cash FROM users WHERE id = :user_id;", user_id=session["user_id"]
    )
    cash_amount = user_cash_data[0]["cash"]

    # report to the user if they do not have enough cash on hand to make the purchase
    if shares * stock_data["price"] > cash_amount:
        return apology("not enough cash", 418)

    # update the user's cash on hand amount
    cash_amount = cash_amount - shares * stock_data["price"]
    db.execute(
        "UPDATE users SET cash = :cash_amount WHERE id = :user_id;",
        cash_amount=cash_amount,
        user_id=session["user_id"],
    )

    # record the purchase of the stock
    db.execute(
        "INSERT INTO shares (user_id, symbol, name, shares, price) VALUES (:user_id, :symbol, :name, :shares, :price);",
        user_id=session["user_id"],
        symbol=stock_data["symbol"],
        name=stock_data["name"],
        shares=shares,
        price=stock_data["price"],
    )

    return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    user_stock_data = db.execute(
        "SELECT symbol, name, shares, price, transacted FROM shares WHERE user_id = :user_id ORDER BY transacted DESC;",
        user_id=session["user_id"],
    )

    return render_template("history.html", user_stock_data=user_stock_data)


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
        rows = db.execute(
            "SELECT * FROM users WHERE username = :username",
            username=request.form.get("username"),
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
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
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")

    # get the stock symbol the user submitted
    symbol = request.form.get("symbol")

    # report to the user that they must provide a stock symbol to lookup
    if not symbol:
        return apology("you must provide a stock symbol", 418)

    # lookup the stock data based on the symbol
    stock_data = lookup(symbol)

    # report to the user if the stock is not found
    if not stock_data:
        return apology(f"stock not found: {symbol}", 418)

    # display the current stock data to the user
    return render_template(
        "quoted.html",
        company_name=stock_data["name"],
        symbol=stock_data["symbol"],
        price=usd(stock_data["price"]),
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username")
    password = request.form.get("password")
    confirm_password = request.form.get("confirm_password")
    if not username:
        return apology("must provide username", 418)

    if not password:
        return apology("must provide password", 418)

    if not confirm_password:
        return apology("must confirm password", 418)

    if password != confirm_password:
        return apology("passwords did not match", 418)

    row = db.execute(
        "SELECT 1 AS 'check' FROM users WHERE username = :username;", username=username
    )
    if row:
        return apology("username already taken", 418)

    hashed_password = generate_password_hash(password)

    db.execute(
        "INSERT INTO users (username, hash) VALUES (:username, :hashed_password);",
        username=username,
        hashed_password=hashed_password,
    )

    return redirect("/login")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # render the sell template on GET
    if request.method == "GET":
        return render_template("sell.html")

    # if POST

    # get the symbol and number of shares from the form
    symbol = request.form.get("symbol")
    shares = request.form.get("shares")

    error_message = validate_transaction(symbol, shares)
    if error_message:
        return apology(*error_message)

    # lookup the stock based on the symbol
    stock_data = lookup(symbol)

    # report to the user if the stock is not found based on the symbol
    if not stock_data:
        return apology("stock not found", 418)

    # get the user's amount of owned stock for the symbol
    user_stock_data = db.execute(
        "SELECT SUM(shares) AS 'shares' FROM shares WHERE user_id = :user_id AND symbol = :symbol;",
        user_id=session["user_id"],
        symbol=stock_data["symbol"],
    )

    # let the user know if they do not own any shares of the stock
    if not user_stock_data or not user_stock_data[0]["shares"]:
        return apology(f"You do not own any shares of {symbol}", 418)

    # report to the user if they attempt to sell more shares than they own
    currently_owned_shares = user_stock_data[0]["shares"]
    if int(shares) > currently_owned_shares:
        return apology(
            f"You are trying to sell more shares of {symbol} than you own ({currently_owned_shares})",
            418,
        )

    # calculate the current total sell price
    # could get the API here again to get a fresher price
    sell_price_total = shares * stock_data["price"]

    # get the user's current cash on hand so we can update (add the total sell price)
    user_cash_data = db.execute(
        "SELECT cash FROM users WHERE id = :user_id;", user_id=session["user_id"]
    )
    cash_amount = user_cash_data[0]["cash"] + sell_price_total

    # update the user's cash on hand amount
    db.execute(
        "UPDATE users SET cash = :cash_amount WHERE id = :user_id;",
        cash_amount=cash_amount,
        user_id=session["user_id"],
    )

    # record the purchase of the stock
    db.execute(
        "INSERT INTO shares (user_id, symbol, name, shares, price) VALUES (:user_id, :symbol, :name, :shares, :price);",
        user_id=session["user_id"],
        symbol=stock_data["symbol"],
        name=stock_data["name"],
        shares=(shares * -1),
        price=stock_data["price"],
    )

    return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
