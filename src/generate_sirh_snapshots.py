"""
=============================================================================
PROJET 2 : SIMULATEUR DE FLUX SIRH MENSUELS (BIC WORLD)
Module : generate_sirh_snapshots.py
Description : Génère 12 extractions mensuelles réelles du SIRH (Workday/SAP)
              avec mouvements de personnel (embauches, départs, promotions,
              heures sup de haute saison 'rentrée scolaire', charges patronales).
Auteur : Jean-Yves Lorenzi KOUTSENE
=============================================================================
"""

import os
from pathlib import Path
import numpy as np
import pandas as pd


def generate_initial_workforce(n_init: int = 1420, seed: int = 101) -> pd.DataFrame:
    """Génère l'effectif actif initial au 1er janvier 2026."""
    np.random.seed(seed)

    departments = [
        ("OPS", "Industrial Operations & Plant", 0.38),
        ("COM", "Commercial & Marketing", 0.28),
        ("RND", "R&D & Packaging Innovation", 0.20),
        ("SCM", "Global Supply Chain & Logistics", 0.09),
        ("CORP", "HR, Legal & Corporate Finance", 0.05),
    ]

    dept_codes = [d[0] for d in departments]
    dept_names = [d[1] for d in departments]
    dept_probs = [d[2] for d in departments]

    chosen_indices = np.random.choice(len(departments), size=n_init, p=dept_probs)
    assigned_codes = [dept_codes[i] for i in chosen_indices]
    assigned_names = [dept_names[i] for i in chosen_indices]

    genders = np.random.choice(["Male", "Female"], size=n_init, p=[0.58, 0.42])

    # Job levels (1 à 5)
    job_levels = np.random.choice([1, 2, 3, 4, 5], size=n_init, p=[0.40, 0.35, 0.15, 0.07, 0.03])

    # Salaires de base annuels temps plein (€)
    level_base_salaries = {
        1: (32000, 42000),   # Opérateurs, techniciens
        2: (43000, 56000),   # Spécialistes, ingénieurs
        3: (58000, 78000),   # Seniors, chefs de projet
        4: (82000, 112000),  # Responsables de pôle, managers
        5: (125000, 175000), # Directeurs
    }

    base_annual = np.zeros(n_init)
    for lvl, (s_min, s_max) in level_base_salaries.items():
        mask = job_levels == lvl
        if np.sum(mask) > 0:
            salaries = np.random.uniform(s_min, s_max, size=np.sum(mask))
            base_annual[mask] = np.round(salaries, 0)

    # Taux d'activité (Temps partiel : 14% chez les femmes, 3% chez les hommes)
    fte = np.ones(n_init)
    for i in range(n_init):
        if genders[i] == "Female":
            fte[i] = np.random.choice([1.0, 0.8, 0.5], p=[0.86, 0.11, 0.03])
        else:
            fte[i] = np.random.choice([1.0, 0.8, 0.5], p=[0.97, 0.02, 0.01])

    emp_ids = [f"BIC-{1000 + i}" for i in range(n_init)]

    df_init = pd.DataFrame({
        "employee_id": emp_ids,
        "gender": genders,
        "department_code": assigned_codes,
        "department_name": assigned_names,
        "job_level": job_levels,
        "contract_type": np.random.choice(["CDI", "CDD"], size=n_init, p=[0.93, 0.07]),
        "fte": fte,
        "monthly_base_salary_eur": np.round(base_annual / 12.0, 2),
        "seniority_years": np.random.randint(1, 20, size=n_init),
        "is_active": True,
        "hire_month": 1,
        "termination_month": np.nan,
    })

    return df_init


def simulate_year_snapshots(output_dir: Path, seed: int = 101):
    """Génère 12 fichiers d'extractions mensuelles (Janvier à Décembre 2026)."""
    np.random.seed(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    df_pool = generate_initial_workforce(n_init=1420, seed=seed)
    current_max_id = 1000 + len(df_pool)

    months_meta = [
        (1, "2026-01-31", "Janvier", 1.0),
        (2, "2026-02-28", "Février", 1.0),
        (3, "2026-03-31", "Mars", 1.05),     # Début montée en cadence usines
        (4, "2026-04-30", "Avril", 1.08),    # Campagne NAO (+1.8% d'augmentation générale)
        (5, "2026-05-31", "Mai", 1.15),      # Pic fabrication Rentrée Scolaire (Papeterie)
        (6, "2026-06-30", "Juin", 1.20),     # Pic heures supplémentaires usines
        (7, "2026-07-31", "Juillet", 1.12),  # Livraisons distributeurs & saison été briquets
        (8, "2026-08-31", "Août", 0.95),     # Période de congés principaux
        (9, "2026-09-30", "Septembre", 1.02),# Rentrée & clôture Q3
        (10, "2026-10-31", "Octobre", 1.0),
        (11, "2026-11-30", "Novembre", 1.0),
        (12, "2026-12-31", "Décembre", 1.25),# Clôture annuelle & Versement des Bonus
    ]

    # Suivi des KPI par mois
    summary_records = []

    for m_num, m_date, m_name, activity_factor in months_meta:
        # 1. Augmentation annuelle générale en Avril (NAO +1.8%)
        if m_num == 4:
            active_mask = df_pool["is_active"]
            df_pool.loc[active_mask, "monthly_base_salary_eur"] = np.round(
                df_pool.loc[active_mask, "monthly_base_salary_eur"] * 1.018, 2
            )

        # 2. Départs mensuels (Turnover naturel : démissions, fins de CDD, départs en retraite)
        # Entre 6 et 12 départs par mois
        active_indices = df_pool[df_pool["is_active"]].index.tolist()
        n_leaves = np.random.randint(6, 12)
        leaving_idx = np.random.choice(active_indices, size=n_leaves, replace=False)
        df_pool.loc[leaving_idx, "is_active"] = False
        df_pool.loc[leaving_idx, "termination_month"] = m_num

        # 3. Arrivées mensuelles (Embauches en usine, renforts logistiques et commerciaux)
        # Entre 8 et 15 embauches par mois (pic avant l'été)
        n_hires = np.random.randint(8, 16) if m_num not in [5, 6] else np.random.randint(14, 22)
        new_emps = []
        for _ in range(n_hires):
            current_max_id += 1
            new_dept = np.random.choice(["OPS", "COM", "RND", "SCM", "CORP"], p=[0.42, 0.28, 0.16, 0.09, 0.05])
            new_gender = np.random.choice(["Male", "Female"], p=[0.55, 0.45])
            new_level = np.random.choice([1, 2, 3, 4], p=[0.55, 0.32, 0.10, 0.03])
            
            salary_map = {1: (32000, 42000), 2: (43000, 56000), 3: (58000, 78000), 4: (82000, 112000)}
            s_min, s_max = salary_map[new_level]
            new_sal = round(np.random.uniform(s_min, s_max) / 12.0, 2)

            new_fte = 1.0 if new_gender == "Male" else np.random.choice([1.0, 0.8], p=[0.88, 0.12])
            dept_full_name = {
                "OPS": "Industrial Operations & Plant",
                "COM": "Commercial & Marketing",
                "RND": "R&D & Packaging Innovation",
                "SCM": "Global Supply Chain & Logistics",
                "CORP": "HR, Legal & Corporate Finance",
            }[new_dept]

            new_emps.append({
                "employee_id": f"BIC-{current_max_id}",
                "gender": new_gender,
                "department_code": new_dept,
                "department_name": dept_full_name,
                "job_level": new_level,
                "contract_type": "CDI" if np.random.rand() > 0.15 else "CDD",
                "fte": new_fte,
                "monthly_base_salary_eur": new_sal,
                "seniority_years": 0,
                "is_active": True,
                "hire_month": m_num,
                "termination_month": np.nan,
            })

        if new_emps:
            df_new = pd.DataFrame(new_emps)
            df_pool = pd.concat([df_pool, df_new], ignore_index=True)

        # 4. Construction de l'extraction du mois M
        # Ne conserver que les salariés actifs à la fin de ce mois
        current_active = df_pool[df_pool["is_active"]].copy()

        # Heures supplémentaires (Overtime) : concentrées sur les opérations industrielles
        is_ops = current_active["department_code"] == "OPS"
        is_l1_l2 = current_active["job_level"].isin([1, 2])
        ot_eligible = is_ops & is_l1_l2

        overtime_hours = np.zeros(len(current_active))
        # Taux horaire moyen dérivé du salaire mensuel (base 151.67h légales)
        hourly_rate = (current_active["monthly_base_salary_eur"] / 151.67).values

        if m_num in [5, 6, 7]: # Pic de production papeterie rentrée scolaire
            ot_prob = 0.35
            ot_avg = 14 * activity_factor
        else:
            ot_prob = 0.15
            ot_avg = 6

        ot_mask = ot_eligible & (np.random.rand(len(current_active)) < ot_prob)
        overtime_hours[ot_mask] = np.random.poisson(ot_avg, size=np.sum(ot_mask))

        # Rémunération des heures sup (majoration légale 125%)
        overtime_pay = np.round(overtime_hours * hourly_rate * 1.25, 2)

        # Primes & Bonus mensuels
        # Primes courantes de production / objectifs
        monthly_bonus = np.zeros(len(current_active))
        if m_num == 12: # En décembre : Versement du bonus annuel de performance
            # Entre 5% et 20% du salaire annuel
            bonus_pct = current_active["job_level"].map({1: 0.05, 2: 0.08, 3: 0.12, 4: 0.18, 5: 0.25})
            annual_bonus = current_active["monthly_base_salary_eur"] * 12 * bonus_pct
            monthly_bonus = np.round(annual_bonus, 2)
        else:
            # Primes mensuelles de performance opérationnelle (quelques salariés éligibles)
            spot_bonus_mask = np.random.rand(len(current_active)) < 0.08
            monthly_bonus[spot_bonus_mask] = np.random.choice([250, 400, 600, 900], size=np.sum(spot_bonus_mask))

        # Salaire brut mensuel réel perçu (proratisé à l'ETP + Heures sup + Primes)
        gross_base_real = np.round(current_active["monthly_base_salary_eur"] * current_active["fte"], 2)
        gross_total = np.round(gross_base_real + overtime_pay + monthly_bonus, 2)

        # Cotisations patronales de sécurité sociale (~42% en France : URSSAF, Retraite, Prévoyance)
        employer_charges_rate = 0.42
        employer_charges_eur = np.round(gross_total * employer_charges_rate, 2)

        # Coût total de main-d'œuvre (Total Labor Cost)
        total_labor_cost_eur = np.round(gross_total + employer_charges_eur, 2)

        # Schéma final de l'extraction mensuelle SIRH
        current_active["snapshot_month"] = m_num
        current_active["snapshot_date"] = m_date
        current_active["base_salary_fte_eur"] = current_active["monthly_base_salary_eur"]
        current_active["base_salary_real_eur"] = gross_base_real
        current_active["overtime_hours"] = overtime_hours
        current_active["overtime_pay_eur"] = overtime_pay
        current_active["monthly_bonus_eur"] = monthly_bonus
        current_active["gross_salary_eur"] = gross_total
        current_active["employer_charges_eur"] = employer_charges_eur
        current_active["total_labor_cost_eur"] = total_labor_cost_eur

        # Statut du mouvement dans le mois
        current_active["movement_type"] = np.where(
            current_active["hire_month"] == m_num, "NEW_HIRE", "ACTIVE"
        )

        export_cols = [
            "snapshot_date",
            "snapshot_month",
            "employee_id",
            "gender",
            "department_code",
            "department_name",
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

        out_file = output_dir / f"sirh_snapshot_2026_{m_num:02d}.csv"
        current_active[export_cols].to_csv(out_file, index=False, encoding="utf-8-sig")

        # Synthèse mensuelle
        hc_total = len(current_active)
        fte_total = current_active["fte"].sum()
        labor_cost_total = total_labor_cost_eur.sum()

        summary_records.append({
            "Mois": f"{m_num:02d} - {m_name}",
            "Date": m_date,
            "Headcount (EOM)": hc_total,
            "Total FTE": round(fte_total, 1),
            "Entrées (Hires)": n_hires,
            "Sorties (Leavers)": n_leaves,
            "Heures Sup (h)": int(overtime_hours.sum()),
            "Labor Cost Chargé (€)": f"{labor_cost_total:,.0f} €",
        })

    print("=" * 80)
    print("SIMULATION DES 12 EXTRACTIONS MENSUELLES SIRH (EXERCICE 2026 - BIC WORLD)")
    print("=" * 80)
    df_summary = pd.DataFrame(summary_records)
    print(df_summary.to_string(index=False))
    print("=" * 80)
    print(f"-> 12 fichiers CSV générés avec succès dans : {output_dir.name}/\n")


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    raw_dir = base_dir / "data" / "raw_monthly_sirh"
    simulate_year_snapshots(raw_dir)
