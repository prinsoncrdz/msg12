# PDF to Excel Summary Sheet Generator

An automated web application that parses Sales Order & Purchase Order PDFs, extracts line items, supports multi-heat & partial item splits, and exports styled Excel Summary Sheets.

---

## 🌟 Key Features

- **Automatic PDF Extraction**: Extracts `Client Name`, `PO Number`, `MSG Ref`, and line items (`SL NO`, `Description`, `PO Qty`, `UOM`) from uploaded PDFs.
- **Dual Excel Export Modes**:
  - **Client Summary Sheet (.xlsx)**: Strictly 8 columns (`SL NO`, `Description`, `PO Qty`, `UOM`, `Heat Number`, `Certificate Number`, `MAKE`, `Remarks`). Automatically hides internal supplier & machining info from clients.
  - **Internal Stores Sheet (.xlsx)**: Full 10 columns including `SUPPLIER NAME` and `MACHINING NAMES` for internal warehouse records.
- **Item Splitting**: Split rows for partial stock/local purchases or multiple heat numbers under the same Client Item `SL NO`.
- **Machining Auto-Detection**: Flags items requiring machining (e.g. *"machined from S.40 to Sch.20"*).

---

## 🚀 Deploying to Vercel

This repository is pre-configured for instant **1-Click Vercel Deployment**.

### Step 1: Push Code to GitHub

```bash
git init
git add .
git commit -m "Initial commit - PDF to Excel Summary Sheet Generator"
git branch -M main
git remote add origin https://github.com/prinsoncrdz/msg12.git
git push -u origin main --force
```

### Step 2: Deploy on Vercel

1. Go to your [Vercel Dashboard](https://vercel.com/dashboard).
2. Click **Add New...** -> **Project**.
3. Select **Import** next to your GitHub repository: `prinsoncrdz/msg12`.
4. Keep all default settings (Vercel automatically detects `vercel.json` and `@vercel/python`).
5. Click **Deploy**!

Your live web application URL (e.g. `https://msg12.vercel.app`) will be generated instantly.

---

## 💻 Local Setup & Development

```bash
# 1. Clone repository
git clone https://github.com/prinsoncrdz/msg12.git
cd msg12

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run application locally
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your web browser.
