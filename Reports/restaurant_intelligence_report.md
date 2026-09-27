# DineIQ Analytics - Restaurant Intelligence Report

## 1. Top 5 Most Profitable Dishes
| Item_Name        |   Total_Profit |   Profit_Pct |
|:-----------------|---------------:|-------------:|
| Company Classic  |    1.35798e+07 |        64.2  |
| Southern Classic |    1.27461e+07 |        62.7  |
| Recent Platter   |    1.2425e+07  |        60.85 |
| City Classic     |    1.16307e+07 |        62.68 |
| Wish Combo       |    1.14652e+07 |        61.53 |

## 2. Top 5 Highest-Volume Dishes
| Item_Name        |   Total_Quantity_Sold |
|:-----------------|----------------------:|
| Wish Combo       |                  9055 |
| House Platter    |                  9051 |
| Plan Combo       |                  9041 |
| Language Combo   |                  9037 |
| Position Platter |                  9032 |

## 3. Hidden Opportunities (34 items)
| Item_Name        |   Profit_Pct |   Total_Quantity_Sold |
|:-----------------|-------------:|----------------------:|
| Evidence Classic |        60.69 |                  8711 |
| Property Special |        57.12 |                  8741 |
| Summer Classic   |        62.54 |                  8809 |
| Level Combo      |        61.93 |                  8775 |
| Control Special  |        54.75 |                  8529 |

## 4. Low Performers (41 items)
| Item_Name          |   Profit_Pct |   Total_Quantity_Sold |
|:-------------------|-------------:|----------------------:|
| We Deluxe          |        35.23 |                  8706 |
| Particularly Combo |        40.02 |                  8732 |
| Join Platter       |        39.16 |                  8815 |
| Claim Special      |        45.74 |                  8728 |
| Industry Platter   |        43.22 |                  8808 |

## 5. Top 5 High-Wastage Items
| Item_Name        |   Total_Wasted |   Total_Cost_Impact |
|:-----------------|---------------:|--------------------:|
| Evidence Classic |           4625 |              386575 |
| Much Special     |           4417 |              366944 |
| We Deluxe        |           4344 |              354755 |
| Summer Classic   |           4460 |              363525 |
| Nothing Combo    |           4368 |              346169 |

## 6. Customer Segments Distribution
| Customer_Segment   |   count |
|:-------------------|--------:|
| Occasional         |   16003 |
| High-Value Loyal   |   15124 |
| At-Risk            |   11490 |

## 7. At-Risk (Churn) Customers: 10705 customers identified

## 9. Demand Forecast Model Performance
| Model            |     MAE |    RMSE |          R2 |
|:-----------------|--------:|--------:|------------:|
| LinearRegression | 211.893 | 365.248 |   0.0255386 |
| RandomForest     | 228.02  | 375.265 |  -0.0286426 |
| GradientBoosting | 225.21  | 379.966 |  -0.0545719 |
| Baseline_Mean    | 215.615 | nan     | nan         |

## 10. Price-Sensitive Items: 17 items identified

## 11. Top 3 Performing Locations
| City       |   Total_Revenue |   Total_Orders |
|:-----------|----------------:|---------------:|
| Karachi    |     7.60899e+07 |           4948 |
| Faisalabad |     7.51172e+07 |           4885 |
| Lahore     |     7.48387e+07 |           4888 |

## 12. Total Recommendations Generated: 163
| Priority   |   count |
|:-----------|--------:|
| Medium     |      91 |
| Critical   |      38 |
| High       |      34 |