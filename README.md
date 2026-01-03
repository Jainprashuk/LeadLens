 # LeadLens 🧠  

**Intent-based Business Discovery & Lead Qualification Engine**

LeadLens is an automation engine that discovers local and service-based businesses from Google Maps and evaluates **where digital improvement (website, UX, conversion)** can realistically increase inbound leads.

Unlike traditional lead scrapers, LeadLens focuses on **signal quality, intent, and explainable scoring**, not raw volume.

---

## 🚀 What This Software Does

- Scrapes **public Google Maps listings**
- Extracts:
  - Business name
  - Category
  - Rating & review count
  - Website (validated)
  - Phone number
  - Physical address
- Applies **rule-based lead scoring**
- Classifies businesses into **LOW / POTENTIAL / HIGH** opportunity
- Provides a **clear explanation** for every score

The output is **CRM-ready CSV data**, designed for sales, outreach, and automation workflows.

---

## 🧠 Core Philosophy

> **Not every business without a website needs one.  
> Not every business with a website is doing it right.**

LeadLens identifies businesses where:
- Digital presence already matters
- Improvements can create measurable business impact
- Outreach is realistic and non-spammy

---

## 📂 Output Format

Each run generates a CSV with the following structure:

```csv
business_name,
category,
rating,
reviews,
has_website,
website,
phone,
address,
lead_type,
classification_reason,
lead_score
