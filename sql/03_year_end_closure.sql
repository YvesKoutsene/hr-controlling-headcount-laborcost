-- =============================================================================
-- PROJET 2 : AUTOMATISATION DU SUIVI "HEADCOUNT & LABOR COST" (BIC WORLD)
-- Script : 03_year_end_closure.sql
-- Description : Requêtes de clôture de fin d'année (Year-End Closure) et
--               analyse de variance de la masse salariale (Effet Effectif vs Noria)
-- Auteur : Jean-Yves Lorenzi KOUTSENE
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. CONSOLIDATION ANNUELLE GLOBALE (Exercice 2026 complet)
-- -----------------------------------------------------------------------------
SELECT 
    COUNT(DISTINCT f.employee_id) AS effectif_cumule_annuel,
    ROUND(AVG(sub.monthly_hc), 1) AS effectif_moyen_mensuel,
    ROUND(AVG(sub.monthly_fte), 1) AS fte_moyen_mensuel,
    ROUND(SUM(f.base_salary_real_eur), 2) AS masse_salaire_base_annuelle,
    ROUND(SUM(f.overtime_pay_eur), 2) AS masse_heures_sup_annuelle,
    ROUND(SUM(f.monthly_bonus_eur), 2) AS masse_bonus_primes_annuelle,
    ROUND(SUM(f.gross_salary_eur), 2) AS masse_salariale_brute_annuelle,
    ROUND(SUM(f.employer_charges_eur), 2) AS cotisations_patronales_annuelles,
    ROUND(SUM(f.total_labor_cost_eur), 2) AS labor_cost_charge_annuel_total
FROM fact_monthly_payroll f
CROSS JOIN (
    SELECT 
        snapshot_date, 
        COUNT(employee_id) AS monthly_hc, 
        SUM(fte) AS monthly_fte
    FROM fact_monthly_payroll
    GROUP BY snapshot_date
) sub;


-- -----------------------------------------------------------------------------
-- 2. COÛT ANNUEL MOYEN PAR ETP PAR DIRECTION (Cost per FTE)
-- Rapprochement direct / indirect pour le Contrôle de Gestion
-- -----------------------------------------------------------------------------
SELECT 
    d.department_name,
    d.operational_type,
    d.cost_center_category,
    COUNT(DISTINCT f.employee_id) AS effectif_annuel,
    ROUND(SUM(f.fte) / 12.0, 1) AS etp_moyen_annuel,
    ROUND(SUM(f.total_labor_cost_eur), 0) AS labor_cost_annuel_eur,
    -- Coût moyen annuel par Équivalent Temps Plein (K€ / ETP)
    ROUND(SUM(f.total_labor_cost_eur) / (SUM(f.fte) / 12.0), 0) AS cout_annuel_charge_par_etp_eur
FROM fact_monthly_payroll f
JOIN dim_department d ON f.department_code = d.department_code
GROUP BY d.department_name, d.operational_type, d.cost_center_category
ORDER BY cout_annuel_charge_par_etp_eur DESC;


-- -----------------------------------------------------------------------------
-- 3. ANALYSE DE VARIANCE CLÔTURE ANNUELLE : DÉCOMPOSITION EFFECTIF VS NORIA
-- Décomposition mathématique de l'évolution de la masse salariale mensuelle
-- entre Janvier 2026 (Début d'exercice) et Décembre 2026 (Fin d'exercice)
-- -----------------------------------------------------------------------------
WITH jan_dec_comparison AS (
    SELECT 
        -- Période Janvier
        SUM(CASE WHEN c.month_number = 1 THEN f.fte ELSE 0 END) AS fte_janvier,
        SUM(CASE WHEN c.month_number = 1 THEN f.base_salary_real_eur ELSE 0 END) AS masse_base_janvier,
        (SUM(CASE WHEN c.month_number = 1 THEN f.base_salary_real_eur ELSE 0 END) / 
         SUM(CASE WHEN c.month_number = 1 THEN f.fte ELSE 0 END)) AS salaire_moyen_etp_janvier,

        -- Période Décembre
        SUM(CASE WHEN c.month_number = 12 THEN f.fte ELSE 0 END) AS fte_decembre,
        SUM(CASE WHEN c.month_number = 12 THEN f.base_salary_real_eur ELSE 0 END) AS masse_base_decembre,
        (SUM(CASE WHEN c.month_number = 12 THEN f.base_salary_real_eur ELSE 0 END) / 
         SUM(CASE WHEN c.month_number = 12 THEN f.fte ELSE 0 END)) AS salaire_moyen_etp_decembre
    FROM fact_monthly_payroll f
    JOIN dim_calendar c ON f.snapshot_date = c.snapshot_date
)
SELECT 
    ROUND(fte_janvier, 1) AS fte_debut_annee,
    ROUND(fte_decembre, 1) AS fte_fin_annee,
    ROUND(fte_decembre - fte_janvier, 1) AS variation_nette_fte,
    
    ROUND(masse_base_janvier, 0) AS masse_base_janvier_eur,
    ROUND(masse_base_decembre, 0) AS masse_base_decembre_eur,
    ROUND(masse_base_decembre - masse_base_janvier, 0) AS ecart_total_mensuel_eur,

    -- 1. Effet d'Effectif (Volume) : (ETP_fin - ETP_debut) * Salaire_moyen_debut
    ROUND((fte_decembre - fte_janvier) * salaire_moyen_etp_janvier, 0) AS effet_effectif_volume_eur,

    -- 2. Effet Salaire / Noria / GVT (Prix) : (Salaire_moyen_fin - Salaire_moyen_debut) * ETP_fin
    ROUND((salaire_moyen_etp_decembre - salaire_moyen_etp_janvier) * fte_decembre, 0) AS effet_salaire_noria_prix_eur
FROM jan_dec_comparison;
