import sqlite3

def build_database():
    # Establishes or opens a persistent binary database file link
    conn = sqlite3.connect("statistical_catalog.db")
    cursor = conn.cursor()

    # Drop old table structure if it exists to maintain pristine overwrite stability
    cursor.execute("DROP TABLE IF EXISTS MASTER_TESTS")

    # Create the relational SQL schema table layout parameters
    cursor.execute("""
        CREATE TABLE MASTER_TESTS (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            analysis_purpose TEXT NOT NULL,
            group_count TEXT NOT NULL,
            iv_count TEXT NOT NULL,
            dv_count TEXT NOT NULL,
            iv_type TEXT NOT NULL,
            dv_type TEXT NOT NULL,
            data_pairing TEXT NOT NULL,
            is_normal_distribution TEXT NOT NULL,
            has_covariates TEXT NOT NULL
        )
    """)

    # Universal statistical records registry arrays mapping your logic parameters
    tests_dataset = [
        # --- DIFFERENCES BRANCH (categorical nominal parameters) ---
        ("Independent Samples t-test", "differences", "two", "1", "1", "Nominal", "Interval/Ratio", "unpaired", "True", "False"),
        ("Mann-Whitney U Test", "differences", "two", "1", "1", "Nominal", "Interval/Ratio", "unpaired", "False", "False"),
        ("Paired Samples t-test", "differences", "two", "1", "1", "Nominal", "Interval/Ratio", "paired", "True", "False"),
        ("Wilcoxon Signed-Rank Test", "differences", "two", "1", "1", "Nominal", "Ordinal", "paired", "False", "False"),
        ("One-Way ANOVA", "differences", "more_than_two", "1", "1", "Nominal", "Interval/Ratio", "unpaired", "True", "False"),
        ("Kruskal-Wallis H Test", "differences", "more_than_two", "1", "1", "Nominal", "Ordinal", "unpaired", "False", "False"),
        ("Factorial ANOVA", "differences", "more_than_two", "More than 1", "1", "Nominal", "Interval/Ratio", "unpaired", "True", "False"),
        ("Repeated Measures ANOVA", "differences", "more_than_two", "1", "1", "Nominal", "Interval/Ratio", "paired", "True", "False"),
        ("Friedman Test", "differences", "more_than_two", "1", "1", "Nominal", "Ordinal", "paired", "False", "False"),
        ("ANCOVA", "differences", "Any", "Any", "1", "Nominal", "Interval/Ratio", "unpaired", "True", "True"),
        ("One-Way MANOVA", "differences", "Any", "1", "More than 1", "Nominal", "Interval/Ratio", "unpaired", "True", "False"),
        ("MANCOVA", "differences", "Any", "Any", "More than 1", "Nominal", "Interval/Ratio", "unpaired", "True", "True"),

        # --- RELATIONSHIPS BRANCH ---
        ("Pearson's r Correlation", "relation", "None", "1", "1", "Interval/Ratio", "Interval/Ratio", "any", "True", "False"),
        ("Spearman's Rank Correlation", "relation", "None", "1", "1", "Ordinal", "Ordinal", "any", "False", "False"),
        ("Point-Biserial Correlation", "relation", "two", "1", "1", "Nominal", "Interval/Ratio", "any", "True", "False"),
        ("Chi-Square Test of Independence", "relation", "Any", "1", "1", "Nominal", "Nominal", "any", "Any", "False"),
        ("Multiple Linear Regression", "relation", "None", "More than 1", "1", "Mixed", "Interval/Ratio", "any", "True", "False"),
        ("Binary Logistic Regression", "relation", "None", "Any", "1", "Mixed", "Nominal", "any", "Any", "False"),
        ("Hierarchical Linear Modeling (HLM)", "relation", "None", "More than 1", "1", "Mixed", "Interval/Ratio", "any", "Any", "False"),

        # --- DATA REDUCTION BYPASSES ---
        ("Factor Analysis", "factor", "Any", "Any", "Any", "Any", "Any", "any", "Any", "Any"),
        ("Cluster Analysis", "cluster", "Any", "Any", "Any", "Any", "Any", "any", "Any", "Any")
    ]

    # Batch execute atomic SQL insertion queries
    cursor.executemany("""
        INSERT INTO MASTER_TESTS (
            name, analysis_purpose, group_count, iv_count, dv_count, iv_type, dv_type, data_pairing, is_normal_distribution, has_covariates
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, tests_dataset)

    conn.commit()
    print("🎯 RELATIONAL SQL DATABASE COMPILED SUCCESSFULLY: Created statistical_catalog.db")
    conn.close()

if __name__ == "__main__":
    build_database()
