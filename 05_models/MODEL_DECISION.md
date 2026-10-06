# Model Strategy Decision Report

**Generated**: 2026-06-11 11:32:20
**Pipeline Version**: 2.0
**JSON SHA256**: `d66522ee82b1ded2e7c1bc30a426829e533fbd04e80ad227a92fb0ae5b2de324`

---

## 🎯 Recommendation

**Strategy**: **HYBRID**

**Justification**: HYBRID achieves best performance (F1=0.908) with single model. Recommended as best trade-off between performance and simplicity.

---

## 📊 Performance Comparison

| Strategy | F1 Score | Delta vs GLOBAL |
|----------|----------|-----------------|
| GLOBAL | 0.8935 | - |
| CUSTOM | 0.9058 | +0.0123 |
| HYBRID | 0.9076 | +0.0142 |

---

## 📋 Decision Framework

- **ΔF1 < 3.0%**: Recommend GLOBAL
- **ΔF1 > 5.0%**: Recommend CUSTOM
- **3.0% ≤ ΔF1 ≤ 5.0%**: Business evaluation

---

## 🔍 Feature Importance Analysis (GLOBAL Model)

**Summary Statistics:**
- Total features: 18
- Top 10 cumulative importance: 91.6%
- Top 20 cumulative importance: 100.0%
- Zero-importance features: 1
- Country dummies in top 10: 0

**Top 20 Features:**

| Rank | Feature | Importance | Cumulative % |
|------|---------|------------|--------------|
| 1 | matchResult_Name__norm | 0.2804 | 28.0% |
| 2 | matchResult_Name__bin__MISSING | 0.1308 | 41.1% |
| 3 | Profile1_MatchCategory__norm | 0.1021 | 51.3% |
| 4 | Profile2_MatchCategory__norm | 0.0978 | 61.1% |
| 5 | Profile2_MatchCategory__bin__0_20 | 0.0713 | 68.2% |
| 6 | matchResult_City__norm__MATCH | 0.0712 | 75.4% |
| 7 | matchResult_LastName__norm | 0.0569 | 81.1% |
| 8 | Profile2_MatchCategory__bin__80_100 | 0.0523 | 86.3% |
| 9 | Profile1_MatchCategory__bin__0_20 | 0.0328 | 89.6% |
| 10 | matchResult_City__norm__NO_MATCH | 0.0202 | 91.6% |
| 11 | matchResult_StateProvince__norm__MATCH | 0.0192 | 93.5% |
| 12 | matchResult_Name__bin__80_100 | 0.0186 | 95.4% |
| 13 | matchResult_LastName__bin__MISSING | 0.0177 | 97.1% |
| 14 | matchResult_MatchCategory__norm | 0.0107 | 98.2% |
| 15 | matchResult_Gender__norm__NA | 0.0102 | 99.2% |
| 16 | matchResult_PhoneNumber__norm__NA | 0.0048 | 99.7% |
| 17 | matchResult_Country__norm__MATCH | 0.0028 | 100.0% |
| 18 | matchResult_Suffix__norm__NA | 0.0000 | 100.0% |

**⚠️ Risk Assessment:**

- 🟢 **LOW RISK**: No country dummies in top 10 - features are geography-agnostic
- 🟡 **MEDIUM**: 1 features have zero importance - can be removed in next iteration

---

## 🌳 Decision Rules Analysis (Top Rules from Random Forest)

**Purpose:** Understand the key decision paths the model uses to classify potential matches.

**Methodology:** Extracted from random_forest ensemble. Rules represent the most frequent and pure paths leading to class predictions.

### 🔴 High-Probability NO-MERGE Rules

Rules leading to high confidence of NOT merging records:

**Rule 1:** (Support: 20,397 samples = 12.2%)

```
IF:
  - matchResult_Name__norm <= 91.5000
  - Profile2_MatchCategory__bin__80_100 > 0.5000
  - Profile1_MatchCategory__bin__0_20 <= 0.5000
  - Profile1_MatchCategory__norm <= 89.5000
  - matchResult_StateProvince__norm__MATCH > 0.5000
  - matchResult_City__norm__MATCH > 0.5000
  - matchResult_LastName__norm <= inf
  - matchResult_PhoneNumber__norm__NA > 0.5000
  - matchResult_Gender__norm__NA > 0.5000
  - matchResult_MatchCategory__norm <= 45.0000
THEN:
  → P(NO-MERGE) = 0.994
  → Leaf Purity = 0.994
  → Tree ID: 43
```

**Features involved:** `matchResult_Name__norm`, `Profile2_MatchCategory__bin__80_100`, `Profile1_MatchCategory__bin__0_20`, `Profile1_MatchCategory__norm`, `matchResult_StateProvince__norm__MATCH`

---

**Rule 2:** (Support: 19,402 samples = 11.6%)

```
IF:
  - Profile2_MatchCategory__norm > 87.5000
  - matchResult_Gender__norm__NA > 0.5000
  - matchResult_Name__norm <= 94.5000
  - Profile2_MatchCategory__norm <= 88.5000
  - matchResult_City__norm__NO_MATCH <= 0.5000
  - matchResult_Name__bin__MISSING <= 0.5000
  - matchResult_StateProvince__norm__MATCH > 0.5000
  - matchResult_PhoneNumber__norm__NA > 0.5000
  - Profile1_MatchCategory__bin__0_20 <= 0.5000
  - matchResult_Name__norm <= 93.5000
THEN:
  → P(NO-MERGE) = 0.993
  → Leaf Purity = 0.993
  → Tree ID: 21
```

**Features involved:** `Profile2_MatchCategory__norm`, `matchResult_Gender__norm__NA`, `matchResult_Name__norm`, `matchResult_City__norm__NO_MATCH`, `matchResult_Name__bin__MISSING`

---

**Rule 3:** (Support: 19,312 samples = 11.6%)

```
IF:
  - matchResult_Name__norm <= 92.5000
  - Profile2_MatchCategory__bin__0_20 <= 0.5000
  - Profile1_MatchCategory__norm > 50.0000
  - Profile2_MatchCategory__norm <= 89.5000
  - matchResult_City__norm__MATCH > 0.5000
  - matchResult_StateProvince__norm__MATCH > 0.5000
  - matchResult_Name__bin__MISSING <= 0.5000
  - Profile2_MatchCategory__norm <= 88.5000
  - matchResult_PhoneNumber__norm__NA > 0.5000
  - matchResult_Gender__norm__NA > 0.5000
THEN:
  → P(NO-MERGE) = 0.993
  → Leaf Purity = 0.993
  → Tree ID: 27
```

**Features involved:** `matchResult_Name__norm`, `Profile2_MatchCategory__bin__0_20`, `Profile1_MatchCategory__norm`, `Profile2_MatchCategory__norm`, `matchResult_City__norm__MATCH`

---

**Rule 4:** (Support: 19,137 samples = 11.5%)

```
IF:
  - Profile2_MatchCategory__bin__0_20 <= 0.5000
  - matchResult_Name__bin__MISSING <= 0.5000
  - Profile1_MatchCategory__norm > 50.0000
  - matchResult_Gender__norm__NA > 0.5000
  - Profile2_MatchCategory__norm <= 89.5000
  - matchResult_StateProvince__norm__MATCH > 0.5000
  - Profile2_MatchCategory__norm <= 88.5000
  - matchResult_Name__norm <= 94.5000
  - matchResult_Name__norm <= 92.5000
  - matchResult_City__norm__MATCH > 0.5000
THEN:
  → P(NO-MERGE) = 0.995
  → Leaf Purity = 0.995
  → Tree ID: 61
```

**Features involved:** `Profile2_MatchCategory__bin__0_20`, `matchResult_Name__bin__MISSING`, `Profile1_MatchCategory__norm`, `matchResult_Gender__norm__NA`, `Profile2_MatchCategory__norm`

---

**Rule 5:** (Support: 19,004 samples = 11.4%)

```
IF:
  - Profile2_MatchCategory__norm > 87.5000
  - matchResult_Name__bin__MISSING <= 0.5000
  - matchResult_Name__norm <= 93.5000
  - matchResult_City__norm__MATCH > 0.5000
  - Profile1_MatchCategory__norm <= 89.5000
  - Profile1_MatchCategory__bin__0_20 <= 0.5000
  - matchResult_Gender__norm__NA > 0.5000
  - matchResult_StateProvince__norm__MATCH > 0.5000
  - matchResult_Name__norm <= 90.5000
  - Profile2_MatchCategory__norm <= 88.5000
THEN:
  → P(NO-MERGE) = 0.995
  → Leaf Purity = 0.995
  → Tree ID: 6
```

**Features involved:** `Profile2_MatchCategory__norm`, `matchResult_Name__bin__MISSING`, `matchResult_Name__norm`, `matchResult_City__norm__MATCH`, `Profile1_MatchCategory__norm`

---

### 📊 Key Insights

**Most Discriminative Features** (appear most frequently in rules):

1. `matchResult_Name__norm` — appears in **9/10 rules** (90%)
2. `matchResult_StateProvince__norm__MATCH` — appears in **9/10 rules** (90%)
3. `Profile1_MatchCategory__norm` — appears in **8/10 rules** (80%)
4. `matchResult_PhoneNumber__norm__NA` — appears in **8/10 rules** (80%)
5. `Profile2_MatchCategory__norm` — appears in **8/10 rules** (80%)

**Rule Complexity:**

- Average conditions per rule: **10.0**
- Simplest rule: 10 conditions
- Most complex rule: 10 conditions

**Coverage:**

- Average support per rule: **11.2%** (min: 10.4%, max: 12.2%)
- Merge rules average support: **0.0%**
- No-merge rules average support: **11.2%**
- Note: Coverage is per-tree and not additive (rules from different trees)

**Strategic Observations:**

- ✅ **No workflow artifacts in rules** — confirms successful exclusion of non-predictive columns

---

## 📋 Executive Summary

**Model Performance:**

- **GLOBAL**: F1 = 0.8935
- **CUSTOM**: F1 = 0.9058
- **HYBRID**: F1 = 0.9076

**Deployment Recommendation:**

✅ **Deploy HYBRID model** - Single model with country features provides:
- Best of both worlds: high performance + single model
- Moderate complexity
- Scales to new countries easily

---

## 🌍 Per-Country Performance (CUSTOM)

| Country | F1 Score | Precision | Recall | N Train | N Test |
|---------|----------|-----------|--------|---------|--------|
| ARGENTINA | 0.6909 | 0.7440 | 0.6765 | 5552 | 1388 |
| BRAZIL | 0.9768 | 0.9777 | 0.9766 | 44406 | 11102 |
| CANADA | 0.9788 | 0.9788 | 0.9788 | 754 | 189 |
| CHILE | 0.9894 | 0.9910 | 0.9888 | 356 | 89 |
| COLOMBIA | 0.9484 | 0.9559 | 0.9450 | 9088 | 2273 |
| COSTA_RICA | 0.9964 | 0.9964 | 0.9964 | 6748 | 1688 |
| DOMINICAN_REPUBLIC | 0.9880 | 0.9881 | 0.9880 | 6328 | 1582 |
| EL_SALVADOR | 0.9720 | 0.9804 | 0.9641 | 3008 | 753 |
| GUATEMALA | 0.9761 | 0.9837 | 0.9715 | 8000 | 2000 |
| HONDURAS | 0.9778 | 0.9799 | 0.9766 | 1877 | 470 |
| HONG_KONG | 0.8512 | 0.8662 | 0.8470 | 2587 | 647 |
| MEXICO | 0.9531 | 0.9606 | 0.9492 | 31732 | 7934 |
| NETHERLANDS | 0.7908 | 0.7906 | 0.7914 | 1109 | 278 |
| NICARAGUA | 0.9906 | 0.9904 | 0.9910 | 1328 | 332 |
| PAKISTAN | 0.8090 | 0.8133 | 0.8075 | 21072 | 5268 |
| PANAMA | 0.9818 | 0.9838 | 0.9805 | 2866 | 717 |
| SOUTH_KOREA | 0.9835 | 0.9843 | 0.9840 | 999 | 250 |
| SWITZERLAND | 1.0000 | 1.0000 | 1.0000 | 1481 | 371 |
| UNITED_STATES | 0.6869 | 0.6913 | 0.6833 | 17817 | 4455 |
---
Generated under **Singular** | PM Automation  
Author: Salvador Soto
