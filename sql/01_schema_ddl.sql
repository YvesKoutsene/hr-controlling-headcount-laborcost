-- =============================================================================
-- PROJET 2 : AUTOMATISATION DU SUIVI "HEADCOUNT & LABOR COST" (BIC WORLD)
-- Script : 01_schema_ddl.sql
-- Description : Schéma relationnel en étoile (Star Schema) sous SQLite / SQL
--               conforme aux standards de modélisation dimensionnelle (Kimball)
-- Auteur : Jean-Yves Lorenzi KOUTSENE
-- =============================================================================

-- Suppression des tables existantes pour assurer l'idempotence du script
DROP TABLE IF EXISTS fact_monthly_payroll;
DROP TABLE IF EXISTS dim_employee;
DROP TABLE IF EXISTS dim_department;
DROP TABLE IF EXISTS dim_calendar;

-- -----------------------------------------------------------------------------
-- 1. DIMENSION CALENDRIER : Suivi des périodes de paie et clôtures mensuelles
-- -----------------------------------------------------------------------------
CREATE TABLE dim_calendar (
    snapshot_date TEXT PRIMARY KEY,          -- Format ISO : '2026-01-31'
    month_number INTEGER NOT NULL,           -- 1 à 12
    month_name TEXT NOT NULL,                -- 'Janvier', 'Février', etc.
    quarter TEXT NOT NULL,                   -- 'Q1', 'Q2', 'Q3', 'Q4'
    fiscal_year INTEGER NOT NULL,            -- 2026
    is_year_end_closure BOOLEAN DEFAULT 0   -- 1 pour le mois de clôture (Décembre)
);

-- -----------------------------------------------------------------------------
-- 2. DIMENSION DÉPARTEMENT : Centres de coûts et pôles industriels de BIC
-- -----------------------------------------------------------------------------
CREATE TABLE dim_department (
    department_code TEXT PRIMARY KEY,        -- 'OPS', 'COM', 'RND', 'SCM', 'CORP'
    department_name TEXT NOT NULL,           -- Intitulé complet de la direction
    operational_type TEXT NOT NULL,          -- 'Industrial / Usine' ou 'Corporate / Support'
    cost_center_category TEXT NOT NULL       -- 'Direct Labor' ou 'Indirect / Overhead'
);

-- -----------------------------------------------------------------------------
-- 3. DIMENSION COLLABORATEUR : Référentiel des salariés (SCD Type 1)
-- -----------------------------------------------------------------------------
CREATE TABLE dim_employee (
    employee_id TEXT PRIMARY KEY,            -- 'BIC-1001', etc.
    gender TEXT NOT NULL,                    -- 'Male', 'Female'
    initial_hire_month INTEGER NOT NULL,     -- Mois d'arrivée (1 à 12)
    contract_type TEXT NOT NULL              -- 'CDI', 'CDD'
);

-- -----------------------------------------------------------------------------
-- 4. TABLE DE FAITS MENSUELLE : Événements de paie et effectifs actifs (Snapshots)
-- -----------------------------------------------------------------------------
CREATE TABLE fact_monthly_payroll (
    payroll_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    employee_id TEXT NOT NULL,
    department_code TEXT NOT NULL,
    job_level INTEGER NOT NULL,              -- 1 (Entry) à 5 (Executive)
    contract_type TEXT NOT NULL,             -- 'CDI', 'CDD'
    fte REAL NOT NULL,                       -- Taux d'activité ETP (1.0, 0.8, 0.5)
    base_salary_fte_eur REAL NOT NULL,       -- Salaire mensuel de base à 100%
    base_salary_real_eur REAL NOT NULL,      -- Salaire mensuel de base perçu (proratisé ETP)
    overtime_hours REAL NOT NULL DEFAULT 0,  -- Heures supplémentaires travaillées
    overtime_pay_eur REAL NOT NULL DEFAULT 0,-- Rémunération des heures sup (majorées 125%)
    monthly_bonus_eur REAL NOT NULL DEFAULT 0,-- Primes de performance / bonus annuel
    gross_salary_eur REAL NOT NULL,          -- Salaire brut total mensuel
    employer_charges_eur REAL NOT NULL,      -- Cotisations patronales de sécurité sociale (~42%)
    total_labor_cost_eur REAL NOT NULL,      -- Coût de main-d'œuvre complet chargé
    movement_type TEXT NOT NULL,             -- 'ACTIVE', 'NEW_HIRE', 'TERMINATED'

    -- Contraintes d'intégrité référentielle
    FOREIGN KEY (snapshot_date) REFERENCES dim_calendar(snapshot_date),
    FOREIGN KEY (employee_id) REFERENCES dim_employee(employee_id),
    FOREIGN KEY (department_code) REFERENCES dim_department(department_code),

    -- Contrainte d'unicité : un collaborateur ne peut avoir qu'une seule fiche par mois
    UNIQUE (snapshot_date, employee_id)
);

-- Index pour accélérer les requêtes d'agrégation et de clôture
CREATE INDEX idx_payroll_date ON fact_monthly_payroll(snapshot_date);
CREATE INDEX idx_payroll_dept ON fact_monthly_payroll(department_code);
CREATE INDEX idx_payroll_emp ON fact_monthly_payroll(employee_id);
CREATE INDEX idx_payroll_level ON fact_monthly_payroll(job_level);
