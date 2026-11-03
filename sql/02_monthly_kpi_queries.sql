-- =============================================================================
-- PROJET 2 : AUTOMATISATION DU SUIVI "HEADCOUNT & LABOR COST" (BIC WORLD)
-- Script : 02_monthly_kpi_queries.sql
-- Description : Requêtes analytiques SQL de suivi mensuel des effectifs, ETP,
--               flux de mouvements (Turnover) et saisonnalité des coûts.
-- Auteur : Jean-Yves Lorenzi KOUTSENE
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. SUIVI MENSUEL DES EFFECTIFS : Headcount EOM, Total FTE et Taux d'Activité
-- -----------------------------------------------------------------------------
-- Permet à la Direction RH de suivre l'évolution des effectifs physiques vs ETP
SELECT 
    c.snapshot_date,
    c.month_number,
    c.month_name,
    c.quarter,
    COUNT(f.employee_id) AS headcount_eom,
    ROUND(SUM(f.fte), 1) AS total_fte,
    ROUND(SUM(f.fte) * 100.0 / COUNT(f.employee_id), 1) AS taux_activite_pct,
    COUNT(CASE WHEN f.contract_type = 'CDI' THEN 1 END) AS effectif_cdi,
    COUNT(CASE WHEN f.contract_type = 'CDD' THEN 1 END) AS effectif_cdd
FROM dim_calendar c
LEFT JOIN fact_monthly_payroll f ON c.snapshot_date = f.snapshot_date
GROUP BY c.snapshot_date, c.month_number, c.month_name, c.quarter
ORDER BY c.month_number;


-- -----------------------------------------------------------------------------
-- 2. SUIVI DES FLUX RH : Entrées (Hires), Sorties (Leavers) et Taux de Turnover
-- Formule officielle : Turnover = ((Entrées + Sorties) / 2) / Effectif Moyen
-- -----------------------------------------------------------------------------
WITH monthly_movements AS (
    SELECT 
        c.snapshot_date,
        c.month_number,
        c.month_name,
        COUNT(f.employee_id) AS headcount_fin_mois,
        COUNT(CASE WHEN f.movement_type = 'NEW_HIRE' THEN 1 END) AS nb_entrees,
        -- Estimation des départs par rapprochement avec le mois précédent
        LAG(COUNT(f.employee_id), 1) OVER (ORDER BY c.month_number) AS headcount_debut_mois
    FROM dim_calendar c
    JOIN fact_monthly_payroll f ON c.snapshot_date = f.snapshot_date
    GROUP BY c.snapshot_date, c.month_number, c.month_name
)
SELECT 
    month_number,
    month_name,
    headcount_fin_mois,
    nb_entrees,
    -- Sorties = Effectif Début + Entrées - Effectif Fin
    CASE 
        WHEN headcount_debut_mois IS NULL THEN 6 -- Valeur d'étalonnage janvier
        ELSE (headcount_debut_mois + nb_entrees - headcount_fin_mois)
    END AS nb_sorties,
    -- Taux de turnover mensuel (%)
    ROUND(
        (
            (nb_entrees + CASE WHEN headcount_debut_mois IS NULL THEN 6 ELSE (headcount_debut_mois + nb_entrees - headcount_fin_mois) END) / 2.0
        ) * 100.0 / headcount_fin_mois,
        2
    ) AS turnover_rate_pct
FROM monthly_movements
ORDER BY month_number;


-- -----------------------------------------------------------------------------
-- 3. DÉCOMPOSITION DU LABOR COST MENSUEL : Fixe, Heures Sup, Primes et Charges
-- -----------------------------------------------------------------------------
SELECT 
    c.month_number,
    c.month_name,
    c.quarter,
    ROUND(SUM(f.base_salary_real_eur), 0) AS masse_salaire_base_eur,
    ROUND(SUM(f.overtime_pay_eur), 0) AS masse_heures_sup_eur,
    ROUND(SUM(f.monthly_bonus_eur), 0) AS masse_primes_bonus_eur,
    ROUND(SUM(f.gross_salary_eur), 0) AS masse_brute_totale_eur,
    ROUND(SUM(f.employer_charges_eur), 0) AS cotisations_patronales_eur,
    ROUND(SUM(f.total_labor_cost_eur), 0) AS total_labor_cost_charge_eur,
    ROUND(SUM(f.overtime_hours), 0) AS volume_heures_sup_h
FROM dim_calendar c
JOIN fact_monthly_payroll f ON c.snapshot_date = f.snapshot_date
GROUP BY c.month_number, c.month_name, c.quarter
ORDER BY c.month_number;


-- -----------------------------------------------------------------------------
-- 4. ANALYSE DU PIC INDUSTRIEL USINES (Saisonnalité Rentrée Scolaire BIC)
-- -----------------------------------------------------------------------------
SELECT 
    c.month_number,
    c.month_name,
    COUNT(CASE WHEN f.department_code = 'OPS' THEN 1 END) AS effectif_usines,
    ROUND(SUM(CASE WHEN f.department_code = 'OPS' THEN f.overtime_hours ELSE 0 END), 0) AS heures_sup_usines,
    ROUND(SUM(CASE WHEN f.department_code = 'OPS' THEN f.overtime_pay_eur ELSE 0 END), 0) AS cout_heures_sup_usines_eur,
    ROUND(SUM(CASE WHEN f.department_code = 'OPS' THEN f.total_labor_cost_eur ELSE 0 END), 0) AS labor_cost_usines_eur
FROM dim_calendar c
JOIN fact_monthly_payroll f ON c.snapshot_date = f.snapshot_date
GROUP BY c.month_number, c.month_name
ORDER BY c.month_number;
