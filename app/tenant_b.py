from flask import Flask, render_template, request, redirect, url_for, session, flash, g
import re

app = Flask(__name__, template_folder="templates_b")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.secret_key = "dev-secret-do-not-use-in-production-tenant-b"

# Same underlying product, different field label and name attribute.
MEMBERS = {
    "12345": {
        "id": "12345",
        "name": "Jane Smith",
        "accounts": [
            {"type": "Savings", "number": "100-12345-0", "balance": 5420.75},
            {"type": "Checking", "number": "200-12345-9", "balance": 1840.20},
        ],
    },
    "67890": {
        "id": "67890",
        "name": "Robert Chen",
        "accounts": [
            {"type": "Savings", "number": "100-67890-1", "balance": 120.00},
        ],
    },
}

VALID_CREDENTIALS = {"teller": "password123"}


@app.before_request
def require_login():
    allowed = {"login", "do_login", "static"}
    if request.endpoint in allowed:
        return
    if not session.get("logged_in"):
        return redirect(url_for("login"))


@app.route("/")
def login():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def do_login():
    username = request.form.get("f1", "").strip()
    password = request.form.get("f2", "").strip()
    if VALID_CREDENTIALS.get(username) == password:
        session["logged_in"] = True
        session["username"] = username
        return redirect(url_for("search"))
    flash("Invalid credentials")
    return redirect(url_for("login"))


@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "POST":
        member_id = request.form.get("f4", "").strip()
        if member_id in MEMBERS:
            return redirect(url_for("member_detail", member_id=member_id))
        flash("Member not found")
    return render_template("search.html")


@app.route("/member/<member_id>")
def member_detail(member_id):
    member = MEMBERS.get(member_id)
    if not member:
        flash("Member not found")
        return redirect(url_for("search"))
    return render_template("member_detail.html", member=member)


@app.route("/open_account/<member_id>", methods=["GET", "POST"])
def open_account(member_id):
    member = MEMBERS.get(member_id)
    if not member:
        flash("Member not found")
        return redirect(url_for("search"))

    if request.method == "POST":
        account_type = request.form.get("account_type", "").strip()
        deposit = request.form.get("initial_deposit", "").strip()
        if account_type and re.match(r"^\d+(\.\d{1,2})?$", deposit):
            new_number = f"{300 if account_type == 'Checking' else 100}-{member_id}-{len(member['accounts'])}"
            member["accounts"].append({
                "type": account_type,
                "number": new_number,
                "balance": float(deposit),
            })
            return redirect(url_for("confirmation", member_id=member_id, new_account=new_number))
        flash("Please enter a valid deposit amount")

    return render_template("open_account.html", member=member)


@app.route("/confirmation/<member_id>")
def confirmation(member_id):
    member = MEMBERS.get(member_id)
    if not member:
        flash("Member not found")
        return redirect(url_for("search"))
    new_account = request.args.get("new_account", "")
    return render_template("confirmation.html", member=member, new_account=new_account)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
