# Lead Scoring Logic

This document explains how LeadLens calculates the **lead score**, classifies businesses, and assigns priority levels.

The scoring system is designed to be:
- Explainable
- Conservative
- Industry-aware
- Safe from spammy false positives

---

## 🎯 Objective of Scoring

The goal is **not** to find businesses without websites.

The goal is to identify:

> **Service-based businesses where improving digital presence (website, UX, conversion) can realistically increase inbound leads.**

---

## 🔢 Lead Score Overview

- Each business is assigned a **lead_score between 0 and 100**
- The score is derived **only from public Google Maps signals**
- Scores are **directional**, not absolute judgments

---

## 🧩 Signals Used in Scoring

### 1️⃣ Website Presence

A valid website is a strong indicator of digital intent.

| Condition | Points |
|---------|-------|
Valid standalone website detected | +20 |
Website missing or invalid | +0 |

### Website Validation Rules
A website is considered **invalid** if it:
- Belongs to Google infrastructure  
  (`google.com`, `gstatic.com`, `fonts.gstatic.com`, etc.)
- Is a static asset (`.css`, `.js`, `.svg`, `.woff`)
- Is empty or malformed

---

### 2️⃣ Google Rating Score

Ratings indicate trust and perceived service quality.

| Rating | Points |
|------|-------|
≥ 4.5 | +20 |
4.0 – 4.49 | +15 |
3.5 – 3.99 | +10 |
< 3.5 | +5 |
No rating | +0 |

---

### 3️⃣ Review Volume (Engagement Signal)

Reviews represent customer interaction and visibility.

| Reviews Count | Points |
|--------------|-------|
≥ 200 | +25 |
100 – 199 | +20 |
50 – 99 | +15 |
20 – 49 | +10 |
5 – 19 | +5 |
< 5 or hidden | +0 |

> Review count is treated cautiously for professional services  
> (architects, designers) where reviews may be hidden or irrelevant.

---

### 4️⃣ Contact Availability

Contact signals indicate readiness for inbound leads.

| Signal | Points |
|------|-------|
Phone number available | +10 |
Physical address available | +5 |

---

## 🧮 Final Score Calculation

```text
lead_score =
  website_score
+ rating_score
+ review_score
+ contact_score
