"""
=============================================================================
PROJET 2 : PIPELINE ETL D'INGESTION AUTOMATISÉE VERS BASE SQL RELATIONNELLE
Module : etl_pipeline.py
Description : Ingestion, validation d'intégrité et chargement des 12 snapshots
              SIRH mensuels dans la base SQLite 'bic_controlling.db' structurée
              selon un schéma dimensionnel en étoile (Kimball).
Auteur : Jean-Yves Lorenzi KOUTSENE
=============================================================================
"""

import os
from pathlib import Path
import sqlite3
import pandas as pd


def get_db_connection(db_path: Path) -> sqlite3.Connection:
    """Établit la connexion SQLite et active le contrôle strict des clés étrangères."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def initialize_database_schema(conn: sqlite3.Connection, ddl_path: Path):
    """Exécute le script DDL pour créer le schéma en étoile (Star Schema)."""
    if not ddl_path.exists():
        raise FileNotFoundError(f"Fichier DDL introuvable : {ddl_path}")
    
    with open(ddl_path, "r", encoding="utf-8") as f:
        ddl_script = f.read()

    conn.executescript(ddl_script)
    conn.commit()
    print("[1/4] Schéma relationnel initialisé avec succès (4 tables créées).")


def populate_dimension_tables(conn: sqlite3.Connection, raw_files: list):
    """Alimente les dimensions techniques : dim_calendar, dim_department et dim_employee."""
    cursor = conn.cursor()

    # 1. Alimentation de dim_calendar
    calendar_data = [
        ("2026-01-31", 1, "Janvier", "Q1", 2026, 0),
        ("2026-02-28", 2, "Février", "Q1", 2026, 0),
        ("2026-03-31", 3, "Mars", "Q1", 2026, 0),
        ("2026-04-30", 4, "Avril", "Q2", 2026, 0),
        ("2026-05-31", 5, "Mai", "Q2", 2026, 0),
        ("2026-06-30", 6, "Juin", "Q2", 2026, 0),
        ("2026-07-31", 7, "Juillet", "Q3", 2026, 0),
        ("2026-08-31", 8, "Août", "Q3", 2026, 0),
        ("2026-09-30", 9, "Septembre", "Q3", 2026, 0),
        ("2026-10-31", 10, "Octobre", "Q4", 2026, 0),
        ("2026-11-30", 11, "Novembre", "Q4", 2026, 0),
        ("2026-12-31", 12, "Décembre", "Q4", 2026, 1), # Mois de clôture annuelle
    ]
    cursor.executemany(
        "INSERT INTO dim_calendar VALUES (?, ?, ?, ?, ?, ?);", calendar_data
    )

    # 2. Alimentation de dim_department
    department_data = [
        ("OPS", "Industrial Operations & Plant", "Industrial / Usine", "Direct Labor"),
        ("COM", "Commercial & Marketing", "Corporate / Business", "Indirect / Commercial"),
        ("RND", "R&D & Packaging Innovation", "Corporate / Innovation", "Indirect / R&D"),
        ("SCM", "Global Supply Chain & Logistics", "Industrial / Logistics", "Direct Logistics"),
        ("CORP", "HR, Legal & Corporate Finance", "Corporate / Support", "Overhead / G&A"),
    ]
    cursor.executemany(
        "INSERT INTO dim_department VALUES (?, ?, ?, ?);", department_data
    )

    # 3. Extraction et alimentation de dim_employee (répertoire unique des salariés)
    all_dfs = [pd.read_csv(f) for f in raw_files]
    df_combined = pd.concat(all_dfs, ignore_index=True)

    # Pour chaque salarié unique, on conserve son genre, son premier mois d'apparition et son contrat
    df_emp_unique = (
        df_combined.sort_values(by="snapshot_month")
        .groupby("employee_id")
        .first()
        .reset_index()
    )

    emp_records = [
        (
            row["employee_id"],
            row["gender"],
            int(row["snapshot_month"]),
            row["contract_type"],
        )
        for _, row in df_emp_unique.iterrows()
    ]

    cursor.executemany(
        "INSERT INTO dim_employee VALUES (?, ?, ?, ?);", emp_records
    )

    conn.commit()
    print(f"[2/4] Tables de dimensions chargées : 12 mois, 5 départements et {len(emp_records)} collaborateurs uniques.")


def load_fact_payroll(conn: sqlite3.Connection, raw_files: list):
    """Charge l'ensemble des enregistrements mensuels dans la table de faits fact_monthly_payroll."""
    cursor = conn.cursor()
    total_loaded = 0

    fact_cols = [
        "snapshot_date",
        "employee_id",
        "department_code",
        "job_level",
        "contract_type",
        "fte",
        "base_salary_fte_eur",
        "base_salary_real_eur",
        "overtime_hours",
        "overtime_pay_eur",
        "monthly_bonus_eur",
        "gross_salary_eur",
        "employer_charges_eur",
        "total_labor_cost_eur",
        "movement_type",
    ]

    insert_sql = f"""
    INSERT INTO fact_monthly_payroll ({', '.join(fact_cols)})
    VALUES ({', '.join(['?'] * len(fact_cols))});
    """

    for f_path in sorted(raw_files):
        df_month = pd.read_csv(f_path)
        records = [tuple(row[col] for col in fact_cols) for _, row in df_month.iterrows()]
        cursor.executemany(insert_sql, records)
        total_loaded += len(records)

    conn.commit()
    print(f"[3/4] Table de faits chargée : {total_loaded:,} lignes de paie mensuelles insérées.")
    return total_loaded


def run_data_quality_audit(conn: sqlite3.Connection):
    """Exécute des tests de contrôle qualité automatisés (Data Quality Audit)."""
    cursor = conn.cursor()

    print("\n" + "=" * 80)
    print("CONTRÔLE QUALITÉ & AUDIT D'INTÉGRITÉ DE LA BASE SQL (BIC CONTROLLING)")
    print("=" * 80)

    # 1. Total enregistrements et masse salariale chargée consolidée
    cursor.execute("""
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT employee_id) as total_distinct_employees,
            ROUND(SUM(total_labor_cost_eur), 2) as grand_total_labor_cost,
            ROUND(SUM(overtime_hours), 0) as grand_total_overtime_hours
        FROM fact_monthly_payroll;
    """)
    rec, emp_cnt, labor_cost, ot_hrs = cursor.fetchone()

    print(f"• Total des fiches de paie mensuelles consolidées : {rec:,} lignes")
    print(f"• Nombre total de collaborateurs uniques audités   : {emp_cnt:,} salariés")
    print(f"• Masse salariale chargée annuelle globale (2026) : {labor_cost:,.2f} €")
    print(f"• Cumul annuel des heures supplémentaires         : {ot_hrs:,.0f} heures")

    # 2. Test d'absence de doublons (Unicité Date + Salarié)
    cursor.execute("""
        SELECT snapshot_date, employee_id, COUNT(*)
        FROM fact_monthly_payroll
        GROUP BY snapshot_date, employee_id
        HAVING COUNT(*) > 1;
    """)
    duplicates = cursor.fetchall()
    if len(duplicates) == 0:
        print("• Test d'unicité (Date, Salarié) : SUCCÈS (0 doublon détecté).")
    else:
        print(f"• ALERTE : {len(duplicates)} doublons détectés !")

    # 3. Répartition du Labor Cost par Département
    print("\nVENTILATION ANNUELLE DU COÛT DE MAIN-D'ŒUVRE PAR DÉPARTEMENT :")
    cursor.execute("""
        SELECT 
            d.department_name,
            COUNT(DISTINCT f.employee_id) as headcount_annuel,
            ROUND(AVG(f.fte), 1) as fte_moyen,
            ROUND(SUM(f.total_labor_cost_eur), 0) as labor_cost_eur,
            ROUND(SUM(f.total_labor_cost_eur) * 100.0 / (SELECT SUM(total_labor_cost_eur) FROM fact_monthly_payroll), 2) as part_pct
        FROM fact_monthly_payroll f
        JOIN dim_department d ON f.department_code = d.department_code
        GROUP BY d.department_name
        ORDER BY labor_cost_eur DESC;
    """)
    dept_rows = cursor.fetchall()

    df_dept_report = pd.DataFrame(dept_rows, columns=["Direction", "Salariés Actifs", "FTE Moyen", "Labor Cost Total (€)", "Poids (%)"])
    print(df_dept_report.to_string(index=False))
    print("=" * 80)
    print("Pipeline ETL terminé : Base SQL prête pour les requêtes de clôture !\n")


def run_pipeline():
    base_dir = Path(__file__).resolve().parent.parent
    raw_dir = base_dir / "data" / "raw_monthly_sirh"
    db_path = base_dir / "data" / "database" / "bic_controlling.db"
    ddl_path = base_dir / "sql" / "01_schema_ddl.sql"

    print("=" * 80)
    print("DÉMARRAGE DU PIPELINE ETL : INGESTION SIRH VERS BASE SQL RELATIONNELLE")
    print("=" * 80)

    raw_files = list(raw_dir.glob("sirh_snapshot_2026_*.csv"))
    if len(raw_files) != 12:
        raise ValueError(f"Attendu : 12 fichiers mensuels, Trouvé : {len(raw_files)}")

    conn = get_db_connection(db_path)
    try:
        initialize_database_schema(conn, ddl_path)
        populate_dimension_tables(conn, raw_files)
        load_fact_payroll(conn, raw_files)
        run_data_quality_audit(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    run_pipeline()
