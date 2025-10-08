# 🧩 Olist ETL Project

ETL project developed as part of my Data Engineering training with Generation Italy.  
The goal was to build a complete and reproducible **Extract–Transform–Load** pipeline using Python and PostgreSQL, starting from e-commerce CSV data (Olist dataset, 2016–2018).

---

## ⚙️ Overview

The project simulates a real ETL process that takes raw CSV files from an e-commerce platform, transforms them into a clean and consistent structure, and loads them into a PostgreSQL database for analysis.

The workflow includes:
1. **Extraction** from CSV (per year)
2. **Transformation** (cleaning, validation, normalization)
3. **Loading** into PostgreSQL tables  
4. **Monitoring & control** through a CLI menu

Each phase can be executed manually or as a full batch through the main menu.

---

## 🏗️ Project Structure
project/
├── src/
│   ├── init.py          # Defines ROOT paths and reads config.yaml
│   ├── extract.py           # Extracts CSV → DataFrame
│   ├── transform.py         # Cleans & standardizes data
│   ├── load.py              # Loads data into PostgreSQL (inserts)
│   ├── main.py              # CLI controller (batch / single run)
│
├── data/
│   ├── raw/                 # Original input CSVs
│   ├── wip/                 # Intermediate merged files
│   ├── processed/           # Cleaned, transformed files ready for DB
│
├── config/
│   └── config.yaml          # Paths and folder setup
├── .env                     # PostgreSQL credentials
├── requirements.txt         # Dependencies
├── schema.sql               # Contains the schema of the DB 
└── README.md

---

## 🧰 Main Technologies

- **Python 3.11+**
- **PostgreSQL 15**
- **Pandas**, **psycopg**, **tqdm**, **python-dotenv**
- **YAML** for configuration management

---

## 🔑 Environment Setup

1. Clone the project and create a virtual environment:

$ bash
git clone <repository>
cd project
python3 -m venv venv
source venv/bin/activate

2.	Install dependencies:

pip install -r requirements.txt

3.	Set up your .env file (example below):

dbhost=localhost
dbname=olist
dbuser=postgres
dbpw=pass123
dbport=5432

4.	Make sure PostgreSQL is running and accessible on your system.


## 🧠 How It Works

**Extraction**

Raw CSV files (one per table per year) are read using extract.py.

Example:
olistPW_2016_orders.csv → DataFrame

Automatic type inference and basic consistency checks are applied


**Transformation**

Each table has its own transformation function (transform_<table>).
Tasks include:
	•	Deduplication
	•	Type conversion
	•	Handling of missing values
	•	Mapping and relational consistency between tables
	•	Adding IDs and standardized column names

Example:
df = transform_orders(df)


**Loading**

Each table is created (DDL) and filled (INSERT) in PostgreSQL via load.py.
Existing tables are dropped and recreated if needed.

Progress bars and row counts are displayed during the load phase.

Example:
[Batch load summary]
- customers_2017: PASSED (16,860 rows)
- products_2017: FAILED (FK violation)


## ⚡ One-Click Automation

You can run the entire ETL pipeline automatically using the built-in CLI menu.

Main Options:
1 - Full ETL (ALL years)
2 - ETL for ONE year
3 - Preview a RAW file
4 - Advanced…
5 - Exit

•	Option 1 performs a complete rebuild:
1.	Drops and recreates the database schema
2.  Builds and loads a master categories table across all detected years
3.	Runs transformation and loading for every available year (2016–2018)
•	Option 2 runs the same process but for a single selected year.

If you manually stop the execution (Ctrl + C), the program safely exits and prints:
Stopped manually


## 🔍 Advanced Menu

For more control, the advanced section provides fine-grained actions:
A1 - Transform ONE RAW file → processed
A2 - Batch transform (chosen year) → processed
A3 - Load ONE processed file
A4 - Batch load (chosen year) from processed
A5 - Delete ALL from processed
A6 - Reset DB (drop & recreate)
A0 - Back
This allows you to test and debug specific steps without running the full pipeline.


## 🧩 Key Features

	•	Full ETL orchestration via CLI
	•	Auto-detection of available years based on filenames
	•	Master categories builder to maintain consistent IDs across years
	•	Dynamic progress bars for each operation
	•	Error handling with clear messages and traceback visibility
	•	Automatic overwrite of processed files using timestamped filenames
	•	Graceful manual stop handling (Ctrl + C)


## 📊 Power BI Integration

After loading data into PostgreSQL, you can:
	1.	Export tables from the database to CSV
	2.	Or connect Power BI Desktop directly to PostgreSQL

The dashboards built from this project include:
	•	Overview of orders, customers, and sales across years
	•	On-time delivery performance and delays
	•	Regional and category-based distributions
	•	Product and seller performance insights

## 🧭 Project Motivation

The project was designed to simulate a real-world data engineering workflow — covering everything from extraction to visualization.
I wanted to focus on automation, clean structure, and practical execution — something that would feel like a real company ETL job.
It also served as the foundation for my Power BI dashboard, which connects directly to the final PostgreSQL database.

⸻

## ✍️ Author

Cristian Pichin
Junior Data Engineer | Data Analyst
📍 Milan, Italy
📧 pichin.cristian@gmail.com
🔗 linkedin.com/in/cristian-pichin




