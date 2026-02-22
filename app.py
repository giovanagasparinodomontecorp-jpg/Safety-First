from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "safety_first.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key-change-in-production")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)

PRIORITIES = ["Baixa", "Média", "Alta", "Crítica"]
STATUSES = ["Aberto", "Em atendimento", "Aguardando terceiros", "Resolvido", "Cancelado"]
OCCURRENCE_TYPES = ["Acidente", "Risco", "Estrutural", "Elétrica", "Ambiental", "Outros"]


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    with open(BASE_DIR / "schema.sql", "r", encoding="utf-8") as f:
        db.executescript(f.read())

    user_count = db.execute("SELECT COUNT(*) as total FROM users").fetchone()["total"]
    if user_count == 0:
        db.executemany(
            "INSERT INTO users (name, email, role, password) VALUES (?, ?, ?, ?)",
            [
                ("Administrador", "admin@safety.local", "administrador", "admin123"),
                ("João Operação", "joao@safety.local", "responsavel", "123"),
                ("Maria Segurança", "maria@safety.local", "usuario", "123"),
                ("Gestor Geral", "gestor@safety.local", "administrador", "123"),
            ],
        )

    area_count = db.execute("SELECT COUNT(*) as total FROM areas").fetchone()["total"]
    if area_count == 0:
        db.executemany(
            "INSERT INTO areas (name, manager_user_id) VALUES (?, ?)",
            [
                ("Caldeiras", 2),
                ("Subestação", 2),
                ("Produção", 2),
                ("Pátio Industrial", 2),
            ],
        )

    db.commit()
    db.close()


def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapped


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if session.get("role") not in roles:
                flash("Acesso negado para seu perfil.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)

        return wrapped

    return decorator


def send_priority_notification(occurrence_row, area_manager_email, upper_manager_email=None):
    if occurrence_row["priority"] not in ["Alta", "Crítica"]:
        return

    subject = "⚠️ Nova Ocorrência Crítica – Ação Imediata Necessária" if occurrence_row["priority"] == "Crítica" else "⚠️ Nova Ocorrência Alta – Acompanhamento Necessário"
    body = (
        f"Local: {occurrence_row['area_name']}\n"
        f"Descrição: {occurrence_row['description']}\n"
        f"Prioridade: {occurrence_row['priority']}\n"
        f"Link: /occurrences/{occurrence_row['id']}\n"
    )

    recipients = [area_manager_email]
    if occurrence_row["priority"] == "Crítica" and upper_manager_email:
        recipients.append(upper_manager_email)

    print("=" * 60)
    print("EMAIL AUTOMÁTICO DISPARADO")
    print(f"Para: {', '.join(recipients)}")
    print(f"Assunto: {subject}")
    print(body)
    print("=" * 60)


@app.route("/")
def root():
    return redirect(url_for("dashboard")) if session.get("user_id") else redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE email = ? AND password = ?", (email, password)
        ).fetchone()
        if user:
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        flash("Credenciais inválidas.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()

    period_days = int(request.args.get("period", 30))
    period_clause = "datetime(created_at) >= datetime('now', ?)"
    param = (f"-{period_days} days",)

    total_open = db.execute(
        f"SELECT COUNT(*) as total FROM occurrences WHERE status != 'Resolvido' AND {period_clause}", param
    ).fetchone()["total"]

    by_priority = db.execute(
        f"SELECT priority, COUNT(*) as total FROM occurrences WHERE {period_clause} GROUP BY priority", param
    ).fetchall()

    by_area = db.execute(
        f"SELECT a.name as area, COUNT(o.id) as total FROM areas a LEFT JOIN occurrences o ON o.area_id = a.id AND {period_clause} GROUP BY a.id ORDER BY total DESC",
        param,
    ).fetchall()

    by_status = db.execute(
        f"SELECT status, COUNT(*) as total FROM occurrences WHERE {period_clause} GROUP BY status", param
    ).fetchall()

    avg_resolution = db.execute(
        """
        SELECT AVG((julianday(closed_at) - julianday(created_at)) * 24.0) as avg_hours
        FROM occurrences
        WHERE status = 'Resolvido' AND closed_at IS NOT NULL
        """
    ).fetchone()["avg_hours"]

    recent = db.execute(
        """
        SELECT o.id, o.description, o.priority, o.status, o.created_at, a.name as area_name
        FROM occurrences o
        JOIN areas a ON a.id = o.area_id
        ORDER BY o.created_at DESC
        LIMIT 10
        """
    ).fetchall()

    return render_template(
        "dashboard.html",
        total_open=total_open,
        by_priority=by_priority,
        by_area=by_area,
        by_status=by_status,
        avg_resolution=round(avg_resolution, 2) if avg_resolution else None,
        period_days=period_days,
        recent=recent,
    )


@app.route("/occurrences/new", methods=["GET", "POST"])
@login_required
def new_occurrence():
    db = get_db()
    areas = db.execute("SELECT id, name FROM areas ORDER BY name").fetchall()
    area_responsibles = db.execute(
        "SELECT id, name, email FROM users WHERE role IN ('responsavel', 'administrador')"
    ).fetchall()

    if request.method == "POST":
        area_id = request.form.get("area_id")
        occurrence_type = request.form.get("occurrence_type")
        description = request.form.get("description", "").strip()
        priority = request.form.get("priority")
        responsible_id = request.form.get("responsible_id")

        if not all([area_id, occurrence_type, description, priority, responsible_id]):
            flash("Preencha todos os campos obrigatórios.", "danger")
            return render_template(
                "new_occurrence.html",
                areas=areas,
                priorities=PRIORITIES,
                occurrence_types=OCCURRENCE_TYPES,
                users=area_responsibles,
            )

        cur = db.execute(
            """
            INSERT INTO occurrences (
                area_id, occurrence_type, description, priority, status,
                requester_id, responsible_id, created_at
            ) VALUES (?, ?, ?, ?, 'Aberto', ?, ?, ?)
            """,
            (
                area_id,
                occurrence_type,
                description,
                priority,
                session["user_id"],
                responsible_id,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        occurrence_id = cur.lastrowid

        files = request.files.getlist("images")
        for image in files:
            if image and image.filename:
                filename = f"{occurrence_id}_{datetime.now().timestamp()}_{image.filename}"
                save_path = UPLOAD_DIR / filename
                image.save(save_path)
                db.execute(
                    "INSERT INTO occurrence_images (occurrence_id, file_path) VALUES (?, ?)",
                    (occurrence_id, str(save_path.relative_to(BASE_DIR))),
                )

        db.execute(
            """
            INSERT INTO occurrence_history (occurrence_id, user_id, old_status, new_status, comment, changed_at)
            VALUES (?, ?, NULL, 'Aberto', ?, ?)
            """,
            (
                occurrence_id,
                session["user_id"],
                "Ocorrência criada.",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

        occurrence = db.execute(
            """
            SELECT o.*, a.name as area_name, u.email as responsible_email
            FROM occurrences o
            JOIN areas a ON a.id = o.area_id
            JOIN users u ON u.id = o.responsible_id
            WHERE o.id = ?
            """,
            (occurrence_id,),
        ).fetchone()

        upper_manager = db.execute(
            "SELECT email FROM users WHERE role = 'administrador' ORDER BY id LIMIT 1"
        ).fetchone()

        send_priority_notification(
            occurrence,
            area_manager_email=occurrence["responsible_email"],
            upper_manager_email=upper_manager["email"] if upper_manager else None,
        )

        db.commit()
        flash("Ocorrência registrada com sucesso!", "success")
        return redirect(url_for("occurrence_detail", occurrence_id=occurrence_id))

    return render_template(
        "new_occurrence.html",
        areas=areas,
        priorities=PRIORITIES,
        occurrence_types=OCCURRENCE_TYPES,
        users=area_responsibles,
    )


@app.route("/occurrences/<int:occurrence_id>", methods=["GET", "POST"])
@login_required
def occurrence_detail(occurrence_id: int):
    db = get_db()

    if request.method == "POST":
        old_status = request.form.get("old_status")
        new_status = request.form.get("status")
        comment = request.form.get("comment", "").strip()

        closed_at = datetime.now().isoformat(timespec="seconds") if new_status == "Resolvido" else None
        db.execute(
            "UPDATE occurrences SET status = ?, closed_at = COALESCE(?, closed_at) WHERE id = ?",
            (new_status, closed_at, occurrence_id),
        )
        db.execute(
            """
            INSERT INTO occurrence_history (occurrence_id, user_id, old_status, new_status, comment, changed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                occurrence_id,
                session["user_id"],
                old_status,
                new_status,
                comment,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        db.commit()
        flash("Status atualizado.", "success")

    occurrence = db.execute(
        """
        SELECT o.*, a.name as area_name, r.name as responsible_name, req.name as requester_name
        FROM occurrences o
        JOIN areas a ON a.id = o.area_id
        JOIN users r ON r.id = o.responsible_id
        JOIN users req ON req.id = o.requester_id
        WHERE o.id = ?
        """,
        (occurrence_id,),
    ).fetchone()

    history = db.execute(
        """
        SELECT h.*, u.name as changed_by
        FROM occurrence_history h
        JOIN users u ON u.id = h.user_id
        WHERE h.occurrence_id = ?
        ORDER BY h.changed_at DESC
        """,
        (occurrence_id,),
    ).fetchall()

    images = db.execute(
        "SELECT file_path FROM occurrence_images WHERE occurrence_id = ?", (occurrence_id,)
    ).fetchall()

    return render_template(
        "occurrence_detail.html",
        occurrence=occurrence,
        statuses=STATUSES,
        history=history,
        images=images,
    )


@app.route("/reports")
@login_required
@role_required("responsavel", "administrador")
def reports():
    db = get_db()

    qty_by_area = db.execute(
        """
        SELECT a.name as area_name, COUNT(o.id) as total
        FROM areas a
        LEFT JOIN occurrences o ON o.area_id = a.id
        GROUP BY a.id
        ORDER BY total DESC
        """
    ).fetchall()

    qty_by_risk = db.execute(
        "SELECT priority, COUNT(*) as total FROM occurrences GROUP BY priority ORDER BY total DESC"
    ).fetchall()

    avg_service_time = db.execute(
        """
        SELECT AVG((julianday(closed_at) - julianday(created_at)) * 24.0) as avg_hours
        FROM occurrences
        WHERE closed_at IS NOT NULL
        """
    ).fetchone()["avg_hours"]

    recurrence_index = db.execute(
        """
        SELECT a.name as area_name, occurrence_type, COUNT(*) as total
        FROM occurrences o
        JOIN areas a ON a.id = o.area_id
        GROUP BY a.name, occurrence_type
        HAVING total > 1
        ORDER BY total DESC
        """
    ).fetchall()

    monthly_evolution = db.execute(
        """
        SELECT strftime('%Y-%m', created_at) as year_month, COUNT(*) as total
        FROM occurrences
        GROUP BY year_month
        ORDER BY year_month
        """
    ).fetchall()

    return render_template(
        "reports.html",
        qty_by_area=qty_by_area,
        qty_by_risk=qty_by_risk,
        avg_service_time=round(avg_service_time, 2) if avg_service_time else None,
        recurrence_index=recurrence_index,
        monthly_evolution=monthly_evolution,
    )


@app.route("/reports/export/<fmt>")
@login_required
def export_reports(fmt: str):
    if fmt not in {"pdf", "excel"}:
        flash("Formato de exportação inválido.", "danger")
        return redirect(url_for("reports"))
    flash(f"Exportação {fmt.upper()} simulada com sucesso (placeholder).", "info")
    return redirect(url_for("reports"))


if __name__ == "__main__":
    if not DB_PATH.exists():
        init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
